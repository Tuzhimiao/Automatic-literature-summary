"""
历史记录管理模块
用于保存和加载分析历史记录
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from loguru import logger


class HistoryManager:
    """历史记录管理器"""
    
    def __init__(self, history_dir: str = "history"):
        """
        初始化历史记录管理器
        
        Args:
            history_dir: 历史记录存储目录
        """
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(exist_ok=True)
        self.history_index_file = self.history_dir / "index.json"
        self._ensure_index_file()
    
    def _ensure_index_file(self):
        """确保索引文件存在"""
        if not self.history_index_file.exists():
            with open(self.history_index_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def save_history(
        self,
        topic: str,
        papers: List[Dict],
        analysis_result: Dict,
        validation_result: Dict,
        source_stats: Dict,
        reports: Dict
    ) -> str:
        """
        保存历史记录
        
        Args:
            topic: 研究主题
            papers: 论文列表
            analysis_result: 分析结果
            validation_result: 验证结果
            source_stats: 来源统计
            reports: 报告路径
        
        Returns:
            历史记录ID
        """
        try:
            # 生成历史记录ID（使用时间戳）
            record_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 精确到毫秒
            
            # 生成标题：搜索关键词_年月日_搜索时间
            safe_topic = topic.replace(' ', '_').replace('/', '_').replace('\\', '_')
            date_str = datetime.now().strftime("%Y%m%d")
            time_str = datetime.now().strftime("%H%M%S")
            title = f"{safe_topic}_{date_str}_{time_str}"
            
            # 创建历史记录数据
            history_data = {
                "id": record_id,
                "title": title,
                "topic": topic,
                "created_at": datetime.now().isoformat(),
                "papers": papers,
                "analysis": analysis_result,
                "validation": validation_result,
                "source_stats": source_stats,
                "reports": reports,
                "papers_count": len(papers)
            }
            
            # 保存历史记录文件
            history_file = self.history_dir / f"{record_id}.json"
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            
            # 更新索引文件
            self._add_to_index(record_id, title, topic, datetime.now().isoformat(), len(papers))
            
            logger.info(f"历史记录已保存: {title} (ID: {record_id})")
            return record_id
            
        except Exception as e:
            logger.error(f"保存历史记录失败: {str(e)}")
            raise
    
    def _add_to_index(self, record_id: str, title: str, topic: str, created_at: str, papers_count: int):
        """添加到索引文件"""
        try:
            with open(self.history_index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
            
            # 添加到开头（最新的在前面）
            index.insert(0, {
                "id": record_id,
                "title": title,
                "topic": topic,
                "created_at": created_at,
                "papers_count": papers_count
            })
            
            # 只保留最近1000条记录
            index = index[:1000]
            
            with open(self.history_index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"更新索引文件失败: {str(e)}")
    
    def get_history_list(self, limit: int = 100) -> List[Dict]:
        """
        获取历史记录列表
        
        Args:
            limit: 返回的最大记录数
        
        Returns:
            历史记录列表
        """
        try:
            with open(self.history_index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
            
            return index[:limit]
            
        except Exception as e:
            logger.error(f"读取历史记录列表失败: {str(e)}")
            return []
    
    def get_history(self, record_id: str) -> Optional[Dict]:
        """
        获取单条历史记录
        
        Args:
            record_id: 历史记录ID
        
        Returns:
            历史记录数据，如果不存在返回None
        """
        try:
            history_file = self.history_dir / f"{record_id}.json"
            if not history_file.exists():
                return None
            
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"读取历史记录失败: {str(e)}")
            return None
    
    def delete_history(self, record_id: str) -> bool:
        """
        删除历史记录
        
        Args:
            record_id: 历史记录ID
        
        Returns:
            是否删除成功
        """
        try:
            # 删除历史记录文件
            history_file = self.history_dir / f"{record_id}.json"
            if history_file.exists():
                history_file.unlink()
            
            # 从索引中删除
            with open(self.history_index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
            
            index = [item for item in index if item.get('id') != record_id]
            
            with open(self.history_index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            
            logger.info(f"历史记录已删除: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除历史记录失败: {str(e)}")
            return False







