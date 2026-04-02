"""
关键术语匹配验证模块
"""

from typing import List, Dict, Set
from loguru import logger

from ..utils.data_structures import Paper


class TermValidator:
    """术语验证器"""
    
    def __init__(self):
        """初始化术语验证器"""
        pass
    
    def extract_terms_from_papers(self, papers: List[Paper]) -> Set[str]:
        """
        从论文中提取关键术语（改进版）
        
        Args:
            papers: 论文列表
        
        Returns:
            术语集合
        """
        import re
        from collections import Counter
        
        terms = set()
        
        # 方法1：从标题提取（标题中的词通常更重要）
        for paper in papers:
            # 提取标题中的主要词汇（包括大写开头的词和重要名词）
            title_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', paper.title)
            terms.update([w.lower() for w in title_words if len(w) > 3])
            
            # 提取标题中的常见学术术语（如"learning", "network", "model"等）
            title_lower = paper.title.lower()
            academic_keywords = ['learning', 'network', 'model', 'algorithm', 'method', 
                               'system', 'framework', 'approach', 'technique', 'analysis']
            for keyword in academic_keywords:
                if keyword in title_lower:
                    terms.add(keyword)
        
        # 方法2：从摘要中提取高频词（TF-IDF思想）
        all_abstracts = [p.abstract.lower() for p in papers if p.abstract]
        if all_abstracts:
            # 统计词频
            word_freq = Counter()
            for abstract in all_abstracts:
                # 提取长度>4的词（更可能是专业术语）
                words = re.findall(r'\b[a-z]{4,}\b', abstract)
                word_freq.update(words)
            
            # 选择出现频率>=2的词作为关键术语（至少在多篇论文中出现）
            common_terms = {word for word, freq in word_freq.items() 
                           if freq >= 2 and len(word) > 4}
            terms.update(common_terms)
        
        # 方法3：提取摘要中的首字母大写词（专有名词、技术术语）
        for paper in papers:
            if paper.abstract:
                abstract_words = re.findall(r'\b[A-Z][a-z]+\b', paper.abstract)
                terms.update([w.lower() for w in abstract_words if len(w) > 3])
        
        logger.info(f"提取了 {len(terms)} 个关键术语")
        return terms
    
    def validate_terms_in_summary(self, summary: str, expected_terms: Set[str]) -> Dict[str, bool]:
        """
        验证摘要中是否包含预期术语（改进版，支持词干匹配）
        
        Args:
            summary: 生成的摘要
            expected_terms: 预期应该出现的术语集合
        
        Returns:
            术语到是否出现的映射
        """
        import re
        summary_lower = summary.lower()
        validation_result = {}
        
        # 将摘要分词（用于更精确的匹配）
        summary_words = set(re.findall(r'\b[a-z]+\b', summary_lower))
        
        for term in expected_terms:
            term_lower = term.lower()
            
            # 方法1：精确匹配
            appears = term_lower in summary_lower
            
            # 方法2：如果精确匹配失败，尝试词干匹配（简单版）
            if not appears:
                # 检查术语是否作为完整词出现在摘要中
                term_pattern = r'\b' + re.escape(term_lower) + r'\b'
                appears = bool(re.search(term_pattern, summary_lower))
            
            # 方法3：如果还是失败，检查是否包含术语的主要部分（至少4个字符）
            if not appears and len(term_lower) >= 4:
                # 检查术语的前4个字符是否在摘要中
                term_prefix = term_lower[:4]
                if term_prefix in summary_lower:
                    # 进一步检查：术语的主要部分是否在摘要词汇中
                    for word in summary_words:
                        if term_prefix in word or word in term_lower:
                            appears = True
                            break
            
            validation_result[term] = appears
        
        matched_count = sum(validation_result.values())
        logger.info(f"术语验证: {matched_count}/{len(expected_terms)} 个术语在摘要中出现")
        
        return validation_result
    
    def calculate_term_coverage(self, validation_result: Dict[str, bool]) -> float:
        """
        计算术语覆盖率
        
        Args:
            validation_result: 验证结果
        
        Returns:
            覆盖率（0-1之间）
        """
        if not validation_result:
            return 0.0
        
        matched = sum(validation_result.values())
        total = len(validation_result)
        coverage = matched / total if total > 0 else 0.0
        
        return coverage

