"""
Web应用主入口
使用Flask构建的研究现状分析系统Web界面
"""

import os
import sys
import json
import threading
import time
import webbrowser
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import yaml
from loguru import logger
from datetime import datetime


def _project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


_ROOT = _project_root()
# 项目根加入路径，以便 ``from src.xxx`` 导入
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.paper_fetcher import ArxivFetcher, IeeeXploreFetcher, PubmedFetcher
from src.paper_fetcher.ai_search_keywords import generate_search_keywords
from src.analysis import GPTAnalyzer
from src.hallucination import (
    ConsistencyChecker,
    CitationCounter,
    TermValidator,
    ConfidenceEstimator,
)
# 置信度评估模块：直接使用LLM置信度
from src.report import MarkdownGenerator, HTMLGenerator, PDFGenerator, Visualizer, BibTeXGenerator
from src.utils.data_structures import ValidationResult
from src.utils.history_manager import HistoryManager
from src.utils.cited_reference_search import search_papers_for_cited_title
from src.utils.network_search import (
    extend_network_search_results,
    fetch_expansion_keyword_batch,
)
from src.report.web_report_pipeline import (
    recommended_keywords_from_analysis,
    run_analysis_report_artifacts,
)

app = Flask(
    __name__,
    template_folder=os.path.join(_ROOT, "templates"),
    static_folder=os.path.join(_ROOT, "static"),
)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # 生产环境请修改
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size（支持较大的PDF文件）

# 确保目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)

# 配置日志
logger.add("logs/web_app.log", rotation="10 MB", level="INFO")


def _resolve_config_path(config_path=None) -> str:
    if config_path:
        return config_path
    p = os.path.join(_ROOT, "config", "config.yaml")
    if os.path.isfile(p):
        return p
    return p


def load_config(config_path=None) -> dict:
    """加载配置文件（项目根目录下 ``config/config.yaml``）。"""
    path = _resolve_config_path(config_path)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"加载配置失败: {str(e)}")
        return {}


# 全局配置
config = load_config()

# 初始化历史记录管理器
history_manager = HistoryManager(history_dir='history')


def initialize_modules():
    """初始化所有模块"""
    modules = {}
    
    # 论文检索器（先创建，稍后传入gpt_analyzer）
    paper_fetch_config = config.get('paper_fetch', {})
    # 注意：gpt_analyzer将在后面设置
    
    # GPT分析器（优先级：DeepSeek > Kimi > Qwen）
    deepseek_config = config.get('deepseek', {})
    kimi_config = config.get('kimi', {})
    qwen_config = config.get('qwen', {})
    
    if deepseek_config.get('api_key'):
        api_provider = "deepseek"
        api_config = deepseek_config
    elif kimi_config.get('api_key'):
        api_provider = "kimi"
        api_config = kimi_config
    elif qwen_config.get('api_key'):
        api_provider = "qwen"
        api_config = qwen_config
    else:
        api_provider = None
        api_config = {}
    
    if api_provider:
        # 根据提供商设置默认模型
        default_models = {
            'deepseek': 'deepseek-chat',
            'kimi': 'moonshot-v1-32k',
            'qwen': 'qwen-max'
        }
        default_model = default_models.get(api_provider, 'deepseek-chat')
        
        modules['gpt_analyzer'] = GPTAnalyzer(
            api_key=api_config.get('api_key'),
            model=api_config.get('model', default_model),
            temperature=api_config.get('temperature', 0.3),
            max_tokens=api_config.get('max_tokens', 2000),
            api_provider=api_provider,
            base_url=api_config.get('base_url')
        )
    else:
        modules['gpt_analyzer'] = None
    
    # 现在创建arXiv检索器，传入gpt_analyzer用于AI关键词生成
    modules['arxiv_fetcher'] = ArxivFetcher(
        max_results=paper_fetch_config.get('arxiv', {}).get('max_results', 20),
        sort_by=paper_fetch_config.get('arxiv', {}).get('sort_by', 'relevance'),
        fetch_fulltext=paper_fetch_config.get('arxiv', {}).get('fetch_fulltext', False),
        title_only=paper_fetch_config.get('arxiv', {}).get('title_only', False),  # 默认在所有字段中搜索
        use_ai_keywords=True,  # 启用AI关键词生成
        gpt_analyzer=modules['gpt_analyzer']  # 传入GPT分析器
    )
    
    # 创建IEEE Xplore检索器，传入gpt_analyzer用于AI关键词生成
    try:
        ieee_xplore_api_key = config.get('ieee_xplore', {}).get('api_key', None)
        use_ieee_web_scraper = config.get('ieee_xplore', {}).get('use_web_scraper', True)
        # 检查是否启用全文获取
        fetch_ieee_fulltext = paper_fetch_config.get('ieee_xplore', {}).get('fetch_fulltext', False)
        modules['ieee_xplore_fetcher'] = IeeeXploreFetcher(
            max_results=paper_fetch_config.get('ieee_xplore', {}).get('max_results', 20),
            use_ai_keywords=True,  # 启用AI关键词生成
            gpt_analyzer=modules['gpt_analyzer'],  # 传入GPT分析器
            api_key=ieee_xplore_api_key,  # IEEE Xplore API密钥（可选）
            use_web_scraper=use_ieee_web_scraper,  # 如果没有API密钥，是否使用网页爬虫
            fetch_fulltext=fetch_ieee_fulltext  # 是否获取全文
        )
        logger.info("IEEE Xplore检索器初始化成功")
    except Exception as e:
        logger.warning(f"IEEE Xplore检索器初始化失败: {str(e)}")
        import traceback
        logger.debug(f"IEEE Xplore初始化详细错误: {traceback.format_exc()}")
        modules['ieee_xplore_fetcher'] = None
    
    # PubMed（NCBI E-utilities）
    try:
        pubmed_cfg = config.get("pubmed", {}) or {}
        modules["pubmed_fetcher"] = PubmedFetcher(
            max_results=paper_fetch_config.get("pubmed", {}).get("max_results", 20),
            use_ai_keywords=True,
            gpt_analyzer=modules["gpt_analyzer"],
            api_key=pubmed_cfg.get("api_key"),
            email=pubmed_cfg.get("email"),
            tool=pubmed_cfg.get("tool", "research_status_analyzer"),
        )
        logger.info("PubMed 检索器初始化成功")
    except Exception as e:
        logger.warning(f"PubMed 检索器初始化失败: {str(e)}")
        modules["pubmed_fetcher"] = None
    
    try:
        modules["consistency_checker"] = ConsistencyChecker()
        modules["citation_counter"] = CitationCounter()
        modules["term_validator"] = TermValidator()
        modules["confidence_estimator"] = ConfidenceEstimator()
        logger.info("置信度融合模块（一致性/引用/术语 + LLM）初始化成功")
    except Exception as e:
        logger.warning(f"置信度融合模块初始化失败，将仅使用 LLM 自评: {e}")
        modules["consistency_checker"] = None
        modules["citation_counter"] = None
        modules["term_validator"] = None
        modules["confidence_estimator"] = None

    # 报告生成器
    modules['markdown_generator'] = MarkdownGenerator()
    modules['html_generator'] = HTMLGenerator()
    modules['visualizer'] = Visualizer()
    
    # PDF生成器（可选，如果reportlab未安装会失败）
    try:
        modules['pdf_generator'] = PDFGenerator()
        logger.info("PDF生成器初始化成功")
    except Exception as e:
        logger.warning(f"PDF生成器初始化失败: {str(e)}")
        modules['pdf_generator'] = None
    
    # BibTeX生成器
    try:
        modules['bibtex_generator'] = BibTeXGenerator()
        logger.info("BibTeX生成器初始化成功")
    except Exception as e:
        logger.warning(f"BibTeX生成器初始化失败: {str(e)}")
        modules['bibtex_generator'] = None
    
    return modules


