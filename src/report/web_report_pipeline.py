"""
Web 分析任务：推荐关键词 + 报告/可视化产物生成（与 app 内联顺序一致）。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from loguru import logger


def recommended_keywords_from_analysis(
    analysis_result: Any,
    topic_local: str,
    keyword_analyzer: Any,
) -> List[str]:
    """步骤4.1：与 ``app.search_papers`` 分析线程内逻辑一致。"""
    recommended_keywords: List[str] = []
    try:
        if not keyword_analyzer:
            return recommended_keywords

        review_content = ""
        if analysis_result.section1_research_intro:
            review_content = f"""研究介绍：{analysis_result.section1_research_intro[:500]}
研究进展：{analysis_result.section2_research_progress[:500] if analysis_result.section2_research_progress else ''}
研究现状：{analysis_result.section3_research_status[:500] if analysis_result.section3_research_status else ''}
现有方法：{analysis_result.section4_existing_methods[:500] if analysis_result.section4_existing_methods else ''}
未来发展：{analysis_result.section5_future_development[:500] if analysis_result.section5_future_development else ''}"""
        elif analysis_result.summary:
            review_content = analysis_result.summary[:1000]

        keyword_prompt = f"""基于以下研究综述内容，请推荐5个最适合继续深入搜索的关键词。这些关键词应该：
1. 能够帮助发现更多相关的研究论文
2. 覆盖综述中提到的不同研究方向或技术点
3. 适合在学术搜索引擎（如arXiv、IEEE Xplore等）中使用
4. 使用英文关键词（学术搜索通常使用英文）

## 研究主题：{topic_local}

## 综述内容：
{review_content}

请严格按照JSON格式返回，格式如下：
{{
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}

只返回JSON，不要有其他文字说明。"""

        response = keyword_analyzer.client.chat.completions.create(
            model=keyword_analyzer.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一位学术搜索专家，擅长为研究主题生成有效的搜索关键词。请严格按照JSON格式返回结果。",
                },
                {"role": "user", "content": keyword_prompt},
            ],
            temperature=0.7,
            max_tokens=200,
            stream=False,
        )

        response_text = response.choices[0].message.content.strip()

        try:
            if response_text.startswith("{"):
                result = json.loads(response_text)
            else:
                match = re.search(r"\{[^}]+\}", response_text)
                if match:
                    result = json.loads(match.group())
                else:
                    raise ValueError("无法找到JSON格式")

            keywords = result.get("keywords", [])
            if keywords and isinstance(keywords, list) and len(keywords) >= 3:
                recommended_keywords = keywords[:5]
                logger.info(f"生成推荐关键词: {recommended_keywords}")
            else:
                logger.warning(f"推荐关键词格式不正确: {keywords}")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"解析推荐关键词失败: {str(e)}")
    except Exception as e:
        logger.warning(f"生成推荐关键词失败: {str(e)}")
        import traceback

        logger.debug(f"详细错误: {traceback.format_exc()}")

    return recommended_keywords


def run_analysis_report_artifacts(
    modules: Dict[str, Any],
    topic_local: str,
    all_papers: List[Any],
    analysis_result: Any,
    validation_result: Any,
    output_folder: str,
) -> Dict[str, Any]:
    """
    生成 HTML/MD/PDF/BibTeX/时间线/词云，返回路径字典（供 JSON 与前端使用）。
    """
    from werkzeug.utils import secure_filename

    safe_topic = secure_filename(
        topic_local.replace(" ", "_").replace("/", "_").replace("\\", "_")
    )
    paper_count = len(all_papers)
    file_base_name = f"{safe_topic}_{paper_count}"
    output_dir = os.path.join(output_folder, safe_topic)
    os.makedirs(output_dir, exist_ok=True)

    html_path = os.path.join(output_dir, f"{file_base_name}.html")
    modules["html_generator"].generate(
        topic_local, all_papers, analysis_result, validation_result, html_path
    )

    md_path = os.path.join(output_dir, f"{file_base_name}.md")
    modules["markdown_generator"].generate(
        topic_local, all_papers, analysis_result, validation_result, md_path
    )

    pdf_path: Optional[str] = None
    if modules.get("pdf_generator"):
        try:
            pdf_path = os.path.join(output_dir, f"{file_base_name}.pdf")
            modules["pdf_generator"].generate(
                topic_local, all_papers, analysis_result, validation_result, pdf_path
            )
            logger.info(f"PDF报告已生成: {pdf_path}")
        except Exception as e:
            logger.warning(f"PDF报告生成失败: {str(e)}")
            pdf_path = None

    bibtex_path: Optional[str] = None
    if modules.get("bibtex_generator"):
        try:
            bibtex_path = os.path.join(output_dir, f"{file_base_name}.bib")
            modules["bibtex_generator"].generate(all_papers, bibtex_path)
            logger.info(f"BibTeX文件已生成: {bibtex_path}")
        except Exception as e:
            logger.warning(f"BibTeX文件生成失败: {str(e)}")
            bibtex_path = None

    timeline_path = os.path.join(output_dir, f"timeline_{file_base_name}.png")
    modules["visualizer"].generate_timeline(all_papers, timeline_path)

    wordcloud_path: Optional[str] = None
    if hasattr(analysis_result, "keywords") and analysis_result.keywords:
        wordcloud_path = os.path.join(output_dir, f"wordcloud_{file_base_name}.png")
        modules["visualizer"].generate_wordcloud(
            analysis_result.keywords, wordcloud_path
        )
        if wordcloud_path and os.path.exists(wordcloud_path):
            logger.info(f"词云图已生成: {wordcloud_path}")
        else:
            wordcloud_path = None

    return {
        "safe_topic": safe_topic,
        "file_base_name": file_base_name,
        "output_dir": output_dir,
        "html_path": html_path,
        "md_path": md_path,
        "pdf_path": pdf_path,
        "bibtex_path": bibtex_path,
        "timeline_path": timeline_path,
        "wordcloud_path": wordcloud_path,
    }
