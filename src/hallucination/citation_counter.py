"""
引用出现频次统计模块
"""

from typing import List, Dict
from collections import Counter
from loguru import logger

from ..utils.data_structures import Paper


class CitationCounter:
    """引用频次统计器"""
    
    def count_citations(self, papers: List[Paper]) -> Dict[str, int]:
        """
        统计论文的引用频次
        
        Args:
            papers: 论文列表
        
        Returns:
            论文ID到引用次数的映射
        """
        citation_dict = {}
        
        for paper in papers:
            if paper.citation_count is not None:
                citation_dict[paper.paper_id] = paper.citation_count
            else:
                # 如果没有引用数据，设为0
                citation_dict[paper.paper_id] = 0
        
        logger.info(f"统计了 {len(citation_dict)} 篇论文的引用次数")
        return citation_dict
    
    def get_highly_cited_papers(self, papers: List[Paper], threshold: int = 10) -> List[Paper]:
        """
        获取高引用论文
        
        Args:
            papers: 论文列表
            threshold: 引用次数阈值
        
        Returns:
            高引用论文列表
        """
        high_cited = [p for p in papers if p.citation_count and p.citation_count >= threshold]
        logger.info(f"找到 {len(high_cited)} 篇高引用论文（引用次数 >= {threshold}）")
        return high_cited
    
    def extract_key_terms(self, papers: List[Paper], top_n: int = 10) -> List[tuple]:
        """
        从论文中提取高频术语
        
        Args:
            papers: 论文列表
            top_n: 返回前N个术语
        
        Returns:
            (术语, 出现次数) 的列表
        """
        from collections import Counter
        import re
        
        # 合并所有摘要和标题
        all_text = " ".join([p.title + " " + p.abstract for p in papers])
        
        # 提取单词（简单方法）
        words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text.lower())
        
        # 统计词频
        word_counts = Counter(words)
        
        # 返回最常见的术语
        top_terms = word_counts.most_common(top_n)
        logger.info(f"提取了前 {top_n} 个高频术语")
        return top_terms












