"""
BibTeX报告生成模块
将论文列表导出为BibTeX格式
"""

import re
from typing import List, Dict
from datetime import datetime
from loguru import logger

from ..utils.data_structures import Paper


class BibTeXGenerator:
    """BibTeX生成器"""
    
    def __init__(self):
        """初始化BibTeX生成器"""
        pass
    
    def generate(self, papers: List[Paper], output_path: str) -> str:
        """
        生成BibTeX文件
        
        Args:
            papers: 论文列表
            output_path: 输出文件路径
        
        Returns:
            生成的BibTeX内容
        """
        logger.info(f"开始生成BibTeX文件: {output_path}")
        
        bibtex_entries = []
        used_keys = set()  # 用于确保key唯一性
        
        for paper in papers:
            try:
                entry = self._paper_to_bibtex(paper, used_keys)
                if entry:
                    bibtex_entries.append(entry)
            except Exception as e:
                logger.warning(f"转换论文为BibTeX失败 {paper.title[:50]}: {str(e)}")
                continue
        
        # 组合所有条目
        bibtex_content = "\n\n".join(bibtex_entries)
        
        # 保存文件
        import os
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(bibtex_content)
        
        logger.info(f"BibTeX文件已保存: {output_path}，包含 {len(bibtex_entries)} 个条目")
        return bibtex_content
    
    def _paper_to_bibtex(self, paper: Paper, used_keys: set) -> str:
        """
        将Paper对象转换为BibTeX条目
        
        Args:
            paper: 论文对象
            used_keys: 已使用的key集合（用于确保唯一性）
        
        Returns:
            BibTeX条目字符串
        """
        # 确定entry类型
        entry_type = self._determine_entry_type(paper)
        
        # 生成唯一的key
        bibtex_key = self._generate_bibtex_key(paper, used_keys)
        used_keys.add(bibtex_key)
        
        # 构建字段
        fields = []
        
        # 标题（必需）
        if paper.title:
            fields.append(f"  title = {{{self._escape_latex(paper.title)}}}")
        
        # 作者（必需）
        if paper.authors:
            authors_str = self._format_authors(paper.authors)
            fields.append(f"  author = {{{authors_str}}}")
        
        # 年份
        if paper.publication_date:
            year = paper.publication_date.year
            fields.append(f"  year = {{{year}}}")
        elif paper.publication_date is None:
            # 尝试从其他信息推断年份
            year = self._extract_year_from_title(paper.title)
            if year:
                fields.append(f"  year = {{{year}}}")
        
        # URL
        if paper.url:
            fields.append(f"  url = {{{self._escape_latex(paper.url)}}}")
        
        # 摘要（如果有）
        if paper.abstract and len(paper.abstract.strip()) > 0:
            # 限制摘要长度，避免过长
            abstract_short = paper.abstract[:500] + "..." if len(paper.abstract) > 500 else paper.abstract
            fields.append(f"  abstract = {{{self._escape_latex(abstract_short)}}}")
        
        # 根据entry类型添加特定字段
        if entry_type == "article":
            # 对于article，尝试添加journal或eprint
            if paper.source == "arxiv":
                # arXiv论文使用eprint字段
                arxiv_id = self._extract_arxiv_id(paper.url) or self._extract_arxiv_id(paper.paper_id)
                if arxiv_id:
                    fields.append(f"  eprint = {{{arxiv_id}}}")
                    fields.append(f"  eprinttype = {{arXiv}}")
                else:
                    fields.append(f"  journal = {{arXiv preprint}}")
            else:
                # 其他来源，如果有venue信息可以添加
                # 这里暂时不添加，因为Paper对象可能没有venue字段
                pass
        elif entry_type == "inproceedings":
            # 对于会议论文，可以添加booktitle
            # 由于Paper对象可能没有会议名称，这里暂时不添加
            pass
        elif entry_type == "misc":
            # misc类型，可以添加note字段说明来源
            if paper.source:
                source_name = paper.source.replace('_', ' ').title()
                fields.append(f"  note = {{Source: {source_name}}}")
        
        # 添加注释字段（包含引用数等信息）
        note_parts = []
        if paper.citation_count:
            note_parts.append(f"Citations: {paper.citation_count}")
        if paper.source:
            note_parts.append(f"Source: {paper.source}")
        
        if note_parts:
            # 如果已经有note字段，合并；否则创建新字段
            existing_note = None
            for i, field in enumerate(fields):
                if field.startswith("  note ="):
                    existing_note = i
                    break
            
            if existing_note is not None:
                # 合并到现有note
                existing_value = fields[existing_note]
                # 提取现有值并合并
                note_content = ", ".join(note_parts)
                fields[existing_note] = f"  note = {{{existing_value.split('{{')[1].split('}}')[0]}, {note_content}}}"
            else:
                fields.append(f"  note = {{{', '.join(note_parts)}}}")
        
        # 组合BibTeX条目
        bibtex_entry = f"@{entry_type}{{{bibtex_key},\n"
        bibtex_entry += ",\n".join(fields)
        bibtex_entry += "\n}"
        
        return bibtex_entry
    
    def _determine_entry_type(self, paper: Paper) -> str:
        """
        根据论文来源确定BibTeX entry类型
        
        Args:
            paper: 论文对象
        
        Returns:
            entry类型字符串
        """
        source = paper.source.lower() if paper.source else ""
        
        if source == "arxiv":
            return "article"  # arXiv论文通常使用article
        elif source == "ieee_xplore":
            # IEEE可能是会议或期刊，默认使用inproceedings
            # 可以根据venue进一步判断，但Paper对象可能没有这个信息
            return "inproceedings"
        elif source == "pubmed":
            return "article"
        else:
            # 其他来源（如 uploaded 等）使用 misc
            return "misc"
    
    def _generate_bibtex_key(self, paper: Paper, used_keys: set) -> str:
        """
        生成BibTeX key
        
        格式：{第一作者姓氏}{年份}{标题首词}
        
        Args:
            paper: 论文对象
            used_keys: 已使用的key集合
        
        Returns:
            BibTeX key
        """
        # 提取第一作者姓氏
        author_part = "Author"
        if paper.authors and len(paper.authors) > 0:
            first_author = paper.authors[0]
            # 尝试提取姓氏（假设格式为"LastName, FirstName"或"FirstName LastName"）
            if ',' in first_author:
                # "LastName, FirstName"格式
                author_part = first_author.split(',')[0].strip()
            else:
                # "FirstName LastName"格式，取最后一个词作为姓氏
                name_parts = first_author.strip().split()
                if name_parts:
                    author_part = name_parts[-1]
        
        # 清理作者部分（只保留字母和数字）
        author_part = re.sub(r'[^a-zA-Z0-9]', '', author_part)
        if not author_part:
            author_part = "Author"
        
        # 提取年份
        year_part = ""
        if paper.publication_date:
            year_part = str(paper.publication_date.year)
        else:
            # 尝试从标题或其他地方提取年份
            year = self._extract_year_from_title(paper.title)
            if year:
                year_part = str(year)
        
        if not year_part:
            year_part = "0000"
        
        # 提取标题首词（去除常见停用词）
        title_part = "Paper"
        if paper.title:
            # 提取标题中的第一个有意义的词
            words = re.findall(r'\b[a-zA-Z]{3,}\b', paper.title)
            for word in words:
                # 跳过常见停用词
                if word.lower() not in ['the', 'a', 'an', 'and', 'or', 'but', 'for', 'with', 'from', 'using']:
                    title_part = word[:10]  # 最多10个字符
                    break
        
        # 组合key
        base_key = f"{author_part}{year_part}{title_part}"
        base_key = re.sub(r'[^a-zA-Z0-9]', '', base_key)
        
        # 确保唯一性
        key = base_key
        counter = 1
        while key in used_keys:
            key = f"{base_key}{counter}"
            counter += 1
        
        return key
    
    def _format_authors(self, authors: List[str]) -> str:
        """
        格式化作者列表为BibTeX格式
        
        BibTeX格式：Last, First and Last, First
        
        Args:
            authors: 作者列表
        
        Returns:
            格式化后的作者字符串
        """
        formatted_authors = []
        
        for author in authors:
            if not author or not author.strip():
                continue
            
            # 尝试判断格式
            if ',' in author:
                # 已经是"Last, First"格式
                formatted_authors.append(author.strip())
            else:
                # "First Last"格式，转换为"Last, First"
                name_parts = author.strip().split()
                if len(name_parts) >= 2:
                    # 有多个部分，假设最后一个是姓氏
                    last_name = name_parts[-1]
                    first_name = ' '.join(name_parts[:-1])
                    formatted_authors.append(f"{last_name}, {first_name}")
                else:
                    # 只有一个部分，直接使用
                    formatted_authors.append(author.strip())
        
        # 用 " and " 连接
        return " and ".join(formatted_authors)
    
    def _escape_latex(self, text: str) -> str:
        """
        转义LaTeX特殊字符
        
        Args:
            text: 要转义的文本
        
        Returns:
            转义后的文本
        """
        if not text:
            return ""
        
        # LaTeX特殊字符
        replacements = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '^': r'\^{}',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\~{}',
            '\\': r'\textbackslash{}',
        }
        
        # 按顺序替换（注意顺序很重要）
        result = text
        for char, replacement in replacements.items():
            result = result.replace(char, replacement)
        
        return result
    
    def _extract_year_from_title(self, title: str) -> int:
        """
        从标题中提取年份（备用方法）
        
        Args:
            title: 论文标题
        
        Returns:
            年份（如果找到），否则返回None
        """
        # 查找4位数字（可能是年份）
        year_match = re.search(r'\b(19|20)\d{2}\b', title)
        if year_match:
            try:
                return int(year_match.group())
            except:
                pass
        return None
    
    def _extract_arxiv_id(self, text: str) -> str:
        """
        从URL或ID中提取arXiv ID
        
        Args:
            text: 包含arXiv ID的文本
        
        Returns:
            arXiv ID（如果找到），否则返回None
        """
        if not text:
            return None
        
        # 匹配arXiv ID格式：arXiv:1234.5678 或 1234.5678
        arxiv_pattern = r'(?:arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)'
        match = re.search(arxiv_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None







