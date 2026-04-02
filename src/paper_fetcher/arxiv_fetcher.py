"""
arXiv论文检索模块
支持获取PDF全文
支持使用AI生成关键词优化搜索
"""

import arxiv
import requests
from typing import List, Optional
from datetime import datetime
from loguru import logger

from ..utils.data_structures import Paper
from ..utils.pdf_parser import PDFParser
from .ai_search_keywords import generate_search_keywords


class ArxivFetcher:
    """arXiv论文检索器"""
    
    def __init__(self, max_results: int = 20, sort_by: str = "relevance", fetch_fulltext: bool = False, title_only: bool = False, use_ai_keywords: bool = True, gpt_analyzer=None):
        """
        初始化arXiv检索器
        
        Args:
            max_results: 最大返回结果数
            sort_by: 排序方式 (relevance, lastUpdatedDate, submittedDate)
            fetch_fulltext: 是否获取全文（PDF内容）
            title_only: 是否只在标题中搜索（True=只在标题，False=所有字段）
            use_ai_keywords: 是否使用AI生成关键词（默认True）
            gpt_analyzer: GPT分析器实例（用于生成关键词），如果为None且use_ai_keywords=True，将尝试创建
        """
        self.max_results = max_results
        self.sort_by = sort_by
        self.fetch_fulltext = fetch_fulltext
        self.title_only = title_only
        self.use_ai_keywords = use_ai_keywords
        self.gpt_analyzer = gpt_analyzer
    
    def search_exact_title(self, exact_title: str, max_results: int = 3) -> List[Paper]:
        """
        精确匹配标题搜索（不使用AI关键词生成）
        专门用于搜索完整标题，例如从PDF引用文献中提取的重点文献
        
        Args:
            exact_title: 完整的论文标题（可能包含引号）
            max_results: 最大返回结果数（默认3，因为精确匹配通常只需要少量结果）
        
        Returns:
            论文列表
        """
        try:
            # 移除可能存在的引号（如果用户已经加了引号）
            clean_title = exact_title.strip().strip('"').strip("'")
            
            # 使用ti:前缀，只在标题中搜索，并使用引号包裹进行精确匹配
            search_query = f'ti:"{clean_title}"'
            logger.info(f"精确匹配标题搜索: {search_query}")
            
            # 确定排序方式（精确匹配使用相关性排序）
            sort_criterion = arxiv.SortCriterion.Relevance
            
            # 精确匹配只需要少量结果
            search = arxiv.Search(
                query=search_query,
                max_results=max_results,
                sort_by=sort_criterion
            )
            
            papers = []
            for result in arxiv.Client().results(search):
                try:
                    # 提取论文信息
                    title = result.title
                    abstract = result.summary if hasattr(result, 'summary') else ""
                    authors = [author.name for author in result.authors]
                    pub_date = result.published
                    paper_id = result.entry_id.split('/')[-1]  # 提取arXiv ID
                    url = result.entry_id
                    
                    # 处理时区问题
                    if pub_date and pub_date.tzinfo is not None:
                        pub_date = pub_date.replace(tzinfo=None)
                    
                    # 创建Paper对象
                    paper = Paper(
                        title=title,
                        abstract=abstract,
                        authors=authors,
                        publication_date=pub_date,
                        source='arxiv',
                        url=url,
                        paper_id=paper_id
                    )
                    
                    # 如果需要获取全文
                    if self.fetch_fulltext:
                        try:
                            pdf_url = result.pdf_url
                            if pdf_url:
                                response = requests.get(pdf_url, timeout=30)
                                if response.status_code == 200:
                                    try:
                                        parser = PDFParser()
                                        full_text = parser.extract_text_from_bytes(
                                            response.content, max_pages=5
                                        )
                                    except ImportError:
                                        full_text = ""
                                    if full_text:
                                        paper.abstract = (
                                            abstract + "\n\n[全文前5页内容]\n" + full_text[:5000]
                                        )
                                        logger.debug(
                                            f"已获取全文（前5页，{len(full_text)}字符）"
                                        )
                        except Exception as e:
                            logger.warning(f"获取全文失败: {str(e)}")
                    
                    papers.append(paper)
                    
                    if len(papers) >= max_results:
                        break
                        
                except Exception as e:
                    logger.warning(f"处理arXiv结果失败: {str(e)}")
                    continue
            
            logger.info(f"精确匹配标题搜索完成，找到 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            logger.error(f"精确匹配标题搜索失败: {str(e)}")
            return []
    
    def search_papers(
        self, 
        query: str, 
        max_results: Optional[int] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        sort_by: str = "relevance"  # "relevance", "date_asc", "date_desc", "citation"
    ) -> List[Paper]:
        """
        搜索论文
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数（如果为None则使用初始化时的值）
            start_year: 起始年份（如果为None则使用默认值2023）
            end_year: 结束年份（如果为None则使用当前年份）
            sort_by: 排序方式 ("relevance", "date_asc", "date_desc", "citation")
        
        Returns:
            论文列表
        """
        max_results = max_results or self.max_results
        
        # 设置默认年份范围
        if start_year is None:
            start_year = 2023
        if end_year is None:
            end_year = datetime.now().year
        
        try:
            logger.info(f"开始从arXiv搜索: {query} (限制在{start_year}-{end_year}年，排序: {sort_by})")
            
            search_keywords = [query]
            if self.use_ai_keywords and self.gpt_analyzer:
                logger.info("使用 AI 生成搜索关键词（统一模块）...")
                search_keywords = generate_search_keywords(self.gpt_analyzer, query)
                logger.info(f"将使用以下关键词搜索: {search_keywords}")
            
            # 构建日期范围（arXiv API不支持直接在查询中使用日期过滤，我们会在结果中过滤）
            # 注意：arXiv的日期过滤语法比较复杂，我们改为在结果中过滤
            
            # 使用多个关键词进行搜索，合并结果
            all_papers = []
            seen_paper_ids = set()  # 用于去重
            
            for keyword in search_keywords:
                # 构建搜索查询（不使用日期过滤，在结果中过滤）
                # 如果title_only=True，只在标题中搜索（使用ti:前缀）
                # 否则在所有字段中搜索（标题、摘要、作者、评论等）- 默认行为
                if self.title_only:
                    # 只在标题中搜索：使用ti:前缀
                    search_query = f"ti:{keyword}"
                    logger.info(f"使用关键词搜索: ti:{keyword}")
                else:
                    # 在所有字段中搜索（标题、摘要、作者、评论等）- 这是默认和推荐的方式
                    search_query = keyword
                    logger.info(f"使用关键词搜索: {keyword}")
                
                # 确定排序方式
                if sort_by == "relevance":
                    sort_criterion = arxiv.SortCriterion.Relevance
                elif sort_by == "date_asc":
                    sort_criterion = arxiv.SortCriterion.SubmittedDate
                elif sort_by == "date_desc":
                    sort_criterion = arxiv.SortCriterion.SubmittedDate
                else:  # 默认相关性
                    sort_criterion = arxiv.SortCriterion.Relevance
                
                # 每个关键词搜索时，获取足够的结果以便合并后仍有足够数量
                # 注意：arXiv API理论上支持最多30000条结果，但实际建议不超过2000-3000
                # 我们使用更保守的策略：每个关键词获取足够的结果，但不超过3000
                per_keyword_results = max(10, max_results // len(search_keywords) + 5)
                # 计算需要获取的结果数，但不超过arXiv API的推荐上限（3000）
                fetch_count = min(per_keyword_results * 3, 3000)
                search = arxiv.Search(
                    query=search_query,
                    max_results=fetch_count,  # 获取更多结果以便过滤后仍有足够数量，但不超过3000
                    sort_by=sort_criterion
                )
                logger.debug(f"关键词 '{keyword}' 将获取最多 {fetch_count} 条结果（目标: {max_results} 条）")
                
                # 定义日期范围
                start_date = datetime(start_year, 1, 1)
                end_date = datetime(end_year, 12, 31, 23, 59, 59)
                
                keyword_papers = []
                # 先收集所有符合条件的论文元数据，避免在循环中等待PDF下载
                valid_results = []
                for result in arxiv.Client().results(search):
                    # 检查日期是否在指定年份范围内
                    pub_date = result.published
                    if pub_date:
                        # 处理时区问题：如果pub_date是aware datetime，转换为naive
                        if pub_date.tzinfo is not None:
                            # 转换为UTC然后移除时区信息
                            pub_date = pub_date.replace(tzinfo=None)
                        
                        # 如果日期不在范围内，跳过
                        if pub_date < start_date or pub_date > end_date:
                            continue
                    else:
                        # 如果没有日期，跳过
                        continue
                    
                    # 检查是否已存在（去重）
                    paper_id = result.entry_id.split('/')[-1]
                    if paper_id in seen_paper_ids:
                        continue
                    seen_paper_ids.add(paper_id)
                    
                    # 如果已经达到所需数量，停止
                    if len(all_papers) >= max_results:
                        break
                    
                    valid_results.append((result, pub_date, paper_id))
                    
                    # 如果已经收集足够的结果，停止
                    if len(valid_results) + len(all_papers) >= max_results:
                        break
                
                # 批量处理收集到的结果
                # 如果启用全文获取，只对前3篇论文获取全文（避免太慢）
                fulltext_limit = 3 if self.fetch_fulltext else 0
                for idx, (result, pub_date, paper_id) in enumerate(valid_results):
                    # 如果已经达到所需数量，停止
                    if len(all_papers) >= max_results:
                        break
                    
                    # 获取摘要
                    abstract = result.summary
                    
                    # 如果启用全文获取，只对前几篇论文获取全文
                    fulltext = None
                    if self.fetch_fulltext and idx < fulltext_limit:
                        try:
                            fulltext = self._fetch_pdf_text(result.entry_id)
                            if fulltext:
                                logger.debug(f"成功获取全文: {result.title[:50]}... ({idx+1}/{min(fulltext_limit, len(valid_results))})")
                        except Exception as e:
                            logger.debug(f"获取全文失败: {str(e)}")
                    
                    # 如果获取到全文，将全文添加到摘要后面（用于AI分析）
                    content = abstract
                    if fulltext:
                        # 只使用前5000字符的全文（避免token过多）
                        content = abstract + "\n\n[全文内容]\n" + fulltext[:5000]
                    
                    paper = Paper(
                        title=result.title,
                        abstract=content,  # 包含全文的内容
                        authors=[author.name for author in result.authors],
                        publication_date=pub_date,
                        source="arxiv",
                        url=result.entry_id,
                        paper_id=paper_id
                    )
                    keyword_papers.append(paper)
                    all_papers.append(paper)
                    logger.debug(f"找到论文: {paper.title} ({pub_date.strftime('%Y-%m-%d')})")
                
                logger.info(f"关键词 '{keyword}' 检索到 {len(keyword_papers)} 篇新论文")
                
                # 如果已经达到所需数量，停止搜索其他关键词
                if len(all_papers) >= max_results:
                    break
            
            # 根据排序方式排序
            if sort_by == "date_asc":
                all_papers.sort(key=lambda p: p.publication_date if p.publication_date else datetime.max)
            elif sort_by == "date_desc":
                all_papers.sort(key=lambda p: p.publication_date if p.publication_date else datetime.min, reverse=True)
            elif sort_by == "citation":
                # 按引用量降序排序（如果有引用量信息）
                all_papers.sort(key=lambda p: p.citation_count if p.citation_count else 0, reverse=True)
            # relevance 已经在API层面排序，不需要再次排序
            
            # 确保不超过最大数量
            all_papers = all_papers[:max_results]
            
            logger.info(f"成功检索到 {len(all_papers)} 篇论文（{start_year}-{end_year}年，排序: {sort_by}，使用{len(search_keywords)}个关键词）")
            return all_papers
            
        except Exception as e:
            logger.error(f"arXiv检索失败: {str(e)}")
            return []
    
    def _fetch_pdf_text(self, arxiv_url: str) -> Optional[str]:
        """
        从arXiv下载PDF并提取文本
        
        Args:
            arxiv_url: arXiv论文URL
        
        Returns:
            提取的文本内容，如果失败返回None
        """
        try:
            # 构建PDF URL
            arxiv_id = arxiv_url.split('/')[-1]
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            
            # 下载PDF
            response = requests.get(pdf_url, timeout=10)
            if response.status_code != 200:
                return None
            
            try:
                parser = PDFParser()
                text = parser.extract_text_from_bytes(response.content, max_pages=5)
                return text.strip() if text else None
            except ImportError:
                logger.warning("PyPDF2未安装，无法提取PDF文本。安装: pip install PyPDF2")
                return None
            except Exception as e:
                logger.debug(f"PDF文本提取失败: {str(e)}")
                return None
                
        except Exception as e:
            logger.debug(f"下载PDF失败: {str(e)}")
            return None

