"""
免费翻译API模块
支持中英文互译，使用多个免费API作为备选
"""

import requests
from typing import Optional
from loguru import logger


class Translator:
    """翻译器类，支持多个免费API"""
    
    def __init__(self):
        """初始化翻译器"""
        self.apis = [
            self._translate_google,  # Google翻译（免费，无需API key）
            self._translate_baidu,   # 百度翻译（免费额度）
            self._translate_mymemory  # MyMemory翻译（免费）
        ]
    
    def detect_language(self, text: str) -> str:
        """
        检测文本语言
        
        Args:
            text: 待检测的文本
        
        Returns:
            'zh' 或 'en'
        """
        # 简单检测：如果包含中文字符，认为是中文
        import re
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        if chinese_pattern.search(text):
            return 'zh'
        return 'en'
    
    def translate(self, text: str, target_lang: str = 'en', source_lang: Optional[str] = None) -> Optional[str]:
        """
        翻译文本
        
        Args:
            text: 待翻译的文本
            target_lang: 目标语言 ('zh' 或 'en')
            source_lang: 源语言（如果为None则自动检测）
        
        Returns:
            翻译后的文本，如果失败返回None
        """
        if not text or not text.strip():
            return text
        
        # 自动检测源语言
        if source_lang is None:
            source_lang = self.detect_language(text)
        
        # 如果源语言和目标语言相同，直接返回
        if source_lang == target_lang:
            return text
        
        # 尝试使用各个API
        api_names = ['Google翻译', '百度翻译', 'MyMemory翻译']
        for i, (api_func, api_name) in enumerate(zip(self.apis, api_names)):
            try:
                result = api_func(text, source_lang, target_lang)
                if result and result != text:  # 确保翻译结果与原文不同
                    logger.info(f"{api_name}翻译成功: {text[:50]}... -> {result[:50]}...")
                    return result
                elif result == text:
                    logger.debug(f"{api_name}返回原文，继续尝试其他API")
            except Exception as e:
                logger.debug(f"{api_name}失败: {str(e)}")
                continue
        
        logger.warning(f"所有翻译API都失败，使用原文")
        return text
    
    def _translate_google(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """使用Google翻译（免费，无需API key）"""
        try:
            # 使用Google翻译的免费接口
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                'client': 'gtx',
                'sl': source_lang,
                'tl': target_lang,
                'dt': 't',
                'q': text
            }
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                result = response.json()
                if result and len(result) > 0 and len(result[0]) > 0:
                    translated = ''.join([item[0] for item in result[0] if item[0]])
                    return translated
        except Exception as e:
            logger.debug(f"Google翻译失败: {str(e)}")
        return None
    
    def _translate_baidu(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """使用百度翻译（需要API key，但这里使用免费接口）"""
        try:
            # 百度翻译免费接口（有限制）
            url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
            # 注意：这里需要API key，如果没有配置则跳过
            # 可以后续在config.yaml中配置
            return None
        except Exception as e:
            logger.debug(f"百度翻译失败: {str(e)}")
        return None
    
    def _translate_mymemory(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """使用MyMemory翻译（免费，有额度限制）"""
        try:
            url = "https://api.mymemory.translated.net/get"
            params = {
                'q': text,
                'langpair': f'{source_lang}|{target_lang}'
            }
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                result = response.json()
                if result.get('responseStatus') == 200:
                    translated = result.get('responseData', {}).get('translatedText')
                    if translated:
                        return translated
        except Exception as e:
            logger.debug(f"MyMemory翻译失败: {str(e)}")
        return None
    
    def translate_for_search(self, text: str) -> dict:
        """
        为搜索准备翻译文本
        
        Args:
            text: 原始搜索关键词
        
        Returns:
            {
                'original': 原文,
                'lang': 检测到的语言,
                'zh': 中文版本,
                'en': 英文版本
            }
        """
        lang = self.detect_language(text)
        
        result = {
            'original': text,
            'lang': lang,
            'zh': text if lang == 'zh' else None,
            'en': text if lang == 'en' else None
        }
        
        # 如果需要翻译
        if lang == 'zh':
            translated_en = self.translate(text, target_lang='en', source_lang='zh')
            result['en'] = translated_en if translated_en and translated_en != text else text
            # 如果翻译失败（返回原文），不记录为翻译成功
            if result['en'] == text:
                logger.debug(f"中文关键词无需翻译或翻译失败，使用原文: {text}")
        elif lang == 'en':
            translated_zh = self.translate(text, target_lang='zh', source_lang='en')
            result['zh'] = translated_zh if translated_zh and translated_zh != text else text
            # 如果翻译失败（返回原文），不记录为翻译成功
            if result['zh'] == text:
                logger.debug(f"英文关键词无需翻译或翻译失败，使用原文: {text}")
        
        return result



