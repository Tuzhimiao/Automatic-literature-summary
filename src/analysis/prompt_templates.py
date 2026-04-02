"""
提示词模板模块
"""

from typing import List, Dict
from ..utils.data_structures import Paper


class PromptTemplates:
    """提示词模板类"""
    
    @staticmethod
    def get_paper_type_classification_prompt(papers: List[Paper]) -> str:
        """
        获取批量判断论文类型的提示词
        
        Args:
            papers: 论文列表
        
        Returns:
            格式化的提示词
        """
        papers_info = []
        for i, paper in enumerate(papers, 1):
            authors_str = ', '.join(paper.authors[:3]) if paper.authors else "未知"
            papers_info.append(f"""
论文{i}：
- 标题：{paper.title}
- 摘要：{paper.abstract[:500] if paper.abstract else "无摘要"}...
- 作者：{authors_str}
""")
        
        prompt = f"""请判断以下论文的类型。论文类型分为两种：
1. **综述类（review）**：对某个研究领域进行全面梳理、总结和评述的文章，通常包含"survey"、"review"、"综述"等关键词，或者文章内容主要是总结现有研究、分析研究现状、展望未来发展等。
2. **方法论类（method）**：提出新方法、新算法、新技术的文章，通常包含具体的实现方案、实验验证等。

## 论文列表：
{''.join(papers_info)}

## 要求：
- 请严格按照JSON格式返回结果
- 对于每篇论文，判断其类型：如果是综述类论文，返回"review"；如果是方法论论文，返回"method"
- 格式如下：
{{
  "papers": [
    {{"paper_index": 1, "paper_type": "review"}},
    {{"paper_index": 2, "paper_type": "method"}},
    ...
  ]
}}

请开始判断："""
        
        return prompt
    
    @staticmethod
    def classify_paper_type(paper: Paper) -> str:
        """
        识别论文类型：综述（review/survey）或方法论（method）
        
        注意：此方法已废弃，现在使用批量判断方式。保留此方法作为备用。
        改进版：使用更全面的关键词和内容分析
        
        Args:
            paper: 论文对象
        
        Returns:
            "review" 或 "method"
        """
        # 关键词识别（备用方法，改进版）
        title_lower = paper.title.lower()
        abstract_lower = (paper.abstract.lower() if paper.abstract else "")
        
        # 综述类关键词（扩展版）
        review_keywords = [
            # 英文关键词
            'survey', 'review', 'overview', 'state of the art', 
            'state-of-the-art', 'literature review', 'systematic review',
            'comprehensive review', 'taxonomy', 'taxonomies',
            'survey paper', 'review paper', 'survey of', 'review of',
            'state-of-the-art survey', 'comprehensive survey',
            'systematic survey', 'bibliographic survey',
            # 中文关键词
            '综述', '综述文章', '文献综述', '研究综述',
            '现状综述', '进展综述', '发展综述',
            # 其他可能的表达
            'a survey', 'the survey', 'surveys on', 'reviews on',
            'surveying', 'reviewing', 'taxonomic'
        ]
        
        # 方法论类关键词（用于排除误判）
        method_keywords = [
            'propose', 'proposed', 'novel', 'new method', 'new approach',
            'new algorithm', 'new framework', 'new technique',
            'introduce', 'introduction of', 'present', 'presented',
            'design', 'designed', 'implement', 'implementation',
            'experiment', 'experimental', 'evaluation', 'evaluate',
            'proposed method', 'proposed approach', 'proposed algorithm',
            '提出', '方法', '算法', '框架', '技术', '实现', '实验'
        ]
        
        # 检查标题和摘要中是否包含综述关键词
        review_score = 0
        method_score = 0
        
        # 标题中的关键词权重更高
        for keyword in review_keywords:
            if keyword in title_lower:
                review_score += 2  # 标题中的关键词权重更高
            if keyword in abstract_lower:
                review_score += 1
        
        for keyword in method_keywords:
            if keyword in title_lower:
                method_score += 2
            if keyword in abstract_lower:
                method_score += 1
        
        # 如果标题中包含明确的综述关键词，直接返回review
        strong_review_indicators = ['survey', 'review', '综述', 'overview', 'taxonomy']
        for indicator in strong_review_indicators:
            if indicator in title_lower:
                return "review"
        
        # 如果标题中包含明确的方法论关键词，且没有综述关键词，返回method
        if method_score > 0 and review_score == 0:
            return "method"
        
        # 根据得分判断
        if review_score > method_score:
            return "review"
        
        # 默认认为是方法论文章
        return "method"
    
    @staticmethod
    def get_paper_detail_prompt(paper: Paper, paper_type: str = None) -> str:
        """
        获取单篇论文详细分析的提示词
        
        Args:
            paper: 论文对象
            paper_type: 论文类型（"review"或"method"），如果为None则自动识别
        
        Returns:
            格式化的提示词
        """
        # 如果没有指定类型，自动识别
        if paper_type is None:
            paper_type = PromptTemplates.classify_paper_type(paper)
        
        # 如果是综述类论文，使用综述提示词
        if paper_type == "review":
            return PromptTemplates.get_review_paper_prompt(paper)
        
        # 方法论论文使用原有的8个问题
        # 构建作者信息
        authors_str = ', '.join(paper.authors) if paper.authors else "未知"
        pub_date_str = paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知"
        
        prompt = f"""请仔细阅读以下文章，填写文章信息并回答问题。

## 文章信息：
标题：{paper.title}
摘要：{paper.abstract}
作者：{authors_str}
发表时间：{pub_date_str}
来源：{paper.source}
链接：{paper.url}

## 请填写以下信息：

1. **研究方向背景**：文章研究方向背景是什么？作者想解决什么问题？**本问题答案不得少于100字。**
2. **实现内容**：作者实现了什么？作者用了什么方法？**本问题答案不得少于100字。**
3. **结果**：作者得到了什么实验结果？得到了什么结论？**本问题答案不得少于100字。**
4. **方法模块**：该方法有什么模块？每个模块作用是什么？**本问题答案不得少于100字。**
5. **相关工作**：前人有什么工作？获得了什么成果？还存在什么问题？**本问题答案不得少于100字。**
6. **评估**：数据集用了什么？用了什么测试方法和评价指标？**本问题答案不得少于100字。**
7. **对比方法**：作者主要和哪些方法进行了对比？**本问题答案不得少于100字。**
8. **方法总结**：请用一句话总结文章的方法和创新点

## 要求：
- **每个问题的答案必须至少100字**，确保内容详细完整
- 请严格按照JSON格式返回，格式如下：
{{
  "paper_type": "method",
  "q1_background": "问题1的答案",
  "q2_implementation": "问题2的答案",
  "q3_result": "问题3的答案",
  "q4_modules": "问题4的答案",
  "q5_related_work": "问题5的答案",
  "q6_evaluation": "问题6的答案",
  "q7_comparison": "问题7的答案",
  "q8_summary": "问题8的答案",
  "recommendation_score": 5
}}
- **推荐阅读程度（recommendation_score）**：请根据论文的创新性、重要性、实验质量、对研究主题的相关性等因素，评价这篇论文的推荐阅读程度，给出1-5星的评分：
  * 5星：非常推荐，论文质量高、创新性强、对研究主题非常重要
  * 4星：推荐，论文质量较好、有一定创新性、对研究主题较重要
  * 3星：一般推荐，论文质量中等、创新性一般、对研究主题有一定参考价值
  * 2星：不太推荐，论文质量一般、创新性较弱、对研究主题参考价值有限
  * 1星：不推荐，论文质量较差、创新性弱、对研究主题参考价值很小
- **每个问题的答案必须至少100字**，如果信息不足，请尽可能详细地说明已知信息，并明确标注哪些方面信息不足
- 基于提供的摘要内容，不要编造信息
- 使用客观、准确的语言
- 对于信息不足的问题，也要尽量写满100字，可以说明：从摘要中能获取的信息、缺失的信息、以及可能的推测（需明确标注为推测）

请开始分析："""
        
        return prompt
    
    @staticmethod
    def get_review_paper_prompt(paper: Paper) -> str:
        """
        获取综述论文详细分析的提示词
        
        Args:
            paper: 论文对象
        
        Returns:
            格式化的提示词
        """
        authors_str = ', '.join(paper.authors) if paper.authors else "未知"
        pub_date_str = paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知"
        
        prompt = f"""请仔细阅读以下综述文章，填写文章信息并回答以下综述相关问题。

## 综述文章信息：
标题：{paper.title}
摘要：{paper.abstract}
作者：{authors_str}
发表时间：{pub_date_str}
来源：{paper.source}
链接：{paper.url}

## 请填写以下综述信息：

1. **研究介绍**：这篇综述文章介绍了什么研究领域？研究目标、研究意义和应用场景是什么？
2. **研究进展**：这篇综述文章梳理了该研究领域的发展历程和重要里程碑是什么？
3. **研究现状**：这篇综述文章分析了当前研究领域面临的主要挑战、技术瓶颈和理论局限是什么？
4. **现有方法**：这篇综述文章系统梳理了现有研究方法，分析了各方法的优缺点，并指出了尚未解决的问题是什么？
5. **未来发展**：这篇综述文章展望了未来研究方向，提出了可能的技术路径和解决方案是什么？

## 要求：
- 请严格按照JSON格式返回，格式如下：
{{
  "paper_type": "review",
  "section1_research_intro": "研究介绍部分内容",
  "section2_research_progress": "研究进展部分内容",
  "section3_research_status": "研究现状部分内容",
  "section4_existing_methods": "现有方法部分内容",
  "section5_future_development": "未来发展部分内容",
  "recommendation_score": 5
}}
- **推荐阅读程度（recommendation_score）**：请根据综述论文的全面性、系统性、时效性、对研究主题的相关性等因素，评价这篇综述论文的推荐阅读程度，给出1-5星的评分：
  * 5星：非常推荐，综述全面系统、时效性强、对研究主题非常重要
  * 4星：推荐，综述较全面、时效性较好、对研究主题较重要
  * 3星：一般推荐，综述一般、时效性中等、对研究主题有一定参考价值
  * 2星：不太推荐，综述不够全面、时效性较弱、对研究主题参考价值有限
  * 1星：不推荐，综述质量较差、时效性差、对研究主题参考价值很小
- 基于提供的摘要内容，不要编造信息
- 使用客观、准确的语言

请开始分析："""
        
        return prompt
    
    @staticmethod
    def get_analysis_prompt(papers: List[Paper], paper_details: List[Dict], topic: str, detail_level: int = 500) -> str:
        """
        获取综合分析提示词（基于详细论文信息）
        
        Args:
            papers: 论文列表
            paper_details: 每篇论文的详细信息列表
            topic: 研究主题
            detail_level: 综述详细程度（每部分的字数），可选200、500、800，默认为500
        
        Returns:
            格式化的提示词
        """
        # 根据详细程度设置字数要求
        if detail_level == 200:
            section_min_words = 200
            point_min_words = 50
            sub_point_min_words = 30
        elif detail_level == 800:
            section_min_words = 800
            point_min_words = 200
            sub_point_min_words = 100
        else:  # 默认500
            section_min_words = 500
            point_min_words = 100
            sub_point_min_words = 50
        # 构建论文详细信息列表
        paper_summaries = []
        review_papers = []  # 存储综述类论文的信息
        
        for i, (paper, detail) in enumerate(zip(papers, paper_details), 1):
            paper_type = detail.get('paper_type', 'method')
            
            if paper_type == 'review':
                # 综述类论文：直接使用5个部分
                review_papers.append({
                    'index': i,
                    'title': paper.title,
                    'venue': detail.get('publication_venue', '未知'),
                    'time': detail.get('publication_time', '未知'),
                    'author': detail.get('first_author', '未知'),
                    'institution': detail.get('main_institution', '未知'),
                    'section1': detail.get('section1_research_intro', '信息不足'),
                    'section2': detail.get('section2_research_progress', '信息不足'),
                    'section3': detail.get('section3_research_status', '信息不足'),
                    'section4': detail.get('section4_existing_methods', '信息不足'),
                    'section5': detail.get('section5_future_development', '信息不足')
                })
            else:
                # 方法论论文：使用8个问题
                paper_summaries.append(f"""
## 论文{i}：{paper.title}
- 来源：{detail.get('publication_venue', '未知')} ({detail.get('publication_time', '未知')})
- 第一作者：{detail.get('first_author', '未知')}，主要单位：{detail.get('main_institution', '未知')}
- 研究方向背景：{detail.get('q1_background', '信息不足')}
- 实现内容：{detail.get('q2_implementation', '信息不足')}
- 结果：{detail.get('q3_result', '信息不足')}
- 方法模块：{detail.get('q4_modules', '信息不足')}
- 相关工作：{detail.get('q5_related_work', '信息不足')}
- 评估：{detail.get('q6_evaluation', '信息不足')}
- 对比方法：{detail.get('q7_comparison', '信息不足')}
- 方法总结：{detail.get('q8_summary', '信息不足')}
""")
        
        # 根据详细程度计算各部分的字数要求
        if detail_level == 200:
            # 简洁版：每部分200字
            section1_words = 60
            section2_words = 50
            section3_words = 50
            section4_words = 50
            section5_words = 50
            section_other_words = 20
        elif detail_level == 800:
            # 详细版：每部分800字
            section1_words = 250
            section2_words = 200
            section3_words = 200
            section4_words = 200
            section5_words = 200
            section_other_words = 150
        else:  # 默认500
            # 标准版：每部分500字
            section1_words = 150
            section2_words = 100
            section3_words = 100
            section4_words = 150
            section5_words = 150
            section_other_words = 50
        
        # 构建综述类论文信息
        review_section = ""
        if review_papers:
            review_section = "\n## 综述类论文（已包含完整综述内容，请直接整合到最终报告中）：\n"
            for rev in review_papers:
                review_section += f"""
### 综述论文{rev['index']}：{rev['title']}
- 来源：{rev['venue']} ({rev['time']})
- 第一作者：{rev['author']}，主要单位：{rev['institution']}

**该综述论文的5个部分：**

**1. 研究介绍：**
{rev['section1']}

**2. 研究进展：**
{rev['section2']}

**3. 研究现状：**
{rev['section3']}

**4. 现有方法：**
{rev['section4']}

**5. 未来发展：**
{rev['section5']}

---
"""
        
        prompt = f"""你是一位专业的研究分析师。请基于以下论文的详细信息，对研究主题"{topic}"撰写一篇完整的综述报告。

## 方法论论文详细信息：
{''.join(paper_summaries) if paper_summaries else "（无方法论论文）"}
{review_section}

## 综述结构要求：

请按照以下5个部分撰写综述，**每个部分必须分点列段，每个部分不得少于{section_min_words}字**，形成一篇详细完整的综述报告：

### 1. 研究介绍
这个课题要完成一项什么工作？请详细说明研究目标、研究意义和应用场景。

**要求：**
- **必须分点列段**，使用清晰的段落结构和要点
- **每个要点至少{point_min_words}字**，详细阐述
- **本部分总字数至少{section_min_words}字**
- 建议结构：
  * 第一段：研究背景和重要性（至少{section1_words}字）
  * 第二段：研究目标和核心问题（至少{section1_words}字）
  * 第三段：应用场景和实际意义（至少{section1_words}字）
  * 其他要点：根据实际情况补充（至少{section_other_words}字）

### 2. 研究进展
这个课题的发展历程是什么？请按照时间顺序或逻辑顺序，梳理该研究领域的发展脉络和重要里程碑。

**要求：**
- **必须分点列段**，按时间线或发展阶段组织
- **每个发展阶段至少{point_min_words}字**，详细说明
- **本部分总字数至少{section_min_words}字**
- 建议结构：
  * 早期阶段（至少{section2_words}字）
  * 发展阶段（至少{section2_words}字）
  * 成熟阶段（至少{section2_words}字）
  * 最新进展（至少{section2_words}字）

### 3. 研究现状
目前研究中存在的问题有哪些？请详细分析当前研究领域面临的主要挑战、技术瓶颈和理论局限。

**要求：**
- **必须分点列段**，每个问题单独成段
- **每个问题至少{point_min_words}字**，详细分析
- **本部分总字数至少{section_min_words}字**
- 建议结构：
  * 问题1：技术挑战（至少{section3_words}字）
  * 问题2：理论局限（至少{section3_words}字）
  * 问题3：实际应用障碍（至少{section3_words}字）
  * 其他问题：根据实际情况补充（至少{section_other_words}字）

### 4. 现有方法
请系统梳理现有研究方法，分析各方法的优缺点，并指出尚未解决的问题。

**要求：**
- **必须分点列段**，每种方法单独成段
- **每种方法至少{section4_words}字**，详细分析其优缺点
- **本部分总字数至少{section_min_words}字**
- 建议结构：
  * 方法1：详细说明（至少{section4_words}字）
    - 优点（至少{sub_point_min_words}字）
    - 缺点（至少{sub_point_min_words}字）
    - 适用场景（至少{sub_point_min_words}字）
  * 方法2：详细说明（至少{section4_words}字）
    - 优点（至少{sub_point_min_words}字）
    - 缺点（至少{sub_point_min_words}字）
    - 适用场景（至少{sub_point_min_words}字）
  * 其他方法：根据实际情况补充

### 5. 未来发展
还有哪些问题没被解决？可能有什么方法可以解决？请展望未来研究方向，提出可能的技术路径和解决方案。

**要求：**
- **必须分点列段**，每个方向单独成段
- **每个方向至少{section5_words}字**，详细阐述
- **本部分总字数至少{section_min_words}字**
- 建议结构：
  * 未解决问题1：详细说明（至少{section5_words}字）
    - 可能的解决方案（至少{point_min_words}字）
  * 未解决问题2：详细说明（至少{section5_words}字）
    - 可能的解决方案（至少{point_min_words}字）
  * 未来研究方向：详细展望（至少{point_min_words}字）

### 6. 置信度评估
请基于以下三点客观评估你的综述的置信度（0.0~1.0）：
   - **一致性**：多数论文是否支持相同结论？有多少篇论文支持主要结论？
   - **覆盖度**：关键问题是否有足够文献支撑？是否所有重要方面都有论文支持？
   - **冲突性**：是否存在不可调和的观点矛盾？如果有，请列出具体的冲突点。

## 输出格式要求：
请严格按照以下JSON格式返回结果：
{{
  "section1_research_intro": "研究介绍部分内容（必须分点列段，至少{section_min_words}字）",
  "section2_research_progress": "研究进展部分内容（必须分点列段，至少{section_min_words}字）",
  "section3_research_status": "研究现状部分内容（必须分点列段，至少{section_min_words}字）",
  "section4_existing_methods": "现有方法部分内容（必须分点列段，至少{section_min_words}字）",
  "section5_future_development": "未来发展部分内容（必须分点列段，至少{section_min_words}字）",
  "confidence": 0.85,
  "confidence_reason": "详细说明置信度评估的依据，包括：1) 支持主要结论的论文数量（如'论文1、论文3、论文5等共X篇支持该结论'）；2) 关键问题的文献覆盖情况（如'所有重要方面都有至少2篇论文支持'）；3) 是否存在冲突及冲突程度（如'无明显冲突'或'存在X个轻微冲突'）。字数不少于{point_min_words}字。",
  "conflicts": ["关于X方法，论文2与论文5观点相反"],
  "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5", "关键词6", "关键词7", "关键词8", "关键词9", "关键词10"]
}}

## 要求：
- **每个部分必须分点列段，总字数至少{section_min_words}字**，确保内容详细充实
- **每个要点或段落至少{point_min_words}字**，详细阐述
- **置信度说明（confidence_reason）必须详细，至少{point_min_words}字**，包括：
  * 支持主要结论的论文数量和编号
  * 关键问题的文献覆盖情况
  * 是否存在冲突及冲突程度
  * 其他影响置信度的因素
- **关键词（keywords）**：请根据综述内容，生成10-20个最能代表该研究领域的关键词。这些关键词应该：
  * 涵盖研究主题、方法、应用场景等各个方面
  * 使用中英文均可，但建议使用英文（便于后续搜索）
  * 是学术研究中常用的术语
  * 能够有效概括综述的核心内容
- 严格基于提供的论文详细信息，不要编造信息
- 如果某些方面信息不足，请明确说明
- 使用客观、学术的语言，符合学术综述的写作规范
- 重点关注多篇论文共同支持的观点
- 引用具体的论文编号（如"论文1"、"论文2"）来支持你的分析
- **置信度评估必须基于客观依据**：统计支持论文数量、识别冲突点，不要凭感觉打分
- 确保综述逻辑清晰，各部分之间衔接自然

请开始撰写综述："""
        
        return prompt
    
    @staticmethod
    def get_batch_paper_detail_prompt(papers: List[Paper]) -> str:
        """
        获取批量论文详细分析的提示词
        
        Args:
            papers: 论文列表
        
        Returns:
            格式化的提示词
        """
        papers_info = []
        for i, paper in enumerate(papers, 1):
            authors_str = ', '.join(paper.authors) if paper.authors else "未知"
            pub_date_str = paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知"
            
            papers_info.append(f"""
## 文章{i}：
标题：{paper.title}
摘要：{paper.abstract}
作者：{authors_str}
发表时间：{pub_date_str}
来源：{paper.source}
链接：{paper.url}
""")
        
        prompt = f"""请仔细阅读以下{len(papers)}篇文章，为每篇文章填写信息并回答问题。

{''.join(papers_info)}

## 请为每篇文章填写以下信息：

对于每篇文章，请回答以下8个问题：

1. **研究方向背景**：文章研究方向背景是什么？作者想解决什么问题？**本问题答案不得少于100字。**
2. **实现内容**：作者实现了什么？作者用了什么方法？**本问题答案不得少于100字。**
3. **结果**：作者得到了什么实验结果？得到了什么结论？**本问题答案不得少于100字。**
4. **方法模块**：该方法有什么模块？每个模块作用是什么？**本问题答案不得少于100字。**
5. **相关工作**：前人有什么工作？获得了什么成果？还存在什么问题？**本问题答案不得少于100字。**
6. **评估**：数据集用了什么？用了什么测试方法和评价指标？**本问题答案不得少于100字。**
7. **对比方法**：作者主要和哪些方法进行了对比？**本问题答案不得少于100字。**
8. **方法总结**：请用一句话总结文章的方法和创新点（**本问题答案不得少于100字**）

## 要求：
- **每个问题的答案必须至少100字**，确保内容详细完整
- 请严格按照JSON格式返回，格式如下（为每篇文章返回一个对象）：
{{
  "papers": [
    {{
      "paper_index": 1,
      "paper_title": "文章1的标题",
      "q1_background": "问题1的答案",
      "q2_implementation": "问题2的答案",
      "q3_result": "问题3的答案",
      "q4_modules": "问题4的答案",
      "q5_related_work": "问题5的答案",
      "q6_evaluation": "问题6的答案",
      "q7_comparison": "问题7的答案",
      "q8_summary": "问题8的答案"
    }},
    {{
      "paper_index": 2,
      "paper_title": "文章2的标题",
      "q1_background": "问题1的答案",
      ...
    }}
  ]
}}
- **必须为所有{len(papers)}篇文章都提供完整的答案**
- **每个问题的答案必须至少100字**，如果信息不足，请尽可能详细地说明已知信息，并明确标注哪些方面信息不足
- 基于提供的摘要内容，不要编造信息
- 使用客观、准确的语言
- 对于信息不足的问题，也要尽量写满100字，可以说明：从摘要中能获取的信息、缺失的信息、以及可能的推测（需明确标注为推测）

请开始分析："""
        
        return prompt
    
    @staticmethod
    def get_consistency_check_prompt(summary: str, papers: List[Paper]) -> str:
        """
        获取一致性检查提示词
        
        Args:
            summary: 生成的摘要
            papers: 论文列表
        
        Returns:
            格式化的提示词
        """
        paper_titles = "\n".join([f"- {p.title}" for p in papers])
        
        prompt = f"""请评估以下研究综述与原始论文的一致性。

## 研究综述：
{summary}

## 原始论文列表：
{paper_titles}

请评估：
1. 综述中的主要观点是否在原始论文中有支持？
2. 是否存在综述中声称但论文中未提及的内容？
3. 整体一致性评分（0-1之间，1表示完全一致）

请提供评估结果："""
        
        return prompt
