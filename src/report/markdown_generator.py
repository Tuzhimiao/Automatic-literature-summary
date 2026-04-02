"""
Markdown报告生成模块
"""

from typing import List
from datetime import datetime
from loguru import logger

from ..utils.data_structures import Paper, AnalysisResult, ValidationResult


class MarkdownGenerator:
    """Markdown报告生成器"""
    
    def generate(
        self,
        topic: str,
        papers: List[Paper],
        analysis: AnalysisResult,
        validation: ValidationResult,
        output_path: str
    ) -> str:
        """
        生成Markdown报告
        
        Args:
            topic: 研究主题
            papers: 论文列表
            analysis: 分析结果
            validation: 验证结果
            output_path: 输出文件路径
        
        Returns:
            生成的Markdown内容
        """
        logger.info(f"开始生成Markdown报告: {output_path}")
        
        # 构建Markdown内容
        md_content = self._build_markdown(topic, papers, analysis, validation)
        
        # 保存文件
        import os
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"Markdown报告已保存: {output_path}")
        return md_content
    
    def _build_markdown(
        self,
        topic: str,
        papers: List[Paper],
        analysis: AnalysisResult,
        validation: ValidationResult
    ) -> str:
        """构建Markdown内容"""
        
        md = f"""# 研究现状分析报告

## 研究主题
{topic}

## 报告生成信息
- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 分析论文数: {len(papers)}
- 模型置信度: {validation.model_confidence:.2%}

---

## 综述报告

"""
        
        # 如果有新的5个部分结构，优先使用
        if analysis.section1_research_intro:
            if analysis.section1_research_intro:
                md += f"""### 1. 研究介绍

{analysis.section1_research_intro}

"""
            if analysis.section2_research_progress:
                md += f"""### 2. 研究进展

{analysis.section2_research_progress}

"""
            if analysis.section3_research_status:
                md += f"""### 3. 研究现状

{analysis.section3_research_status}

"""
            if analysis.section4_existing_methods:
                md += f"""### 4. 现有方法

{analysis.section4_existing_methods}

"""
            if analysis.section5_future_development:
                md += f"""### 5. 未来发展

{analysis.section5_future_development}

"""
        else:
            # 兼容旧格式
            md += f"""{analysis.summary}

---

## 关键发现

"""
            for i, finding in enumerate(analysis.key_findings, 1):
                md += f"{i}. {finding}\n\n"
            md += "## 研究趋势\n\n"
            for i, trend in enumerate(analysis.research_trends, 1):
                md += f"{i}. {trend}\n\n"
        
        md += "## 模型置信度\n\n"
        md += f"- **模型置信度**: {validation.model_confidence:.2%}\n\n"
        
        # 添加置信度解释（如果有）
        if validation.confidence_reason:
            md += f"### 置信度说明\n\n{validation.confidence_reason}\n\n"
        
        # 添加冲突信息（如果有）
        if validation.conflicts and len(validation.conflicts) > 0:
            md += "### 检测到的冲突\n\n"
            for conflict in validation.conflicts:
                md += f"- ⚠️ {conflict}\n"
            md += "\n"
        
        md += "\n## 参考文献\n\n"
        for i, paper in enumerate(papers, 1):
            md += f"{i}. **{paper.title}**\n"
            md += f"   - 作者: {', '.join(paper.authors[:3])}\n"
            if paper.publication_date:
                md += f"   - 发表日期: {paper.publication_date.strftime('%Y-%m-%d')}\n"
            md += f"   - 来源: {paper.source}\n"
            md += f"   - 链接: {paper.url}\n"
            if paper.citation_count:
                md += f"   - 引用次数: {paper.citation_count}\n"
            md += "\n"
        
        md += "\n---\n\n"
        md += f"*报告由自动化研究现状分析系统生成*\n"
        
        return md


