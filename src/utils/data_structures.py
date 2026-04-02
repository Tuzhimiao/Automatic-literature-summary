"""
数据结构定义模块
定义系统中使用的数据结构和数据类
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Paper:
    """论文数据类"""
    title: str
    abstract: str
    authors: List[str]
    publication_date: Optional[datetime]
    source: str  # 如 "arxiv", "ieee_xplore", "pubmed", "uploaded"
    url: str
    paper_id: str  # arXiv ID 或 Scholar ID
    citation_count: Optional[int] = None
    
    def __str__(self):
        return f"{self.title} ({self.source})"


@dataclass
class PaperDetail:
    """论文详细信息数据类（包含10个问题的答案或5个综述部分）"""
    paper_id: str  # 对应的论文ID
    paper_type: str = "method"  # 论文类型："method"（方法论）或"review"（综述）
    # 基本信息
    publication_venue: Optional[str] = None  # 发表地点
    publication_time: Optional[str] = None  # 发表时间
    first_author: Optional[str] = None  # 第一作者
    corresponding_author: Optional[str] = None  # 通讯作者
    main_institution: Optional[str] = None  # 主要单位
    # 方法论论文的8个问题的答案
    q1_background: Optional[str] = None  # 研究方向背景和要解决的问题
    q2_implementation: Optional[str] = None  # 实现了什么
    q3_result: Optional[str] = None  # 结果：得到了什么实验结果和结论
    q4_modules: Optional[str] = None  # 方法模块及作用
    q5_related_work: Optional[str] = None  # 前人工作和存在的问题
    q6_evaluation: Optional[str] = None  # 评估：数据集、测试方法和评价指标
    q7_comparison: Optional[str] = None  # 对比方法
    q8_summary: Optional[str] = None  # 方法总结和创新点
    # 综述论文的5个部分
    section1_research_intro: Optional[str] = None  # 1. 研究介绍
    section2_research_progress: Optional[str] = None  # 2. 研究进展
    section3_research_status: Optional[str] = None  # 3. 研究现状
    section4_existing_methods: Optional[str] = None  # 4. 现有方法
    section5_future_development: Optional[str] = None  # 5. 未来发展
    # 推荐阅读程度（1-5星，5星为最推荐）
    recommendation_score: Optional[int] = None  # 推荐阅读程度：1-5星
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        result = {
            "paper_id": self.paper_id,
            "paper_type": self.paper_type,
            "publication_venue": self.publication_venue,
            "publication_time": self.publication_time,
            "first_author": self.first_author,
            "corresponding_author": self.corresponding_author,
            "main_institution": self.main_institution,
            "recommendation_score": self.recommendation_score,  # 推荐阅读程度
        }
        
        # 根据论文类型添加相应字段
        if self.paper_type == "review":
            result.update({
                "section1_research_intro": self.section1_research_intro,
                "section2_research_progress": self.section2_research_progress,
                "section3_research_status": self.section3_research_status,
                "section4_existing_methods": self.section4_existing_methods,
                "section5_future_development": self.section5_future_development,
            })
        else:
            result.update({
                "q1_background": self.q1_background,
                "q2_implementation": self.q2_implementation,
                "q3_result": self.q3_result,
                "q4_modules": self.q4_modules,
                "q5_related_work": self.q5_related_work,
                "q6_evaluation": self.q6_evaluation,
                "q7_comparison": self.q7_comparison,
                "q8_summary": self.q8_summary
            })
        
        return result


@dataclass
class AnalysisResult:
    """分析结果数据类"""
    summary: str  # 综合总结（兼容旧格式）
    key_findings: List[str]  # 关键发现（兼容旧格式）
    research_trends: List[str]  # 研究趋势（兼容旧格式）
    confidence_score: float  # 置信度评分（0-1）
    consistency_score: float  # 一致性评分（0-1）
    papers_analyzed: int  # 分析的论文数量
    paper_details: Optional[List[Dict]] = None  # 每篇论文的详细信息
    # LLM自评置信度相关字段
    llm_confidence: Optional[float] = None  # LLM自评置信度（0-1）
    confidence_reason: Optional[str] = None  # 置信度理由
    conflicts: Optional[List[str]] = None  # 冲突列表
    # 新的5个部分结构
    section1_research_intro: Optional[str] = None  # 1. 研究介绍
    section2_research_progress: Optional[str] = None  # 2. 研究进展
    section3_research_status: Optional[str] = None  # 3. 研究现状
    section4_existing_methods: Optional[str] = None  # 4. 现有方法
    section5_future_development: Optional[str] = None  # 5. 未来发展
    # 子话题推荐
    subtopics: Optional[List[str]] = None  # 子话题关键词列表（至少5个）
    # 综述关键词（用于词云图）
    keywords: Optional[List[str]] = None  # 关键词列表（10-20个）
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "summary": self.summary,
            "key_findings": self.key_findings,
            "research_trends": self.research_trends,
            "confidence_score": self.confidence_score,
            "consistency_score": self.consistency_score,
            "papers_analyzed": self.papers_analyzed,
            "paper_details": self.paper_details or [],
            "llm_confidence": self.llm_confidence,
            "confidence_reason": self.confidence_reason,
            "conflicts": self.conflicts or [],
            "section1_research_intro": self.section1_research_intro,
            "section2_research_progress": self.section2_research_progress,
            "section3_research_status": self.section3_research_status,
            "section4_existing_methods": self.section4_existing_methods,
            "section5_future_development": self.section5_future_development,
            "subtopics": self.subtopics or [],
            "keywords": self.keywords or []
        }


@dataclass
class ValidationResult:
    """置信度评估结果"""
    consistency_score: float  # 一致性评分
    citation_frequency: Dict[str, int]  # 引用频次统计
    term_validation: Dict[str, bool]  # 术语验证结果
    model_confidence: float  # 模型自估置信度
    overall_confidence: float  # 总体置信度
    diagnostic: Optional[Dict] = None  # 诊断信息（可选）
    confidence_reason: Optional[str] = None  # 置信度理由
    conflicts: Optional[List[str]] = None  # 冲突列表
    term_coverage: Optional[float] = None  # 术语覆盖率
    
    def is_valid(self, threshold: float = 0.6) -> bool:
        """判断验证结果是否通过阈值"""
        return self.overall_confidence >= threshold

