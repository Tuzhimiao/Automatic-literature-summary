"""
相似度匹配工具
用于匹配论文标题和作者的相似度
"""

from typing import List, Tuple
from loguru import logger
import re


def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度（使用简单的字符匹配）
    
    Args:
        text1: 文本1
        text2: 文本2
    
    Returns:
        相似度（0-1之间）
    """
    if not text1 or not text2:
        return 0.0
    
    # 转换为小写并移除标点符号
    text1_clean = re.sub(r'[^\w\s]', '', text1.lower())
    text2_clean = re.sub(r'[^\w\s]', '', text2.lower())
    
    # 计算单词集合
    words1 = set(text1_clean.split())
    words2 = set(text2_clean.split())
    
    if not words1 or not words2:
        return 0.0
    
    # 计算Jaccard相似度
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    if union == 0:
        return 0.0
    
    jaccard_similarity = intersection / union
    
    # 也计算字符级别的相似度（用于处理缩写等情况）
    # 使用最长公共子序列的思想（简化版）
    char_similarity = _calculate_char_similarity(text1_clean, text2_clean)
    
    # 综合两种相似度
    final_similarity = (jaccard_similarity * 0.6 + char_similarity * 0.4)
    
    return final_similarity


def _calculate_char_similarity(text1: str, text2: str) -> float:
    """计算字符级别的相似度"""
    if not text1 or not text2:
        return 0.0
    
    # 使用编辑距离的简化版本
    # 计算相同字符的比例
    common_chars = set(text1) & set(text2)
    all_chars = set(text1) | set(text2)
    
    if not all_chars:
        return 0.0
    
    return len(common_chars) / len(all_chars)


def match_paper_by_similarity(
    target_title: str,
    target_authors: List[str],
    candidate_papers: List,
    title_threshold: float = 0.8,
    author_threshold: float = 0.8
) -> Tuple[bool, any, float]:
    """
    根据相似度匹配论文
    
    Args:
        target_title: 目标标题
        target_authors: 目标作者列表
        candidate_papers: 候选论文列表（Paper对象或包含title和authors的字典）
        title_threshold: 标题相似度阈值（默认0.8）
        author_threshold: 作者相似度阈值（默认0.8）
    
    Returns:
        (是否匹配成功, 匹配的论文对象, 综合相似度)
    """
    if not target_title or not candidate_papers:
        return False, None, 0.0
    
    best_match = None
    best_similarity = 0.0
    
    for paper in candidate_papers:
        # 获取论文标题和作者
        if hasattr(paper, 'title'):
            paper_title = paper.title
            paper_authors = paper.authors if hasattr(paper, 'authors') else []
        elif isinstance(paper, dict):
            paper_title = paper.get('title', '')
            paper_authors = paper.get('authors', [])
        else:
            continue
        
        if not paper_title:
            continue
        
        # 计算标题相似度
        title_sim = calculate_similarity(target_title, paper_title)
        
        # 计算作者相似度
        author_sim = 0.0
        if target_authors and paper_authors:
            # 计算所有作者对的相似度，取最大值
            max_author_sim = 0.0
            for target_author in target_authors:
                for paper_author in paper_authors:
                    author_pair_sim = calculate_similarity(target_author, paper_author)
                    max_author_sim = max(max_author_sim, author_pair_sim)
            author_sim = max_author_sim
        
        # 综合相似度（标题权重0.6，作者权重0.4）
        if target_authors:
            combined_sim = title_sim * 0.6 + author_sim * 0.4
        else:
            # 如果没有作者信息，只使用标题
            combined_sim = title_sim
        
        # 检查是否满足匹配条件（按优先级）
        matched = False
        
        # 条件1: 标题相似度 > 0.9，不需要看作者相似度就可以算作精准匹配
        if title_sim > 0.9:
            matched = True
        # 条件2: 标题相似度 > 0.7 且作者相似度 > 0.7，也算做精准匹配
        elif title_sim > 0.7 and target_authors and paper_authors and author_sim > 0.7:
            matched = True
        # 条件3: 原有的阈值匹配（作为后备）
        elif title_sim >= title_threshold and (not target_authors or author_sim >= author_threshold):
            matched = True
        
        if matched:
            if combined_sim > best_similarity:
                best_similarity = combined_sim
                best_match = paper
    
    if best_match:
        logger.info(f"找到匹配论文: {best_match.title if hasattr(best_match, 'title') else best_match.get('title', '')} (相似度: {best_similarity:.2f})")
        return True, best_match, best_similarity
    else:
        return False, None, 0.0



