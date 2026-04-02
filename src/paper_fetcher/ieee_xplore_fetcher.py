"""
IEEE Xplore论文检索模块
支持API和网页爬虫两种方式
优先使用API（如果配置了API密钥），否则使用网页爬虫
支持使用AI生成关键词优化搜索
"""

import requests
import json
import re
import time
from typing import List, Optional
from datetime import datetime
from loguru import logger
from urllib.parse import quote, urljoin

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    logger.warning("BeautifulSoup未安装，IEEE Xplore网页检索功能可能不可用。安装: pip install beautifulsoup4")

from ..utils.data_structures import Paper
from .ai_search_keywords import generate_search_keywords


class IeeeXploreFetcher:
    """IEEE Xplore论文检索器"""
    
    def __init__(
        self,
        max_results: int = 20,
        use_ai_keywords: bool = True,
        gpt_analyzer=None,
        api_key: Optional[str] = None,
        use_web_scraper: bool = True,
        fetch_fulltext: bool = False
    ):
        """
        初始化IEEE Xplore检索器
        
        Args:
            max_results: 最大返回结果数
            use_ai_keywords: 是否使用AI生成关键词（默认True）
            gpt_analyzer: GPT分析器实例（用于生成关键词）
            api_key: IEEE Xplore API密钥（可选，如果提供则优先使用API）
            use_web_scraper: 如果没有API密钥，是否使用网页爬虫（默认True）
            fetch_fulltext: 是否获取全文（默认False，获取全文需要访问详情页，速度较慢）
        """
        self.max_results = max_results
        self.use_ai_keywords = use_ai_keywords
        self.gpt_analyzer = gpt_analyzer
        self.api_key = api_key
        self.use_web_scraper = use_web_scraper
        self.fetch_fulltext = fetch_fulltext
        
        # IEEE Xplore API配置
        self.api_base_url = "https://ieeexploreapi.ieee.org/api/v1"
        
        # IEEE Xplore网页配置
        self.base_url = "https://ieeexplore.ieee.org"
        self.search_url = "https://ieeexplore.ieee.org/search/searchresult.jsp"
        
        # 模拟浏览器请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://ieeexplore.ieee.org/',
        }
        
        # 决定使用哪种方式
        self.use_api = bool(api_key and api_key.strip() and api_key != 'null')
        
        if self.use_api:
            logger.info("IEEE Xplore检索器：使用API模式（需要API密钥）")
        elif use_web_scraper:
            logger.info("IEEE Xplore检索器：使用网页爬虫模式（不需要API密钥）")
        else:
            logger.warning("IEEE Xplore检索器：未配置API密钥且未启用网页爬虫，功能可能受限")
    
    def _search_via_api(self, query: str, max_results: int, start_year: Optional[int] = None, end_year: Optional[int] = None) -> List[Paper]:
        """
        通过IEEE Xplore API搜索论文
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
            start_year: 起始年份
            end_year: 结束年份
        
        Returns:
            论文列表
        """
        if not self.api_key:
            return []
        
        try:
            logger.info(f"使用IEEE Xplore API搜索: {query}")
            
            all_papers = []
            start_record = 1
            records_per_page = min(200, max_results)  # IEEE API最多返回200条
            
            while len(all_papers) < max_results:
                params = {
                    'apikey': self.api_key,
                    'querytext': query,
                    'format': 'json',
                    'max_records': records_per_page,
                    'start_record': start_record,
                    'sort_order': 'desc',
                    'sort_field': 'article_title'
                }
                
                # 添加年份过滤
                if start_year or end_year:
                    year_filter = []
                    if start_year:
                        year_filter.append(f"publication_year:{start_year}")
                    if end_year:
                        year_filter.append(f"publication_year:{end_year}")
                    if year_filter:
                        params['querytext'] = f"{query} AND ({' AND '.join(year_filter)})"
                
                response = requests.get(
                    f"{self.api_base_url}/search/articles",
                    params=params,
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.error(f"IEEE Xplore API返回错误: {response.status_code}")
                    break
                
                data = response.json()
                
                if 'articles' not in data or not data['articles']:
                    logger.debug("没有更多结果")
                    break
                
                articles = data['articles']
                
                for article in articles:
                    try:
                        # 提取标题
                        title = article.get('title', '').strip()
                        if not title:
                            continue
                        
                        # 提取摘要
                        abstract = article.get('abstract', '').strip()
                        if not abstract:
                            abstract = "摘要不可用"
                        
                        # 提取作者
                        authors = []
                        if 'authors' in article and article['authors']:
                            for author in article['authors']:
                                if isinstance(author, dict):
                                    author_name = author.get('fullName', '') or author.get('firstName', '') + ' ' + author.get('lastName', '')
                                    if author_name.strip():
                                        authors.append(author_name.strip())
                                elif isinstance(author, str):
                                    authors.append(author)
                        
                        # 提取年份
                        pub_date = None
                        year = article.get('publicationYear') or article.get('year')
                        if year:
                            try:
                                year_int = int(year)
                                if start_year and year_int < start_year:
                                    continue
                                if end_year and year_int > end_year:
                                    continue
                                pub_date = datetime(year_int, 1, 1)
                            except (ValueError, TypeError):
                                pass
                        
                        # 提取URL
                        url = article.get('htmlUrl', '') or article.get('pdfUrl', '')
                        if url and not url.startswith('http'):
                            url = urljoin(self.base_url, url)
                        if not url:
                            # 构建URL
                            article_number = article.get('articleNumber') or article.get('id')
                            if article_number:
                                url = f"{self.base_url}/document/{article_number}"
                        
                        # 提取引用数
                        citation_count = article.get('citationCount') or article.get('citingPaperCount')
                        
                        # 如果启用全文获取，尝试获取全文
                        if self.fetch_fulltext and url:
                            try:
                                fulltext = self._fetch_article_fulltext(url, article.get('articleNumber') or article.get('id'))
                                if fulltext:
                                    # 将全文添加到摘要后面
                                    abstract = abstract + "\n\n[全文内容]\n" + fulltext[:5000]  # 限制长度
                                    logger.debug(f"成功获取全文: {title[:50]}...")
                            except Exception as e:
                                logger.debug(f"获取全文失败: {str(e)}")
                        
                        # 创建Paper对象
                        paper = Paper(
                            title=title,
                            abstract=abstract,
                            authors=authors,
                            publication_date=pub_date,
                            source="ieee_xplore",
                            url=url,
                            paper_id=article.get('articleNumber') or article.get('id') or title,
                            citation_count=citation_count
                        )
                        
                        all_papers.append(paper)
                        
                        if len(all_papers) >= max_results:
                            break
                    
                    except Exception as e:
                        logger.debug(f"解析IEEE API论文数据失败: {str(e)}")
                        continue
                
                # 检查是否还有更多结果
                total_found = data.get('totalRecords', 0)
                if start_record + len(articles) >= total_found or len(articles) < records_per_page:
                    break
                
                start_record += len(articles)
                
                # API速率限制，添加延迟
                time.sleep(0.5)
            
            logger.info(f"IEEE Xplore API检索到 {len(all_papers)} 篇论文")
            return all_papers[:max_results]
            
        except Exception as e:
            logger.error(f"IEEE Xplore API搜索失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return []
    
    def _fetch_search_page(self, query: str, page: int = 1) -> Optional[requests.Response]:
        """
        获取IEEE Xplore搜索页面（使用POST请求，参考CSDN博客方法）
        
        Args:
            query: 搜索关键词
            page: 页码（从1开始）
        
        Returns:
            Response对象或None
        """
        try:
            # IEEE Xplore使用POST请求，参考：https://blog.csdn.net/wp7xtj98/article/details/112711465
            # POST URL: https://ieeexplore.ieee.org/rest/search
            post_url = "https://ieeexplore.ieee.org/rest/search"
            
            # 更新headers，添加必要的Referer
            post_headers = self.headers.copy()
            post_headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/plain, */*',
                'Referer': f'https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText={quote(query)}',
                'Origin': 'https://ieeexplore.ieee.org'
            })
            
            # POST请求的data（JSON格式）
            post_data = {
                'queryText': query,
                'newsearch': True,
                'pageNumber': page,
                'rowsPerPage': 25,  # 每页25条
                'searchWithin': [],
                'refinements': [],
                'sortType': 'relevance',
                'matchBoolean': True
            }
            
            logger.debug(f"正在使用POST请求获取IEEE Xplore搜索: query={query}, page={page}")
            
            response = requests.post(
                post_url,
                json=post_data,  # 使用json参数自动设置Content-Type和序列化
                headers=post_headers,
                timeout=30
            )
            
            # 检查响应状态
            if response.status_code == 200:
                # POST请求通常返回JSON格式
                try:
                    json_data = response.json()
                    logger.debug(f"IEEE Xplore POST请求成功，返回JSON数据，包含 {len(json_data.get('records', []))} 条记录")
                except (ValueError, json.JSONDecodeError):
                    logger.debug(f"IEEE Xplore返回非JSON格式，可能是HTML")
                return response
            elif response.status_code == 403:
                logger.error(f"IEEE Xplore返回403禁止访问，可能需要登录或验证")
                return None
            elif response.status_code == 429:
                logger.warning(f"IEEE Xplore返回429速率限制，等待后重试...")
                time.sleep(5)
                return None
            else:
                logger.warning(f"IEEE Xplore返回状态码: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"请求IEEE Xplore超时")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"请求IEEE Xplore失败: {str(e)}")
            return None
    
    def _parse_search_results(self, response: requests.Response) -> List[dict]:
        """
        解析IEEE Xplore搜索结果（支持JSON和HTML两种格式）
        
        Args:
            response: Response对象（可能是JSON或HTML）
        
        Returns:
            论文信息列表
        """
        papers = []
        
        try:
            # 首先尝试解析为JSON（POST请求通常返回JSON）
            try:
                json_data = response.json()
                logger.debug(f"检测到JSON响应，开始解析JSON数据")
                
                # 解析JSON格式的搜索结果
                if 'records' in json_data:
                    records = json_data['records']
                    logger.info(f"从JSON中找到 {len(records)} 条记录")
                    
                    for record in records:
                        try:
                            paper_info = {}
                            
                            # 提取标题
                            paper_info['title'] = record.get('articleTitle', '').strip()
                            if not paper_info['title']:
                                continue
                            
                            # 提取摘要
                            paper_info['abstract'] = record.get('abstract', '').strip()
                            if not paper_info['abstract']:
                                paper_info['abstract'] = "摘要不可用"
                            
                            # 提取作者
                            authors = []
                            if 'authors' in record and record['authors']:
                                for author in record['authors']:
                                    if isinstance(author, dict):
                                        author_name = author.get('preferredName', '') or author.get('fullName', '')
                                        if author_name:
                                            authors.append(author_name.strip())
                                    elif isinstance(author, str):
                                        authors.append(author)
                            paper_info['authors'] = authors
                            
                            # 提取年份
                            year = record.get('publicationYear') or record.get('year')
                            if year:
                                try:
                                    paper_info['year'] = int(year)
                                except (ValueError, TypeError):
                                    paper_info['year'] = None
                            else:
                                paper_info['year'] = None
                            
                            # 提取URL
                            article_number = record.get('articleNumber') or record.get('id')
                            if article_number:
                                paper_info['url'] = f"{self.base_url}/document/{article_number}"
                            else:
                                paper_info['url'] = ''
                            
                            # 提取引用数
                            paper_info['citation_count'] = record.get('citationCount') or record.get('citingPaperCount')
                            
                            # 如果启用全文获取，尝试获取全文
                            if self.fetch_fulltext and paper_info.get('url'):
                                try:
                                    fulltext = self._fetch_article_fulltext(paper_info['url'], article_number)
                                    if fulltext:
                                        # 将全文添加到摘要后面
                                        original_abstract = paper_info.get('abstract', '')
                                        paper_info['abstract'] = original_abstract + "\n\n[全文内容]\n" + fulltext[:5000]  # 限制长度
                                        logger.debug(f"成功获取全文: {paper_info['title'][:50]}...")
                                except Exception as e:
                                    logger.debug(f"获取全文失败: {str(e)}")
                            
                            papers.append(paper_info)
                        except Exception as e:
                            logger.debug(f"解析JSON记录失败: {str(e)}")
                            continue
                    
                    return papers
                
            except (ValueError, json.JSONDecodeError):
                # 不是JSON格式，尝试解析HTML
                logger.debug(f"不是JSON格式，尝试解析HTML")
                pass
        
        except Exception as e:
            logger.debug(f"JSON解析失败，尝试HTML解析: {str(e)}")
        
        # 如果JSON解析失败，尝试HTML解析
        if not BEAUTIFULSOUP_AVAILABLE:
            logger.error("BeautifulSoup未安装，无法解析HTML")
            return papers
        
        try:
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # IEEE Xplore的搜索结果通常在特定的容器中
            # 常见的选择器：
            # - 论文卡片: .List-results-items, .search-result-item
            # - 论文标题: h3 a 或 .result-item-title
            # - 摘要: .abstract-text
            
            paper_elements = []
            
            # 尝试多种选择器
            selectors = [
                '.List-results-items li',
                '.search-result-item',
                '.result-item',
                'li[data-article-number]',
                'article.result-item',
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    paper_elements = elements
                    logger.debug(f"使用选择器 '{selector}' 找到 {len(elements)} 个结果")
                    break
            
            # 如果没找到，尝试查找所有包含论文链接的元素
            if not paper_elements:
                # 查找所有包含IEEE文档链接的元素
                all_links = soup.find_all('a', href=re.compile(r'/document/'))
                if all_links:
                    # 找到这些链接的父元素
                    paper_elements = []
                    seen = set()
                    for link in all_links:
                        parent = link.find_parent(['li', 'div', 'article'])
                        if parent and id(parent) not in seen:
                            paper_elements.append(parent)
                            seen.add(id(parent))
                    logger.debug(f"通过链接找到 {len(paper_elements)} 个可能的论文元素")
            
            for element in paper_elements:
                try:
                    paper_info = {}
                    
                    # 提取标题和URL
                    title_elem = element.find('h3') or element.find('h2') or element.find('a', class_=re.compile(r'.*title.*', re.I))
                    if not title_elem:
                        # 尝试查找包含/document/的链接
                        link = element.find('a', href=re.compile(r'/document/'))
                        if link:
                            title_elem = link
                    
                    if title_elem:
                        if title_elem.name == 'a':
                            title = title_elem.get_text(strip=True)
                            href = title_elem.get('href', '')
                        else:
                            title = title_elem.get_text(strip=True)
                            link = element.find('a', href=re.compile(r'/document/'))
                            href = link.get('href', '') if link else ''
                        
                        if title:
                            paper_info['title'] = title
                            
                            if href:
                                if href.startswith('/'):
                                    paper_info['url'] = urljoin(self.base_url, href)
                                else:
                                    paper_info['url'] = href
                            else:
                                paper_info['url'] = ''
                        else:
                            continue
                    else:
                        continue  # 没有标题，跳过
                    
                    # 提取摘要
                    abstract_elem = element.find(['div', 'p', 'span'], class_=re.compile(r'.*abstract.*', re.I))
                    if not abstract_elem:
                        abstract_elem = element.find('div', class_=re.compile(r'.*snippet.*|.*description.*', re.I))
                    
                    if abstract_elem:
                        abstract = abstract_elem.get_text(strip=True)
                        # 限制摘要长度
                        if len(abstract) > 500:
                            abstract = abstract[:500] + '...'
                        paper_info['abstract'] = abstract
                    else:
                        paper_info['abstract'] = "摘要不可用"
                    
                    # 提取作者
                    authors = []
                    author_elems = element.find_all('a', class_=re.compile(r'.*author.*', re.I))
                    if not author_elems:
                        # 尝试查找包含作者信息的span或div
                        author_spans = element.find_all(['span', 'div'], class_=re.compile(r'.*author.*', re.I))
                        for span in author_spans:
                            author_text = span.get_text(strip=True)
                            # 可能是多个作者，用逗号或分号分隔
                            if author_text:
                                authors.extend([a.strip() for a in re.split(r'[,;]', author_text) if a.strip()])
                    else:
                        for author_elem in author_elems:
                            author_name = author_elem.get_text(strip=True)
                            if author_name:
                                authors.append(author_name)
                    
                    paper_info['authors'] = authors[:10]  # 限制作者数量
                    
                    # 提取年份
                    year = None
                    year_elem = element.find(string=re.compile(r'\b(19|20)\d{2}\b'))
                    if year_elem:
                        year_match = re.search(r'\b(19|20)\d{2}\b', year_elem)
                        if year_match:
                            try:
                                year = int(year_match.group())
                            except ValueError:
                                pass
                    
                    paper_info['year'] = year
                    
                    # 提取引用数（如果有）
                    citation_elem = element.find(string=re.compile(r'\d+\s*citation', re.I))
                    if citation_elem:
                        citation_match = re.search(r'(\d+)\s*citation', citation_elem, re.I)
                        if citation_match:
                            try:
                                paper_info['citation_count'] = int(citation_match.group(1))
                            except ValueError:
                                pass
                    
                    if paper_info.get('title'):
                        papers.append(paper_info)
                
                except Exception as e:
                    logger.debug(f"解析论文元素失败: {str(e)}")
                    continue
            
            logger.info(f"从HTML中解析到 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            logger.error(f"解析IEEE Xplore搜索结果失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return []
    
    def _search_via_web(self, query: str, max_results: int, start_year: Optional[int] = None, end_year: Optional[int] = None) -> List[Paper]:
        """
        通过网页爬虫搜索IEEE Xplore论文
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
            start_year: 起始年份
            end_year: 结束年份
        
        Returns:
            论文列表
        """
        if not BEAUTIFULSOUP_AVAILABLE:
            logger.error("BeautifulSoup未安装，无法使用IEEE Xplore网页检索功能")
            return []
        
        try:
            logger.info(f"使用IEEE Xplore网页爬虫搜索: {query}")
            
            all_papers = []
            seen_titles = set()
            page = 1
            max_pages = 5  # 最多爬取5页
            
            while len(all_papers) < max_results and page <= max_pages:
                # 获取搜索页面
                response = self._fetch_search_page(query, page)
                if not response:
                    logger.warning(f"无法获取第{page}页，停止翻页")
                    break
                
                # 解析搜索结果（支持JSON和HTML）
                papers_data = self._parse_search_results(response)
                
                if not papers_data:
                    logger.debug(f"第{page}页没有找到论文，停止翻页")
                    break
                
                # 转换为Paper对象并过滤
                for paper_data in papers_data:
                    try:
                        title = paper_data.get('title', '')
                        if not title or title in seen_titles:
                            continue
                        seen_titles.add(title)
                        
                        # 检查年份
                        year = paper_data.get('year')
                        if year:
                            if start_year and year < start_year:
                                continue
                            if end_year and year > end_year:
                                continue
                            pub_date = datetime(year, 1, 1)
                        else:
                            pub_date = None
                        
                        # 如果启用全文获取，尝试获取全文
                        abstract = paper_data.get('abstract', '摘要不可用')
                        if self.fetch_fulltext and paper_data.get('url'):
                            try:
                                fulltext = self._fetch_article_fulltext(paper_data['url'])
                                if fulltext:
                                    # 将全文添加到摘要后面
                                    abstract = abstract + "\n\n[全文内容]\n" + fulltext[:5000]  # 限制长度
                                    logger.debug(f"成功获取全文: {title[:50]}...")
                            except Exception as e:
                                logger.debug(f"获取全文失败: {str(e)}")
                        
                        # 创建Paper对象
                        paper = Paper(
                            title=title,
                            abstract=abstract,
                            authors=paper_data.get('authors', []),
                            publication_date=pub_date,
                            source="ieee_xplore_web",
                            url=paper_data.get('url', f"{self.search_url}?queryText={quote(query)}"),
                            paper_id=title,
                            citation_count=paper_data.get('citation_count')
                        )
                        
                        all_papers.append(paper)
                        
                        if len(all_papers) >= max_results:
                            break
                    
                    except Exception as e:
                        logger.debug(f"创建Paper对象失败: {str(e)}")
                        continue
                
                if len(all_papers) >= max_results:
                    break
                
                page += 1
                # 添加延迟，避免请求过快
                time.sleep(2)
            
            logger.info(f"IEEE Xplore网页爬虫检索到 {len(all_papers)} 篇论文")
            return all_papers[:max_results]
            
        except Exception as e:
            logger.error(f"IEEE Xplore网页爬虫检索失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return []
    
    def search_exact_title(self, exact_title: str, max_results: int = 3) -> List[Paper]:
        """
        精确匹配标题搜索（不使用AI关键词生成）
        专门用于搜索完整标题，例如从PDF引用文献中提取的重点文献
        
        Args:
            exact_title: 完整的论文标题（可能包含引号）
            max_results: 最大返回结果数（默认3，因为精确匹配通常只需要少量结果）
        
        Returns:
            论文列表
        """
        try:
            # 移除可能存在的引号（如果用户已经加了引号）
            clean_title = exact_title.strip().strip('"').strip("'")
            logger.info(f"IEEE Xplore精确匹配标题搜索: {clean_title[:60]}...")
            
            # 直接调用内部搜索方法，不使用AI关键词生成
            if self.use_api:
                papers = self._search_via_api(clean_title, max_results, start_year=None, end_year=None)
            elif self.use_web_scraper:
                papers = self._search_via_web(clean_title, max_results, start_year=None, end_year=None)
            else:
                logger.warning("未配置API密钥且未启用网页爬虫，无法搜索")
                return []
            
            logger.info(f"IEEE Xplore精确匹配标题搜索完成，找到 {len(papers)} 篇论文")
            return papers[:max_results]
            
        except Exception as e:
            logger.error(f"IEEE Xplore精确匹配标题搜索失败: {str(e)}")
            return []
    
    def search_papers(
        self,
        query: str,
        max_results: Optional[int] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        sort_by: str = "relevance"
    ) -> List[Paper]:
        """
        搜索论文
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数（如果为None则使用初始化时的值）
            start_year: 起始年份
            end_year: 结束年份
            sort_by: 排序方式
        
        Returns:
            论文列表
        """
        max_results = max_results or self.max_results
        
        # 设置默认年份范围
        if start_year is None:
            start_year = 2023
        if end_year is None:
            end_year = datetime.now().year
        
        try:
            logger.info(f"开始从IEEE Xplore搜索: {query} (限制在{start_year}-{end_year}年)")
            
            search_keywords = [query]
            if self.use_ai_keywords and self.gpt_analyzer:
                logger.info("使用 AI 生成搜索关键词（统一模块）...")
                search_keywords = generate_search_keywords(self.gpt_analyzer, query)
                logger.info(f"将使用以下关键词搜索: {search_keywords}")
            
            # 使用多个关键词进行搜索，合并结果
            all_papers = []
            seen_titles = set()
            
            for keyword in search_keywords:
                # 根据配置选择使用API还是网页爬虫
                if self.use_api:
                    keyword_papers = self._search_via_api(keyword, max_results // len(search_keywords) + 5, start_year, end_year)
                elif self.use_web_scraper:
                    keyword_papers = self._search_via_web(keyword, max_results // len(search_keywords) + 5, start_year, end_year)
                else:
                    logger.warning("未配置API密钥且未启用网页爬虫，跳过IEEE Xplore搜索")
                    continue
                
                # 去重
                for paper in keyword_papers:
                    if paper.title not in seen_titles:
                        seen_titles.add(paper.title)
                        all_papers.append(paper)
                        
                        if len(all_papers) >= max_results:
                            break
                
                if len(all_papers) >= max_results:
                    break
            
            # 确保不超过最大数量
            all_papers = all_papers[:max_results]
            
            logger.info(f"成功检索到 {len(all_papers)} 篇论文（{start_year}-{end_year}年，使用{len(search_keywords)}个关键词）")
            return all_papers
            
        except Exception as e:
            logger.error(f"IEEE Xplore检索失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return []
    
    def _fetch_article_fulltext(self, article_url: str, article_number: Optional[str] = None) -> Optional[str]:
        """
        从IEEE Xplore论文详情页获取全文内容
        
        Args:
            article_url: 论文详情页URL
            article_number: 论文编号（可选，用于构建URL）
        
        Returns:
            提取的文本内容，如果失败返回None
        """
        try:
            # 如果没有URL，尝试构建
            if not article_url and article_number:
                article_url = f"{self.base_url}/document/{article_number}"
            
            if not article_url:
                return None
            
            logger.debug(f"正在获取IEEE论文全文: {article_url}")
            
            # 访问论文详情页
            response = requests.get(
                article_url,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.debug(f"无法访问论文详情页: {response.status_code}")
                return None
            
            # 解析HTML提取全文
            if not BEAUTIFULSOUP_AVAILABLE:
                logger.warning("BeautifulSoup未安装，无法提取全文")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尝试多种方式提取全文内容
            fulltext_parts = []
            
            # 方法1: 查找包含全文的div（常见的选择器）
            content_selectors = [
                '.article-content',
                '.article-body',
                '.full-text',
                '#article-content',
                '#article-body',
                '.document-content',
                'div[class*="content"]',
                'div[class*="article"]',
                'div[class*="text"]',
            ]
            
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    for elem in elements:
                        text = elem.get_text(separator=' ', strip=True)
                        if len(text) > 200:  # 确保是有效内容
                            fulltext_parts.append(text)
                            logger.debug(f"使用选择器 '{selector}' 找到全文内容")
                    if fulltext_parts:
                        break
            
            # 方法2: 如果没找到，尝试查找所有段落
            if not fulltext_parts:
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 50:  # 过滤太短的段落
                        fulltext_parts.append(text)
                
                if fulltext_parts:
                    logger.debug(f"通过段落找到全文内容")
            
            # 方法3: 尝试从JavaScript中提取（参考CSDN博客的方法）
            if not fulltext_parts:
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        # 查找包含全文的JavaScript变量
                        # IEEE有时会将全文内容放在JavaScript变量中
                        text_match = re.search(r'xplGlobal\.document\.metadata\s*=\s*({.*?});', script.string, re.DOTALL)
                        if text_match:
                            try:
                                metadata = json.loads(text_match.group(1))
                                if 'abstract' in metadata:
                                    fulltext_parts.append(metadata['abstract'])
                                if 'fullText' in metadata:
                                    fulltext_parts.append(metadata['fullText'])
                            except:
                                pass
            
            if fulltext_parts:
                fulltext = ' '.join(fulltext_parts)
                # 清理文本：移除多余的空白
                fulltext = re.sub(r'\s+', ' ', fulltext).strip()
                logger.info(f"成功提取全文，长度: {len(fulltext)} 字符")
                return fulltext
            else:
                logger.debug(f"未能从页面中提取全文内容")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"请求论文详情页失败: {str(e)}")
            return None
        except Exception as e:
            logger.debug(f"提取全文失败: {str(e)}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return None

