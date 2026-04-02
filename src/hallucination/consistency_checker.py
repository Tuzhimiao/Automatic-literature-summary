"""
多文献一致性评分模块
"""

from typing import List
import numpy as np
from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    TRANSFORMERS_AVAILABLE = True
except (ImportError, OSError, RuntimeError) as e:
    # 处理ImportError（未安装）、OSError（模型加载失败）、RuntimeError（PyTorch版本不匹配）
    TRANSFORMERS_AVAILABLE = False
    if isinstance(e, ImportError):
        logger.info("sentence-transformers未安装，将使用简单文本相似度方法")
    else:
        logger.info(f"sentence-transformers不可用（{type(e).__name__}），将使用简单文本相似度方法")

from ..utils.data_structures import Paper


class ConsistencyChecker:
    """一致性检查器"""
    
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        """
        初始化一致性检查器
        
        Args:
            model_name: 用于计算文本相似度的模型名称
        """
        self.model = None
        if TRANSFORMERS_AVAILABLE:
            try:
                # 尝试加载模型，如果失败（如PyTorch版本不匹配）则使用简单方法
                self.model = SentenceTransformer(model_name)
                logger.info(f"已加载相似度模型: {model_name}")
            except (OSError, RuntimeError, ImportError) as e:
                # 静默处理，不显示警告，因为已经有备用方案
                logger.debug(f"无法加载sentence-transformers模型: {str(e)}，将使用简单文本相似度方法")
                self.model = None
                # 注意：不修改全局变量，只在当前实例中禁用
    
    def calculate_consistency(self, papers: List[Paper]) -> float:
        """
        计算多篇论文的一致性评分
        
        Args:
            papers: 论文列表
        
        Returns:
            一致性评分（0-1之间）
        """
        if len(papers) < 2:
            logger.warning("论文数量少于2篇，无法计算一致性")
            return 0.0
        
        try:
            # 提取摘要
            abstracts = [paper.abstract for paper in papers if paper.abstract]
            
            if not abstracts:
                return 0.0
            
            if self.model and TRANSFORMERS_AVAILABLE:
                # 使用sentence transformers计算相似度
                embeddings = self.model.encode(abstracts)
                similarity_matrix = cosine_similarity(embeddings)
                
                # 计算平均相似度（排除对角线）
                mask = ~np.eye(len(similarity_matrix), dtype=bool)
                avg_similarity = similarity_matrix[mask].mean()
                
                logger.info(f"一致性评分: {avg_similarity:.3f}")
                return float(avg_similarity)
            else:
                # 简单的基于关键词的相似度
                return self._simple_similarity(abstracts)
                
        except Exception as e:
            logger.error(f"计算一致性时出错: {str(e)}")
            return 0.0
    
    def _simple_similarity(self, texts: List[str]) -> float:
        """改进的文本相似度计算（基于共同词汇和TF-IDF思想）"""
        if len(texts) < 2:
            return 0.0
        
        import re
        from collections import Counter
        
        # 提取关键词（改进方法）
        word_sets = []
        all_words = Counter()
        
        for text in texts:
            # 提取长度>3的词
            words = re.findall(r'\b[a-z]{4,}\b', text.lower())
            # 过滤常见停用词
            stopwords = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 
                        'will', 'would', 'could', 'should', 'their', 'there', 'these'}
            words = {w for w in words if w not in stopwords}
            word_sets.append(words)
            all_words.update(words)
        
        # 计算TF-IDF权重（出现频率适中的词更重要）
        word_weights = {}
        total_docs = len(texts)
        for word, freq in all_words.items():
            # 出现在多篇文档中的词权重更高
            doc_freq = sum(1 for ws in word_sets if word in ws)
            if doc_freq > 0:
                # 简单的TF-IDF：词频 × log(文档数/包含该词的文档数)
                import math
                word_weights[word] = math.log(total_docs / doc_freq) if doc_freq > 0 else 0
        
        # 计算加权Jaccard相似度
        similarities = []
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                set1, set2 = word_sets[i], word_sets[j]
                
                # 计算加权交集和并集
                intersection_weight = sum(word_weights.get(w, 1) for w in set1 & set2)
                union_weight = sum(word_weights.get(w, 1) for w in set1 | set2)
                
                if union_weight > 0:
                    similarity = intersection_weight / union_weight
                    similarities.append(similarity)
        
        avg_similarity = np.mean(similarities) if similarities else 0.0
        
        # 如果相似度很低，但有很多共同词汇，给予补偿
        if avg_similarity < 0.2:
            # 检查是否有足够的共同词汇
            common_words = set.intersection(*word_sets) if word_sets else set()
            if len(common_words) >= 5:  # 至少有5个共同词
                avg_similarity = min(avg_similarity + 0.1, 0.5)  # 最多补偿到0.5
        
        return float(avg_similarity)

