"""
PDF论文解析模块
从PDF文件中提取论文信息（标题、作者、摘要等）
"""

import io
import re
import os
from typing import Optional, List, Dict
from datetime import datetime
from loguru import logger

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logger.warning("PyPDF2未安装，PDF解析功能不可用")

from ..utils.data_structures import Paper


class PDFParser:
    """PDF论文解析器"""
    
    def __init__(self):
        """初始化PDF解析器"""
        if not PYPDF2_AVAILABLE:
            raise ImportError("PyPDF2未安装，请运行: pip install PyPDF2")
    
    def extract_text(self, pdf_path: str, max_pages: int = 5) -> str:
        """
        从PDF中提取文本（前几页，通常包含标题、作者、摘要）
        
        Args:
            pdf_path: PDF文件路径
            max_pages: 最大提取页数（默认前5页）
        
        Returns:
            提取的文本
        """
        try:
            reader = PdfReader(pdf_path)
            text_parts = []
            
            # 提取前几页的文本
            for i, page in enumerate(reader.pages[:max_pages]):
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"提取PDF文本失败: {str(e)}")
            return ""

    def extract_text_from_bytes(self, pdf_bytes: bytes, max_pages: int = 5) -> str:
        """
        从 PDF 二进制内容提取前几页纯文本（与 extract_text 逻辑一致，供远程下载等场景复用）。
        """
        if not PYPDF2_AVAILABLE:
            return ""
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text_parts = []
            n = min(max_pages, len(reader.pages))
            for i in range(n):
                page = reader.pages[i]
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n".join(text_parts)
        except Exception as e:
            logger.debug(f"从字节提取 PDF 文本失败: {e}")
            return ""
    
    def parse_paper_info(self, pdf_path: str) -> Optional[Paper]:
        """
        从PDF文件中解析论文信息
        
        Args:
            pdf_path: PDF文件路径
        
        Returns:
            Paper对象，如果解析失败则返回None
        """
        try:
            # 提取文本
            text = self.extract_text(pdf_path, max_pages=5)
            if not text:
                logger.warning(f"无法从PDF中提取文本: {pdf_path}")
                return None
            
            # 解析标题（通常在文档开头，可能是最大字体或第一行）
            title = self._extract_title(text)
            
            # 解析作者
            authors = self._extract_authors(text)
            
            # 解析摘要
            abstract = self._extract_abstract(text)
            
            # 解析日期（尝试从文件名或文本中提取）
            publication_date = self._extract_date(text, pdf_path)
            
            # 生成论文ID（基于文件名）
            paper_id = os.path.splitext(os.path.basename(pdf_path))[0]
            
            if not title:
                # 如果无法提取标题，使用文件名
                title = os.path.splitext(os.path.basename(pdf_path))[0]
            
            return Paper(
                title=title,
                abstract=abstract or "摘要不可用",
                authors=authors,
                publication_date=publication_date,
                source="uploaded",
                url=pdf_path,  # 本地文件路径
                paper_id=f"uploaded_{paper_id}",
                citation_count=None
            )
        except Exception as e:
            logger.error(f"解析PDF论文信息失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return None
    
    def _extract_title(self, text: str) -> str:
        """提取标题"""
        lines = text.split('\n')
        
        # 尝试找到标题（通常是前几行中最长的一行，或包含特定关键词的行）
        title_candidates = []
        for i, line in enumerate(lines[:20]):  # 检查前20行
            line = line.strip()
            if not line:
                continue
            
            # 跳过明显的非标题行
            if any(skip in line.lower() for skip in ['abstract', 'introduction', 'keywords', 'doi:', 'http']):
                continue
            
            # 标题通常不会太长（少于200字符）
            if 10 <= len(line) <= 200:
                title_candidates.append((len(line), i, line))
        
        if title_candidates:
            # 选择最长的候选标题（通常是标题）
            title_candidates.sort(reverse=True, key=lambda x: x[0])
            return title_candidates[0][2]
        
        # 如果找不到，返回第一行非空文本
        for line in lines:
            line = line.strip()
            if line and len(line) > 5:
                return line
        
        return "未知标题"
    
    def _extract_authors(self, text: str) -> List[str]:
        """提取作者"""
        lines = text.split('\n')
        authors = []
        
        # 常见的作者模式
        author_patterns = [
            r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # 英文姓名
            r'([A-Z]\.[A-Z]\.\s+[A-Z][a-z]+)',  # 缩写形式
            r'([A-Z][a-z]+\s+et\s+al\.)',  # et al.
        ]
        
        # 在前20行中查找作者
        for line in lines[:20]:
            line = line.strip()
            if not line:
                continue
            
            # 跳过明显的非作者行
            if any(skip in line.lower() for skip in ['abstract', 'introduction', 'title', 'keywords']):
                continue
            
            # 尝试匹配作者模式
            for pattern in author_patterns:
                matches = re.findall(pattern, line)
                if matches:
                    # 处理 "et al." 情况
                    if 'et al' in line.lower():
                        # 提取 "et al." 之前的所有作者
                        before_et_al = line.split('et al')[0]
                        authors.extend(re.findall(pattern, before_et_al))
                        break
                    else:
                        authors.extend(matches)
                        break
        
        # 去重并清理
        unique_authors = []
        seen = set()
        for author in authors:
            author = author.strip()
            if author and author not in seen and len(author) > 2:
                seen.add(author)
                unique_authors.append(author)
        
        # 如果找到作者，返回前10个
        if unique_authors:
            return unique_authors[:10]
        
        return ["未知作者"]
    
    def _extract_abstract(self, text: str) -> str:
        """提取摘要"""
        # 查找 "Abstract" 或 "摘要" 关键词
        abstract_patterns = [
            r'(?i)abstract\s*:?\s*(.+?)(?=\n\s*(?:introduction|keywords|1\.|1\s+introduction|references))',
            r'(?i)摘要\s*:?\s*(.+?)(?=\n\s*(?:引言|关键词|1\.|1\s+引言|参考文献))',
        ]
        
        for pattern in abstract_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                abstract = match.group(1).strip()
                # 清理摘要（移除多余空白）
                abstract = re.sub(r'\s+', ' ', abstract)
                if len(abstract) > 50:  # 摘要应该有一定长度
                    return abstract[:2000]  # 限制长度
        
        # 如果找不到明确的摘要，尝试提取前几段文本作为摘要
        lines = text.split('\n')
        abstract_lines = []
        found_abstract = False
        
        for i, line in enumerate(lines[:50]):
            line = line.strip()
            if not line:
                continue
            
            # 查找 "Abstract" 标记
            if 'abstract' in line.lower() and not found_abstract:
                found_abstract = True
                continue
            
            if found_abstract:
                # 如果遇到新的章节（如 "Introduction"），停止
                if any(section in line.lower() for section in ['introduction', '1.', 'keywords', 'references']):
                    break
                abstract_lines.append(line)
        
        if abstract_lines:
            abstract = ' '.join(abstract_lines)
            return abstract[:2000]
        
        return ""
    
    def _extract_date(self, text: str, pdf_path: str) -> Optional[datetime]:
        """提取日期"""
        # 尝试从文件名中提取日期
        filename = os.path.basename(pdf_path)
        date_match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', filename)
        if date_match:
            try:
                year, month, day = map(int, date_match.groups())
                return datetime(year, month, day)
            except:
                pass
        
        # 尝试从文件名中提取年份
        year_match = re.search(r'(\d{4})', filename)
        if year_match:
            try:
                year = int(year_match.group(1))
                if 2000 <= year <= datetime.now().year:
                    return datetime(year, 1, 1)
            except:
                pass
        
        # 尝试从文本中提取日期
        date_patterns = [
            r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})',  # MM-DD-YYYY
            r'(\d{4})\s+年\s+(\d{1,2})\s+月',  # 中文日期
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text[:2000])  # 只在前2000字符中搜索
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 3:
                        if len(groups[0]) == 4:  # YYYY-MM-DD
                            year, month, day = map(int, groups)
                        else:  # MM-DD-YYYY
                            month, day, year = map(int, groups)
                        if 2000 <= year <= datetime.now().year and 1 <= month <= 12:
                            return datetime(year, month, min(day, 28))
                    elif len(groups) == 2:  # 中文日期
                        year, month = map(int, groups)
                        if 2000 <= year <= datetime.now().year and 1 <= month <= 12:
                            return datetime(year, month, 1)
                except:
                    continue
        
        # 如果找不到，返回当前日期
        return datetime.now()