# 初始化模块
modules = initialize_modules()


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/papers')
def papers_page():
    """论文列表页面"""
    return render_template('papers.html')


@app.route('/results')
def results_page():
    """分析结果页面"""
    return render_template('results.html')


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    """处理文件过大错误"""
    max_size_mb = app.config.get('MAX_CONTENT_LENGTH', 0) / 1024 / 1024
    logger.warning(f"文件上传失败：文件大小超过限制（当前限制：{max_size_mb:.0f}MB）")
    return jsonify({
        'error': f'文件大小超过限制。当前最大允许上传：{max_size_mb:.0f}MB。请尝试上传较小的文件或联系管理员增加限制。'
    }), 413


@app.route('/api/upload-pdfs', methods=['POST'])
def upload_pdfs():
    """上传PDF文件并解析"""
    try:
        from src.utils.pdf_parser import PDFParser
        from werkzeug.utils import secure_filename
        import tempfile
        import os
        
        if 'pdf_files' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400
        
        files = request.files.getlist('pdf_files')
        if not files or files[0].filename == '':
            return jsonify({'error': '请选择至少一个PDF文件'}), 400
        
        parser = PDFParser()
        papers_data = []
        temp_files = []
        
        # 创建临时目录存储上传的文件
        temp_dir = tempfile.mkdtemp(prefix='pdf_upload_')
        
        for file in files:
            if file.filename.endswith('.pdf'):
                try:
                    # 保存临时文件
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(temp_dir, filename)
                    file.save(file_path)
                    temp_files.append(file_path)
                    
                    # 解析PDF
                    paper = parser.parse_paper_info(file_path)
                    if paper:
                        papers_data.append({
                            'title': paper.title,
                            'abstract': paper.abstract,
                            'authors': paper.authors,
                            'publication_date': paper.publication_date.isoformat() if paper.publication_date else None,
                            'source': paper.source,
                            'url': file_path,  # 保存临时文件路径
                            'paper_id': paper.paper_id,
                            'citation_count': paper.citation_count
                        })
                        logger.info(f"成功解析PDF: {filename} -> {paper.title}")
                    else:
                        logger.warning(f"无法解析PDF: {filename}")
                except Exception as e:
                    logger.error(f"处理PDF文件失败 {file.filename}: {str(e)}")
                    continue
        
        if not papers_data:
            return jsonify({'error': '未能解析任何PDF文件，请确保文件格式正确'}), 400
        
        logger.info(f"成功上传并解析 {len(papers_data)} 个PDF文件")
        
        # 检查是否是用于联想分析
        is_for_association = request.form.get('for_association', 'false') == 'true'
        
        response_data = {
            'success': True,
            'papers': papers_data,
            'count': len(papers_data),
            'temp_dir': temp_dir  # 返回临时目录，后续需要清理
        }
        
        # 如果是用于联想分析，返回PDF文件路径
        if is_for_association and temp_files:
            response_data['pdf_file_id'] = temp_files[0]  # 返回第一个PDF文件的路径作为ID
            response_data['pdf_file_path'] = temp_files[0]
        
        return jsonify(response_data)
        
    except ImportError as e:
        logger.error(f"PDF解析模块导入失败: {str(e)}")
        return jsonify({'error': 'PDF解析功能不可用，请安装PyPDF2: pip install PyPDF2'}), 500
    except Exception as e:
        logger.error(f"上传PDF失败: {str(e)}")
        import traceback
        logger.debug(f"详细错误: {traceback.format_exc()}")
        return jsonify({'error': f'上传失败: {str(e)}'}), 500


