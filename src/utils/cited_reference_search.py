"""
PDF 联想：按引用标题检索（与历史 app 内联逻辑一致）。
"""

from __future__ import annotations

from typing import Any, List


def search_papers_for_cited_title(
    fetcher: Any, ref_title: str, max_results: int = 3
) -> List[Any]:
    """
    优先 ``search_exact_title``；否则临时关闭 AI 关键词后 ``search_papers``。
    若 ``search_papers`` 抛错，**不**恢复 ``use_ai_keywords``，与旧版 app 行为一致。
    """
    if hasattr(fetcher, "search_exact_title"):
        return fetcher.search_exact_title(ref_title, max_results=max_results)
    original_use_ai = getattr(fetcher, "use_ai_keywords", True)
    if hasattr(fetcher, "use_ai_keywords"):
        fetcher.use_ai_keywords = False
    search_results = fetcher.search_papers(
        ref_title,
        max_results=max_results,
        start_year=None,
        end_year=None,
        sort_by="relevance",
    )
    if hasattr(fetcher, "use_ai_keywords"):
        fetcher.use_ai_keywords = original_use_ai
    return search_results
