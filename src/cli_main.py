"""
命令行批处理流程：检索 → 分析 → 传统置信度管线 → 导出报告。
Web 应用请使用项目根目录的 app.py。
"""

import os
import sys

# 保证可从任意工作目录以「python main.py」方式运行
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import yaml
from loguru import logger

from src.paper_fetcher import ArxivFetcher, IeeeXploreFetcher
from src.analysis import GPTAnalyzer
from src.hallucination import (
    ConsistencyChecker,
    CitationCounter,
    TermValidator,
    ConfidenceEstimator,
)
from src.report import MarkdownGenerator, PDFGenerator, HTMLGenerator, Visualizer, BibTeXGenerator
from src.utils.data_structures import ValidationResult


def load_config(config_path: str = "config/config.yaml") -> dict:
    """加载配置文件（相对于当前工作目录或项目根）。"""
    path = config_path
    if not os.path.isabs(path):
        cwd_path = os.path.join(os.getcwd(), path)
        root_path = os.path.join(_ROOT, path)
        if os.path.isfile(cwd_path):
            path = cwd_path
        elif os.path.isfile(root_path):
            path = root_path
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"加载配置失败: {str(e)}")
        return {}


def run_cli() -> None:
    """命令行主流程。"""
    logger.add("logs/system.log", rotation="10 MB", level="INFO")
    logger.info("=" * 50)
    logger.info("自动化研究现状收集与置信度评估系统启动")
    logger.info("=" * 50)

    os.chdir(_ROOT)

    config = load_config()
    if not config:
        logger.error("配置加载失败，程序退出")
        return

    topic = input("请输入研究主题: ").strip()
    if not topic:
        logger.error("研究主题不能为空")
        return

    logger.info(f"研究主题: {topic}")

    logger.info("初始化模块...")

    arxiv_fetcher = ArxivFetcher(
        max_results=config.get("paper_fetch", {}).get("arxiv", {}).get("max_results", 20)
    )

    ieee_xplore_fetcher = None
    try:
        ieee_xplore_fetcher = IeeeXploreFetcher(
            max_results=config.get("paper_fetch", {})
            .get("ieee_xplore", {})
            .get("max_results", 20),
            use_ai_keywords=True,
            gpt_analyzer=None,
            api_key=config.get("ieee_xplore", {}).get("api_key"),
            use_web_scraper=config.get("ieee_xplore", {}).get("use_web_scraper", True),
        )
        logger.info("IEEE Xplore检索器初始化成功")
    except Exception as e:
        logger.warning(f"IEEE Xplore检索器初始化失败: {str(e)}")

    deepseek_config = config.get("deepseek", {})
    kimi_config = config.get("kimi", {})
    qwen_config = config.get("qwen", {})

    if deepseek_config.get("api_key"):
        api_provider = "deepseek"
        api_config = deepseek_config
        logger.info("使用DeepSeek API")
    elif kimi_config.get("api_key"):
        api_provider = "kimi"
        api_config = kimi_config
        logger.info("使用Kimi API")
    elif qwen_config.get("api_key"):
        api_provider = "qwen"
        api_config = qwen_config
        logger.info("使用Qwen API")
    else:
        logger.error("未配置API密钥（请配置DeepSeek、Kimi或Qwen）")
        return

    default_models = {
        "deepseek": "deepseek-chat",
        "kimi": "moonshot-v1-32k",
        "qwen": "qwen-max",
    }
    default_model = default_models.get(api_provider, "deepseek-chat")

    gpt_analyzer = GPTAnalyzer(
        api_key=api_config.get("api_key"),
        model=api_config.get("model", default_model),
        temperature=api_config.get("temperature", 0.3),
        max_tokens=api_config.get("max_tokens", 2000),
        api_provider=api_provider,
        base_url=api_config.get("base_url"),
    )

    consistency_checker = ConsistencyChecker()
    citation_counter = CitationCounter()
    term_validator = TermValidator()
    confidence_estimator = ConfidenceEstimator()

    markdown_generator = MarkdownGenerator()
    html_generator = HTMLGenerator()
    pdf_generator = None
    try:
        pdf_generator = PDFGenerator()
    except Exception as e:
        logger.warning(f"PDF生成器初始化失败: {str(e)}")

    visualizer = Visualizer()
    bibtex_generator = BibTeXGenerator()

    logger.info("=" * 50)
    logger.info("步骤1: 检索论文")
    logger.info("=" * 50)

    all_papers = []

    logger.info("从arXiv检索...")
    arxiv_papers = arxiv_fetcher.search_papers(topic)
    all_papers.extend(arxiv_papers)

    if ieee_xplore_fetcher:
        logger.info("从IEEE Xplore检索...")
        try:
            ieee_xplore_fetcher.gpt_analyzer = gpt_analyzer
            ieee_papers = ieee_xplore_fetcher.search_papers(topic)
            all_papers.extend(ieee_papers)
        except Exception as e:
            logger.warning(f"IEEE Xplore检索失败: {str(e)}")

    if not all_papers:
        logger.error("未检索到任何论文，程序退出")
        return

    logger.info(f"共检索到 {len(all_papers)} 篇论文")

    logger.info("=" * 50)
    logger.info("步骤2: GPT分析")
    logger.info("=" * 50)

    analysis_result = gpt_analyzer.analyze_papers(all_papers, topic)
    logger.info("GPT分析完成")

    logger.info("=" * 50)
    logger.info("步骤3: 置信度评估")
    logger.info("=" * 50)

    consistency_score = consistency_checker.calculate_consistency(all_papers)
    logger.info(f"一致性评分: {consistency_score:.3f}")

    citation_frequency = citation_counter.count_citations(all_papers)

    expected_terms = term_validator.extract_terms_from_papers(all_papers)
    term_validation = term_validator.validate_terms_in_summary(
        analysis_result.summary, expected_terms
    )
    term_coverage = term_validator.calculate_term_coverage(term_validation)

    llm_confidence = getattr(analysis_result, "llm_confidence", None)
    has_conflicts = getattr(analysis_result, "conflicts", None) and len(
        analysis_result.conflicts
    ) > 0

    overall_confidence = confidence_estimator.estimate_confidence(
        all_papers,
        consistency_score,
        term_coverage,
        citation_frequency,
        llm_confidence=llm_confidence,
        has_conflicts=has_conflicts,
    )

    validation_result = ValidationResult(
        consistency_score=consistency_score,
        citation_frequency=citation_frequency,
        term_validation=term_validation,
        model_confidence=llm_confidence if llm_confidence is not None else 0.7,
        overall_confidence=overall_confidence,
        confidence_reason=getattr(analysis_result, "confidence_reason", None),
        conflicts=getattr(analysis_result, "conflicts", None),
        term_coverage=term_coverage,
    )

    logger.info(f"总体置信度: {overall_confidence:.3f}")

    logger.info("=" * 50)
    logger.info("步骤4: 生成报告")
    logger.info("=" * 50)

    output_dir = config.get("report", {}).get("output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)

    safe_topic = topic.replace(" ", "_")
    md_path = os.path.join(output_dir, f"report_{safe_topic}.md")
    markdown_generator.generate(topic, all_papers, analysis_result, validation_result, md_path)

    html_path = os.path.join(output_dir, f"report_{safe_topic}.html")
    html_generator.generate(topic, all_papers, analysis_result, validation_result, html_path)
    logger.info(f"HTML报告已生成，可在浏览器中打开: {html_path}")

    if pdf_generator:
        pdf_path = os.path.join(output_dir, f"report_{safe_topic}.pdf")
        pdf_generator.generate(topic, all_papers, analysis_result, validation_result, pdf_path)

    bibtex_path = os.path.join(output_dir, f"report_{safe_topic}.bib")
    bibtex_generator.generate(all_papers, bibtex_path)
    logger.info(f"BibTeX文件已生成: {bibtex_path}")

    if config.get("report", {}).get("include_visualizations", True):
        timeline_path = os.path.join(output_dir, f"timeline_{safe_topic}.png")
        visualizer.generate_timeline(all_papers, timeline_path)

        if len(all_papers) >= 2:
            topic_graph_path = os.path.join(output_dir, f"topic_graph_{safe_topic}.html")
            generated_path = visualizer.generate_interactive_topic_graph(
                all_papers,
                topic_graph_path,
                use_topics=True,
                similarity_threshold=0.15,
            )

            if generated_path:
                html_generator.generate(
                    topic,
                    all_papers,
                    analysis_result,
                    validation_result,
                    html_path,
                    topic_graph_path=generated_path,
                )
                logger.info(f"主题图谱已生成并嵌入到HTML报告: {generated_path}")

    logger.info("=" * 50)
    logger.info("系统运行完成！")
    logger.info(f"报告已保存到: {output_dir}")
    logger.info("=" * 50)
