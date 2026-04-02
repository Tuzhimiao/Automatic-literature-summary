"""
PDF报告生成模块
"""

from typing import List
from datetime import datetime
from loguru import logger

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os
    import platform
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab未安装，PDF生成功能不可用")

from ..utils.data_structures import Paper, AnalysisResult, ValidationResult


class PDFGenerator:
    """PDF报告生成器"""
    
    def __init__(self):
        """初始化PDF生成器"""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab未安装，请运行: pip install reportlab")
        
        # 注册中文字体
        self._register_chinese_fonts()
    
    def _register_chinese_fonts(self):
        """注册中文字体"""
        try:
            system = platform.system()
            chinese_font_path = None
            font_name = "ChineseFont"
            
            # 根据操作系统查找中文字体
            if system == "Windows":
                # Windows系统字体路径
                font_paths = [
                    r"C:\Windows\Fonts\simsun.ttc",  # 宋体
                    r"C:\Windows\Fonts\simhei.ttf",  # 黑体
                    r"C:\Windows\Fonts\msyh.ttc",    # 微软雅黑
                    r"C:\Windows\Fonts\simkai.ttf",  # 楷体
                ]
                for path in font_paths:
                    if os.path.exists(path):
                        chinese_font_path = path
                        break
            elif system == "Darwin":  # macOS
                font_paths = [
                    "/System/Library/Fonts/PingFang.ttc",
                    "/System/Library/Fonts/STHeiti Light.ttc",
                    "/Library/Fonts/Arial Unicode.ttf",
                ]
                for path in font_paths:
                    if os.path.exists(path):
                        chinese_font_path = path
                        break
            elif system == "Linux":
                font_paths = [
                    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                    "/usr/share/fonts/truetype/arphic/uming.ttc",
                ]
                for path in font_paths:
                    if os.path.exists(path):
                        chinese_font_path = path
                        break
            
            # 注册字体
            if chinese_font_path:
                try:
                    # 对于.ttc文件，需要指定字体索引（通常是0）
                    if chinese_font_path.endswith('.ttc'):
                        pdfmetrics.registerFont(TTFont(font_name, chinese_font_path, subfontIndex=0))
                    else:
                        pdfmetrics.registerFont(TTFont(font_name, chinese_font_path))
                    logger.info(f"成功注册中文字体: {chinese_font_path}")
                    self.chinese_font_name = font_name
                except Exception as e:
                    logger.warning(f"注册中文字体失败: {str(e)}，将使用默认字体")
                    self.chinese_font_name = "Helvetica"
            else:
                logger.warning("未找到中文字体文件，将使用默认字体（可能无法正确显示中文）")
                self.chinese_font_name = "Helvetica"
                
        except Exception as e:
            logger.warning(f"注册中文字体时出错: {str(e)}，将使用默认字体")
            self.chinese_font_name = "Helvetica"
    
    def generate(
        self,
        topic: str,
        papers: List[Paper],
        analysis: AnalysisResult,
        validation: ValidationResult,
        output_path: str
    ) -> None:
        """
        生成PDF报告
        
        Args:
            topic: 研究主题
            papers: 论文列表
            analysis: 分析结果
            validation: 验证结果
            output_path: 输出文件路径
        """
        logger.info(f"开始生成PDF报告: {output_path}")
        
        # 创建PDF文档
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        story = []
        
        # 获取样式
        styles = getSampleStyleSheet()
        
        # 使用中文字体
        chinese_font = getattr(self, 'chinese_font_name', 'Helvetica')
        
        # 创建支持中文的样式
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=chinese_font,
            fontSize=24,
            textColor='#1a1a1a',
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # 修改Normal样式以支持中文
        normal_style = ParagraphStyle(
            'ChineseNormal',
            parent=styles['Normal'],
            fontName=chinese_font,
            fontSize=12,
            leading=18
        )
        
        heading2_style = ParagraphStyle(
            'ChineseHeading2',
            parent=styles['Heading2'],
            fontName=chinese_font,
            fontSize=16,
            spaceAfter=12
        )
        
        # 添加标题
        story.append(Paragraph("研究现状分析报告", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # 添加研究主题和元信息
        story.append(Paragraph(f"<b>研究主题:</b> {self._escape_html(topic)}", normal_style))
        story.append(Paragraph(f"生成时间: {self._get_current_time()}", normal_style))
        story.append(Paragraph(f"分析论文数: {len(papers)} 篇", normal_style))
        story.append(Spacer(1, 0.2*inch))
        
        # 如果有新的5个部分结构，优先使用
        if analysis.section1_research_intro:
            # 使用新的5部分结构
            story.append(Paragraph("<b>1. 研究介绍</b>", heading2_style))
            story.append(Paragraph(self._escape_html(analysis.section1_research_intro).replace('\n', '<br/>'), normal_style))
            story.append(Spacer(1, 0.15*inch))
            
            if analysis.section2_research_progress:
                story.append(Paragraph("<b>2. 研究进展</b>", heading2_style))
                story.append(Paragraph(self._escape_html(analysis.section2_research_progress).replace('\n', '<br/>'), normal_style))
                story.append(Spacer(1, 0.15*inch))
            
            if analysis.section3_research_status:
                story.append(Paragraph("<b>3. 研究现状</b>", heading2_style))
                story.append(Paragraph(self._escape_html(analysis.section3_research_status).replace('\n', '<br/>'), normal_style))
                story.append(Spacer(1, 0.15*inch))
            
            if analysis.section4_existing_methods:
                story.append(Paragraph("<b>4. 现有方法</b>", heading2_style))
                story.append(Paragraph(self._escape_html(analysis.section4_existing_methods).replace('\n', '<br/>'), normal_style))
                story.append(Spacer(1, 0.15*inch))
            
            if analysis.section5_future_development:
                story.append(Paragraph("<b>5. 未来发展</b>", heading2_style))
                story.append(Paragraph(self._escape_html(analysis.section5_future_development).replace('\n', '<br/>'), normal_style))
                story.append(Spacer(1, 0.2*inch))
        else:
            # 使用旧格式（兼容）
            story.append(Paragraph("<b>执行摘要</b>", heading2_style))
            if analysis.summary:
                story.append(Paragraph(self._escape_html(analysis.summary).replace('\n', '<br/>'), normal_style))
            story.append(Spacer(1, 0.2*inch))
            
            # 添加关键发现
            if analysis.key_findings:
                story.append(Paragraph("<b>关键发现</b>", heading2_style))
                for finding in analysis.key_findings:
                    story.append(Paragraph(f"• {self._escape_html(finding)}", normal_style))
                story.append(Spacer(1, 0.2*inch))
            
            # 添加研究趋势
            if analysis.research_trends:
                story.append(Paragraph("<b>研究趋势</b>", heading2_style))
                for trend in analysis.research_trends:
                    story.append(Paragraph(f"• {self._escape_html(trend)}", normal_style))
                story.append(Spacer(1, 0.2*inch))
        
        # 添加验证结果
        story.append(Paragraph("<b>验证结果</b>", heading2_style))
        story.append(Paragraph(f"总体置信度: {validation.model_confidence:.2%}", normal_style))
        story.append(Paragraph(f"一致性评分: {validation.consistency_score:.2%}", normal_style))
        if hasattr(validation, 'term_coverage') and validation.term_coverage:
            story.append(Paragraph(f"术语覆盖率: {validation.term_coverage:.2%}", normal_style))
        
        # 添加置信度解释（如果有）
        if validation.confidence_reason:
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph("<b>置信度说明：</b>", normal_style))
            story.append(Paragraph(self._escape_html(validation.confidence_reason).replace('\n', '<br/>'), normal_style))
        
        # 添加冲突信息（如果有）
        if validation.conflicts and len(validation.conflicts) > 0:
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph("<b>检测到的冲突：</b>", normal_style))
            for conflict in validation.conflicts:
                story.append(Paragraph(f"• {self._escape_html(conflict)}", normal_style))
        
        story.append(Spacer(1, 0.2*inch))
    
        # 添加子话题推荐（如果有）
        if analysis.subtopics and len(analysis.subtopics) > 0:
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph("<b>子话题推荐</b>", heading2_style))
            subtopics_text = "、".join([self._escape_html(st) for st in analysis.subtopics])
            story.append(Paragraph(f"基于论文分析和综述内容，系统自动提取了以下出现频率高、具有代表性的关键词作为子话题：{subtopics_text}", normal_style))
        
        # 添加参考文献
        story.append(PageBreak())
        story.append(Paragraph("<b>参考文献</b>", heading2_style))
        for i, paper in enumerate(papers, 1):
            authors_str = ', '.join(paper.authors[:3]) if paper.authors else "未知"
            if len(paper.authors) > 3:
                authors_str += f" 等 {len(paper.authors)} 人"
            
            date_str = paper.publication_date.strftime('%Y-%m-%d') if paper.publication_date else "未知"
            citation_str = f" | 引用: {paper.citation_count} 次" if paper.citation_count else ""
            
            ref_text = f"{i}. {self._escape_html(paper.title)}<br/>"
            ref_text += f"作者: {self._escape_html(authors_str)}<br/>"
            ref_text += f"发表日期: {date_str}{citation_str}<br/>"
            ref_text += f"来源: {paper.source.upper()}<br/>"
            if paper.url:
                ref_text += f"链接: {self._escape_html(paper.url)}"
            story.append(Paragraph(ref_text, normal_style))
            story.append(Spacer(1, 0.1*inch))
        
        # 生成PDF
        doc.build(story)
        logger.info(f"PDF报告已保存: {output_path}")
    
    def _escape_html(self, text: str) -> str:
        """
        转义HTML特殊字符，但保留中文字符
        
        Args:
            text: 要转义的文本
        
        Returns:
            转义后的文本
        """
        if not text:
            return ""
        # 转义HTML特殊字符
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')
        return text
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        return datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')


