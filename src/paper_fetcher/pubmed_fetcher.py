"""
PubMed 论文检索模块
使用 NCBI E-utilities 官方 API（https://www.ncbi.nlm.nih.gov/books/NBK25501/）
"""

import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional
import requests
from loguru import logger

from ..utils.data_structures import Paper
from .ai_search_keywords import generate_search_keywords

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EFETCH_BATCH = 200  # NCBI 建议单次 efetch 不宜过大


def _local_tag(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


class PubmedFetcher:
    """PubMed 检索器（生物医学文献，https://pubmed.ncbi.nlm.nih.gov/）"""

    def __init__(
        self,
        max_results: int = 20,
        use_ai_keywords: bool = True,
        gpt_analyzer=None,
        api_key: Optional[str] = None,
        email: Optional[str] = None,
        tool: str = "research_status_analyzer",
    ):
        self.max_results = max_results
        self.use_ai_keywords = use_ai_keywords
        self.gpt_analyzer = gpt_analyzer
        self.api_key = (api_key or "").strip() or None
        self.email = (email or "user@example.com").strip() or "user@example.com"
        self.tool = tool
        self._last_request = 0.0
        self._min_interval = 0.12 if self.api_key else 0.35  # 有 key 约 10/s，无 key 约 3/s

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.time()

    def _esearch(self, term: str, retmax: int, sort: str, mindate: str, maxdate: str) -> List[str]:
        self._throttle()
        sort_map = {
            "relevance": "relevance",
            "citation": "relevance",
            "date_desc": "pub date",
            "date_asc": "pub date",
        }
        esort = sort_map.get(sort, "relevance")
        params = {
            "db": "pubmed",
            "term": term,
            "retmax": str(min(retmax, 10000)),
            "retmode": "json",
            "sort": esort,
            "mindate": mindate,
            "maxdate": maxdate,
            "datetype": "pdat",
            "tool": self.tool,
            "email": self.email,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        r = requests.get(f"{EUTILS_BASE}/esearch.fcgi", params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        idlist = data.get("esearchresult", {}).get("idlist", []) or []
        if sort == "date_asc":
            idlist = list(reversed(idlist))
        return idlist

    def _efetch_xml(self, pmids: List[str]) -> str:
        self._throttle()
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "tool": self.tool,
            "email": self.email,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        r = requests.get(f"{EUTILS_BASE}/efetch.fcgi", params=params, timeout=120)
        r.raise_for_status()
        return r.text

    def _parse_pubmed_xml(self, xml_text: str) -> List[Paper]:
        papers: List[Paper] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error(f"PubMed XML 解析失败: {e}")
            return papers

        for article in root.iter():
            if _local_tag(article.tag) != "PubmedArticle":
                continue
            pmid = ""
            title = ""
            abstract_parts: List[str] = []
            authors: List[str] = []
            pub_date: Optional[datetime] = None

            for el in article.iter():
                t = _local_tag(el.tag)
                if t == "PMID" and el.text and not pmid:
                    pmid = el.text.strip()
                elif t == "ArticleTitle" and el.text:
                    title = el.text.strip()
                elif t == "AbstractText" and el.text:
                    label = el.attrib.get("Label", "")
                    txt = el.text.strip()
                    abstract_parts.append(f"{label}: {txt}" if label else txt)
                elif t == "Author":
                    last = fore = ""
                    for child in el:
                        ct = _local_tag(child.tag)
                        if ct == "LastName" and child.text:
                            last = child.text.strip()
                        elif ct == "ForeName" and child.text:
                            fore = child.text.strip()
                    if last or fore:
                        authors.append(f"{fore} {last}".strip() if fore else last)
                elif t == "PubDate":
                    y = m = d = None
                    for child in el:
                        ct = _local_tag(child.tag)
                        if ct == "Year" and child.text:
                            try:
                                y = int(child.text.strip())
                            except ValueError:
                                pass
                        elif ct == "Month" and child.text:
                            mo = child.text.strip()
                            if mo.isdigit():
                                m = int(mo)
                            else:
                                mmap = {
                                    "jan": 1,
                                    "feb": 2,
                                    "mar": 3,
                                    "apr": 4,
                                    "may": 5,
                                    "jun": 6,
                                    "jul": 7,
                                    "aug": 8,
                                    "sep": 9,
                                    "oct": 10,
                                    "nov": 11,
                                    "dec": 12,
                                }
                                m = mmap.get(mo[:3].lower(), 1)
                        elif ct == "Day" and child.text:
                            try:
                                d = int(child.text.strip())
                            except ValueError:
                                pass
                    if y:
                        try:
                            pub_date = datetime(y, m or 1, d or 1)
                        except ValueError:
                            pub_date = datetime(y, 1, 1)

            if pmid and title:
                abstract = "\n".join(abstract_parts) if abstract_parts else ""
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                papers.append(
                    Paper(
                        title=title,
                        abstract=abstract,
                        authors=authors if authors else ["Unknown"],
                        publication_date=pub_date,
                        source="pubmed",
                        url=url,
                        paper_id=pmid,
                        citation_count=None,
                    )
                )
        return papers

    def search_exact_title(self, exact_title: str, max_results: int = 3) -> List[Paper]:
        """标题检索（用于 PDF 联想中的引用匹配）"""
        clean = exact_title.strip().strip('"').strip("'")
        if not clean:
            return []
        # PubMed 短语检索：双引号 + 字段
        esc = clean.replace('"', " ")
        term = f'"{esc}"[Title]'
        try:
            mindate = "1900/01/01"
            maxdate = datetime.now().strftime("%Y/%m/%d")
            ids = self._esearch(term, retmax=max_results, sort="relevance", mindate=mindate, maxdate=maxdate)
            if not ids:
                return []
            xml_text = self._efetch_xml(ids[:max_results])
            return self._parse_pubmed_xml(xml_text)[:max_results]
        except Exception as e:
            logger.error(f"PubMed 精确标题搜索失败: {e}")
            return []

    def search_papers(
        self,
        query: str,
        max_results: Optional[int] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        sort_by: str = "relevance",
    ) -> List[Paper]:
        max_results = max_results or self.max_results
        if start_year is None:
            start_year = 2023
        if end_year is None:
            end_year = datetime.now().year
        mindate = f"{start_year}/01/01"
        maxdate = f"{end_year}/12/31"

        try:
            logger.info(
                f"开始从 PubMed 搜索: {query} ({start_year}-{end_year}年, sort={sort_by})"
            )
            keywords = [query]
            if self.use_ai_keywords and self.gpt_analyzer:
                keywords = generate_search_keywords(self.gpt_analyzer, query)
                logger.info(f"PubMed 使用关键词: {keywords}")

            seen: set = set()
            all_papers: List[Paper] = []
            per_kw = max(5, max_results // max(len(keywords), 1) + 3)
            fetch_cap = min(per_kw * 2, 500)

            for kw in keywords:
                term = f"({kw})"
                ids = self._esearch(term, retmax=fetch_cap, sort=sort_by, mindate=mindate, maxdate=maxdate)
                for i in range(0, len(ids), EFETCH_BATCH):
                    batch = ids[i : i + EFETCH_BATCH]
                    if not batch:
                        continue
                    try:
                        xml_text = self._efetch_xml(batch)
                        for p in self._parse_pubmed_xml(xml_text):
                            if p.paper_id not in seen:
                                seen.add(p.paper_id)
                                all_papers.append(p)
                                if len(all_papers) >= max_results:
                                    break
                    except Exception as e:
                        logger.warning(f"PubMed efetch 批次失败: {e}")
                    if len(all_papers) >= max_results:
                        break
                if len(all_papers) >= max_results:
                    break

            result = all_papers[:max_results]
            logger.info(f"PubMed 检索完成，共 {len(result)} 篇")
            return result
        except Exception as e:
            logger.error(f"PubMed 搜索失败: {e}")
            return []
