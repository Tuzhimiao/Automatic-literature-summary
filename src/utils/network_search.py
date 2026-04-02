"""
主流程网络检索：按来源拉取论文（与 app 内联块行为一致，便于单测与阅读）。
"""

from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger

_ASSOCIATION_FETCH_SOURCES = frozenset({"arxiv", "ieee_xplore", "pubmed"})


def fetch_expansion_keyword_batch(
    fetcher: Any,
    source_name: str,
    keyword: str,
    per_keyword_count: int,
    start_year: int,
    end_year: int,
    sort_by: str,
) -> List[Any]:
    """拓展关键词搜索：三源调用相同签名。"""
    if source_name not in _ASSOCIATION_FETCH_SOURCES:
        return []
    return fetcher.search_papers(
        keyword,
        max_results=per_keyword_count,
        start_year=start_year,
        end_year=end_year,
        sort_by=sort_by,
    )


def extend_network_search_results(
    *,
    sources: List[str],
    modules: Dict[str, Any],
    source_counts: Dict[str, Any],
    search_query: str,
    start_year: int,
    end_year: int,
    sort_by: str,
    data: Dict[str, Any],
    all_papers: List[Any],
    source_stats: Dict[str, Any],
) -> None:
    """
    与 ``search_papers`` 路由中三段 arXiv / IEEE / PubMed 逻辑等价，就地 extend ``all_papers`` 并写 ``source_stats``。
    """
    if "arxiv" in sources:
        try:
            arxiv_count = source_counts.get("arxiv", 20)
            arxiv_fulltext = source_counts.get("arxiv_fulltext", False)

            try:
                arxiv_count = int(arxiv_count)
                if arxiv_count <= 0:
                    arxiv_count = 20
                    logger.warning("arXiv数量无效，使用默认值20")
            except (ValueError, TypeError):
                arxiv_count = 20
                logger.warning("arXiv数量格式错误，使用默认值20")

            logger.info(f"arXiv检索设置: 数量={arxiv_count}, 全文={arxiv_fulltext}")

            modules["arxiv_fetcher"].max_results = arxiv_count
            modules["arxiv_fetcher"].fetch_fulltext = arxiv_fulltext

            arxiv_papers = modules["arxiv_fetcher"].search_papers(
                search_query,
                max_results=arxiv_count,
                start_year=start_year,
                end_year=end_year,
                sort_by=sort_by,
            )
            source_stats["arxiv"] = len(arxiv_papers)
            logger.info(
                f"从arXiv检索到 {len(arxiv_papers)} 篇论文（使用{'全文' if arxiv_fulltext else '摘要'}）"
            )

            all_papers.extend(arxiv_papers)
        except Exception as e:
            logger.error(f"arXiv检索失败: {str(e)}")
            source_stats["arxiv"] = 0

    if "ieee_xplore" in sources:
        if not modules.get("ieee_xplore_fetcher"):
            logger.warning("IEEE Xplore检索器未初始化，跳过IEEE Xplore检索")
            source_stats["ieee_xplore"] = 0
        else:
            try:
                ieee_xplore_count = source_counts.get("ieee_xplore", 20)

                try:
                    ieee_xplore_count = int(ieee_xplore_count)
                    if ieee_xplore_count <= 0:
                        ieee_xplore_count = 20
                        logger.warning("IEEE Xplore数量无效，使用默认值20")
                except (ValueError, TypeError):
                    ieee_xplore_count = 20
                    logger.warning("IEEE Xplore数量格式错误，使用默认值20")

                logger.info(f"IEEE Xplore检索设置: 数量={ieee_xplore_count}")

                modules["ieee_xplore_fetcher"].max_results = ieee_xplore_count

                ieee_xplore_fulltext = data.get("ieee_xplore_fulltext", False)
                modules["ieee_xplore_fetcher"].fetch_fulltext = bool(ieee_xplore_fulltext)

                ieee_xplore_papers = modules["ieee_xplore_fetcher"].search_papers(
                    search_query,
                    max_results=ieee_xplore_count,
                    start_year=start_year,
                    end_year=end_year,
                    sort_by=sort_by,
                )
                source_stats["ieee_xplore"] = len(ieee_xplore_papers)
                logger.info(f"从IEEE Xplore检索到 {len(ieee_xplore_papers)} 篇论文")

                all_papers.extend(ieee_xplore_papers)
            except Exception as e:
                logger.error(f"IEEE Xplore检索失败: {str(e)}")
                import traceback

                logger.debug(f"IEEE Xplore检索详细错误: {traceback.format_exc()}")
                source_stats["ieee_xplore"] = 0

    if "pubmed" in sources:
        if not modules.get("pubmed_fetcher"):
            logger.warning("PubMed 检索器未初始化，跳过 PubMed 检索")
            source_stats["pubmed"] = 0
        else:
            try:
                pubmed_count = source_counts.get("pubmed", 20)
                try:
                    pubmed_count = int(pubmed_count)
                    if pubmed_count <= 0:
                        pubmed_count = 20
                except (ValueError, TypeError):
                    pubmed_count = 20
                logger.info(f"PubMed 检索设置: 数量={pubmed_count}")
                modules["pubmed_fetcher"].max_results = pubmed_count
                pubmed_papers = modules["pubmed_fetcher"].search_papers(
                    search_query,
                    max_results=pubmed_count,
                    start_year=start_year,
                    end_year=end_year,
                    sort_by=sort_by,
                )
                source_stats["pubmed"] = len(pubmed_papers)
                logger.info(f"从 PubMed 检索到 {len(pubmed_papers)} 篇论文")
                all_papers.extend(pubmed_papers)
            except Exception as e:
                logger.error(f"PubMed 检索失败: {str(e)}")
                source_stats["pubmed"] = 0