@app.route('/api/search', methods=['POST'])
def search_papers():
    """检索论文接口（第一步）"""
    try:
        data = request.get_json()
        
        # 获取来源类型
        use_network = data.get('use_network', False)
        use_upload = data.get('use_upload', False)
        use_pdf_association = data.get('use_pdf_association', False)
        uploaded_papers_data = data.get('uploaded_papers', [])
        
        if not use_network and not use_upload and not use_pdf_association:
            return jsonify({'error': '请至少选择一个论文来源'}), 400
        
        all_papers = []
        source_stats = {}
        
        # 先处理上传的PDF论文（优先）
        if use_upload and uploaded_papers_data:
            from src.utils.data_structures import Paper
            for paper_data in uploaded_papers_data:
                pub_date = None
                if paper_data.get('publication_date'):
                    try:
                        from datetime import datetime
                        pub_date = datetime.fromisoformat(paper_data['publication_date'])
                    except:
                        pass
                
                paper = Paper(
                    title=paper_data.get('title', '未知标题'),
                    abstract=paper_data.get('abstract', '摘要不可用'),
                    authors=paper_data.get('authors', []),
                    publication_date=pub_date,
                    source='uploaded',
                    url=paper_data.get('url', ''),
                    paper_id=paper_data.get('paper_id', f"uploaded_{len(all_papers)}"),
                    citation_count=paper_data.get('citation_count')
                )
                all_papers.append(paper)
            
            source_stats['uploaded'] = len(all_papers)
            logger.info(f"从上传的PDF中解析到 {len(all_papers)} 篇论文")
        
        # 处理PDF联想分析
        if use_pdf_association:
            pdf_file_id = data.get('pdf_association_file_id')
            if not pdf_file_id:
                return jsonify({'error': 'PDF联想分析需要上传PDF文件'}), 400
            
            try:
                from src.utils.pdf_association import PDFAssociationAnalyzer
                from src.utils.similarity_matcher import match_paper_by_similarity, calculate_similarity
                from src.utils.data_structures import Paper
                
                # 检查文件是否存在
                if not os.path.exists(pdf_file_id):
                    return jsonify({'error': f'PDF文件不存在: {pdf_file_id}'}), 400
                
                logger.info(f"开始PDF联想分析: {pdf_file_id}")
                
                # 初始化PDF联想分析器
                pdf_analyzer = PDFAssociationAnalyzer(gpt_analyzer=modules.get('gpt_analyzer'))
                
                # 1. 提取PDF全文用于DeepSeek分析
                from src.utils.pdf_parser import PDFParser
                pdf_parser = PDFParser()
                logger.info("步骤1: 提取PDF全文...")
                pdf_text = pdf_parser.extract_text(pdf_file_id, max_pages=100)
                logger.info(f"提取PDF文本完成，共 {len(pdf_text)} 字符")
                
                # 2. 直接让DeepSeek分析PDF内容，识别重点引用文献（不依赖提取的引用文献列表）
                key_references_count = data.get('key_references_count', 10)
                try:
                    key_references_count = int(key_references_count)
                    if key_references_count <= 0:
                        key_references_count = 10
                except (ValueError, TypeError):
                    key_references_count = 10
                
                logger.info(f"步骤2: DeepSeek分析PDF内容，识别重点引用文献（目标数量: {key_references_count}）...")
                key_references = pdf_analyzer.identify_key_references_from_pdf(pdf_text, max_count=key_references_count)
                logger.info(f"DeepSeek识别出 {len(key_references)} 篇重点引用文献")
                
                # 3. 搜索重点引用文献（arxiv -> ieee_xplore -> pubmed，带80%相似度匹配）
                logger.info("步骤3: 搜索重点引用文献...")
                cited_papers = []
                for i, ref in enumerate(key_references, 1):
                    ref_title = ref.get('title', '')
                    ref_authors = ref.get('authors', [])
                    
                    if not ref_title:
                        continue
                    
                    authors_str = ', '.join(ref_authors) if ref_authors else '未知作者'
                    logger.info(f"[{i}/{len(key_references)}] 搜索重点文献: {ref_title} (作者: {authors_str})")
                    found = False
                    
                    # 按顺序搜索：arxiv -> ieee -> pubmed（找到即停止）
                    search_sources = [
                        ('arxiv', modules.get('arxiv_fetcher')),
                        ('ieee_xplore', modules.get('ieee_xplore_fetcher')),
                        ('pubmed', modules.get('pubmed_fetcher')),
                    ]
                    
                    for source_name, fetcher in search_sources:
                        if not fetcher:
                            continue
                        
                        try:
                            logger.debug(f"  在{source_name}搜索完整标题（精确匹配）: {ref_title}")
                            search_results = search_papers_for_cited_title(
                                fetcher, ref_title, max_results=3
                            )

                            # 使用相似度匹配
                            matched, matched_paper, similarity = match_paper_by_similarity(
                                target_title=ref_title,
                                target_authors=ref_authors,
                                candidate_papers=search_results,
                                title_threshold=0.8,
                                author_threshold=0.8
                            )
                            
                            if matched and matched_paper:
                                matched_paper.source = f'cited_{source_name}'
                                cited_papers.append(matched_paper)
                                logger.info(f"  ✓ 在{source_name}找到匹配论文 (相似度: {similarity:.2f})，跳过后续搜索")
                                found = True
                                break  # 找到即停止，不继续搜索ieee
                            else:
                                # 添加详细日志，显示为什么匹配失败
                                if search_results:
                                    logger.debug(f"  在{source_name}找到 {len(search_results)} 篇论文，但相似度匹配失败（阈值: 标题≥0.8, 作者≥0.8）")
                                    for idx, paper in enumerate(search_results[:3], 1):
                                        paper_title = paper.title if hasattr(paper, 'title') else paper.get('title', '')
                                        if paper_title:
                                            title_sim = calculate_similarity(ref_title, paper_title)
                                            paper_authors = paper.authors if hasattr(paper, 'authors') else paper.get('authors', [])
                                            author_sim = 0.0
                                            if ref_authors and paper_authors:
                                                max_author_sim = 0.0
                                                for target_author in ref_authors:
                                                    for paper_author in paper_authors:
                                                        author_pair_sim = calculate_similarity(target_author, paper_author)
                                                        max_author_sim = max(max_author_sim, author_pair_sim)
                                                author_sim = max_author_sim
                                            combined_sim = title_sim * 0.6 + author_sim * 0.4 if ref_authors else title_sim
                                            logger.debug(f"    候选{idx}: {paper_title[:60]}... (标题相似度: {title_sim:.2f}, 作者相似度: {author_sim:.2f}, 综合相似度: {combined_sim:.2f})")
                                else:
                                    logger.debug(f"  在{source_name}未找到匹配论文（搜索结果为空）")
                        except Exception as e:
                            logger.warning(f"  在{source_name}搜索引用文献失败: {str(e)}")
                            continue
                    
                    if not found:
                        logger.info(f"  ✗ 未找到匹配的引用文献（已搜索 arxiv、ieee、pubmed）")
                
                logger.info(f"找到 {len(cited_papers)} 篇匹配的引用文献")
                all_papers.extend(cited_papers)
                source_stats['cited_papers'] = len(cited_papers)
                
                # 4. DeepSeek总结推荐相关关键词，然后搜索这些关键词
                logger.info("步骤4: DeepSeek总结推荐相关关键词...")
                expansion_keywords = pdf_analyzer.generate_expansion_keywords(pdf_text)
                logger.info(f"DeepSeek推荐的关键词: {expansion_keywords}")
                
                # 5. 搜索DeepSeek推荐的关键词（使用用户选择的网络源）
                if expansion_keywords:
                    logger.info("步骤5: 搜索DeepSeek推荐的关键词...")
                    # 使用PDF联想分析专用的网络源设置
                    sources = data.get('association_sources', ['arxiv'])
                    source_counts = data.get('association_source_counts', {})
                    start_year = data.get('association_start_year', 2023)
                    end_year = data.get('association_end_year', None)
                    sort_by = 'relevance'  # 联想分析默认使用相关性排序
                    
                    logger.info(f"PDF联想分析拓展搜索设置: 来源={sources}, 各源数量={source_counts}, 年份={start_year}-{end_year}")
                    
                    # 处理年份
                    try:
                        start_year = int(start_year) if start_year else 2023
                    except (ValueError, TypeError):
                        start_year = 2023
                    
                    if end_year is None or end_year == "latest" or end_year == "":
                        from datetime import datetime
                        end_year = datetime.now().year
                    else:
                        try:
                            end_year = int(end_year)
                        except (ValueError, TypeError):
                            from datetime import datetime
                            end_year = datetime.now().year
                    
                    # 先收集所有关键词在所有源中的搜索结果
                    all_expansion_papers = []
                    for keyword in expansion_keywords:
                        logger.info(f"搜索DeepSeek推荐的关键词: {keyword}")
                        
                        # 在选中的网络源中搜索
                        for source_name in sources:
                            fetcher = modules.get(f'{source_name}_fetcher')
                            if not fetcher:
                                continue
                            
                            try:
                                # 每个源的总数限制
                                max_for_source = source_counts.get(source_name, 10)
                                try:
                                    max_for_source = int(max_for_source)
                                    if max_for_source <= 0:
                                        max_for_source = 10
                                        logger.warning(f"{source_name}数量无效，使用默认值10")
                                except (ValueError, TypeError):
                                    max_for_source = 10
                                    logger.warning(f"{source_name}数量格式错误，使用默认值10")
                                
                                # 每个关键词在该源中搜索的数量 = 该源总数 / 关键词数量（至少1篇）
                                per_keyword_count = max(1, max_for_source // len(expansion_keywords))
                                
                                logger.info(f"在{source_name}搜索关键词'{keyword}'，该源总数限制={max_for_source}，本次搜索={per_keyword_count}篇")

                                papers = fetch_expansion_keyword_batch(
                                    fetcher,
                                    source_name,
                                    keyword,
                                    per_keyword_count,
                                    start_year,
                                    end_year,
                                    sort_by,
                                )
                                if not papers:
                                    continue
                                
                                # 为每篇论文标记来源，以便后续按源限制
                                for paper in papers:
                                    if not hasattr(paper, '_source_name'):
                                        paper._source_name = source_name
                                all_expansion_papers.extend(papers)
                                logger.info(f"在{source_name}找到 {len(papers)} 篇论文（关键词: {keyword}）")
                            except Exception as e:
                                logger.warning(f"在{source_name}搜索关键词{keyword}失败: {str(e)}")
                                continue
                    
                    # 去重（基于标题）
                    seen_titles = set()
                    unique_expansion_papers = []
                    for paper in all_expansion_papers:
                        if paper.title.lower() not in seen_titles:
                            seen_titles.add(paper.title.lower())
                            unique_expansion_papers.append(paper)
                    
                    # 按源限制总数：每个源最多返回设置的数量
                    expansion_papers = []
                    source_counts_actual = {}
                    for paper in unique_expansion_papers:
                        source_name = getattr(paper, '_source_name', 'unknown')
                        if source_name not in source_counts_actual:
                            source_counts_actual[source_name] = 0
                        
                        max_for_source = source_counts.get(source_name, 10)
                        try:
                            max_for_source = int(max_for_source)
                            if max_for_source <= 0:
                                max_for_source = 10
                        except (ValueError, TypeError):
                            max_for_source = 10
                        
                        if source_counts_actual[source_name] < max_for_source:
                            expansion_papers.append(paper)
                            source_counts_actual[source_name] += 1
                        else:
                            logger.debug(f"{source_name}已达到最大数量限制({max_for_source})，跳过论文: {paper.title[:50]}...")
                    
                    logger.info(f"拓展关键词搜索完成，去重后共 {len(unique_expansion_papers)} 篇，按源限制后共 {len(expansion_papers)} 篇")
                    for source_name, count in source_counts_actual.items():
                        logger.info(f"  {source_name}: {count} 篇")
                    
                    logger.info(f"找到 {len(expansion_papers)} 篇关键词搜索论文（按源限制后）")
                    all_papers.extend(expansion_papers)
                    source_stats['expansion_papers'] = len(expansion_papers)
                
                logger.info(f"PDF联想分析完成，共找到 {len(cited_papers) + source_stats.get('expansion_papers', 0)} 篇论文")
                
            except Exception as e:
                logger.error(f"PDF联想分析失败: {str(e)}")
                import traceback
                logger.debug(f"详细错误: {traceback.format_exc()}")
                return jsonify({'error': f'PDF联想分析失败: {str(e)}'}), 500
        
        # 处理网络检索（arXiv）
        if use_network:
            topic = data.get('topic', '').strip()
            # 只有在纯网络检索模式（没有上传PDF）时才要求主题
            if not topic and not use_upload and not data.get('use_pdf_association', False):
                return jsonify({'error': '使用网络检索时，研究主题不能为空'}), 400
            # 如果主题为空，使用默认值
            if not topic:
                topic = '综合研究'
            
            sources = data.get('sources', ['arxiv'])
            source_counts = data.get('source_counts', {})
            use_ai_keywords = data.get('use_ai_keywords', True)
            start_year = data.get('start_year', 2023)
            end_year = data.get('end_year', None)
            sort_by = data.get('sort_by', 'relevance')
            
            # 处理年份
            try:
                start_year = int(start_year) if start_year else 2023
            except (ValueError, TypeError):
                start_year = 2023
            
            if end_year is None or end_year == "latest" or end_year == "":
                from datetime import datetime
                end_year = datetime.now().year
            else:
                try:
                    end_year = int(end_year)
                except (ValueError, TypeError):
                    from datetime import datetime
                    end_year = datetime.now().year
            
            logger.info(f"收到检索请求: {topic}, 来源: {sources}, 数量设置: {source_counts}, AI扩展关键词: {use_ai_keywords}")
            logger.debug(f"详细数量设置: {json.dumps(source_counts, ensure_ascii=False, indent=2)}")
            
            search_query = topic
            ai_keywords_list = None
            if use_ai_keywords:
                logger.info("使用 AI 统一生成英文检索关键词（单模块，与各抓取器内逻辑一致）")
                if modules.get("gpt_analyzer"):
                    try:
                        ai_keywords_list = generate_search_keywords(modules["gpt_analyzer"], topic)
                        logger.info(f"AI 统一生成的关键词: {ai_keywords_list}")
                        if len(ai_keywords_list) > 1:
                            search_query = " OR ".join(ai_keywords_list)
                        else:
                            search_query = ai_keywords_list[0] if ai_keywords_list else topic
                    except Exception as e:
                        logger.warning(
                            f"统一生成 AI 关键词失败: {e}，改用原始主题且不再在各源重复调用 LLM"
                        )
                        ai_keywords_list = None
                        search_query = topic
                        for source_name in sources:
                            fk = f"{source_name}_fetcher"
                            if modules.get(fk) and hasattr(modules[fk], "use_ai_keywords"):
                                modules[fk].use_ai_keywords = False
                else:
                    logger.warning("已开启 AI 关键词但未配置 API，改用翻译生成检索用语")
                    from src.utils.translator import Translator

                    translator = Translator()
                    translated = translator.translate_for_search(topic)
                    search_query = translated["en"] if translated["en"] else translated["original"]
                    for source_name in sources:
                        fk = f"{source_name}_fetcher"
                        if modules.get(fk) and hasattr(modules[fk], "use_ai_keywords"):
                            modules[fk].use_ai_keywords = False

                if ai_keywords_list:
                    for source_name in sources:
                        fetcher_key = f"{source_name}_fetcher"
                        if modules.get(fetcher_key) and hasattr(
                            modules[fetcher_key], "use_ai_keywords"
                        ):
                            modules[fetcher_key].use_ai_keywords = False
                            logger.debug(
                                f"已禁用 {source_name} 内重复 AI 关键词（使用统一关键词）"
                            )
            else:
                # 不使用AI关键词时，需要翻译
                from src.utils.translator import Translator
                translator = Translator()
                translated = translator.translate_for_search(topic)
                search_query = translated['en'] if translated['en'] else translated['original']
                logger.info(f"翻译结果: 原文={translated['original']}, 语言={translated['lang']}, "
                           f"中文={translated['zh']}, 英文={translated['en']}")
            
            extend_network_search_results(
                sources=sources,
                modules=modules,
                source_counts=source_counts,
                search_query=search_query,
                start_year=start_year,
                end_year=end_year,
                sort_by=sort_by,
                data=data,
                all_papers=all_papers,
                source_stats=source_stats,
            )

            if not all_papers:
                # 检查是否有来源被选中但初始化失败
                failed_sources = []
                if use_network:
                    if 'ieee_xplore' in sources and not modules.get('ieee_xplore_fetcher'):
                        failed_sources.append('IEEE Xplore')
                    if 'pubmed' in sources and not modules.get('pubmed_fetcher'):
                        failed_sources.append('PubMed')
                
                error_msg = '未检索到任何论文，请尝试其他关键词或来源'
                if failed_sources:
                    error_msg += f'。注意：{", ".join(failed_sources)}检索器未初始化，可能因为依赖未安装或配置错误'
                
                return jsonify({'error': error_msg}), 400
        
        # 去重处理：如果同时有上传和arXiv，优先保留上传的论文
        if use_upload and use_network and len(all_papers) > source_stats.get('uploaded', 0):
            from src.utils.deduplicator import PaperDeduplicator
            deduplicator = PaperDeduplicator(
                title_similarity_threshold=0.85,
                author_overlap_threshold=0.5
            )
            original_count = len(all_papers)
            # 优先保留上传的论文（prefer_source="uploaded"）
            all_papers = deduplicator.deduplicate(all_papers, prefer_source="uploaded")
            removed_count = original_count - len(all_papers)
            if removed_count > 0:
                logger.info(f"去重完成: 移除了{removed_count}篇重复论文（原始{original_count}篇 -> 去重后{len(all_papers)}篇），优先保留上传的论文")
        
        # 准备返回数据
        topic = data.get('topic', '').strip() or '上传的论文'
        papers_data = []
        for paper in all_papers:
            papers_data.append({
                'title': paper.title,
                'abstract': paper.abstract,
                'authors': paper.authors,
                'publication_date': paper.publication_date.isoformat() if paper.publication_date else None,
                'source': paper.source,
                'url': paper.url,
                'paper_id': paper.paper_id,
                'citation_count': paper.citation_count
            })
        
        # 保存论文数据到session（使用文件临时存储）
        safe_topic = secure_filename(topic.replace(' ', '_'))
        temp_file = os.path.join(app.config['OUTPUT_FOLDER'], f"temp_{safe_topic}.json")
        os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump({
                'topic': topic,
                'papers': papers_data,
                'source_stats': source_stats,
                'ai_model': data.get('paper_analysis_model', data.get('ai_model', 'deepseek-chat'))  # 保存选择的模型
            }, f, ensure_ascii=False, indent=2)
        
        # 返回实际检索到的来源统计（只包含有论文的来源）
        actual_source_stats = {k: v for k, v in source_stats.items() if v > 0}
        
        # 保存来源统计到临时文件
        if os.path.exists(temp_file):
            with open(temp_file, 'r', encoding='utf-8') as f:
                temp_data = json.load(f)
            temp_data['source_stats'] = actual_source_stats
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(temp_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'topic': topic,
            'papers': papers_data,
            'total_count': len(all_papers),
            'source_stats': actual_source_stats,  # 只返回有论文的来源
            'temp_file': temp_file
        })
        
    except Exception as e:
        logger.error(f"检索过程出错: {str(e)}")
        return jsonify({'error': str(e)}), 500


