"""
可视化模块（时间轴、主题结构图谱）
"""

import zipfile
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from loguru import logger
import re
from collections import Counter, defaultdict

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import networkx as nx
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib未安装，可视化功能不可用")

try:
    from pyvis.network import Network
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False
    logger.warning("pyvis未安装，交互式图谱功能不可用")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn未安装，语义相似度计算将使用简化方法")

try:
    import nltk

    def _ensure_nltk_data():
        """确保 NLTK 数据可用，损坏时强制重新下载"""
        for name, package in [('tokenizers/punkt', 'punkt'), ('corpora/stopwords', 'stopwords')]:
            try:
                nltk.data.find(name)
            except (LookupError, zipfile.BadZipFile, OSError):
                try:
                    nltk.download(package, quiet=True, force=True)
                except Exception:
                    pass

    _ensure_nltk_data()
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    # 验证 punkt 是否可用（触发加载）
    word_tokenize("test")
    NLTK_AVAILABLE = True
except Exception as e:
    NLTK_AVAILABLE = False
    logger.warning(f"nltk 不可用（{type(e).__name__}），关键词提取将使用简化方法")

try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    WORDCLOUD_AVAILABLE = False
    logger.warning("wordcloud未安装，词云图功能不可用。安装: pip install wordcloud")

from ..utils.data_structures import Paper


