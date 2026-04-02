"""
PDF联想分析模块
从PDF中提取引用文献，识别重点文献，并生成拓展关键词
"""

import re
from typing import List, Dict, Optional, Tuple
from loguru import logger

from .pdf_parser import PDFParser
from .data_structures import Paper


class PDFAssociationAnalyzer:
    """PDF联想分析器"""
    
    def __init__(self, gpt_analyzer=None):
        """
        初始化PDF联想分析器
        
        Args:
            gpt_analyzer: GPT分析器实例（用于提取重点文献和生成关键词）
        """
        self.pdf_parser = PDFParser()
        self.gpt_analyzer = gpt_analyzer
    
    def extract_references(self, pdf_path: str) -> List[Dict[str, str]]:
        """
        从PDF中提取引用文献列表
        
        Args:
            pdf_path: PDF文件路径
        
        Returns:
            引用文献列表，每个文献包含title、authors等信息
        """
        try:
            # 提取PDF全文（重点关注参考文献部分）
            full_text = self.pdf_parser.extract_text(pdf_path, max_pages=100)  # 提取更多页以包含参考文献
            
            # 查找参考文献部分
            references_section = self._find_references_section(full_text)
            
            if not references_section:
                logger.warning("未找到参考文献部分")
                return []
            
            # 解析参考文献
            references = self._parse_references(references_section)
            
            logger.info(f"从PDF中提取到 {len(references)} 条引用文献")
            return references
            
        except Exception as e:
            logger.error(f"提取引用文献失败: {str(e)}")
            return []
    
    def _find_references_section(self, text: str) -> Optional[str]:
        """查找参考文献部分"""
        # 常见的参考文献标记
        reference_markers = [
            r'(?i)references\s*',
            r'(?i)bibliography\s*',
            r'(?i)works?\s+cited\s*',
            r'(?i)参考文献\s*',
            r'(?i)引用文献\s*',
        ]
        
        for marker in reference_markers:
            match = re.search(marker, text)
            if match:
                # 提取参考文献部分（从标记开始到文档结束）
                start_pos = match.end()
                return text[start_pos:]
        
        return None
    
    def _parse_references(self, references_text: str) -> List[Dict[str, str]]:
        """解析参考文献文本，提取文献信息"""
        references = []
        
        # 常见的参考文献格式
        # 格式1: [1] Author, Title, Journal, Year
        # 格式2: 1. Author, Title, Journal, Year
        # 格式3: Author (Year). Title. Journal.
        
        # 按行分割，每行通常是一篇参考文献
        lines = references_text.split('\n')
        
        for line in lines:
            line = line.strip()
            # 更严格的过滤条件：至少20个字符，且包含年份（通常是参考文献的特征）
            if not line or len(line) < 20:
                continue
            
            # 检查是否包含年份（参考文献通常有年份）
            has_year = bool(re.search(r'\b(19|20)\d{2}\b', line))
            if not has_year:
                # 如果没有年份，可能是其他内容，跳过
                continue
            
            # 移除行首的编号（如 [1], 1., (1) 等）
            line = re.sub(r'^[\[\(]?\d+[\)\]\.]\s*', '', line)
            
            # 跳过明显不是参考文献的行（如章节标题、图表说明等）
            if re.match(r'^(Figure|Table|Fig\.|Tab\.|Chapter|Section)', line, re.IGNORECASE):
                continue
            
            # 尝试提取标题和作者
            ref_info = self._extract_reference_info(line)
            if ref_info and ref_info.get('title'):
                # 进一步验证：标题不能太短（至少10个字符）
                if len(ref_info.get('title', '')) >= 10:
                    references.append(ref_info)
        
        return references
    
    def _extract_reference_info(self, ref_text: str) -> Optional[Dict[str, str]]:
        """从单条参考文献文本中提取信息"""
        try:
            # 简单的提取逻辑（可以后续优化）
            # 假设格式：Author, Title, Journal, Year
            
            # 尝试提取年份
            year_match = re.search(r'\b(19|20)\d{2}\b', ref_text)
            year = year_match.group() if year_match else None
            
            # 尝试提取作者（通常在开头，用逗号分隔）
            # 这是一个简化的提取，实际可能需要更复杂的解析
            parts = ref_text.split(',')
            authors = []
            title = ""
            
            if len(parts) >= 2:
                # 前几个部分可能是作者
                authors = [p.strip() for p in parts[:2] if p.strip()]
                # 后面的部分可能是标题
                if len(parts) >= 3:
                    title = parts[2].strip()
            
            if not title and len(parts) > 0:
                # 如果没有明确的标题，使用整个文本作为标题
                title = ref_text[:200]  # 限制长度
            
            if title:
                return {
                    'title': title,
                    'authors': authors,
                    'year': year,
                    'raw_text': ref_text
                }
        except Exception as e:
            logger.debug(f"解析参考文献失败: {str(e)}")
        
        return None
    
    def identify_key_references(self, references: List[Dict[str, str]], pdf_text: str, max_count: int = 10) -> List[Dict[str, str]]:
        """
        使用大模型识别重点引用文献
        
        Args:
            references: 引用文献列表
            pdf_text: PDF全文（用于上下文分析）
            max_count: 最多识别多少篇重点文献（默认10）
        
        Returns:
            重点文献列表
        """
        if not self.gpt_analyzer or not references:
            # 如果没有GPT分析器，返回前max_count条
            logger.warning(f"GPT分析器未配置，返回前{max_count}条引用文献作为重点文献")
            return references[:max_count]
        
        try:
            # 确保max_count在合理范围内
            max_count = max(1, min(max_count, 50))  # 限制在1-50之间
            
            # 构建提示词（限制数量，避免token过多，但确保包含完整信息）
            # 优先选择标题和作者信息完整的引用文献
            valid_references = [ref for ref in references if ref.get('title') and len(ref.get('title', '')) >= 15]
            if len(valid_references) < 20:
                # 如果有效文献不够，补充一些
                valid_references = references[:50]
            else:
                valid_references = valid_references[:50]
            
            references_text = "\n".join([
                f"{i+1}. 标题: {ref.get('title', '未知标题')} | 作者: {', '.join(ref.get('authors', []))} | 年份: {ref.get('year', '未知年份')}"
                for i, ref in enumerate(valid_references)
            ])
            
            prompt = f"""请分析以下论文的引用文献列表，识别出最重要的{max_count}篇重点文献。重点文献应该：
1. 与论文主题高度相关
2. 是论文方法或理论基础的重要来源
3. 在论文中被多次引用或详细讨论
4. 是该研究领域的经典或重要工作

## 论文内容摘要（前2000字）：
{pdf_text[:2000]}

## 引用文献列表：
{references_text}

请以JSON格式返回重点文献的详细信息（标题和作者），最多返回{max_count}篇，格式如下：
{{
  "key_references": [
    {{
      "title": "论文完整标题（必须与引用文献列表中的标题完全一致，不要截断）",
      "authors": ["作者1", "作者2", "作者3"]
    }},
    {{
      "title": "论文完整标题（必须与引用文献列表中的标题完全一致，不要截断）",
      "authors": ["作者1", "作者2"]
    }}
  ]
}}

**重要要求：**
- 必须返回**完整的、未截断的**论文标题
- 标题必须与引用文献列表中的标题**完全一致**（可以复制粘贴）
- 作者列表必须与引用文献列表中的作者**完全一致**
- 只返回JSON，不要有其他文字说明
- 不要截断标题，即使标题很长也要返回完整标题"""
            
            response = self.gpt_analyzer.client.chat.completions.create(
                model=self.gpt_analyzer.model,
                messages=[
                    {"role": "system", "content": "你是一位学术文献分析专家，擅长识别论文中的重点引用文献。请严格按照JSON格式返回结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,  # 增加token数量，确保能返回完整标题
                stream=False
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # 解析JSON响应
            import json
            import re
            try:
                # 尝试提取JSON（可能包含markdown代码块）
                if '```' in response_text:
                    # 提取代码块中的JSON（改进正则表达式，支持多行）
                    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(1).strip()
                    else:
                        # 如果没找到，尝试提取第一个{到最后一个}之间的内容
                        start_idx = response_text.find('{')
                        end_idx = response_text.rfind('}')
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            response_text = response_text[start_idx:end_idx+1]
                
                # 如果还不是JSON格式，尝试找到第一个{开始的内容
                if not response_text.startswith('{'):
                    start_idx = response_text.find('{')
                    if start_idx != -1:
                        # 找到匹配的}
                        brace_count = 0
                        end_idx = start_idx
                        for i in range(start_idx, len(response_text)):
                            if response_text[i] == '{':
                                brace_count += 1
                            elif response_text[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i
                                    break
                        if end_idx > start_idx:
                            response_text = response_text[start_idx:end_idx+1]
                
                if response_text.startswith('{'):
                    result = json.loads(response_text)
                    key_refs_data = result.get('key_references', [])
                    
                    # 直接使用DeepSeek推荐的文献信息（标题和作者）
                    key_references = []
                    for ref_data in key_refs_data:
                        if isinstance(ref_data, dict):
                            title = ref_data.get('title', '').strip()
                            authors = ref_data.get('authors', [])
                            if isinstance(authors, str):
                                # 如果authors是字符串，尝试分割
                                authors = [a.strip() for a in authors.split(',') if a.strip()]
                            elif not isinstance(authors, list):
                                authors = []
                            
                            if title:
                                key_references.append({
                                    'title': title,  # 使用完整标题，不要截断
                                    'authors': authors,
                                    'year': None,  # 年份可能不在推荐中
                                    'raw_text': f"{title} - {', '.join(authors) if authors else '未知作者'}"
                                })
                    
                    # 限制返回数量不超过max_count
                    key_references = key_references[:max_count]
                    logger.info(f"DeepSeek推荐了 {len(key_references)} 篇重点引用文献（最多{max_count}篇）")
                    return key_references
                else:
                    raise ValueError("响应不是有效的JSON格式")
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"解析DeepSeek推荐的重点文献失败: {str(e)}，返回前{max_count}条作为重点文献")
                logger.debug(f"原始响应: {response_text[:1000]}")
                return references[:max_count]
                
        except Exception as e:
            logger.error(f"识别重点引用文献失败: {str(e)}")
            return references[:max_count]  # 失败时返回前max_count条
    
    def identify_key_references_from_pdf(self, pdf_text: str, max_count: int = 10) -> List[Dict[str, str]]:
        """
        直接让DeepSeek分析PDF内容，识别重点引用文献（不依赖提取的引用文献列表）
        
        Args:
            pdf_text: PDF全文
            max_count: 最多识别多少篇重点文献（默认10）
        
        Returns:
            重点文献列表，每个包含title和authors
        """
        if not self.gpt_analyzer:
            logger.warning("GPT分析器未配置，无法识别重点引用文献")
            return []
        
        try:
            # 确保max_count在合理范围内
            max_count = max(1, min(max_count, 20))  # 限制在1-20之间
            
            # 提取PDF文本（尽可能多，但限制长度避免token过多）
            # 优先提取参考文献部分和正文部分
            pdf_content = pdf_text[:15000]  # 提取前15000字符，应该包含足够的信息
            
            prompt = f"""请仔细阅读以下论文内容，识别出这篇论文中引用的{max_count}篇最重要的文献。

这些重点文献应该：
1. 与论文主题高度相关
2. 是论文方法或理论基础的重要来源
3. 在论文中被多次引用或详细讨论
4. 是该研究领域的经典或重要工作

## 论文内容：
{pdf_content}

请从论文内容中找出{max_count}篇重点引用文献，并返回它们的**完整标题**和**作者列表**。

请以JSON格式返回，格式如下：
{{
  "key_references": [
    {{
      "title": "论文的完整标题（不要截断，必须完整）",
      "authors": ["作者1", "作者2", "作者3"]
    }},
    {{
      "title": "论文的完整标题（不要截断，必须完整）",
      "authors": ["作者1", "作者2"]
    }}
  ]
}}

**重要要求：**
- 必须返回**完整的、未截断的**论文标题
- 标题和作者必须是从论文内容中实际引用的文献
- 作者列表必须完整（至少包含第一作者和主要作者）
- 只返回JSON，不要有其他文字说明
- 不要截断标题，即使标题很长也要返回完整标题
- 最多返回{max_count}篇文献"""
            
            response = self.gpt_analyzer.client.chat.completions.create(
                model=self.gpt_analyzer.model,
                messages=[
                    {"role": "system", "content": "你是一位学术文献分析专家，擅长从论文内容中识别重点引用文献。请仔细阅读论文内容，找出其中引用的重要文献，并返回完整的标题和作者信息。请严格按照JSON格式返回结果，确保JSON完整（包含所有闭合括号）。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000,  # 增加token数量，确保能返回完整标题和作者列表
                stream=False
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # 解析JSON响应
            import json
            import re
            try:
                # 尝试提取JSON（可能包含markdown代码块）
                if '```' in response_text:
                    # 提取代码块中的JSON（改进正则表达式，支持多行）
                    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(1).strip()
                    else:
                        # 如果没找到，尝试提取第一个{到最后一个}之间的内容
                        start_idx = response_text.find('{')
                        end_idx = response_text.rfind('}')
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            response_text = response_text[start_idx:end_idx+1]
                
                # 如果还不是JSON格式，尝试找到第一个{开始的内容
                if not response_text.startswith('{'):
                    start_idx = response_text.find('{')
                    if start_idx != -1:
                        # 找到匹配的}
                        brace_count = 0
                        end_idx = start_idx
                        for i in range(start_idx, len(response_text)):
                            if response_text[i] == '{':
                                brace_count += 1
                            elif response_text[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i
                                    break
                        if end_idx > start_idx:
                            response_text = response_text[start_idx:end_idx+1]
                
                # 如果JSON不完整（缺少闭合括号），尝试修复
                if response_text.startswith('{'):
                    # 检查JSON是否完整
                    open_braces = response_text.count('{')
                    close_braces = response_text.count('}')
                    open_brackets = response_text.count('[')
                    close_brackets = response_text.count(']')
                    
                    # 如果缺少闭合括号，尝试补全
                    if open_braces > close_braces:
                        missing_braces = open_braces - close_braces
                        response_text += '}' * missing_braces
                    if open_brackets > close_brackets:
                        missing_brackets = open_brackets - close_brackets
                        # 在最后一个]之前插入缺失的]
                        last_close_brace = response_text.rfind('}')
                        if last_close_brace != -1:
                            response_text = response_text[:last_close_brace] + ']' * missing_brackets + response_text[last_close_brace:]
                    
                    try:
                        result = json.loads(response_text)
                        key_refs_data = result.get('key_references', [])
                    except json.JSONDecodeError:
                        # 如果修复后还是无法解析，尝试手动提取已返回的文献
                        logger.warning("JSON修复后仍无法解析，尝试手动提取已返回的文献...")
                        key_refs_data = []
                        # 使用正则表达式提取所有已返回的文献
                        pattern = r'\{\s*"title":\s*"([^"]+)",\s*"authors":\s*\[([^\]]+)\]\s*\}'
                        matches = re.findall(pattern, response_text, re.DOTALL)
                        for title, authors_str in matches:
                            # 解析作者列表
                            authors = [a.strip().strip('"') for a in authors_str.split(',') if a.strip()]
                            key_refs_data.append({'title': title, 'authors': authors})
                    
                    # 直接使用DeepSeek推荐的文献信息（标题和作者）
                    key_references = []
                    for ref_data in key_refs_data:
                        if isinstance(ref_data, dict):
                            title = ref_data.get('title', '').strip()
                            authors = ref_data.get('authors', [])
                            if isinstance(authors, str):
                                # 如果authors是字符串，尝试分割
                                authors = [a.strip() for a in authors.split(',') if a.strip()]
                            elif not isinstance(authors, list):
                                authors = []
                            
                            if title:
                                key_references.append({
                                    'title': title,  # 使用完整标题，不要截断
                                    'authors': authors,
                                    'year': None,  # 年份可能不在推荐中
                                    'raw_text': f"{title} - {', '.join(authors) if authors else '未知作者'}"
                                })
                    
                    # 限制返回数量不超过max_count
                    key_references = key_references[:max_count]
                    logger.info(f"DeepSeek从PDF中识别出 {len(key_references)} 篇重点引用文献（最多{max_count}篇）")
                    return key_references
                else:
                    raise ValueError("响应不是有效的JSON格式")
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"解析DeepSeek推荐的重点文献失败: {str(e)}")
                logger.debug(f"原始响应: {response_text[:2000]}")
                # 尝试最后一次手动提取
                try:
                    logger.info("尝试手动提取已返回的文献信息...")
                    key_refs_data = []
                    # 使用正则表达式提取所有已返回的文献
                    pattern = r'\{\s*"title":\s*"([^"]+)",\s*"authors":\s*\[([^\]]+)\]\s*\}'
                    matches = re.findall(pattern, response_text, re.DOTALL)
                    for title, authors_str in matches:
                        # 解析作者列表
                        authors = [a.strip().strip('"') for a in authors_str.split(',') if a.strip()]
                        if title:
                            key_refs_data.append({'title': title, 'authors': authors})
                    
                    if key_refs_data:
                        key_references = []
                        for ref_data in key_refs_data[:max_count]:
                            key_references.append({
                                'title': ref_data['title'],
                                'authors': ref_data['authors'],
                                'year': None,
                                'raw_text': f"{ref_data['title']} - {', '.join(ref_data['authors']) if ref_data['authors'] else '未知作者'}"
                            })
                        logger.info(f"手动提取出 {len(key_references)} 篇重点引用文献")
                        return key_references
                except Exception as e2:
                    logger.debug(f"手动提取也失败: {str(e2)}")
                return []
                
        except Exception as e:
            logger.error(f"识别重点引用文献失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return []
    
    def generate_expansion_keywords(self, pdf_text: str) -> List[str]:
        """
        根据PDF内容生成5个拓展关键词（使用DeepSeek推荐）
        
        Args:
            pdf_text: PDF全文
        
        Returns:
            关键词列表（5个）
        """
        if not self.gpt_analyzer:
            logger.warning("GPT分析器未配置，无法生成拓展关键词")
            return []
        
        try:
            prompt = f"""请根据以下论文内容，生成5个最适合用于搜索相关论文的英文关键词。这些关键词应该：
1. 能够有效匹配相关研究论文
2. 覆盖论文的主要研究主题和方法
3. 是学术研究中常用的术语
4. 使用英文（用于在学术数据库中搜索）

## 论文内容（前3000字）：
{pdf_text[:3000]}

请以JSON格式返回关键词，格式如下：
{{
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}

只返回JSON，不要有其他文字说明。"""
            
            response = self.gpt_analyzer.client.chat.completions.create(
                model=self.gpt_analyzer.model,
                messages=[
                    {"role": "system", "content": "你是一位学术搜索专家，擅长为研究主题生成有效的搜索关键词。请严格按照JSON格式返回结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200,
                stream=False
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # 解析JSON响应
            import json
            import re
            try:
                # 尝试提取JSON（可能包含markdown代码块）
                if '```' in response_text:
                    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(1).strip()
                    else:
                        start_idx = response_text.find('{')
                        end_idx = response_text.rfind('}')
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            response_text = response_text[start_idx:end_idx+1]
                
                if not response_text.startswith('{'):
                    start_idx = response_text.find('{')
                    if start_idx != -1:
                        brace_count = 0
                        end_idx = start_idx
                        for i in range(start_idx, len(response_text)):
                            if response_text[i] == '{':
                                brace_count += 1
                            elif response_text[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i
                                    break
                        if end_idx > start_idx:
                            response_text = response_text[start_idx:end_idx+1]
                
                if response_text.startswith('{'):
                    result = json.loads(response_text)
                    keywords = result.get('keywords', [])
                    if keywords and isinstance(keywords, list) and len(keywords) >= 3:
                        logger.info(f"DeepSeek生成拓展关键词: {keywords}")
                        return keywords[:5]  # 最多5个
                    else:
                        logger.warning("DeepSeek返回的关键词数量不足")
                        return []
                else:
                    logger.warning("DeepSeek返回格式不正确")
                    return []
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"解析DeepSeek推荐的关键词失败: {str(e)}")
                logger.debug(f"原始响应: {response_text[:500]}")
                return []
                
        except Exception as e:
            logger.error(f"生成拓展关键词失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return []
    
    def recommend_related_papers(self, pdf_text: str, max_count: int = 10) -> List[Dict[str, str]]:
        """
        使用DeepSeek直接推荐相关论文信息（标题和作者），而不是生成关键词
        
        Args:
            pdf_text: PDF全文
            max_count: 最多推荐多少篇论文（默认10）
        
        Returns:
            推荐论文列表，每个包含title和authors
        """
        if not self.gpt_analyzer:
            logger.warning("GPT分析器未配置，无法推荐相关论文")
            return []
        
        try:
            # 确保max_count在合理范围内
            max_count = max(1, min(max_count, 20))  # 限制在1-20之间
            
            prompt = f"""请根据以下论文内容，直接推荐{max_count}篇最相关的学术论文。这些论文应该：
1. 与当前论文的研究主题高度相关
2. 是该研究领域的重要或经典工作
3. 可能对理解当前论文有帮助
4. 是真实存在的学术论文（请基于论文内容推断，不要编造）

## 论文内容（前4000字）：
{pdf_text[:4000]}

请以JSON格式返回推荐的论文信息，格式如下：
{{
  "recommended_papers": [
    {{
      "title": "论文完整标题",
      "authors": ["作者1", "作者2", "作者3"]
    }},
    {{
      "title": "论文完整标题",
      "authors": ["作者1", "作者2"]
    }}
  ]
}}

注意：
- 必须返回完整的论文标题和作者列表
- 标题和作者应该是真实学术论文的格式
- 最多返回{max_count}篇论文
- 只返回JSON，不要有其他文字说明"""
            
            response = self.gpt_analyzer.client.chat.completions.create(
                model=self.gpt_analyzer.model,
                messages=[
                    {"role": "system", "content": "你是一位学术文献推荐专家，擅长根据论文内容推荐相关的学术论文。请严格按照JSON格式返回结果，只推荐真实存在的学术论文。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1000,
                stream=False
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # 解析JSON响应
            import json
            import re
            try:
                # 尝试提取JSON（可能包含markdown代码块）
                if '```' in response_text:
                    # 提取代码块中的JSON
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(1)
                
                if response_text.startswith('{'):
                    result = json.loads(response_text)
                    recommended_papers_data = result.get('recommended_papers', [])
                    
                    # 解析推荐的论文信息
                    recommended_papers = []
                    for paper_data in recommended_papers_data:
                        if isinstance(paper_data, dict):
                            title = paper_data.get('title', '').strip()
                            authors = paper_data.get('authors', [])
                            if isinstance(authors, str):
                                # 如果authors是字符串，尝试分割
                                authors = [a.strip() for a in authors.split(',') if a.strip()]
                            elif not isinstance(authors, list):
                                authors = []
                            
                            if title:
                                recommended_papers.append({
                                    'title': title,
                                    'authors': authors,
                                    'year': None,  # 年份可能不在推荐中
                                    'raw_text': f"{title} - {', '.join(authors) if authors else '未知作者'}"
                                })
                    
                    # 限制返回数量不超过max_count
                    recommended_papers = recommended_papers[:max_count]
                    logger.info(f"DeepSeek推荐了 {len(recommended_papers)} 篇相关论文（最多{max_count}篇）")
                    return recommended_papers
                else:
                    raise ValueError("响应不是有效的JSON格式")
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"解析DeepSeek推荐的论文失败: {str(e)}")
                logger.debug(f"原始响应: {response_text[:500]}")
                return []
                
        except Exception as e:
            logger.error(f"推荐相关论文失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return []