def create_analyzer(model_name: str):
    """
    根据模型名称创建对应的分析器
    
    Args:
        model_name: 模型名称，如 'deepseek-chat', 'deepseek-reasoner', 'kimi-32k' 等
    
    Returns:
        GPTAnalyzer实例或None
    """
    deepseek_config = config.get('deepseek', {})
    kimi_config = config.get('kimi', {})
    qwen_config = config.get('qwen', {})
    
    # 根据模型名称确定使用哪个API
    if model_name.startswith('deepseek'):
        if not deepseek_config.get('api_key') or deepseek_config.get('api_key') == 'your-deepseek-api-key-here':
            return None
        return GPTAnalyzer(
            api_key=deepseek_config.get('api_key'),
            model=model_name,
            temperature=deepseek_config.get('temperature', 0.3),
            max_tokens=deepseek_config.get('max_tokens', 2000),
            api_provider='deepseek',
            base_url=deepseek_config.get('base_url')
        )
    elif model_name.startswith('moonshot') or model_name.startswith('kimi'):
        if not kimi_config.get('api_key') or kimi_config.get('api_key') == 'your-kimi-api-key-here':
            return None
        # Kimi 使用 OpenAI 兼容接口（openai 库通过 base_url 切换）
        # 如果模型名称是kimi-xxx，转换为moonshot-v1-xxx
        if model_name.startswith('kimi'):
            # kimi-8k -> moonshot-v1-8k, kimi-32k -> moonshot-v1-32k, kimi-128k -> moonshot-v1-128k
            kimi_model = model_name.replace('kimi-', 'moonshot-v1-')
        else:
            kimi_model = model_name
        return GPTAnalyzer(
            api_key=kimi_config.get('api_key'),
            model=kimi_model,
            temperature=kimi_config.get('temperature', 0.3),
            max_tokens=kimi_config.get('max_tokens', 2000),
            api_provider='kimi',
            base_url=kimi_config.get('base_url', 'https://api.moonshot.cn/v1')
        )
    elif model_name.startswith('qwen'):
        if not qwen_config.get('api_key') or qwen_config.get('api_key') == 'your-qwen-api-key-here':
            return None
        return GPTAnalyzer(
            api_key=qwen_config.get('api_key'),
            model=model_name,
            temperature=qwen_config.get('temperature', 0.3),
            max_tokens=qwen_config.get('max_tokens', 2000),
            api_provider='qwen',
            base_url=qwen_config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        )
    else:
        logger.warning(f"未知的模型: {model_name}")
        return None