class Visualizer:
    """可视化器"""
    
    def __init__(self):
        """初始化可视化器"""
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib未安装，部分可视化功能不可用")
        
        # 初始化停用词
        self.stop_words = set()
        if NLTK_AVAILABLE:
            try:
                self.stop_words = set(stopwords.words('english'))
            except:
                self.stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'}
        else:
            self.stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'}
    
    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        从文本中提取关键词
        
        Args:
            text: 输入文本
            max_keywords: 最大关键词数量
            
        Returns:
            关键词列表
        """
        if not text:
            return []
        
        # 转换为小写并移除特殊字符
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 分词
        if NLTK_AVAILABLE:
            try:
                words = word_tokenize(text)
            except:
                words = text.split()
        else:
            words = text.split()
        
        # 过滤停用词和短词
        keywords = [w for w in words if len(w) > 3 and w not in self.stop_words]
        
        # 统计词频
        word_freq = Counter(keywords)
        
        # 返回最常见的词
        return [word for word, _ in word_freq.most_common(max_keywords)]
    
    def _calculate_semantic_similarity(self, papers: List[Paper]) -> Dict[Tuple[str, str], float]:
        """
        计算论文之间的语义相似度
        
        Args:
            papers: 论文列表
            
        Returns:
            论文对到相似度的映射
        """
        similarity_dict = {}
        
        if SKLEARN_AVAILABLE and len(papers) > 1:
            try:
                # 使用TF-IDF计算相似度
                texts = []
                for paper in papers:
                    # 组合标题和摘要
                    text = f"{paper.title} {paper.abstract}"
                    texts.append(text)
                
                # 计算TF-IDF向量
                vectorizer = TfidfVectorizer(max_features=100, stop_words='english', ngram_range=(1, 2))
                tfidf_matrix = vectorizer.fit_transform(texts)
                
                # 计算余弦相似度
                similarity_matrix = cosine_similarity(tfidf_matrix)
                
                # 构建相似度字典
                for i, paper1 in enumerate(papers):
                    for j, paper2 in enumerate(papers[i+1:], start=i+1):
                        similarity = similarity_matrix[i][j]
                        if similarity > 0.1:  # 只保留相似度大于0.1的边
                            similarity_dict[(paper1.paper_id, paper2.paper_id)] = float(similarity)
                
            except Exception as e:
                logger.warning(f"TF-IDF相似度计算失败，使用简化方法: {str(e)}")
                # 降级到基于关键词重叠的相似度
                return self._calculate_keyword_similarity(papers)
        else:
            # 使用基于关键词重叠的相似度
            return self._calculate_keyword_similarity(papers)
        
        return similarity_dict
    
    def _calculate_keyword_similarity(self, papers: List[Paper]) -> Dict[Tuple[str, str], float]:
        """
        基于关键词重叠计算相似度（简化方法）
        
        Args:
            papers: 论文列表
            
        Returns:
            论文对到相似度的映射
        """
        similarity_dict = {}
        
        # 为每篇论文提取关键词
        paper_keywords = {}
        for paper in papers:
            text = f"{paper.title} {paper.abstract}"
            keywords = self._extract_keywords(text, max_keywords=15)
            paper_keywords[paper.paper_id] = set(keywords)
        
        # 计算关键词重叠度
        for i, paper1 in enumerate(papers):
            keywords1 = paper_keywords[paper1.paper_id]
            for paper2 in papers[i+1:]:
                keywords2 = paper_keywords[paper2.paper_id]
                
                # Jaccard相似度
                intersection = len(keywords1 & keywords2)
                union = len(keywords1 | keywords2)
                
                if union > 0:
                    similarity = intersection / union
                    if similarity > 0.1:  # 只保留相似度大于0.1的边
                        similarity_dict[(paper1.paper_id, paper2.paper_id)] = similarity
        
        return similarity_dict
    
    def _extract_topics_from_keywords(self, papers: List[Paper], num_topics: int = 5) -> Dict[str, List[str]]:
        """
        从关键词中提取主题簇（简化版主题建模）
        
        Args:
            papers: 论文列表
            num_topics: 主题数量
            
        Returns:
            主题到论文ID列表的映射
        """
        # 收集所有关键词及其出现频率
        keyword_papers = defaultdict(list)
        
        for paper in papers:
            text = f"{paper.title} {paper.abstract}"
            keywords = self._extract_keywords(text, max_keywords=10)
            for keyword in keywords:
                keyword_papers[keyword].append(paper.paper_id)
        
        # 按出现频率排序，选择最常见的主题词
        sorted_keywords = sorted(keyword_papers.items(), key=lambda x: len(x[1]), reverse=True)
        
        # 构建主题（每个主题是一个高频关键词）
        topics = {}
        used_papers = set()
        
        for keyword, paper_ids in sorted_keywords[:num_topics * 2]:  # 取更多候选
            # 过滤已经分配过的论文
            new_paper_ids = [pid for pid in paper_ids if pid not in used_papers]
            
            if len(new_paper_ids) >= 2:  # 至少2篇论文才形成一个主题
                topic_name = keyword
                topics[topic_name] = new_paper_ids
                used_papers.update(new_paper_ids)
                
                if len(topics) >= num_topics:
                    break
        
        # 将未分配的论文分配到最相似的主题
        all_assigned = set()
        for paper_ids in topics.values():
            all_assigned.update(paper_ids)
        
        for paper in papers:
            if paper.paper_id not in all_assigned:
                # 找到最相似的主题（基于关键词重叠）
                best_topic = None
                best_overlap = 0
                
                paper_text = f"{paper.title} {paper.abstract}"
                paper_keywords = set(self._extract_keywords(paper_text, max_keywords=10))
                
                for topic_name, topic_paper_ids in topics.items():
                    # 计算与主题关键词的重叠
                    topic_keywords = set([topic_name])  # 简化：主题就是关键词本身
                    overlap = len(paper_keywords & topic_keywords)
                    
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_topic = topic_name
                
                if best_topic:
                    topics[best_topic].append(paper.paper_id)
                else:
                    # 如果没有匹配的主题，创建一个新主题
                    if len(topics) < num_topics * 2:
                        topics[f"其他-{paper.paper_id[:8]}"] = [paper.paper_id]
        
        return topics
    
    def generate_timeline(self, papers: List[Paper], output_path: str) -> None:
        """
        生成研究时间轴
        
        Args:
            papers: 论文列表
            output_path: 输出文件路径
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("matplotlib未安装，无法生成时间轴")
            return
        
        try:
            # 过滤有日期的论文
            dated_papers = [p for p in papers if p.publication_date]
            if not dated_papers:
                logger.warning("没有带日期的论文，无法生成时间轴")
                return
            
            # 按日期排序
            dated_papers.sort(key=lambda x: x.publication_date)
            
            # 创建图表
            fig, ax = plt.subplots(figsize=(12, 6))
            
            dates = [p.publication_date for p in dated_papers]
            y_pos = range(len(dated_papers))
            
            # 绘制时间轴
            ax.scatter(dates, y_pos, s=100, alpha=0.6)
            
            # 添加论文标题（简化显示）
            for i, paper in enumerate(dated_papers):
                short_title = paper.title[:50] + "..." if len(paper.title) > 50 else paper.title
                ax.annotate(short_title, (paper.publication_date, i), 
                           xytext=(5, 0), textcoords='offset points', fontsize=8)
            
            # 移除标题和坐标轴标签
            ax.set_xlabel('')
            ax.set_ylabel('')
            ax.set_title('')
            ax.grid(True, alpha=0.3)
            
            # 格式化日期
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.xticks(rotation=45)
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"时间轴已保存: {output_path}")
            
        except Exception as e:
            logger.error(f"生成时间轴失败: {str(e)}")
    
    def generate_topic_graph(self, papers: List[Paper], output_path: str) -> None:
        """
        生成主题结构图谱（静态版本，使用matplotlib）
        
        Args:
            papers: 论文列表
            output_path: 输出文件路径
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.error("matplotlib未安装，无法生成主题图谱")
            return
        
        try:
            import networkx as nx
            
            # 创建图
            G = nx.Graph()
            
            # 添加节点（论文）
            for paper in papers:
                G.add_node(paper.paper_id, title=paper.title[:30])
            
            # 基于相似度添加边（简化：基于共同作者或关键词）
            for i, paper1 in enumerate(papers):
                for paper2 in papers[i+1:]:
                    # 检查是否有共同作者
                    common_authors = set(paper1.authors) & set(paper2.authors)
                    if common_authors:
                        G.add_edge(paper1.paper_id, paper2.paper_id, weight=len(common_authors))
            
            # 绘制图
            plt.figure(figsize=(12, 8))
            pos = nx.spring_layout(G, k=1, iterations=50)
            
            nx.draw_networkx_nodes(G, pos, node_color='lightblue', node_size=500, alpha=0.9)
            nx.draw_networkx_edges(G, pos, alpha=0.5, width=1)
            nx.draw_networkx_labels(G, pos, font_size=8)
            
            plt.title('研究主题结构图谱')
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"主题图谱已保存: {output_path}")
            
        except Exception as e:
            logger.error(f"生成主题图谱失败: {str(e)}")
    
    def generate_interactive_topic_graph(
        self, 
        papers: List[Paper], 
        output_path: str,
        use_topics: bool = True,
        similarity_threshold: float = 0.15
    ) -> Optional[str]:
        """
        生成交互式主题图谱（使用pyvis）
        
        Args:
            papers: 论文列表
            output_path: 输出HTML文件路径
            use_topics: 是否使用主题聚类
            similarity_threshold: 相似度阈值，低于此值的边将被过滤
            
        Returns:
            生成的HTML文件路径，如果失败返回None
        """
        if not PYVIS_AVAILABLE:
            logger.error("pyvis未安装，无法生成交互式主题图谱")
            return None
        
        if len(papers) < 2:
            logger.warning("论文数量太少，无法生成主题图谱")
            return None
        
        try:
            # 创建NetworkX图
            G = nx.Graph()
            
            # 添加论文节点
            paper_dict = {p.paper_id: p for p in papers}
            for paper in papers:
                G.add_node(paper.paper_id)
            
            # 计算语义相似度
            logger.info("计算论文语义相似度...")
            similarity_dict = self._calculate_semantic_similarity(papers)
            
            # 添加边（基于相似度）
            for (paper_id1, paper_id2), similarity in similarity_dict.items():
                if similarity >= similarity_threshold:
                    G.add_edge(paper_id1, paper_id2, weight=similarity)
            
            # 如果没有足够的边，使用共同作者作为补充
            if G.number_of_edges() < len(papers) * 0.1:  # 如果边太少
                logger.info("相似度边较少，添加共同作者边...")
                for i, paper1 in enumerate(papers):
                    for paper2 in papers[i+1:]:
                        common_authors = set(paper1.authors) & set(paper2.authors)
                        if common_authors and not G.has_edge(paper1.paper_id, paper2.paper_id):
                            G.add_edge(paper1.paper_id, paper2.paper_id, weight=0.2)
            
            # 提取主题（如果启用）
            topics = {}
            if use_topics and len(papers) >= 5:
                logger.info("提取主题簇...")
                num_topics = min(8, len(papers) // 3)  # 动态确定主题数量
                topics = self._extract_topics_from_keywords(papers, num_topics=num_topics)
            
            # 创建pyvis网络
            net = Network(
                height='800px',
                width='100%',
                bgcolor='#ffffff',
                font_color='#333333',
                directed=False
            )
            
            # 设置物理引擎
            net.set_options("""
            {
              "physics": {
                "enabled": true,
                "barnesHut": {
                  "gravitationalConstant": -2000,
                  "centralGravity": 0.1,
                  "springLength": 200,
                  "springConstant": 0.04,
                  "damping": 0.09
                }
              }
            }
            """)
            
            # 为每个主题分配颜色
            topic_colors = [
                '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', 
                '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2'
            ]
            topic_color_map = {}
            for i, (topic_name, _) in enumerate(topics.items()):
                topic_color_map[topic_name] = topic_colors[i % len(topic_colors)]
            
            # 添加节点
            for paper in papers:
                # 确定节点颜色（基于主题）
                color = '#95A5A6'  # 默认灰色
                title_text = f"<b>{paper.title}</b><br>"
                title_text += f"作者: {', '.join(paper.authors[:3])}<br>"
                if paper.publication_date:
                    title_text += f"日期: {paper.publication_date.strftime('%Y-%m')}<br>"
                title_text += f"来源: {paper.source}<br>"
                if paper.abstract:
                    abstract_short = paper.abstract[:200] + "..." if len(paper.abstract) > 200 else paper.abstract
                    title_text += f"<br>摘要: {abstract_short}"
                
                # 查找所属主题
                paper_topic = None
                for topic_name, paper_ids in topics.items():
                    if paper.paper_id in paper_ids:
                        paper_topic = topic_name
                        color = topic_color_map[topic_name]
                        title_text += f"<br><br><b>主题: {topic_name}</b>"
                        break
                
                # 计算节点大小（基于连接数）
                degree = G.degree(paper.paper_id)
                node_size = 20 + degree * 5
                node_size = min(node_size, 50)  # 限制最大大小
                
                net.add_node(
                    paper.paper_id,
                    label=paper.title[:40] + "..." if len(paper.title) > 40 else paper.title,
                    title=title_text,
                    color=color,
                    size=node_size,
                    shape='dot'
                )
            
            # 添加边
            for edge in G.edges(data=True):
                paper_id1, paper_id2, data = edge
                weight = data.get('weight', 0.5)
                
                # 边的宽度基于权重
                edge_width = max(1, int(weight * 10))
                
                net.add_edge(
                    paper_id1,
                    paper_id2,
                    width=edge_width,
                    title=f"相似度: {weight:.3f}"
                )
            
            # 如果使用主题，添加主题节点（可选）
            if topics:
                # 为主题添加中心节点（可选，可能会让图太复杂）
                # 这里暂时不添加，只通过颜色区分
                pass
            
            # 保存为HTML
            net.save_graph(output_path)
            logger.info(f"交互式主题图谱已保存: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"生成交互式主题图谱失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return None
    
    def generate_wordcloud(self, keywords: List[str], output_path: str, width: int = 800, height: int = 400) -> Optional[str]:
        """
        生成关键词词云图
        
        Args:
            keywords: 关键词列表
            output_path: 输出文件路径
            width: 图片宽度（默认800）
            height: 图片高度（默认400）
        
        Returns:
            输出文件路径，如果失败返回None
        """
        if not WORDCLOUD_AVAILABLE:
            logger.warning("wordcloud未安装，无法生成词云图")
            return None
        
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib未安装，无法生成词云图")
            return None
        
        if not keywords:
            logger.warning("关键词列表为空，无法生成词云图")
            return None
        
        try:
            # 将关键词列表转换为词频字典（每个关键词出现1次，可以根据需要调整权重）
            word_freq = {}
            for keyword in keywords:
                # 处理中英文混合的关键词
                keyword_clean = keyword.strip()
                if keyword_clean:
                    # 如果关键词包含空格，可能需要拆分（这里暂时不拆分，保持原样）
                    word_freq[keyword_clean] = word_freq.get(keyword_clean, 0) + 1
            
            if not word_freq:
                logger.warning("没有有效的关键词，无法生成词云图")
                return None
            
            # 设置中文字体（如果需要显示中文）
            # 注意：需要确保系统有中文字体，否则中文可能显示为方块
            try:
                # 尝试使用常见的中文字体
                import platform
                if platform.system() == 'Windows':
                    font_path = 'C:/Windows/Fonts/simhei.ttf'  # 黑体
                elif platform.system() == 'Darwin':  # macOS
                    font_path = '/System/Library/Fonts/STHeiti Light.ttc'
                else:  # Linux
                    font_path = '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'
                
                # 检查字体文件是否存在
                import os
                if not os.path.exists(font_path):
                    font_path = None
            except:
                font_path = None
            
            # 创建词云对象
            wordcloud = WordCloud(
                width=width,
                height=height,
                background_color='white',
                max_words=100,
                relative_scaling=0.5,
                colormap='viridis',
                font_path=font_path if font_path else None,
                prefer_horizontal=0.7,
                min_font_size=10,
                max_font_size=100
            ).generate_from_frequencies(word_freq)
            
            # 使用matplotlib保存图片
            plt.figure(figsize=(width/100, height/100), dpi=100)
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            plt.tight_layout(pad=0)
            
            # 保存图片
            plt.savefig(output_path, dpi=100, bbox_inches='tight', pad_inches=0)
            plt.close()
            
            logger.info(f"词云图已保存: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"生成词云图失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return None



