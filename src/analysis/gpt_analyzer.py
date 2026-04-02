"""
GPT分析模块
"""

import os
import json
import re
from typing import List, Optional
from loguru import logger

try:
    from openai import OpenAI  # 通用客户端，DeepSeek/Kimi/Qwen 均使用 OpenAI 兼容接口
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.error("openai 库未安装")

from ..utils.data_structures import Paper, AnalysisResult, PaperDetail
from .prompt_templates import PromptTemplates


class GPTAnalyzer:
    """GPT分析器（支持 DeepSeek、Kimi、Qwen API，均使用 OpenAI 兼容接口）"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-chat",
        temperature: float = 0.3,
        max_tokens: int = 2000,
        api_provider: str = "deepseek",
        base_url: Optional[str] = None
    ):
        """
        初始化GPT分析器
        
        Args:
            api_key: API密钥
            model: 使用的模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            api_provider: API提供商 ("deepseek"、"kimi" 或 "qwen")
            base_url: 自定义API基础URL（如果为None，将根据api_provider自动设置）
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai 库未安装，请运行: pip install openai")
        
        self.api_provider = api_provider.lower()
        
        # 根据提供商设置默认base_url
        if base_url is None:
            if self.api_provider == "deepseek":
                base_url = "https://api.deepseek.com"
            elif self.api_provider == "kimi":
                base_url = "https://api.moonshot.cn/v1"
            elif self.api_provider == "qwen":
                base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            else:
                raise ValueError(f"不支持的API提供商: {self.api_provider}，仅支持 deepseek、kimi、qwen")
        
        # 获取API密钥（去除首尾空格）
        if self.api_provider == "deepseek":
            raw_key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
            self.api_key = raw_key.strip().strip('"').strip("'")  # 去除空格和引号
        elif self.api_provider == "kimi":
            raw_key = api_key or os.getenv("KIMI_API_KEY") or ""
            self.api_key = raw_key.strip().strip('"').strip("'")  # 去除空格和引号
        elif self.api_provider == "qwen":
            raw_key = api_key or os.getenv("QWEN_API_KEY") or ""
            self.api_key = raw_key.strip().strip('"').strip("'")  # 去除空格和引号
        else:
            raise ValueError(f"不支持的API提供商: {self.api_provider}")
        
        # 检查是否是占位符或空值
        if not self.api_key or self.api_key in ["your-deepseek-api-key-here", "your-kimi-api-key-here", "your-qwen-api-key-here", ""]:
            provider_names = {
                "deepseek": "DeepSeek",
                "kimi": "Kimi",
                "qwen": "通义千问"
            }
            provider_name = provider_names.get(self.api_provider, "API")
            raise ValueError(f"{provider_name} API密钥未设置，请在config.yaml中配置或设置环境变量")
        
        # 创建客户端（openai 库兼容多种 API，通过 base_url 切换不同提供商）
        self.client = OpenAI(api_key=self.api_key, base_url=base_url)
        
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.prompt_templates = PromptTemplates()
        
        logger.info(f"已初始化{self.api_provider.upper()}分析器，模型: {model}, base_url: {base_url}")
    
    def analyze_single_paper(self, paper: Paper, progress_callback=None) -> PaperDetail:
        """
        分析单篇论文，提取详细信息（在分析时自动判断类型）
        
        Args:
            paper: 论文对象
            progress_callback: 进度回调函数
        
        Returns:
            论文详细信息
        """
        try:
            # 步骤1：先判断论文类型（使用大模型，基于完整摘要信息）
            if progress_callback:
                progress_callback({
                    'message': f'正在判断论文类型: {paper.title[:50]}...',
                    'current_paper': 0,
                    'total_papers': 1
                })
            
            paper_type = None
            try:
                # 使用大模型判断类型（基于完整摘要）
                type_prompt = self.prompt_templates.get_paper_type_classification_prompt([paper])
                type_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一位专业的学术论文分类专家，擅长准确判断论文类型。请严格按照JSON格式返回结果，只返回JSON，不要有其他文字。"},
                        {"role": "user", "content": type_prompt}
                    ],
                    temperature=0.1,
                    max_tokens=500,
                    stream=False
                )
                
                type_response_text = type_response.choices[0].message.content
                type_response_clean = type_response_text.strip()
                
                # 尝试提取JSON（处理可能的markdown代码块）
                if '```' in type_response_clean:
                    import re
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', type_response_clean, re.DOTALL)
                    if json_match:
                        type_response_clean = json_match.group(1)
                
                if not type_response_clean.startswith('{'):
                    start_idx = type_response_clean.find('{')
                    if start_idx != -1:
                        type_response_clean = type_response_clean[start_idx:]
                    else:
                        raise ValueError("无法找到JSON格式的响应")
                
                type_result = json.loads(type_response_clean)
                type_papers = type_result.get('papers', [])
                if type_papers and len(type_papers) > 0:
                    paper_type = type_papers[0].get('paper_type', 'method')
                    # 验证类型值
                    if paper_type not in ['review', 'method']:
                        logger.warning(f"论文类型值无效: {paper_type}，使用备用方法")
                        paper_type = self.prompt_templates.classify_paper_type(paper)
                    else:
                        logger.info(f"论文类型判断结果: {paper.title[:50]} -> {paper_type}")
                else:
                    raise ValueError("类型判断结果为空")
                    
            except Exception as e:
                logger.warning(f"论文类型判断失败: {str(e)}，使用备用方法（关键词匹配）")
                logger.debug(f"原始响应: {type_response_text[:200] if 'type_response_text' in locals() else 'N/A'}")
                # 如果判断失败，使用备用方法（改进的关键词匹配）
                paper_type = self.prompt_templates.classify_paper_type(paper)
                logger.info(f"备用方法判断结果: {paper.title[:50]} -> {paper_type}")
            
            # 步骤2：根据类型进行详细分析
            return self.analyze_single_paper_with_type(paper, paper_type, progress_callback)
            
        except Exception as e:
            logger.error(f"分析论文 {paper.title} 失败: {str(e)}")
            # 返回默认的详细信息
            paper_type = self.prompt_templates.classify_paper_type(paper)
            return self._create_default_paper_detail(paper, paper_type, str(e))
    
    def analyze_single_paper_with_type(self, paper: Paper, paper_type: str, progress_callback=None) -> PaperDetail:
        """
        分析单篇论文，提取详细信息（使用指定的类型）
        
        Args:
            paper: 论文对象
            paper_type: 论文类型（"review"或"method"）
            progress_callback: 进度回调函数
        
        Returns:
            论文详细信息
        """
        try:
            
            if progress_callback:
                paper_type_name = "综述" if paper_type == "review" else "方法论"
                progress_callback({
                    'message': f'正在详细分析论文（{paper_type_name}）: {paper.title[:50]}...',
                    'current_paper': 0,
                    'total_papers': 1
                })
            
            # 获取提示词（根据论文类型）
            prompt = self.prompt_templates.get_paper_detail_prompt(paper, paper_type)
            
            # 调用API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的学术论文分析专家，擅长从论文摘要中提取结构化信息。请严格按照JSON格式返回结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False
            )
            
            # 解析响应
            response_text = response.choices[0].message.content
            
            # 尝试提取JSON
            detail_dict = None
            try:
                # 尝试直接解析JSON
                response_text_clean = response_text.strip()
                if response_text_clean.startswith('{'):
                    try:
                        detail_dict = json.loads(response_text_clean)
                    except json.JSONDecodeError:
                        # 如果直接解析失败，尝试提取
                        pass
                
                # 如果直接解析失败，尝试从文本中提取JSON
                if detail_dict is None:
                    # 查找第一个{和匹配的}
                    start_idx = response_text.find('{')
                    if start_idx == -1:
                        raise ValueError("无法找到JSON格式的响应")
                    
                    # 从第一个{开始，找到匹配的}
                    brace_count = 0
                    end_idx = start_idx
                    in_string = False
                    escape_next = False
                    
                    for i in range(start_idx, len(response_text)):
                        char = response_text[i]
                        
                        if escape_next:
                            escape_next = False
                            continue
                        
                        if char == '\\':
                            escape_next = True
                            continue
                        
                        if char == '"' and not escape_next:
                            in_string = not in_string
                            continue
                        
                        if not in_string:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                    
                    if brace_count == 0:
                        json_str = response_text[start_idx:end_idx]
                        try:
                            detail_dict = json.loads(json_str)
                        except json.JSONDecodeError:
                            # 尝试修复常见的JSON问题
                            # 如果JSON不完整，尝试添加缺失的闭合括号
                            if brace_count > 0:
                                json_str += '}' * brace_count
                                try:
                                    detail_dict = json.loads(json_str)
                                except json.JSONDecodeError:
                                    pass
                    else:
                        # JSON不完整，尝试修复
                        json_str = response_text[start_idx:]
                        # 尝试添加缺失的闭合括号
                        missing_braces = brace_count
                        json_str += '}' * missing_braces
                        try:
                            detail_dict = json.loads(json_str)
                        except json.JSONDecodeError:
                            pass
                
                # 如果仍然失败，记录响应内容
                if detail_dict is None:
                    logger.warning(f"无法解析JSON响应，响应内容前500字符: {response_text[:500]}")
                    raise ValueError("无法找到完整的JSON格式的响应")
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"JSON解析失败: {str(e)}")
                logger.debug(f"完整响应内容: {response_text}")
                # 如果JSON解析失败，创建默认的详细信息（根据论文类型）
                if paper_type == "review":
                    detail_dict = {
                        "publication_venue": "信息不足",
                        "publication_time": paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知",
                        "first_author": paper.authors[0] if paper.authors else "未知",
                        "corresponding_author": "未明确",
                        "main_institution": "信息不足",
                        "section1_research_intro": "信息不足",
                        "section2_research_progress": "信息不足",
                        "section3_research_status": "信息不足",
                        "section4_existing_methods": "信息不足",
                        "section5_future_development": "信息不足"
                    }
                else:
                    detail_dict = {
                        "publication_venue": "信息不足",
                        "publication_time": paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知",
                        "first_author": paper.authors[0] if paper.authors else "未知",
                        "corresponding_author": "未明确",
                        "main_institution": "信息不足",
                        "q1_background": "信息不足",
                        "q2_implementation": "信息不足",
                        "q3_result": "信息不足",
                        "q4_modules": "信息不足",
                        "q5_related_work": "信息不足",
                        "q6_evaluation": "信息不足",
                        "q7_comparison": "信息不足",
                        "q8_summary": "信息不足"
                    }
            
            # 创建PaperDetail对象（根据论文类型）
            if paper_type == "review":
                # 综述类论文
                # 获取推荐阅读程度，确保在1-5范围内
                rec_score = detail_dict.get("recommendation_score")
                if rec_score is not None:
                    try:
                        rec_score = int(rec_score)
                        if rec_score < 1:
                            rec_score = 1
                        elif rec_score > 5:
                            rec_score = 5
                    except (ValueError, TypeError):
                        rec_score = None
                
                paper_detail = PaperDetail(
                    paper_id=paper.paper_id,
                    paper_type=paper_type,
                    publication_venue=detail_dict.get("publication_venue"),
                    publication_time=detail_dict.get("publication_time"),
                    first_author=detail_dict.get("first_author"),
                    corresponding_author=detail_dict.get("corresponding_author"),
                    main_institution=detail_dict.get("main_institution"),
                    section1_research_intro=detail_dict.get("section1_research_intro"),
                    section2_research_progress=detail_dict.get("section2_research_progress"),
                    section3_research_status=detail_dict.get("section3_research_status"),
                    section4_existing_methods=detail_dict.get("section4_existing_methods"),
                    section5_future_development=detail_dict.get("section5_future_development"),
                    recommendation_score=rec_score
                )
            else:
                # 方法论论文
                # 获取推荐阅读程度，确保在1-5范围内
                rec_score = detail_dict.get("recommendation_score")
                if rec_score is not None:
                    try:
                        rec_score = int(rec_score)
                        if rec_score < 1:
                            rec_score = 1
                        elif rec_score > 5:
                            rec_score = 5
                    except (ValueError, TypeError):
                        rec_score = None
                
                paper_detail = PaperDetail(
                    paper_id=paper.paper_id,
                    paper_type=paper_type,
                    publication_venue=detail_dict.get("publication_venue"),
                    publication_time=detail_dict.get("publication_time"),
                    first_author=detail_dict.get("first_author"),
                    corresponding_author=detail_dict.get("corresponding_author"),
                    main_institution=detail_dict.get("main_institution"),
                    q1_background=detail_dict.get("q1_background"),
                    q2_implementation=detail_dict.get("q2_implementation"),
                    q3_result=detail_dict.get("q3_result"),
                    q4_modules=detail_dict.get("q4_modules"),
                    q5_related_work=detail_dict.get("q5_related_work"),
                    q6_evaluation=detail_dict.get("q6_evaluation"),
                    q7_comparison=detail_dict.get("q7_comparison"),
                    q8_summary=detail_dict.get("q8_summary"),
                    recommendation_score=rec_score
                )
            
            return paper_detail
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"分析论文 {paper.title} 失败: {error_msg}")
            # 如果是JSON解析错误，记录更多信息
            if "JSON" in error_msg or "json" in error_msg.lower():
                logger.debug(f"JSON解析错误详情，论文标题: {paper.title[:100]}")
            # 返回默认的详细信息（根据论文类型）
            paper_type = self.prompt_templates.classify_paper_type(paper)
            if paper_type == "review":
                return PaperDetail(
                    paper_id=paper.paper_id,
                    paper_type=paper_type,
                    publication_venue="分析失败",
                    publication_time=paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知",
                    first_author=paper.authors[0] if paper.authors else "未知",
                    corresponding_author="未明确",
                    main_institution="分析失败",
                    section1_research_intro=f"分析失败: {error_msg[:200]}",
                    section2_research_progress="分析失败",
                    section3_research_status="分析失败",
                    section4_existing_methods="分析失败",
                    section5_future_development="分析失败",
                    recommendation_score=None
                )
            else:
                return PaperDetail(
                    paper_id=paper.paper_id,
                    paper_type=paper_type,
                    publication_venue="分析失败",
                    publication_time=paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知",
                    first_author=paper.authors[0] if paper.authors else "未知",
                    corresponding_author="未明确",
                    main_institution="分析失败",
                    q1_background=f"分析失败: {error_msg[:200]}",  # 限制错误信息长度
                    q2_implementation="分析失败",
                    q3_result="分析失败",
                    q4_modules="分析失败",
                    q5_related_work="分析失败",
                    q6_evaluation="分析失败",
                    q7_comparison="分析失败",
                    q8_summary="分析失败",
                    recommendation_score=None
                )
    
    def analyze_batch_papers(self, papers: List[Paper], progress_callback=None) -> List[PaperDetail]:
        """
        批量分析多篇论文，提取详细信息
        
        Args:
            papers: 论文列表
            progress_callback: 进度回调函数
        
        Returns:
            论文详细信息列表
        """
        if not papers:
            return []
        
        # 检查是否有综述类论文，如果有则回退到单篇分析
        for paper in papers:
            paper_type = self.prompt_templates.classify_paper_type(paper)
            if paper_type == "review":
                logger.info(f"检测到综述类论文，批量分析回退到单篇分析模式")
                return [self.analyze_single_paper(paper, progress_callback) for paper in papers]
        
        try:
            if progress_callback:
                progress_callback({
                    'message': f'正在批量分析 {len(papers)} 篇论文...',
                    'current_paper': 0,
                    'total_papers': len(papers)
                })
            
            # 获取批量分析提示词（仅用于方法论论文）
            prompt = self.prompt_templates.get_batch_paper_detail_prompt(papers)
            
            # 调用API（批量分析需要更大的max_tokens）
            # 估算：每篇论文8个问题 × 100字 × 2 tokens/字 ≈ 1600 tokens/篇
            # 加上JSON格式等，使用更大的max_tokens
            # 注意：DeepSeek API的max_tokens最大值为8192，需要限制在这个范围内
            # 如果批量大小较大，使用8192；否则根据论文数量动态计算
            if len(papers) >= 3:
                # 批量大小较大时，使用最大允许值
                batch_max_tokens = 8192
            else:
                # 批量大小较小时，根据论文数量计算
                estimated_tokens = self.max_tokens * len(papers) * 2
                batch_max_tokens = min(max(estimated_tokens, 4000), 8192)  # 限制在8192以内
            
            logger.debug(f"批量分析 {len(papers)} 篇论文，使用 max_tokens={batch_max_tokens}")
            logger.info(f"批量分析使用的模型: {self.model}, API提供商: {self.api_provider}, base_url: {self.client.base_url if hasattr(self.client, 'base_url') else 'default'}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的学术论文分析专家，擅长从论文摘要中批量提取结构化信息。请严格按照JSON格式返回结果，必须为所有论文提供完整的答案。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=batch_max_tokens,
                stream=False
            )
            
            # 解析响应
            response_text = response.choices[0].message.content
            
            # 尝试提取JSON
            try:
                response_text_clean = response_text.strip()
                if response_text_clean.startswith('{'):
                    batch_result = json.loads(response_text_clean)
                else:
                    # 尝试从文本中提取JSON
                    start_idx = response_text.find('{')
                    if start_idx == -1:
                        raise ValueError("无法找到JSON格式的响应")
                    
                    brace_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(response_text)):
                        if response_text[i] == '{':
                            brace_count += 1
                        elif response_text[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                    
                    if brace_count == 0:
                        json_str = response_text[start_idx:end_idx]
                        batch_result = json.loads(json_str)
                    else:
                        raise ValueError("无法找到完整的JSON格式的响应")
                
                # 解析批量结果
                papers_data = batch_result.get('papers', [])
                paper_details = []
                
                # 创建paper_id到Paper对象的映射
                paper_map = {paper.paper_id: paper for paper in papers}
                
                for paper_data in papers_data:
                    paper_index = paper_data.get('paper_index', 0)
                    paper_title = paper_data.get('paper_title', '')
                    
                    # 根据索引或标题找到对应的Paper对象
                    paper = None
                    if 1 <= paper_index <= len(papers):
                        paper = papers[paper_index - 1]
                    else:
                        # 尝试通过标题匹配
                        for p in papers:
                            if p.title == paper_title or paper_title in p.title:
                                paper = p
                                break
                    
                    if not paper:
                        logger.warning(f"无法匹配论文: index={paper_index}, title={paper_title}")
                        continue
                    
                    # 获取推荐阅读程度
                    rec_score = paper_data.get("recommendation_score")
                    if rec_score is not None:
                        try:
                            rec_score = int(rec_score)
                            if rec_score < 1:
                                rec_score = 1
                            elif rec_score > 5:
                                rec_score = 5
                        except (ValueError, TypeError):
                            rec_score = None
                    
                    # 创建PaperDetail对象（批量分析仅用于方法论论文）
                    paper_detail = PaperDetail(
                        paper_id=paper.paper_id,
                        paper_type="method",  # 批量分析仅用于方法论论文
                        publication_venue=paper_data.get("publication_venue", "信息不足"),
                        publication_time=paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知",
                        first_author=paper.authors[0] if paper.authors else "未知",
                        corresponding_author=paper_data.get("corresponding_author", "未明确"),
                        main_institution=paper_data.get("main_institution", "信息不足"),
                        q1_background=paper_data.get("q1_background", "信息不足"),
                        q2_implementation=paper_data.get("q2_implementation", "信息不足"),
                        q3_result=paper_data.get("q3_result", "信息不足"),
                        q4_modules=paper_data.get("q4_modules", "信息不足"),
                        q5_related_work=paper_data.get("q5_related_work", "信息不足"),
                        q6_evaluation=paper_data.get("q6_evaluation", "信息不足"),
                        q7_comparison=paper_data.get("q7_comparison", "信息不足"),
                        q8_summary=paper_data.get("q8_summary", "信息不足"),
                        recommendation_score=rec_score
                    )
                    paper_details.append(paper_detail)
                
                # 如果批量分析返回的论文数量不足，为缺失的论文创建默认详细信息
                if len(paper_details) < len(papers):
                    analyzed_paper_ids = {detail.paper_id for detail in paper_details}
                    for paper in papers:
                        if paper.paper_id not in analyzed_paper_ids:
                            logger.warning(f"批量分析中缺失论文: {paper.title[:50]}")
                            paper_detail = PaperDetail(
                                paper_id=paper.paper_id,
                                paper_type="method",  # 批量分析仅用于方法论论文
                                publication_venue="信息不足",
                                publication_time=paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知",
                                first_author=paper.authors[0] if paper.authors else "未知",
                                corresponding_author="未明确",
                                main_institution="信息不足",
                                q1_background="批量分析中缺失此论文信息",
                                q2_implementation="信息不足",
                                q3_result="信息不足",
                                q4_modules="信息不足",
                                q5_related_work="信息不足",
                                q6_evaluation="信息不足",
                                q7_comparison="信息不足",
                                q8_summary="信息不足"
                            )
                            paper_details.append(paper_detail)
                
                # 确保顺序与输入一致
                paper_details_sorted = []
                for paper in papers:
                    for detail in paper_details:
                        if detail.paper_id == paper.paper_id:
                            paper_details_sorted.append(detail)
                            break
                    else:
                        # 如果找不到，创建默认的（批量分析仅用于方法论论文）
                        paper_details_sorted.append(PaperDetail(
                            paper_id=paper.paper_id,
                            paper_type="method",
                            publication_venue="信息不足",
                            publication_time=paper.publication_date.strftime("%Y-%m") if paper.publication_date else "未知",
                            first_author=paper.authors[0] if paper.authors else "未知",
                            corresponding_author="未明确",
                            main_institution="信息不足",
                            q1_background="批量分析失败",
                            q2_implementation="信息不足",
                            q3_result="信息不足",
                            q4_modules="信息不足",
                            q5_related_work="信息不足",
                            q6_evaluation="信息不足",
                            q7_comparison="信息不足",
                            q8_summary="信息不足",
                                recommendation_score=None
                            ))
                
                return paper_details_sorted
                
            except json.JSONDecodeError as e:
                logger.warning(f"批量分析JSON解析失败，回退到单篇分析: {str(e)}")
                logger.debug(f"响应内容: {response_text[:500]}")
                # 如果批量分析失败，回退到单篇分析
                return [self.analyze_single_paper(paper, progress_callback) for paper in papers]
            except Exception as e:
                logger.error(f"批量分析失败: {str(e)}")
                # 如果批量分析失败，回退到单篇分析
                return [self.analyze_single_paper(paper, progress_callback) for paper in papers]
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"批量分析过程出错: {error_msg}")
            logger.error(f"使用的模型: {self.model}, API提供商: {self.api_provider}")
            
            # 检查是否是模型不存在的错误
            if "Model Not Exist" in error_msg or "model_not_found" in error_msg.lower():
                logger.error(f"模型 '{self.model}' 在 {self.api_provider} API 中不存在！请检查模型名称是否正确。")
                logger.error(f"DeepSeek支持的模型: deepseek-chat, deepseek-reasoner")
                logger.error(f"Kimi支持的模型: moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k")
            
            # 如果批量分析失败，回退到单篇分析
            return [self.analyze_single_paper(paper, progress_callback) for paper in papers]
    
    def analyze_papers(self, papers: List[Paper], topic: str, progress_callback=None, review_analyzer=None, batch_size: int = 1, review_detail_level: int = 500) -> AnalysisResult:
        """
        分析论文并生成综合总结
        
        Args:
            papers: 论文列表
            topic: 研究主题
            progress_callback: 进度回调函数
            review_analyzer: 用于生成综述的分析器（如果为None，则使用当前分析器）
            batch_size: 批量处理大小，默认为1（逐篇分析）。如果大于1，则批量分析多篇论文以提高速度
            review_detail_level: 综述详细程度（每部分的字数），可选200、500、800，默认为500
        
        Returns:
            分析结果
        """
        if not papers:
            logger.warning("论文列表为空，无法进行分析")
            return AnalysisResult(
                summary="无可用论文",
                key_findings=[],
                research_trends=[],
                confidence_score=0.0,
                consistency_score=0.0,
                papers_analyzed=0
            )
        
        try:
            provider_name = {"deepseek": "DeepSeek", "kimi": "Kimi", "qwen": "Qwen"}.get(self.api_provider, "AI")
            logger.info(f"开始使用{provider_name}分析 {len(papers)} 篇论文，批量大小: {batch_size}")
            
            # 步骤1：对每篇论文进行详细分析（在分析时自动判断类型）
            if progress_callback:
                progress_callback({
                    'message': f'正在详细分析 {len(papers)} 篇论文（步骤1/2，批量大小: {batch_size}）...',
                    'current_paper': 0,
                    'total_papers': len(papers)
                })
            
            paper_details = []
            
            # 根据batch_size决定是批量处理还是逐篇处理
            if batch_size > 1:
                # 批量处理模式
                total_batches = (len(papers) + batch_size - 1) // batch_size
                for batch_idx in range(total_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min(start_idx + batch_size, len(papers))
                    batch_papers = papers[start_idx:end_idx]
                    
                    if progress_callback:
                        progress_callback({
                            'message': f'正在批量分析第 {batch_idx + 1}/{total_batches} 批（{len(batch_papers)} 篇）...',
                            'current_paper': start_idx + 1,
                            'total_papers': len(papers),
                            'current_paper_title': f'批量处理 {len(batch_papers)} 篇论文'
                        })
                    
                    # 批量分析仅支持方法论论文，但我们需要先判断类型
                    # 为了简化，批量分析时也逐篇判断类型和分析
                    # 如果后续需要优化，可以在批量分析前先判断类型
                    for paper in batch_papers:
                        paper_detail = self.analyze_single_paper(paper, progress_callback)
                        paper_details.append(paper_detail)
                    
                    logger.info(f"已完成批量 {batch_idx + 1}/{total_batches} 的分析（{len(batch_papers)} 篇）")
            else:
                # 逐篇处理模式（在分析时自动判断类型）
                for i, paper in enumerate(papers, 1):
                    if progress_callback:
                        progress_callback({
                            'message': f'正在详细分析第 {i}/{len(papers)} 篇论文',
                            'current_paper': i,
                            'total_papers': len(papers),
                            'current_paper_title': paper.title  # 添加论文标题
                        })
                    
                    # 分析单篇论文（会自动判断类型）
                    paper_detail = self.analyze_single_paper(paper, progress_callback)
                    paper_details.append(paper_detail)
                    paper_type_name = "综述" if paper_detail.paper_type == "review" else "方法论"
                    logger.info(f"已完成论文 {i}/{len(papers)} 的详细分析（{paper_type_name}）: {paper.title[:50]}")
            
            # 步骤2：基于详细论文信息进行综合分析
            # 如果提供了review_analyzer，使用它进行综述生成；否则使用当前分析器
            review_analyzer_to_use = review_analyzer if review_analyzer is not None else self
            
            if progress_callback:
                review_model_name = review_analyzer_to_use.model if review_analyzer_to_use != self else self.model
                progress_callback({
                    'message': f'正在基于详细论文信息进行综合分析（步骤2/2，使用模型: {review_model_name}）...',
                    'current_paper': len(papers),
                    'total_papers': len(papers),
                    'current_paper_title': ''  # 综合分析阶段不显示具体论文
                })
            
            # 将PaperDetail转换为字典列表
            paper_details_dict = [detail.to_dict() for detail in paper_details]
            
            # 获取综合分析提示词（传入详细程度）
            prompt = self.prompt_templates.get_analysis_prompt(papers, paper_details_dict, topic, detail_level=review_detail_level)
            
            # 报告进度：正在调用AI进行综合分析
            if progress_callback:
                review_model_name = review_analyzer_to_use.model if review_analyzer_to_use != self else self.model
                progress_callback({
                    'message': f'正在使用 {review_model_name} 进行综合分析，请稍候...',
                    'current_paper': len(papers),
                    'total_papers': len(papers),
                    'current_paper_title': ''  # 综合分析阶段不显示具体论文
                })
            
            # 调用API进行综合分析
            # 综合分析需要生成更长的内容（5个部分，每个至少200字），所以使用更大的max_tokens
            # 估算：5个部分 × 200字 × 2 tokens/字 ≈ 2000 tokens，加上JSON格式等，使用3倍安全值
            analysis_max_tokens = max(review_analyzer_to_use.max_tokens * 3, 6000)  # 至少6000 tokens
            
            response = review_analyzer_to_use.client.chat.completions.create(
                model=review_analyzer_to_use.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的研究分析师，擅长综合多篇学术论文的详细信息，撰写完整的综述报告。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=review_analyzer_to_use.temperature,
                max_tokens=analysis_max_tokens,
                stream=False
            )
            
            # 解析响应
            analysis_text = response.choices[0].message.content
            
            # 解析分析结果
            result = self._parse_analysis(analysis_text, len(papers))
            # 添加论文详细信息
            result.paper_details = paper_details_dict
            
            # 步骤3：提取子话题（在生成综述后）
            if progress_callback:
                progress_callback({
                    'message': '正在提取子话题关键词...',
                    'current_paper': len(papers),
                    'total_papers': len(papers),
                    'current_paper_title': ''
                })
            
            try:
                # 构建综述内容用于子话题提取
                review_content = ""
                if result.section1_research_intro:
                    review_content = f"{result.section1_research_intro}\n\n{result.section2_research_progress}\n\n{result.section3_research_status}\n\n{result.section4_existing_methods}\n\n{result.section5_future_development}"
                elif result.summary:
                    review_content = result.summary
                
                # 获取子话题提取提示词
                subtopics_prompt = self.prompt_templates.get_subtopics_extraction_prompt(
                    papers, topic, review_content
                )
                
                # 调用API提取子话题
                subtopics_response = review_analyzer_to_use.client.chat.completions.create(
                    model=review_analyzer_to_use.model,
                    messages=[
                        {"role": "system", "content": "你是一位专业的研究分析师，擅长从论文和综述中提取关键的子话题关键词。请严格按照JSON格式返回结果。"},
                        {"role": "user", "content": subtopics_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000,
                    stream=False
                )
                
                # 解析子话题
                subtopics_text = subtopics_response.choices[0].message.content
                subtopics_list = self._parse_subtopics(subtopics_text)
                result.subtopics = subtopics_list
                
                if subtopics_list:
                    logger.info(f"成功提取 {len(subtopics_list)} 个子话题: {', '.join(subtopics_list[:5])}")
                else:
                    logger.warning("未能提取到子话题")
                    
            except Exception as e:
                logger.warning(f"子话题提取失败: {str(e)}")
                result.subtopics = []
            
            provider_name = {"deepseek": "DeepSeek", "kimi": "Kimi", "qwen": "Qwen"}.get(self.api_provider, "AI")
            logger.info(f"{provider_name}分析完成")
            return result
            
        except Exception as e:
            provider_name = {"deepseek": "DeepSeek", "kimi": "Kimi", "qwen": "Qwen"}.get(self.api_provider, "AI")
            error_msg = str(e)
            
            # 提供更友好的错误信息
            if "authentication" in error_msg.lower() or "invalid" in error_msg.lower() or "401" in error_msg:
                error_msg = "API密钥无效或已过期。请检查config/config.yaml中的API密钥配置，或运行 python check_api_key.py 进行诊断。"
            elif "insufficient_quota" in error_msg.lower() or "429" in error_msg:
                error_msg = "API账户余额不足或达到速率限制。请检查账户余额或稍后重试。"
            
            logger.error(f"{provider_name}分析失败: {error_msg}")
            return AnalysisResult(
                summary=f"分析失败: {error_msg}",
                key_findings=[],
                research_trends=[],
                confidence_score=0.0,
                consistency_score=0.0,
                papers_analyzed=len(papers)
            )
    
    def _parse_analysis(self, text: str, paper_count: int) -> AnalysisResult:
        """
        解析AI返回的分析文本（支持JSON格式）
        
        Args:
            text: AI返回的文本
            paper_count: 分析的论文数量
        
        Returns:
            分析结果对象
        """
        # 首先尝试解析JSON格式
        try:
            # 尝试提取JSON
            text_clean = text.strip()
            if text_clean.startswith('{'):
                analysis_dict = json.loads(text_clean)
            else:
                # 尝试从文本中提取JSON
                start_idx = text_clean.find('{')
                if start_idx == -1:
                    raise ValueError("无法找到JSON格式")
                
                # 找到匹配的}
                brace_count = 0
                end_idx = start_idx
                for i in range(start_idx, len(text_clean)):
                    if text_clean[i] == '{':
                        brace_count += 1
                    elif text_clean[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                
                if brace_count == 0:
                    json_str = text_clean[start_idx:end_idx]
                    analysis_dict = json.loads(json_str)
                else:
                    raise ValueError("无法找到完整的JSON格式")
            
            # 从JSON中提取信息（支持新旧两种格式）
            # 新格式：5个部分结构
            section1 = analysis_dict.get('section1_research_intro', '')
            section2 = analysis_dict.get('section2_research_progress', '')
            section3 = analysis_dict.get('section3_research_status', '')
            section4 = analysis_dict.get('section4_existing_methods', '')
            section5 = analysis_dict.get('section5_future_development', '')
            
            # 旧格式（兼容）
            summary = analysis_dict.get('summary', '')
            key_findings = analysis_dict.get('key_findings', [])
            research_trends = analysis_dict.get('research_trends', [])
            
            # 如果使用新格式，将5个部分合并为summary
            if section1 and section2 and section3 and section4 and section5:
                summary = f"""# 研究介绍\n\n{section1}\n\n# 研究进展\n\n{section2}\n\n# 研究现状\n\n{section3}\n\n# 现有方法\n\n{section4}\n\n# 未来发展\n\n{section5}"""
                # 从各部分提取关键发现
                if not key_findings:
                    key_findings = [section1[:100] + "...", section3[:100] + "...", section4[:100] + "..."]
                if not research_trends:
                    research_trends = [section2[:100] + "...", section5[:100] + "..."]
            
            llm_confidence = analysis_dict.get('confidence')
            confidence_reason = analysis_dict.get('confidence_reason')
            conflicts = analysis_dict.get('conflicts', [])
            keywords = analysis_dict.get('keywords', [])
            
            # 确保keywords是列表格式
            if keywords and isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(',') if k.strip()]
            elif not keywords:
                keywords = []
            
            # 验证置信度范围
            if llm_confidence is not None:
                llm_confidence = max(0.0, min(1.0, float(llm_confidence)))
            
            # 提取子话题（如果JSON中包含）
            subtopics = analysis_dict.get('subtopics', [])
            if not isinstance(subtopics, list):
                subtopics = []
            
            return AnalysisResult(
                summary=summary.strip() if summary else '',
                key_findings=key_findings[:5] if isinstance(key_findings, list) else [],
                research_trends=research_trends[:3] if isinstance(research_trends, list) else [],
                confidence_score=llm_confidence if llm_confidence is not None else 0.7,
                consistency_score=0.7,  # 默认值，实际应该从验证模块获取
                papers_analyzed=paper_count,
                llm_confidence=llm_confidence,
                confidence_reason=confidence_reason,
                conflicts=conflicts if isinstance(conflicts, list) else [],
                section1_research_intro=section1.strip() if section1 else None,
                section2_research_progress=section2.strip() if section2 else None,
                section3_research_status=section3.strip() if section3 else None,
                section4_existing_methods=section4.strip() if section4 else None,
                section5_future_development=section5.strip() if section5 else None,
                subtopics=subtopics,
                keywords=keywords
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"JSON解析失败，使用文本解析: {str(e)}")
            logger.debug(f"响应内容: {text[:500]}")
            # 如果JSON解析失败，回退到文本解析
            return self._parse_analysis_text(text, paper_count)
    
    def _parse_analysis_text(self, text: str, paper_count: int) -> AnalysisResult:
        """
        文本格式解析（备用方法）
        
        Args:
            text: AI返回的文本
            paper_count: 分析的论文数量
        
        Returns:
            分析结果对象
        """
        lines = text.split('\n')
        
        summary = ""
        key_findings = []
        research_trends = []
        
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 识别章节
            if "综合总结" in line or "总结" in line:
                current_section = "summary"
                continue
            elif "关键发现" in line or "发现" in line:
                current_section = "findings"
                continue
            elif "研究趋势" in line or "趋势" in line:
                current_section = "trends"
                continue
            
            # 收集内容
            if current_section == "summary":
                summary += line + "\n"
            elif current_section == "findings":
                if line.startswith(("-", "•", "1.", "2.", "3.", "4.", "5.")):
                    key_findings.append(line.lstrip("- •1234567890.").strip())
            elif current_section == "trends":
                if line.startswith(("-", "•", "1.", "2.", "3.")):
                    research_trends.append(line.lstrip("- •1234567890.").strip())
        
        # 如果没有解析到内容，使用整个文本作为摘要
        if not summary:
            summary = text[:500]  # 截取前500字符
        
        return AnalysisResult(
            summary=summary.strip(),
            key_findings=key_findings[:5],  # 最多5个发现
            research_trends=research_trends[:3],  # 最多3个趋势
            confidence_score=0.7,  # 默认值
            consistency_score=0.7,  # 默认值
            papers_analyzed=paper_count,
            llm_confidence=None,
            confidence_reason=None,
            conflicts=[]
        )
