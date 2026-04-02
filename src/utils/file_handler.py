"""
文件处理工具模块
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

from .data_structures import Paper, AnalysisResult


def ensure_dir(directory: str) -> None:
    """确保目录存在，不存在则创建"""
    Path(directory).mkdir(parents=True, exist_ok=True)


def save_papers_to_json(papers: List[Paper], filepath: str) -> None:
    """保存论文列表到JSON文件"""
    ensure_dir(os.path.dirname(filepath) if os.path.dirname(filepath) else ".")
    
    papers_data = []
    for paper in papers:
        papers_data.append({
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": paper.authors,
            "publication_date": paper.publication_date.isoformat() if paper.publication_date else None,
            "source": paper.source,
            "url": paper.url,
            "paper_id": paper.paper_id,
            "citation_count": paper.citation_count
        })
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(papers_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"已保存 {len(papers)} 篇论文到 {filepath}")


def load_papers_from_json(filepath: str) -> List[Paper]:
    """从JSON文件加载论文列表"""
    if not os.path.exists(filepath):
        logger.warning(f"文件不存在: {filepath}")
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        papers_data = json.load(f)
    
    papers = []
    for data in papers_data:
        from datetime import datetime
        pub_date = datetime.fromisoformat(data["publication_date"]) if data["publication_date"] else None
        paper = Paper(
            title=data["title"],
            abstract=data["abstract"],
            authors=data["authors"],
            publication_date=pub_date,
            source=data["source"],
            url=data["url"],
            paper_id=data["paper_id"],
            citation_count=data.get("citation_count")
        )
        papers.append(paper)
    
    logger.info(f"从 {filepath} 加载了 {len(papers)} 篇论文")
    return papers