# 全局进度存储（实际应用中应使用Redis等）
analysis_progress = {}

# 全局分析结果存储（用于问答功能）
analysis_results = {}  # key: task_id, value: {topic, papers, paper_details, analysis_result, ai_model}

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """分析接口（第二步）"""
    import uuid
    import threading
    
    try:
        data = request.get_json()
        temp_file = data.get('temp_file')
        topic = data.get('topic', '').strip()
        # 支持分别设置论文详细分析模型和综述生成模型
        paper_analysis_model = data.get('paper_analysis_model', data.get('ai_model', 'deepseek-chat'))  # 论文详细分析模型
        review_model = data.get('review_model', paper_analysis_model)  # 综述生成模型，默认与论文分析模型相同
        # 获取综述详细程度，默认为500字
        review_detail_level = data.get('review_detail_level', '500')
        try:
            review_detail_level = int(review_detail_level)
            if review_detail_level not in [200, 500, 800]:
                review_detail_level = 500
                logger.warning("综述详细程度无效，使用默认值500")
        except (ValueError, TypeError):
            review_detail_level = 500
            logger.warning("综述详细程度格式错误，使用默认值500")
        # 获取批量大小，默认为配置文件中的值或1
        batch_size = data.get('batch_size', None)
        if batch_size is None:
            # 从配置文件读取默认值
            batch_size = config.get('paper_analysis', {}).get('batch_size', 1)
        try:
            batch_size = int(batch_size)
            if batch_size < 1:
                batch_size = 1
                logger.warning("批量大小无效，使用默认值1")
        except (ValueError, TypeError):
            batch_size = 1
            logger.warning("批量大小格式错误，使用默认值1")
        
        if not topic and not temp_file:
            return jsonify({'error': '缺少必要参数'}), 400
        
        # 生成分析任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化进度
        analysis_progress[task_id] = {
            'status': 'starting',
            'progress': 0,
            'step': 1,
            'message': '正在初始化分析...'
        }
        
        # 在后台线程中执行分析
        def analyze_in_background():
            try:
                # 根据选择的模型创建分析器（用于论文详细分析）
                logger.info(f"创建论文分析器，模型名称: {paper_analysis_model}")
                paper_analyzer = create_analyzer(paper_analysis_model)
                if not paper_analyzer:
                    analysis_progress[task_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': f'请为模型 {paper_analysis_model} 在config/config.yaml中配置相应的API密钥'
                    }
                    return
                
                # 创建综述生成分析器（如果与论文分析模型不同）
                review_analyzer = None
                if review_model != paper_analysis_model:
                    review_analyzer = create_analyzer(review_model)
                    if not review_analyzer:
                        logger.warning(f"综述模型 {review_model} 初始化失败，将使用论文分析模型 {paper_analysis_model}")
                        review_analyzer = None
                    else:
                        logger.info(f"使用不同模型：论文分析={paper_analysis_model}, 综述生成={review_model}")
                
                # 从临时文件加载论文数据
                if temp_file and os.path.exists(temp_file):
                    with open(temp_file, 'r', encoding='utf-8') as f:
                        temp_data = json.load(f)
                    topic_local = temp_data.get('topic', topic)
                    papers_data = temp_data.get('papers', [])
                    # 不再从temp_data获取模型，使用传入的参数
                else:
                    analysis_progress[task_id] = {
                        'status': 'error',
                        'progress': 0,
                        'message': '论文数据不存在，请重新检索'
                    }
                    return
                
                # 更新进度：准备分析
                analysis_progress[task_id] = {
                    'status': 'running',
                    'progress': 10,
                    'step': 1,
                    'message': f'已加载 {len(papers_data)} 篇论文，准备开始分析...'
                }
                
                # 重建Paper对象
                from src.utils.data_structures import Paper
                all_papers = []
                for p_data in papers_data:
                    from datetime import datetime
                    pub_date = datetime.fromisoformat(p_data['publication_date']) if p_data.get('publication_date') else None
                    paper = Paper(
                        title=p_data['title'],
                        abstract=p_data['abstract'],
                        authors=p_data['authors'],
                        publication_date=pub_date,
                        source=p_data['source'],
                        url=p_data['url'],
                        paper_id=p_data['paper_id'],
                        citation_count=p_data.get('citation_count')
                    )
                    all_papers.append(paper)
                
                logger.info(f"开始分析 {len(all_papers)} 篇论文，论文分析模型: {paper_analysis_model}, 综述生成模型: {review_model}, 批量大小: {batch_size}")
                
                # 定义进度回调函数
                def update_analysis_progress(progress_info):
                    """更新分析进度的回调函数"""
                    current = progress_info.get('current_paper', 0)
                    total = progress_info.get('total_papers', len(all_papers))
                    message = progress_info.get('message', '分析中...')
                    current_paper_title = progress_info.get('current_paper_title', '')
                    
                    # 计算进度：30% + (当前论文数/总论文数) * 30%
                    progress = 30 + int((current / total) * 30) if total > 0 else 30
                    
                    analysis_progress[task_id] = {
                        'status': 'running',
                        'progress': progress,
                        'step': 2,
                        'message': message,
                        'current_paper': current,
                        'total_papers': total,
                        'current_paper_title': current_paper_title  # 添加论文标题
                    }
                
                # 更新进度：AI分析中
                batch_info = f"（批量大小: {batch_size}）" if batch_size > 1 else ""
                analysis_progress[task_id] = {
                    'status': 'running',
                    'progress': 30,
                    'step': 2,
                    'message': f'开始使用 {paper_analysis_model} 分析 {len(all_papers)} 篇论文{batch_info}...',
                    'current_paper': 0,
                    'total_papers': len(all_papers)
                }
                
                # 步骤2: AI分析（传入进度回调、综述分析器、批量大小和详细程度）
                analysis_result = paper_analyzer.analyze_papers(
                    all_papers, 
                    topic_local, 
                    progress_callback=update_analysis_progress,
                    review_analyzer=review_analyzer,
                    batch_size=batch_size,
                    review_detail_level=review_detail_level
                )
                
                # 更新进度：置信度评估
                analysis_progress[task_id] = {
                    'status': 'running',
                    'progress': 60,
                    'step': 3,
                    'message': '正在进行置信度评估...'
                }
                
                # 步骤3: 置信度融合（与 CLI 相同：一致性 + 术语 + 引用 + LLM 自评）
                cc = modules.get("consistency_checker")
                cit = modules.get("citation_counter")
                tv = modules.get("term_validator")
                ce = modules.get("confidence_estimator")
                if cc and cit and tv and ce:
                    consistency_score = cc.calculate_consistency(all_papers)
                    citation_frequency = cit.count_citations(all_papers)
                    expected_terms = tv.extract_terms_from_papers(all_papers)
                    term_validation = tv.validate_terms_in_summary(
                        analysis_result.summary, expected_terms
                    )
                    term_coverage = tv.calculate_term_coverage(term_validation)
                    llm_c = analysis_result.llm_confidence
                    has_conflicts = bool(
                        getattr(analysis_result, "conflicts", None)
                    )
                    overall_confidence = ce.estimate_confidence(
                        all_papers,
                        consistency_score,
                        term_coverage,
                        citation_frequency,
                        llm_confidence=llm_c,
                        has_conflicts=has_conflicts,
                    )
                    model_confidence = llm_c if llm_c is not None else 0.7
                    validation_result = ValidationResult(
                        consistency_score=consistency_score,
                        citation_frequency=citation_frequency,
                        term_validation=term_validation,
                        model_confidence=model_confidence,
                        overall_confidence=overall_confidence,
                        diagnostic=None,
                        confidence_reason=analysis_result.confidence_reason,
                        conflicts=analysis_result.conflicts,
                        term_coverage=term_coverage,
                    )
                else:
                    model_confidence = (
                        analysis_result.llm_confidence
                        if analysis_result.llm_confidence is not None
                        else 0.7
                    )
                    validation_result = ValidationResult(
                        consistency_score=0.0,
                        citation_frequency={},
                        term_validation={},
                        model_confidence=model_confidence,
                        overall_confidence=model_confidence,
                        diagnostic=None,
                        confidence_reason=analysis_result.confidence_reason,
                        conflicts=analysis_result.conflicts,
                        term_coverage=None,
                    )
                
                # 更新进度：生成推荐关键词
                analysis_progress[task_id] = {
                    'status': 'running',
                    'progress': 75,
                    'step': 4,
                    'message': '正在生成推荐搜索关键词...'
                }

                keyword_analyzer = review_analyzer if review_analyzer else paper_analyzer
                recommended_keywords = recommended_keywords_from_analysis(
                    analysis_result, topic_local, keyword_analyzer
                )

                analysis_progress[task_id] = {
                    'status': 'running',
                    'progress': 80,
                    'step': 5,
                    'message': '正在生成报告和可视化...'
                }

                artifacts = run_analysis_report_artifacts(
                    modules,
                    topic_local,
                    all_papers,
                    analysis_result,
                    validation_result,
                    app.config['OUTPUT_FOLDER'],
                )
                safe_topic = artifacts['safe_topic']
                file_base_name = artifacts['file_base_name']
                wordcloud_path = artifacts['wordcloud_path']

                # 准备返回数据
                result = {
                    'success': True,
                    'topic': topic_local,
                    'papers_count': len(all_papers),
                    'analysis': {
                        'summary': analysis_result.summary,
                        'key_findings': analysis_result.key_findings,
                        'research_trends': analysis_result.research_trends,
                        'section1_research_intro': analysis_result.section1_research_intro,
                        'section2_research_progress': analysis_result.section2_research_progress,
                        'section3_research_status': analysis_result.section3_research_status,
                        'section4_existing_methods': analysis_result.section4_existing_methods,
                        'section5_future_development': analysis_result.section5_future_development,
                        'subtopics': analysis_result.subtopics if hasattr(analysis_result, 'subtopics') and analysis_result.subtopics else [],
                        'keywords': analysis_result.keywords if hasattr(analysis_result, 'keywords') and analysis_result.keywords else [],
                    },
                    'paper_details': analysis_result.paper_details if analysis_result.paper_details else [],
                    'validation': {
                        'model_confidence': validation_result.model_confidence,
                        'llm_confidence': analysis_result.llm_confidence,
                        'confidence_reason': analysis_result.confidence_reason,
                        'conflicts': analysis_result.conflicts,
                    },
                    'papers': [
                        {
                            'title': p.title,
                            'authors': p.authors[:3],
                            'url': p.url,
                            'source': p.source,
                            'citation_count': p.citation_count,
                            'paper_id': p.paper_id,  # 添加paper_id用于匹配paper_details
                            'paper_type': next((d.get('paper_type', 'method') for d in (analysis_result.paper_details if analysis_result.paper_details else []) if d.get('paper_id') == p.paper_id), 'method'),  # 从paper_details中获取类型
                            'recommendation_score': next((d.get('recommendation_score') for d in (analysis_result.paper_details if analysis_result.paper_details else []) if d.get('paper_id') == p.paper_id), None)  # 从paper_details中获取推荐阅读程度
                        }
                        for p in all_papers  # 返回所有论文
                    ],
                    'reports': {
                        'html': f"/output/{safe_topic}/{file_base_name}.html",
                        'markdown': f"/output/{safe_topic}/{file_base_name}.md",
                        'pdf': f"/output/{safe_topic}/{file_base_name}.pdf" if modules.get('pdf_generator') else None,
                        'bibtex': f"/output/{safe_topic}/{file_base_name}.bib" if modules.get('bibtex_generator') else None,
                        'timeline': f"/output/{safe_topic}/timeline_{file_base_name}.png",
                        'wordcloud': f"/output/{safe_topic}/wordcloud_{file_base_name}.png" if wordcloud_path and os.path.exists(wordcloud_path) else None
                    },
                    'recommended_keywords': recommended_keywords  # 添加推荐关键词
                }
                
                # 保存结果到进度
                analysis_progress[task_id] = {
                    'status': 'completed',
                    'progress': 100,
                    'step': 4,
                    'message': '分析完成！',
                    'result': result
                }
                
                # 保存分析结果供问答使用
                # 从分析结果中获取paper_details
                paper_details_list = analysis_result.paper_details if analysis_result.paper_details else []
                
                # 获取AI模型名称（用于问答功能，使用综述模型）
                model_name_for_chat = review_analyzer.model if review_analyzer else paper_analyzer.model
                
                # 保存综述内容（用于问答时的上下文）
                review_summary = ""
                if analysis_result.section1_research_intro:
                    # 如果有5部分结构，组合成完整综述
                    review_summary = f"""# 研究介绍\n\n{analysis_result.section1_research_intro}\n\n# 研究进展\n\n{analysis_result.section2_research_progress}\n\n# 研究现状\n\n{analysis_result.section3_research_status}\n\n# 现有方法\n\n{analysis_result.section4_existing_methods}\n\n# 未来发展\n\n{analysis_result.section5_future_development}"""
                elif analysis_result.summary:
                    # 使用旧格式的summary
                    review_summary = analysis_result.summary
                
                analysis_results[task_id] = {
                    'topic': topic_local,
                    'papers': all_papers,
                    'paper_details': paper_details_list,
                    'analysis_result': analysis_result,
                    'ai_model': model_name_for_chat,
                    'review_summary': review_summary  # 保存生成的综述内容
                }
                
                # 保存历史记录
                try:
                    # 准备论文数据（转换为字典）
                    papers_data = []
                    for paper in all_papers:
                        papers_data.append({
                            'title': paper.title,
                            'abstract': paper.abstract,
                            'authors': paper.authors,
                            'publication_date': paper.publication_date.isoformat() if paper.publication_date else None,
                            'source': paper.source,
                            'url': paper.url,
                            'paper_id': paper.paper_id,
                            'citation_count': paper.citation_count
                        })
                    
                    # 获取来源统计（从临时文件或result中）
                    source_stats_data = {}
                    if temp_file and os.path.exists(temp_file):
                        try:
                            with open(temp_file, 'r', encoding='utf-8') as f:
                                temp_data = json.load(f)
                            source_stats_data = temp_data.get('source_stats', {})
                        except:
                            pass
                    
                    # 如果result中没有source_stats，使用空字典
                    if not source_stats_data:
                        source_stats_data = {}
                    
                    history_id = history_manager.save_history(
                        topic=topic_local,
                        papers=papers_data,
                        analysis_result=result['analysis'],
                        validation_result=result['validation'],
                        source_stats=source_stats_data,
                        reports=result['reports']
                    )
                    logger.info(f"历史记录已保存: {history_id}")
                except Exception as e:
                    logger.warning(f"保存历史记录失败: {str(e)}")
                    import traceback
                    logger.debug(f"详细错误: {traceback.format_exc()}")
                
                logger.info(f"分析完成: {topic_local}")
                
            except Exception as e:
                logger.error(f"分析过程出错: {str(e)}")
                analysis_progress[task_id] = {
                    'status': 'error',
                    'progress': 0,
                    'message': f'分析失败: {str(e)}'
                }
        
        # 启动后台分析线程
        thread = threading.Thread(target=analyze_in_background)
        thread.daemon = True
        thread.start()
        
        # 立即返回任务ID
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '分析任务已启动'
        })
        
    except Exception as e:
        logger.error(f"分析接口出错: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze/progress/<task_id>', methods=['GET'])
def get_analysis_progress(task_id):
    """获取分析进度"""
    progress = analysis_progress.get(task_id, {
        'status': 'not_found',
        'progress': 0,
        'step': 1,
        'message': '任务不存在'
    })
    return jsonify(progress)


@app.route('/output/<path:filename>')
def output_file(filename):
    """提供输出文件访问"""
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return jsonify({'error': '文件不存在'}), 404


@app.route('/api/get-papers', methods=['GET'])
def get_papers():
    """获取论文列表接口"""
    try:
        temp_file = request.args.get('temp_file')
        task_id = request.args.get('task_id')  # 可选：如果提供了task_id，返回包含详细信息的论文列表
        
        if not temp_file or not os.path.exists(temp_file):
            return jsonify({'error': '论文数据不存在'}), 404
        
        with open(temp_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result = {
            'success': True,
            'papers': data.get('papers', []),
            'topic': data.get('topic', '')
        }
        
        # 如果提供了task_id，尝试获取论文详细信息
        if task_id and task_id in analysis_results:
            result['paper_details'] = analysis_results[task_id].get('paper_details', [])
            # 为每篇论文添加类型信息（从paper_details中获取）
            paper_details_map = {d.get('paper_id'): d for d in result.get('paper_details', [])}
            for paper in result['papers']:
                paper_id = paper.get('paper_id')
                if paper_id and paper_id in paper_details_map:
                    paper['paper_type'] = paper_details_map[paper_id].get('paper_type', 'method')
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取论文列表失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/status')
def status():
    """系统状态接口"""
    return jsonify({
        'status': 'running',
        'api_configured': modules['gpt_analyzer'] is not None,
    })


@app.route('/api/history/list', methods=['GET'])
def get_history_list():
    """获取历史记录列表"""
    try:
        limit = request.args.get('limit', 100, type=int)
        history_list = history_manager.get_history_list(limit=limit)
        return jsonify({
            'success': True,
            'history': history_list
        })
    except Exception as e:
        logger.error(f"获取历史记录列表失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/<record_id>', methods=['GET'])
def get_history(record_id):
    """获取单条历史记录"""
    try:
        history_data = history_manager.get_history(record_id)
        if not history_data:
            return jsonify({'error': '历史记录不存在'}), 404
        
        return jsonify({
            'success': True,
            'history': history_data
        })
    except Exception as e:
        logger.error(f"获取历史记录失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/<record_id>', methods=['DELETE'])
def delete_history(record_id):
    """删除历史记录"""
    try:
        success = history_manager.delete_history(record_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': '删除失败'}), 500
    except Exception as e:
        logger.error(f"删除历史记录失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/history')
def history_page():
    """历史记录列表页面"""
    return render_template('history.html')


@app.route('/history/<record_id>')
def history_detail_page(record_id):
    """历史记录详情页面"""
    return render_template('history_detail.html', record_id=record_id)


@app.route('/api/chat', methods=['POST'])
def chat():
    """问答接口，支持联网搜索"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        question = data.get('question', '').strip()
        enable_web_search = data.get('enable_web_search', True)
        
        if not task_id:
            return jsonify({'error': '缺少task_id'}), 400
        
        if not question:
            return jsonify({'error': '问题不能为空'}), 400
        
        # 获取保存的分析结果
        if task_id not in analysis_results:
            return jsonify({'error': '分析结果不存在，请先完成分析'}), 404
        
        result_data = analysis_results[task_id]
        topic = result_data['topic']
        papers = result_data['papers']
        paper_details = result_data['paper_details']
        ai_model = result_data.get('ai_model', 'deepseek-chat')
        review_summary = result_data.get('review_summary', '')  # 获取之前生成的综述
        
        # 根据保存的模型创建分析器（用于问答）
        chat_analyzer = create_analyzer(ai_model)
        if not chat_analyzer:
            # 如果创建失败，回退到全局分析器
            logger.warning(f"无法为问答创建模型 {ai_model}，将使用全局分析器")
            chat_analyzer = modules.get('gpt_analyzer')
            if not chat_analyzer:
                return jsonify({'error': 'AI分析器未初始化'}), 500
        else:
            logger.info(f"问答功能使用模型: {ai_model}（综述生成模型）")
        
        # 构建论文上下文信息
        papers_context = []
        for i, paper in enumerate(papers[:10], 1):  # 最多使用10篇论文
            detail = next((d for d in paper_details if d.get('paper_id') == paper.paper_id), {})
            paper_info = f"""
论文[{i}]: {paper.title}
作者: {', '.join(paper.authors[:3])}
发表时间: {paper.publication_date.strftime('%Y-%m') if paper.publication_date else '未知'}
来源: {paper.source}
摘要: {paper.abstract[:300]}...
"""
            if detail:
                paper_info += f"""
详细分析:
- 研究方向背景: {detail.get('q1_background', 'N/A')}
- 实现内容: {detail.get('q2_implementation', 'N/A')}
- 结果: {detail.get('q3_result', 'N/A')}
- 方法总结: {detail.get('q8_summary', 'N/A')}
"""
            papers_context.append(paper_info)
        
        papers_text = "\n".join(papers_context)
        
        # 网络搜索（如果启用）
        web_search_note = ""
        if enable_web_search:
            web_search_note = """
[联网搜索已启用] 如果论文信息不足以回答用户问题，你可以：
1. 基于你的知识库（训练数据）提供相关信息
2. 明确标注这些信息来自 [网络来源: 通用知识/公开资料]
3. 如果涉及最新进展，请说明这是基于训练数据的知识，可能不是最新信息
4. 建议用户查阅最新文献获取最新信息"""
        
        # 构建提示词
        system_prompt = f"""你是一位专业的研究助手。你之前已经基于多篇论文生成了关于"{topic}"的综述报告。
现在用户会基于这个综述向你提问。请结合之前生成的综述内容和论文详细信息来回答问题。

请根据以下信息回答问题，并明确标注信息来源：
- 如果信息来自之前生成的综述，请标注为 [综述来源]
- 如果信息来自已分析的论文，请标注为 [论文来源: 论文标题]
- 如果信息来自网络/通用知识，请标注为 [网络来源: 通用知识/公开资料]

请确保：
1. 优先使用之前生成的综述内容（这是你之前综合分析的结果）
2. 如果综述中没有相关信息，再参考论文详细信息
3. 明确区分信息来源（综述 vs 论文 vs 网络/通用知识）
4. 如果使用网络/通用知识，请明确标注
5. 保持与之前综述的一致性
{web_search_note if enable_web_search else ''}"""
        
        # 构建用户提示词，包含综述内容
        review_context = ""
        if review_summary:
            review_context = f"""
之前生成的综述报告:
{review_summary}

---
"""
        
        user_prompt = f"""研究主题: {topic}

{review_context}已分析的论文详细信息（供参考）:
{papers_text}

用户问题: {question}

请基于之前生成的综述报告回答用户的问题。如果综述中没有相关信息，可以参考论文详细信息。请明确标注信息来源。"""
        
        # 调用API（使用为问答创建的分析器）
        response = chat_analyzer.client.chat.completions.create(
            model=chat_analyzer.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
            stream=False
        )
        
        answer = response.choices[0].message.content
        
        return jsonify({
            'success': True,
            'answer': answer,
            'question': question
        })
        
    except Exception as e:
        logger.error(f"问答接口出错: {str(e)}")
        return jsonify({'error': str(e)}), 500


def open_browser():
    """延迟打开浏览器，等待Flask应用完全启动"""
    time.sleep(1.5)  # 等待1.5秒确保Flask应用已启动
    url = "http://localhost:5000"
    logger.info(f"正在打开浏览器: {url}")
    webbrowser.open(url)


if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("Web应用启动")
    logger.info("=" * 50)

    _debug = True

    # 只在主进程中打开浏览器（避免reloader进程重复打开）
    # WERKZEUG_RUN_MAIN只在reloader的子进程中存在
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

    logger.info("服务器地址: http://localhost:5000")
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        logger.info("浏览器将自动打开...")
    app.run(debug=_debug, host='0.0.0.0', port=5000)

