"""
统一的学术检索 AI 关键词生成（arXiv / IEEE Xplore / PubMed 等均使用本模块，避免各抓取器重复实现）。
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from ..analysis.gpt_analyzer import GPTAnalyzer


def generate_search_keywords(gpt_analyzer: Optional["GPTAnalyzer"], user_topic: str) -> List[str]:
    """
    使用大模型为检索生成 3–5 个英文关键词（适用于常见学术数据库）。

    Args:
        gpt_analyzer: GPT 分析器；为 None 时返回单元素列表 [user_topic]。
        user_topic: 用户研究主题（中英文均可）。

    Returns:
        关键词列表；失败时回退为 [user_topic]。
    """
    if not gpt_analyzer:
        logger.warning("未配置 GPT 分析器，无法生成 AI 关键词，使用原始主题作为查询")
        return [user_topic]

    prompt = f"""你是一位学术检索专家。用户需要在 arXiv、IEEE Xplore、PubMed 等数据库中检索与下列主题相关的论文：

研究主题：{user_topic}

请生成 3–5 个**英文**检索关键词或短语。要求：
1. 使用英文学术常用表述，便于跨库检索；
2. 覆盖主题的不同侧面，但不要过于宽泛；
3. 优先使用领域内通用术语（生物医学类可兼顾 MeSH/常用说法）。

请**只**返回如下 JSON，不要其他文字：
{{
    "keywords": ["keyword1", "keyword2", "keyword3"]
}}
"""

    try:
        response = gpt_analyzer.client.chat.completions.create(
            model=gpt_analyzer.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是学术检索专家，只输出合法 JSON，keywords 为英文数组。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=220,
            stream=False,
        )
        response_text = response.choices[0].message.content.strip()
        if response_text.startswith("{"):
            result = json.loads(response_text)
        else:
            match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
            if not match:
                raise ValueError("响应中无 JSON")
            result = json.loads(match.group())
        keywords = result.get("keywords", [])
        if keywords and isinstance(keywords, list) and len(keywords) >= 2:
            out = [str(k).strip() for k in keywords if k][:5]
            logger.info(f"AI 生成的检索关键词: {out}")
            return out
        logger.warning(f"AI 返回的关键词格式异常: {keywords}，使用原始主题")
        return [user_topic]
    except Exception as e:
        logger.warning(f"生成 AI 检索关键词失败: {e}，使用原始主题")
        return [user_topic]
