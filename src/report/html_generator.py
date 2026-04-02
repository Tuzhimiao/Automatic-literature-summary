"""
HTML报告生成模块
生成美观的HTML报告，可在浏览器中直接查看
"""

from typing import List, Optional
from datetime import datetime
from loguru import logger
import os
import re

from ..utils.data_structures import Paper, AnalysisResult, ValidationResult


class HTMLGenerator:
    """HTML报告生成器"""
    
    @staticmethod
    def _markdown_to_html(text: str) -> str:
        """
        将Markdown语法转换为HTML
        
        Args:
            text: 包含Markdown语法的文本
        
        Returns:
            转换后的HTML文本
        """
        if not text:
            return ""
        
        # 先转义HTML特殊字符
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        # 处理代码块 ```代码```（先处理，避免内部内容被转换）
        code_blocks = []
        def replace_code_block(match):
            code_blocks.append(match.group(1))
            return f"__CODE_BLOCK_{len(code_blocks)-1}__"
        text = re.sub(r'```([^`]+?)```', replace_code_block, text, flags=re.DOTALL)
        
        # 处理行内代码 `代码`（先处理，避免内部内容被转换）
        inline_codes = []
        def replace_inline_code(match):
            inline_codes.append(match.group(1))
            return f"__INLINE_CODE_{len(inline_codes)-1}__"
        text = re.sub(r'`([^`]+?)`', replace_inline_code, text)
        
        # 处理粗体 **文本** 或 __文本__
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        
        # 处理斜体 *文本*（但不在**内部，且不是列表标记）
        # 使用负向前后查找确保不在**内部，且不是列表开头的*
        text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)
        
        # 处理链接 [文本](URL)
        text = re.sub(r'\[([^\]]+?)\]\(([^\)]+?)\)', r'<a href="\2" target="_blank">\1</a>', text)
        
        # 恢复代码块
        for i, code in enumerate(code_blocks):
            # 代码内容已经转义过了，直接使用
            text = text.replace(f"__CODE_BLOCK_{i}__", f'<pre><code>{code}</code></pre>')
        
        # 恢复行内代码
        for i, code in enumerate(inline_codes):
            text = text.replace(f"__INLINE_CODE_{i}__", f'<code>{code}</code>')
        
        # 处理段落和换行
        # 按双换行符分割段落
        paragraphs = re.split(r'\n\n+', text)
        result_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 检查是否是列表
            lines = para.split('\n')
            is_list = False
            list_type = None
            list_items = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 无序列表（以 - 或 * 开头，后面跟空格，但不是粗体标记）
                list_match = re.match(r'^[-*]\s+(.+)$', line)
                if list_match:
                    if not is_list or list_type != 'ul':
                        if is_list:
                            result_paragraphs.append(f'<{list_type}>{"".join(list_items)}</{list_type}>')
                        list_items = []
                        list_type = 'ul'
                        is_list = True
                    item_content = list_match.group(1)
                    list_items.append(f'<li>{item_content}</li>')
                    continue
                
                # 有序列表
                ordered_match = re.match(r'^\d+\.\s+(.+)$', line)
                if ordered_match:
                    if not is_list or list_type != 'ol':
                        if is_list:
                            result_paragraphs.append(f'<{list_type}>{"".join(list_items)}</{list_type}>')
                        list_items = []
                        list_type = 'ol'
                        is_list = True
                    item_content = ordered_match.group(1)
                    list_items.append(f'<li>{item_content}</li>')
                    continue
                
                # 如果不是列表项，结束列表
                if is_list:
                    result_paragraphs.append(f'<{list_type}>{"".join(list_items)}</{list_type}>')
                    list_items = []
                    is_list = False
                    list_type = None
                
                # 普通段落
                result_paragraphs.append(f'<p>{line}</p>')
            
            # 如果最后还有未结束的列表
            if is_list:
                result_paragraphs.append(f'<{list_type}>{"".join(list_items)}</{list_type}>')
        
        # 将段落用换行符连接
        result = '\n'.join(result_paragraphs)
        
        return result
    
    def generate(
        self,
        topic: str,
        papers: List[Paper],
        analysis: AnalysisResult,
        validation: ValidationResult,
        output_path: str,
        topic_graph_path: Optional[str] = None
    ) -> str:
        """
        生成HTML报告
        
        Args:
            topic: 研究主题
            papers: 论文列表
            analysis: 分析结果
            validation: 验证结果
            output_path: 输出文件路径
            topic_graph_path: 主题图谱HTML文件路径（可选）
        
        Returns:
            生成的HTML内容
        """
        logger.info(f"开始生成HTML报告: {output_path}")
        
        # 构建HTML内容
        html_content = self._build_html(topic, papers, analysis, validation, topic_graph_path)
        
        # 保存文件
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML报告已保存: {output_path}")
        return html_content
    
    def _build_html(
        self,
        topic: str,
        papers: List[Paper],
        analysis: AnalysisResult,
        validation: ValidationResult,
        topic_graph_path: Optional[str] = None
    ) -> str:
        """构建HTML内容"""
        
        # 使用模型置信度
        model_confidence = validation.model_confidence
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>研究现状分析报告 - {topic}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header .meta {{
            opacity: 0.9;
            font-size: 0.9em;
            margin-top: 15px;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .section {{
            margin-bottom: 40px;
        }}
        
        .section h2 {{
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        
        .section h3 {{
            color: #764ba2;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 1.3em;
        }}
        
        .summary-box {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
        }}
        
        .findings-list, .trends-list {{
            list-style: none;
            padding-left: 0;
        }}
        
        .findings-list li, .trends-list li {{
            background: #f8f9fa;
            margin: 10px 0;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #764ba2;
        }}
        
        .findings-list li::before {{
            content: "🔍 ";
            margin-right: 10px;
        }}
        
        .trends-list li::before {{
            content: "📈 ";
            margin-right: 10px;
        }}
        
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .metric-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        
        .metric-card .label {{
            opacity: 0.9;
            font-size: 0.9em;
        }}
        
        .paper-item {{
            background: #f8f9fa;
            padding: 20px;
            margin: 15px 0;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        
        .paper-item h4 {{
            color: #667eea;
            margin-bottom: 10px;
        }}
        
        .paper-item .meta {{
            color: #666;
            font-size: 0.9em;
            margin: 5px 0;
        }}
        
        .paper-item a {{
            color: #667eea;
            text-decoration: none;
        }}
        
        .paper-item a:hover {{
            text-decoration: underline;
        }}
        
        .confidence-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            margin-left: 10px;
        }}
        
        .confidence-high {{
            background: #28a745;
            color: white;
        }}
        
        .confidence-medium {{
            background: #ffc107;
            color: #333;
        }}
        
        .confidence-low {{
            background: #dc3545;
            color: white;
        }}
        
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}
            
            .content {{
                padding: 20px;
            }}
            
            .metrics {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 研究现状分析报告</h1>
            <h2>{topic}</h2>
            <div class="meta">
                生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')} | 
                分析论文数: {len(papers)} 篇
            </div>
        </div>
        
        <div class="content">
            <!-- 关键指标 -->
            <div class="section">
                <h2>📈 关键指标</h2>
                <div class="metrics">
                    <div class="metric-card">
                        <div class="label">模型置信度</div>
                        <div class="value">{model_confidence:.1%}</div>
                    </div>
                    <div class="metric-card">
                        <div class="label">论文数量</div>
                        <div class="value">{len(papers)}</div>
                    </div>
                </div>
            </div>
            
            <!-- 综述报告 -->
            <div class="section">
                <h2>📝 综述报告</h2>
"""
        
        # 如果有新的5个部分结构，优先使用
        if analysis.section1_research_intro:
            if analysis.section1_research_intro:
                html += f"""                <div class="review-section">
                    <h3>1. 研究介绍</h3>
                    <div class="summary-box">
                        {self._markdown_to_html(analysis.section1_research_intro)}
                    </div>
                </div>
"""
            if analysis.section2_research_progress:
                html += f"""                <div class="review-section">
                    <h3>2. 研究进展</h3>
                    <div class="summary-box">
                        {self._markdown_to_html(analysis.section2_research_progress)}
                    </div>
                </div>
"""
            if analysis.section3_research_status:
                html += f"""                <div class="review-section">
                    <h3>3. 研究现状</h3>
                    <div class="summary-box">
                        {self._markdown_to_html(analysis.section3_research_status)}
                    </div>
                </div>
"""
            if analysis.section4_existing_methods:
                html += f"""                <div class="review-section">
                    <h3>4. 现有方法</h3>
                    <div class="summary-box">
                        {self._markdown_to_html(analysis.section4_existing_methods)}
                    </div>
                </div>
"""
            if analysis.section5_future_development:
                html += f"""                <div class="review-section">
                    <h3>5. 未来发展</h3>
                    <div class="summary-box">
                        {self._markdown_to_html(analysis.section5_future_development)}
                    </div>
                </div>
"""
        else:
            # 兼容旧格式
            html += f"""                <div class="summary-box">
                    {self._markdown_to_html(analysis.summary)}
                </div>
            
            <!-- 关键发现 -->
            <div class="section">
                <h2>🔍 关键发现</h2>
                <ul class="findings-list">
"""
            for finding in analysis.key_findings:
                html += f"                    <li>{finding}</li>\n"
            html += """                </ul>
            </div>
            
            <!-- 研究趋势 -->
            <div class="section">
                <h2>📈 研究趋势</h2>
                <ul class="trends-list">
"""
            for trend in analysis.research_trends:
                html += f"                    <li>{trend}</li>\n"
            html += """                </ul>
            </div>
"""
        
        # 确定置信度等级
        confidence_class = "confidence-high" if model_confidence >= 0.7 else "confidence-medium" if model_confidence >= 0.5 else "confidence-low"
        
        html += f"""
            
            <!-- 验证结果详情 -->
            <div class="section">
                <h2>✅ 模型置信度</h2>
                <div class="summary-box">
                    <p><strong>模型置信度:</strong> 
                        <span class="confidence-badge {confidence_class}">{model_confidence:.2%}</span>
                        - 模型对分析结果的自信程度
                    </p>"""
        
        # 添加置信度解释（如果有）
        if validation.confidence_reason:
            html += f"""
                    <div style="margin-top: 15px; padding: 15px; background: #f8f9fa; border-left: 4px solid #667eea; border-radius: 4px;">
                        <strong>📊 置信度说明：</strong>
                        <div style="margin-top: 8px; line-height: 1.8;">{self._markdown_to_html(validation.confidence_reason)}</div>
                    </div>"""
        
        # 添加冲突信息（如果有）
        if validation.conflicts and len(validation.conflicts) > 0:
            html += """
                    <div style="margin-top: 15px; padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px;">
                        <strong>⚠️ 检测到的冲突：</strong>
                        <ul style="margin-top: 8px; padding-left: 20px;">"""
            for conflict in validation.conflicts:
                html += f'<li style="margin: 5px 0;">{conflict}</li>'
            html += """
                        </ul>
                    </div>"""
        
        html += """
                </div>
            </div>
"""
        
        # 添加子话题推荐（如果有）
        if analysis.subtopics and len(analysis.subtopics) > 0:
            html += f"""
            <!-- 子话题推荐 -->
            <div class="section">
                <h2>🔑 子话题推荐</h2>
                <div class="summary-box">
                    <p style="margin-bottom: 15px; color: #666;">
                        基于论文分析和综述内容，系统自动提取了以下出现频率高、具有代表性的关键词作为子话题。这些子话题可以帮助您进一步深入研究该领域的各个方向。
                    </p>
                    <div style="display: flex; flex-wrap: wrap; gap: 10px;">
"""
            for i, subtopic in enumerate(analysis.subtopics, 1):
                html += f"""
                        <span style="
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            padding: 8px 16px;
                            border-radius: 20px;
                            font-size: 0.95em;
                            font-weight: 500;
                            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                        ">{i}. {subtopic}</span>
"""
            html += """
                    </div>
                </div>
            </div>
"""
        
        # 添加主题图谱（如果提供）
        if topic_graph_path and os.path.exists(topic_graph_path):
            # 读取主题图谱HTML内容
            try:
                with open(topic_graph_path, 'r', encoding='utf-8') as f:
                    topic_graph_html = f.read()
                
                # pyvis生成的HTML包含完整的HTML结构，需要提取：
                # 1. head中的style和script
                # 2. body中的内容
                head_content = ""
                body_content = ""
                
                # 提取head部分（包含样式和脚本）
                if '<head>' in topic_graph_html and '</head>' in topic_graph_html:
                    head_start = topic_graph_html.find('<head>') + 6
                    head_end = topic_graph_html.find('</head>')
                    head_section = topic_graph_html[head_start:head_end]
                    # 提取style和script标签
                    import re
                    styles = re.findall(r'<style[^>]*>.*?</style>', head_section, re.DOTALL)
                    scripts = re.findall(r'<script[^>]*>.*?</script>', head_section, re.DOTALL)
                    head_content = '\n'.join(styles + scripts)
                
                # 提取body内容
                if '<body>' in topic_graph_html and '</body>' in topic_graph_html:
                    body_start = topic_graph_html.find('<body>') + 6
                    body_end = topic_graph_html.find('</body>')
                    body_content = topic_graph_html[body_start:body_end].strip()
                else:
                    body_content = topic_graph_html
                
                # 如果成功提取内容，嵌入到报告中
                if body_content:
                    html += f"""
            <!-- 主题图谱 -->
            <div class="section">
                <h2>🗺️ 主题图谱</h2>
                <div class="summary-box" style="padding: 0; overflow: hidden;">
                    <div style="background: #f8f9fa; padding: 15px; border-bottom: 2px solid #667eea;">
                        <p style="margin: 0; color: #666; font-size: 0.9em;">
                            📊 交互式主题图谱：节点表示论文，边的粗细表示语义相似度。相同颜色的节点属于同一主题簇。
                            可以拖拽节点、缩放查看、悬停查看详细信息。
                        </p>
                    </div>
                    {head_content}
                    <div id="topic-graph-container" style="width: 100%; height: 800px; border: none;">
                        {body_content}
                    </div>
                </div>
            </div>
"""
                else:
                    # 如果提取失败，使用iframe作为备选方案
                    graph_filename = os.path.basename(topic_graph_path)
                    html += f"""
            <!-- 主题图谱 -->
            <div class="section">
                <h2>🗺️ 主题图谱</h2>
                <div class="summary-box" style="padding: 0; overflow: hidden;">
                    <div style="background: #f8f9fa; padding: 15px; border-bottom: 2px solid #667eea;">
                        <p style="margin: 0; color: #666; font-size: 0.9em;">
                            📊 交互式主题图谱：节点表示论文，边的粗细表示语义相似度。相同颜色的节点属于同一主题簇。
                            可以拖拽节点、缩放查看、悬停查看详细信息。
                        </p>
                    </div>
                    <iframe src="{graph_filename}" style="width: 100%; height: 800px; border: none;"></iframe>
                </div>
            </div>
"""
            except Exception as e:
                logger.warning(f"无法嵌入主题图谱: {str(e)}")
                # 使用iframe作为最后的备选方案
                try:
                    graph_filename = os.path.basename(topic_graph_path)
                    html += f"""
            <!-- 主题图谱 -->
            <div class="section">
                <h2>🗺️ 主题图谱</h2>
                <div class="summary-box" style="padding: 0; overflow: hidden;">
                    <div style="background: #f8f9fa; padding: 15px; border-bottom: 2px solid #667eea;">
                        <p style="margin: 0; color: #666; font-size: 0.9em;">
                            📊 交互式主题图谱：节点表示论文，边的粗细表示语义相似度。相同颜色的节点属于同一主题簇。
                            可以拖拽节点、缩放查看、悬停查看详细信息。
                        </p>
                    </div>
                    <iframe src="{graph_filename}" style="width: 100%; height: 800px; border: none;"></iframe>
                </div>
            </div>
"""
                except:
                    pass
        
        html += """
            
            <!-- 参考文献 -->
            <div class="section">
                <h2>📚 参考文献</h2>
"""
        
        for i, paper in enumerate(papers, 1):
            authors_str = ', '.join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += f" 等 {len(paper.authors)} 人"
            
            date_str = paper.publication_date.strftime('%Y-%m-%d') if paper.publication_date else "未知"
            citation_str = f" | 引用: {paper.citation_count} 次" if paper.citation_count else ""
            
            html += f"""                <div class="paper-item">
                    <h4>{i}. {paper.title}</h4>
                    <div class="meta">
                        <strong>作者:</strong> {authors_str}<br>
                        <strong>发表日期:</strong> {date_str}{citation_str}<br>
                        <strong>来源:</strong> {paper.source.upper()}<br>
                        <strong>链接:</strong> <a href="{paper.url}" target="_blank">{paper.url}</a>
                    </div>
                </div>
"""
        
        html += """            </div>
        </div>
        
        <div class="footer">
            <p>报告由自动化研究现状收集与置信度评估系统生成</p>
            <p>本报告仅供参考，请结合原始论文进行深入分析</p>
        </div>
    </div>
</body>
</html>"""
        
        return html


