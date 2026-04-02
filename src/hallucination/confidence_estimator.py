"""
模型自估置信度模块
"""

from typing import List, Dict, Optional
from loguru import logger

from ..utils.data_structures import Paper, AnalysisResult


class ConfidenceEstimator:
    """置信度评估器"""
    
    def estimate_confidence(
        self,
        papers: List[Paper],
        consistency_score: float,
        term_coverage: float,
        citation_scores: Dict[str, int],
        llm_confidence: Optional[float] = None,
        has_conflicts: bool = False
    ) -> float:
        """
        综合评估置信度：融合 LLM 自评、文献间一致性、术语覆盖率、引用覆盖度（权重之和为 1）。
        
        Args:
            papers: 论文列表
            consistency_score: 多篇文献间一致性（0–1）
            term_coverage: 综述术语与文献术语的覆盖率（0–1）
            citation_scores: 各篇引用次数（用于推导引用覆盖度）
            llm_confidence: LLM 自评置信度（0–1）
            has_conflicts: 是否存在严重冲突
        """
        import math

        if citation_scores:
            avg_citations = sum(citation_scores.values()) / len(citation_scores)
            if avg_citations > 0:
                citation_coverage = min(math.log(1 + avg_citations) / math.log(51), 1.0)
            else:
                citation_coverage = 0.3
        else:
            citation_coverage = 0.5

        if llm_confidence is None:
            llm_confidence = 0.7
            logger.warning("LLM未提供自评置信度，使用默认值0.7")

        consistency_score = max(0.0, min(1.0, float(consistency_score)))
        term_coverage = max(0.0, min(1.0, float(term_coverage)))

        # 四指标融合（与 Web / CLI 共用同一公式）
        confidence = (
            0.35 * llm_confidence
            + 0.20 * consistency_score
            + 0.25 * term_coverage
            + 0.20 * citation_coverage
        )

        if has_conflicts:
            confidence = confidence * 0.7
            logger.info("检测到严重冲突，置信度应用 0.7 惩罚")

        logger.info(
            f"置信度评估: {confidence:.3f} "
            f"(LLM:{llm_confidence:.2f}, 文献一致性:{consistency_score:.2f}, "
            f"术语覆盖:{term_coverage:.2f}, 引用覆盖:{citation_coverage:.2f}, 冲突:{has_conflicts})"
        )
        
        return confidence
    
    def get_confidence_level(self, confidence: float) -> str:
        """
        获取置信度等级描述
        
        Args:
            confidence: 置信度分数
        
        Returns:
            置信度等级
        """
        if confidence >= 0.8:
            return "高"
        elif confidence >= 0.6:
            return "中"
        elif confidence >= 0.4:
            return "低"
        else:
            return "很低"

