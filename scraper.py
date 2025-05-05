import aiohttp
from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional, Any, Set
import asyncio
import random
import logging
import re
from urllib.parse import urljoin
from datetime import datetime
import pdb 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitHubCrawler:
    """A high-performance GitHub crawler that supports searching repositories, issues, and wikis."""
    
    def __init__(self, base_url: str = "https://github.com", max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the GitHub crawler.
        
        Args:
            base_url (str): The base URL for GitHub
            max_retries (int): Maximum number of retry attempts for failed requests
            retry_delay (float): Initial delay between retries in seconds
        """
        self.base_url = base_url
        self.session = None
        self.proxies = []
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Status codes that should trigger a retry
        self.retry_status_codes = {429, 500, 502, 503, 504}
    
    async def __aenter__(self):
        """Setup async context manager."""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup async context manager."""
        if self.session:
            await self.session.close()
    
    def set_proxies(self, proxies: List[str]):
        """
        Set the list of proxies to use.
        
        Args:
            proxies (List[str]): List of proxy URLs in format 'ip:port'
        """
        self.proxies = proxies
    
    def _get_random_proxy(self) -> Optional[str]:
        """Get a random proxy from the list."""
        return random.choice(self.proxies) if self.proxies else None

    async def _fetch_with_retry(self, url: str, proxy: Optional[str] = None) -> Optional[str]:
        """
        Fetch page content with retry logic.
        
        Args:
            url (str): URL to fetch
            proxy (Optional[str]): Proxy URL to use
            
        Returns:
            Optional[str]: HTML content or None if all retries fail
        """
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
            
        retry_count = 0
        delay = self.retry_delay

        while retry_count <= self.max_retries:
            try:
                if proxy:
                    if not proxy.startswith(('http://', 'https://')):
                        proxy_url = f"http://{proxy}"
                    else:
                        proxy_url = proxy
                    async with self.session.get(url, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status in self.retry_status_codes:
                            if response.status == 429:  # Rate limit
                                retry_after = int(response.headers.get('Retry-After', delay))
                                logger.warning(f"Rate limited. Waiting {retry_after} seconds")
                                await asyncio.sleep(retry_after)
                                retry_count += 1
                                continue
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=response.status
                            )
                        response.raise_for_status()
                        return await response.text()
                else:
                    async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status in self.retry_status_codes:
                            if response.status == 429:  # Rate limit
                                retry_after = int(response.headers.get('Retry-After', delay))
                                logger.warning(f"Rate limited. Waiting {retry_after} seconds")
                                await asyncio.sleep(retry_after)
                                retry_count += 1
                                continue
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=response.status
                            )
                        response.raise_for_status()
                        return await response.text()
            except aiohttp.ClientResponseError as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"Failed to fetch {url} after {self.max_retries} retries. Status: {e.status}")
                    return None
                
                # Exponential backoff with jitter
                jitter = random.uniform(0, 0.1 * delay)
                sleep_time = delay + jitter
                logger.warning(f"Retry {retry_count}/{self.max_retries} for {url} after {sleep_time:.2f}s. Status: {e.status}")
                await asyncio.sleep(sleep_time)
                delay *= 2  # Exponential backoff
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"Failed to fetch {url} after {self.max_retries} retries: {str(e)}")
                    return None
                
                # Exponential backoff with jitter
                jitter = random.uniform(0, 0.1 * delay)
                sleep_time = delay + jitter
                logger.warning(f"Retry {retry_count}/{self.max_retries} for {url} after {sleep_time:.2f}s. Error: {str(e)}")
                await asyncio.sleep(sleep_time)
                delay *= 2  # Exponential backoff
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {str(e)}")
                return None
    
    async def _fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch page content with proxy support and error handling.
        Will try different proxies if one fails.
        
        Args:
            url (str): URL to fetch
            
        Returns:
            Optional[str]: HTML content or None if all proxies fail
        """
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
        
        # Create a copy of proxies to try
        proxies_to_try = self.proxies.copy() if self.proxies else []
        
        # If no proxies available, try direct connection with retry
        if not proxies_to_try:
            return await self._fetch_with_retry(url)

        # Try each proxy until one works
        for proxy in proxies_to_try:
            content = await self._fetch_with_retry(url, proxy)
            if content is not None:
                return content
            logger.error(f"Failed to fetch {url} with proxy {proxy}")

        logger.error("All proxies failed to fetch the page")
        return None

    async def _get_repo_details(self, repo_url: str) -> Dict[str, Any]:
        """
        Fetch and parse details from a repository page.
        
        Args:
            repo_url (str): URL of the repository
            
        Returns:
            Dict[str, Any]: Dictionary containing repository details
        """
        content = await self._fetch_page(repo_url)
        if not content:
            return {"url": repo_url, "extra": {"owner": "", "language_stats": {}}}
            
        soup = BeautifulSoup(content, 'html.parser')
        repo_info = {
            "url": repo_url,
            "extra": {
                "owner": "",
                "language_stats": {}
            }
        }
        
        # Get owner from the repository header
        owner_element = soup.select_one('span[itemprop="author"]')
        if owner_element:
            repo_info["extra"]["owner"] = owner_element.text.strip()
            
        # Get language statistics
        lang_box = soup.find("h2", string=re.compile(r"\bLanguages\b", re.I))
        if isinstance(lang_box, Tag):
            ul = lang_box.find_next("ul")
            if isinstance(ul, Tag):
                for li in ul.find_all("li", attrs={"class": "d-inline"}):
                    if not isinstance(li, Tag):
                        continue
                    lang = li.find("span", attrs={"class": "text-bold"})
                    pct = lang.find_next("span") if isinstance(lang, Tag) else None
                    if isinstance(lang, Tag) and isinstance(pct, Tag):
                        try:
                            repo_info["extra"]["language_stats"][lang.text.strip()] = float(pct.text.strip("%"))
                        except ValueError:
                            pass
                            
        return repo_info
    
    def _parse_search_results(self, html_content: str) -> List[str]:
        """
        Parse search results from HTML content to get repository URLs.
        
        Args:
            html_content (str): HTML content to parse
            
        Returns:
            List[str]: List of repository URLs
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        repo_urls = []
        
        for repo in soup.select('div[data-testid="results-list"] a[class^="prc-Link-Link"]'):
            if not isinstance(repo, Tag):
                continue
                
            href = repo.get('href')
            if href:
                repo_urls.append(urljoin(self.base_url, str(href)))
        
        return repo_urls
    
    async def search(self, keywords: List[str], search_type: str = "Repositories") -> List[Dict[str, Any]]:
        """
        Search GitHub for the given keywords.
        
        Args:
            keywords (List[str]): List of keywords to search for
            search_type (str): Type of search (Repositories, Issues, Wikis)
            
        Returns:
            List[Dict[str, Any]]: For Repositories: List of dicts with url, owner, and language stats
                                 For other types: List of dicts with just urls
        """
        if search_type not in ["Repositories", "Issues", "Wikis"]:
            raise ValueError("search_type must be one of: Repositories, Issues, Wikis")
        
        keywords_q = "+".join(keywords)
        search_url = f"{self.base_url}/search?q={keywords_q}&type={search_type.lower()}"
        content = await self._fetch_page(search_url)
        
        if not content:
            return []
            
        if search_type == "Repositories":
            repo_urls = self._parse_search_results(content)
            # Fetch details for each repository concurrently
            tasks = [self._get_repo_details(url) for url in repo_urls]
            results = await asyncio.gather(*tasks)
            return results
        else:
            # For Issues and Wikis, return just the URLs
            soup = BeautifulSoup(content, 'html.parser')
            results = []
            for link in soup.select('div[data-testid="results-list"] a[class^="prc-Link-Link"]'):
                if not isinstance(link, Tag):
                    continue
                href = link.get('href')
                if href:
                    results.append({"url": urljoin(self.base_url, str(href))})
            return results
