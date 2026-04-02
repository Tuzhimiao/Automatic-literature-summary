"""
论文去重模块
用于检测和移除来自不同搜索引擎的重复论文
"""

import re
from typing import List, Set, Tuple
from loguru import logger
from difflib import SequenceMatcher

from .data_structures import Paper


class PaperDeduplicator:
    """论文去重器"""
    
    def __init__(self, title_similarity_threshold: float = 0.85, author_overlap_threshold: float = 0.5):
        """
        初始化去重器
        
        Args:
            title_similarity_threshold: 标题相似度阈值（0-1），超过此值认为是重复
            author_overlap_threshold: 作者重叠度阈值（0-1），超过此值认为是重复
        """
        self.title_similarity_threshold = title_similarity_threshold
        self.author_overlap_threshold = author_overlap_threshold
    
    def _normalize_title(self, title: str) -> str:
        """
        标准化标题（用于比较）
        
        Args:
            title: 原始标题
        
        Returns:
            标准化后的标题
        """
        # 转换为小写
        normalized = title.lower()
        
        # 移除特殊字符和标点符号
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        # 移除多余空格
        normalized = ' '.join(normalized.split())
        
        # 移除常见的冠词和连接词（可选，但可能影响准确性）
        # normalized = re.sub(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', '', normalized)
        
        return normalized
    
    def _normalize_author_name(self, name: str) -> str:
        """
        标准化作者姓名（用于比较）
        
        Args:
            name: 原始作者姓名
        
        Returns:
            标准化后的姓名
        """
        # 转换为小写并移除多余空格
        normalized = name.lower().strip()
        
        # 移除常见的称谓和中间名缩写
        normalized = re.sub(r'\b(mr|mrs|ms|dr|prof|professor)\b\.?\s*', '', normalized)
        
        return normalized
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        计算两个标题的相似度
        
        使用多种方法：
        1. SequenceMatcher（基于最长公共子序列）
        2. Jaccard相似度（基于词汇集合）
        3. 取两者的最大值
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
        
        Returns:
            相似度分数（0-1）
        """
        # 标准化标题
        norm1 = self._normalize_title(title1)
        norm2 = self._normalize_title(title2)
        
        # 如果标准化后完全相同，返回1.0
        if norm1 == norm2:
            return 1.0
        
        # 方法1：SequenceMatcher相似度
        seq_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # 方法2：Jaccard相似度（基于词汇）
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return seq_similarity
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        jaccard_similarity = intersection / union if union > 0 else 0.0
        
        # 方法3：考虑标题长度差异（如果长度差异很大，降低相似度）
        length_ratio = min(len(norm1), len(norm2)) / max(len(norm1), len(norm2)) if max(len(norm1), len(norm2)) > 0 else 0
        
        # 综合相似度：取SequenceMatcher和Jaccard的加权平均，并考虑长度
        combined_similarity = (seq_similarity * 0.6 + jaccard_similarity * 0.4) * length_ratio
        
        return max(seq_similarity, jaccard_similarity, combined_similarity)
    
    def _calculate_author_overlap(self, authors1: List[str], authors2: List[str]) -> float:
        """
        计算两个作者列表的重叠度
        
        Args:
            authors1: 第一个作者列表
            authors2: 第二个作者列表
        
        Returns:
            重叠度（0-1），表示有多少作者匹配
        """
        if not authors1 or not authors2:
            return 0.0
        
        # 标准化作者姓名
        norm_authors1 = {self._normalize_author_name(a) for a in authors1}
        norm_authors2 = {self._normalize_author_name(a) for a in authors2}
        
        # 计算交集和并集
        intersection = len(norm_authors1 & norm_authors2)
        union = len(norm_authors1 | norm_authors2)
        
        # Jaccard相似度
        if union == 0:
            return 0.0
        
        # 也考虑重叠作者占较小列表的比例（更严格）
        min_list_size = min(len(norm_authors1), len(norm_authors2))
        overlap_ratio = intersection / min_list_size if min_list_size > 0 else 0.0
        
        # 返回Jaccard和重叠比例的加权平均
        jaccard = intersection / union
        return (jaccard * 0.5 + overlap_ratio * 0.5)
    
    def _are_duplicates(self, paper1: Paper, paper2: Paper) -> Tuple[bool, str]:
        """
        判断两篇论文是否是重复的
        
        Args:
            paper1: 第一篇论文
            paper2: 第二篇论文
        
        Returns:
            (是否重复, 原因说明)
        """
        # 如果来源相同，不认为是重复（同一来源内的重复由各自fetcher处理）
        if paper1.source == paper2.source:
            return (False, "来源相同")
        
        # 计算标题相似度
        title_sim = self._calculate_title_similarity(paper1.title, paper2.title)
        
        # 如果标题相似度很高，认为是重复
        if title_sim >= self.title_similarity_threshold:
            # 进一步检查作者重叠度
            author_overlap = self._calculate_author_overlap(paper1.authors, paper2.authors)
            
            if author_overlap >= self.author_overlap_threshold:
                return (True, f"标题相似度{title_sim:.2f}，作者重叠度{author_overlap:.2f}")
            elif title_sim >= 0.95:  # 标题几乎完全相同，即使作者不完全匹配也认为是重复
                return (True, f"标题相似度{title_sim:.2f}（几乎完全相同）")
            else:
                return (False, f"标题相似但作者重叠度{author_overlap:.2f}不足")
        
        # 如果标题相似度中等，但作者重叠度很高，也可能是重复
        if title_sim >= 0.7:  # 降低阈值，考虑中等相似度
            author_overlap = self._calculate_author_overlap(paper1.authors, paper2.authors)
            if author_overlap >= 0.7:  # 作者高度重叠
                return (True, f"标题相似度{title_sim:.2f}，作者高度重叠{author_overlap:.2f}")
        
        return (False, f"标题相似度{title_sim:.2f}不足")
    
    def deduplicate(self, papers: List[Paper], prefer_source: str = "arxiv") -> List[Paper]:
        """
        对论文列表进行去重
        
        策略：
        1. 优先保留指定来源的论文（默认arxiv，因为通常信息更完整）
        2. 如果两篇论文被认为是重复的，保留优先来源的论文
        3. 如果优先来源相同，保留第一篇
        
        Args:
            papers: 论文列表
            prefer_source: 优先保留的来源（"arxiv" 或 "ieee"）
        
        Returns:
            去重后的论文列表
        """
        if len(papers) <= 1:
            return papers
        
        logger.info(f"开始去重，原始论文数: {len(papers)}")
        
        # 创建去重后的列表
        deduplicated = []
        seen_indices = set()  # 已处理的论文索引
        
        # 统计信息
        duplicate_count = 0
        duplicate_pairs = []
        
        for i, paper1 in enumerate(papers):
            if i in seen_indices:
                continue
            
            is_duplicate = False
            
            # 与已保留的论文比较
            for j, paper2 in enumerate(deduplicated):
                is_dup, reason = self._are_duplicates(paper1, paper2)
                
                if is_dup:
                    is_duplicate = True
                    duplicate_count += 1
                    duplicate_pairs.append({
                        'paper1': f"{paper1.title[:50]}... ({paper1.source})",
                        'paper2': f"{paper2.title[:50]}... ({paper2.source})",
                        'reason': reason
                    })
                    
                    # 决定保留哪一篇
                    # 如果当前论文的来源是优先来源，替换已保留的论文
                    if paper1.source == prefer_source and paper2.source != prefer_source:
                        deduplicated[j] = paper1
                        logger.debug(f"替换重复论文: 保留{paper1.source}的版本")
                    # 否则保留已存在的论文
                    else:
                        logger.debug(f"保留已存在的论文: {paper2.source}的版本")
                    
                    break
            
            # 如果没有找到重复，添加到结果列表
            if not is_duplicate:
                deduplicated.append(paper1)
            
            seen_indices.add(i)
        
        logger.info(f"去重完成: 原始{len(papers)}篇 -> 去重后{len(deduplicated)}篇，移除{duplicate_count}篇重复")
        
        if duplicate_pairs:
            logger.info("发现的重复论文对:")
            for pair in duplicate_pairs[:5]:  # 只显示前5对
                logger.info(f"  - {pair['paper1']} <-> {pair['paper2']} ({pair['reason']})")
            if len(duplicate_pairs) > 5:
                logger.info(f"  ... 还有{len(duplicate_pairs) - 5}对重复论文")
        
        return deduplicated










