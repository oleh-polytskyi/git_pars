import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pytest_asyncio
from scraper import GitHubCrawler
from unittest.mock import patch, MagicMock, AsyncMock
import aiohttp
import json
from datetime import datetime
from bs4 import BeautifulSoup
import asyncio


@pytest_asyncio.fixture
async def crawler():
    """Create a GitHubCrawler instance for testing."""
    async with GitHubCrawler() as crawler:
        yield crawler

@pytest.fixture
def sample_repo_html():
    """Sample repository HTML content."""
    return """
    <html>
        <body>
            <span itemprop="author">testuser</span>
            <h2>Languages</h2>
            <ul>
                <li class="d-inline">
                    <span class="text-bold">Python</span>
                    <span>75.5%</span>
                </li>
                <li class="d-inline">
                    <span class="text-bold">JavaScript</span>
                    <span>24.5%</span>
                </li>
            </ul>
        </body>
    </html>
    """

@pytest.fixture
def sample_search_results():
    """Sample search results HTML content."""
    return """
    <div data-testid="results-list">
        <a class="prc-Link-Link" href="/user/repo1">Repo 1</a>
        <a class="prc-Link-Link" href="/user/repo2">Repo 2</a>
        <div class="repo-description">Test repository</div>
        <div class="repo-stars">1000 stars</div>
    </div>
    """

@pytest.mark.asyncio
async def test_fetch_page(crawler):
    """Test fetching page content."""
    with patch.object(crawler, '_fetch_with_retry') as mock_fetch:
        mock_fetch.return_value = "<html>Test</html>"
        content = await crawler._fetch_page("https://example.com")
        assert content is not None
        assert isinstance(content, str)
        assert len(content) > 0

@pytest.mark.asyncio
async def test_search_repositories(crawler, sample_search_results):
    """Test repository search functionality."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = sample_search_results
        results = await crawler.search(["python"], search_type="Repositories")
        assert isinstance(results, list)
        if results:  # If we got any results
            repo = results[0]
            assert isinstance(repo, dict)
            assert "url" in repo
            assert "extra" in repo

@pytest.mark.asyncio
async def test_proxy_usage(crawler):
    """Test proxy usage."""
    test_proxies = ["127.0.0.1:8080", "127.0.0.1:8081"]
    crawler.set_proxies(test_proxies)
    assert crawler.proxies == test_proxies

@pytest.mark.asyncio
async def test_fetch_page_success(crawler):
    """Test successful page fetching."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.text = AsyncMock()
        mock_response.text.return_value = "<html>Test</html>"
        mock_get.return_value.__aenter__.return_value = mock_response
        
        content = await crawler._fetch_page("https://github.com")
        assert content == "<html>Test</html>"

def test_parse_search_results_repositories(crawler):
    """Test parsing repository search results."""
    html = """
    <div data-testid="results-list">
        <a class="prc-Link-Link" href="/user/repo1">Repo 1</a>
        <a class="prc-Link-Link" href="/user/repo2">Repo 2</a>
    </div>
    """
    urls = crawler._parse_search_results(html)
    assert len(urls) == 2
    assert "https://github.com/user/repo1" in urls
    assert "https://github.com/user/repo2" in urls

def test_parse_search_results_issues(crawler):
    """Test parsing issue search results."""
    html = """
    <div data-testid="results-list">
        <a class="prc-Link-Link" href="/user/repo/issues/1">Issue 1</a>
        <a class="prc-Link-Link" href="/user/repo/issues/2">Issue 2</a>
    </div>
    """
    urls = crawler._parse_search_results(html)
    assert len(urls) == 2
    assert "https://github.com/user/repo/issues/1" in urls
    assert "https://github.com/user/repo/issues/2" in urls

def test_parse_search_results_wikis(crawler):
    """Test parsing wiki search results."""
    html = """
    <div data-testid="results-list">
        <a class="prc-Link-Link" href="/user/repo/wiki/page1">Wiki 1</a>
        <a class="prc-Link-Link" href="/user/repo/wiki/page2">Wiki 2</a>
    </div>
    """
    urls = crawler._parse_search_results(html)
    assert len(urls) == 2
    assert "https://github.com/user/repo/wiki/page1" in urls
    assert "https://github.com/user/repo/wiki/page2" in urls

@pytest.mark.asyncio
async def test_search_success(crawler):
    """Test successful search operation."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = """
        <div data-testid="results-list">
            <a class="prc-Link-Link" href="/user/repo1">Repo 1</a>
            <a class="prc-Link-Link" href="/user/repo2">Repo 2</a>
        </div>
        """
        
        results = await crawler.search(["test"], search_type="Repositories")
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(result, dict) for result in results)
        assert all("url" in result for result in results)

@pytest.mark.asyncio
async def test_search_failure(crawler):
    """Test search operation with failed page fetch."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = None
        results = await crawler.search(["test"], search_type="Repositories")
        assert isinstance(results, list)
        assert len(results) == 0

@pytest.mark.asyncio
async def test_rate_limit_handling(crawler):
    """Test rate limit handling with retry logic."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        # First request returns 429 (rate limit)
        mock_response1 = AsyncMock()
        mock_response1.status = 429
        mock_response1.headers = {'Retry-After': '2'}
        mock_response1.__aenter__.return_value = mock_response1
        
        # Second request succeeds
        mock_response2 = AsyncMock()
        mock_response2.status = 200
        mock_response2.raise_for_status = AsyncMock()
        mock_response2.text = AsyncMock(return_value="<html>Success</html>")
        mock_response2.__aenter__.return_value = mock_response2
        
        mock_get.side_effect = [mock_response1, mock_response2]
        
        content = await crawler._fetch_with_retry("https://github.com")
        assert content == "<html>Success</html>"

@pytest.mark.asyncio
async def test_retry_logic(crawler):
    """Test retry logic with exponential backoff."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        # Create mock response for successful request
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = AsyncMock()
        mock_response.text = AsyncMock(return_value="<html>Success</html>")
        mock_response.__aenter__.return_value = mock_response
        
        # Set up side effects: three failures followed by success
        mock_get.side_effect = [
            aiohttp.ClientError(),
            aiohttp.ClientError(),
            aiohttp.ClientError(),
            mock_response
        ]
        
        content = await crawler._fetch_with_retry("https://github.com")
        assert content == "<html>Success</html>"

@pytest.mark.asyncio
async def test_session_management(crawler):
    """Test proper session management."""
    assert crawler.session is not None
    
    # Test session cleanup
    await crawler.__aexit__(None, None, None)
    await crawler.session.close()  # Ensure session is closed
    assert crawler.session.closed

@pytest.mark.asyncio
async def test_search_with_real_data(crawler, sample_search_results):
    """Test search functionality with real data structure."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = sample_search_results
        
        results = await crawler.search(["python"], search_type="Repositories")
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Verify URL structure
        for result in results:
            assert result["url"].startswith("https://github.com/")

@pytest.mark.asyncio
async def test_search_multiple_keywords(crawler, sample_search_results):
    """Test search with multiple keywords."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = sample_search_results
        
        results = await crawler.search(["python", "django"], search_type="Repositories")
        assert isinstance(results, list)
        assert len(results) > 0

@pytest.mark.asyncio
async def test_search_issues(crawler):
    """Test issue search with real data structure."""
    issue_html = """
    <div data-testid="results-list">
        <a class="prc-Link-Link" href="/user/repo/issues/1">Issue 1</a>
        <a class="prc-Link-Link" href="/user/repo/issues/2">Issue 2</a>
    </div>
    """
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = issue_html
        
        results = await crawler.search(["bug"], search_type="Issues")
        assert isinstance(results, list)
        assert len(results) == 2
        assert all("issues" in result["url"] for result in results)

@pytest.mark.asyncio
async def test_search_wikis(crawler):
    """Test wiki search with real data structure."""
    wiki_html = """
    <div data-testid="results-list">
        <a class="prc-Link-Link" href="/user/repo/wiki/page1">Wiki 1</a>
        <a class="prc-Link-Link" href="/user/repo/wiki/page2">Wiki 2</a>
    </div>
    """
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = wiki_html
        
        results = await crawler.search(["documentation"], search_type="Wikis")
        assert isinstance(results, list)
        assert len(results) == 2
        assert all("wiki" in result["url"] for result in results)

@pytest.mark.asyncio
async def test_invalid_html_handling(crawler):
    """Test handling of invalid HTML content."""
    invalid_html = "<invalid>html</content>"
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = invalid_html
        
        results = await crawler.search(["test"], search_type="Repositories")
        assert isinstance(results, list)
        assert len(results) == 0

@pytest.mark.asyncio
async def test_proxy_rotation(crawler):
    """Test proxy rotation when a proxy fails."""
    test_proxies = ["127.0.0.1:8080", "127.0.0.1:8081"]
    crawler.set_proxies(test_proxies)
    
    with patch.object(crawler, '_fetch_with_retry') as mock_fetch:
        # First proxy fails
        mock_fetch.side_effect = [None, "<html>Success</html>"]
        
        content = await crawler._fetch_page("https://github.com")
        assert content == "<html>Success</html>"
        assert mock_fetch.call_count == 2

@pytest.mark.asyncio
async def test_search_invalid_type(crawler):
    """Test search with invalid type."""
    with pytest.raises(ValueError):
        await crawler.search(["test"], search_type="Invalid")

@pytest.mark.asyncio
async def test_crawler_initialization(crawler):
    """Test crawler initialization."""
    assert crawler.base_url == "https://github.com"
    assert isinstance(crawler.proxies, list)
    assert crawler.session is not None

def test_set_proxies(crawler):
    """Test proxy setting functionality."""
    test_proxies = ["127.0.0.1:8080", "127.0.0.1:8081"]
    crawler.set_proxies(test_proxies)
    assert crawler.proxies == test_proxies

def test_get_random_proxy(crawler):
    """Test random proxy selection."""
    test_proxies = ["127.0.0.1:8080", "127.0.0.1:8081"]
    crawler.set_proxies(test_proxies)
    
    # Test multiple selections to ensure randomness
    selected_proxies = set()
    for _ in range(10):
        proxy = crawler._get_random_proxy()
        assert proxy in test_proxies
        selected_proxies.add(proxy)
    
    # Verify that both proxies were selected at least once
    assert len(selected_proxies) > 1

@pytest.mark.asyncio
async def test_fetch_page_failure(crawler):
    """Test page fetching failure handling."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = aiohttp.ClientError()
        content = await crawler._fetch_page("https://github.com")
        assert content is None

@pytest.mark.asyncio
async def test_fetch_with_retry_with_proxy(crawler):
    """Test fetch_with_retry with proxy support."""
    test_proxies = ["127.0.0.1:8080"]
    crawler.set_proxies(test_proxies)
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = AsyncMock()
        mock_response.text = AsyncMock(return_value="<html>Test</html>")
        mock_get.return_value.__aenter__.return_value = mock_response
        
        content = await crawler._fetch_with_retry("https://github.com", proxy=test_proxies[0])
        assert content == "<html>Test</html>"

@pytest.mark.asyncio
async def test_fetch_with_retry_rate_limit(crawler):
    """Test fetch_with_retry with rate limit handling."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        # First request returns 429 (rate limit)
        mock_response1 = AsyncMock()
        mock_response1.status = 429
        mock_response1.headers = {'Retry-After': '1'}
        mock_response1.__aenter__.return_value = mock_response1
        
        # Second request succeeds
        mock_response2 = AsyncMock()
        mock_response2.status = 200
        mock_response2.raise_for_status = AsyncMock()
        mock_response2.text = AsyncMock(return_value="<html>Success</html>")
        mock_response2.__aenter__.return_value = mock_response2
        
        mock_get.side_effect = [mock_response1, mock_response2]
        
        content = await crawler._fetch_with_retry("https://github.com")
        assert content == "<html>Success</html>"

@pytest.mark.asyncio
async def test_fetch_with_retry_max_retries(crawler):
    """Test fetch_with_retry with maximum retries exceeded."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__.return_value = mock_response
        
        mock_get.side_effect = [mock_response] * (crawler.max_retries + 1)
        
        content = await crawler._fetch_with_retry("https://github.com")
        assert content is None

@pytest.mark.asyncio
async def test_fetch_page_with_proxies(crawler):
    """Test fetch_page with multiple proxies."""
    test_proxies = ["127.0.0.1:8080", "127.0.0.1:8081"]
    crawler.set_proxies(test_proxies)
    
    with patch.object(crawler, '_fetch_with_retry') as mock_fetch:
        # First proxy fails, second succeeds
        mock_fetch.side_effect = [None, "<html>Success</html>"]
        
        content = await crawler._fetch_page("https://github.com")
        assert content == "<html>Success</html>"
        assert mock_fetch.call_count == 2

@pytest.mark.asyncio
async def test_fetch_page_all_proxies_fail(crawler):
    """Test fetch_page when all proxies fail."""
    test_proxies = ["127.0.0.1:8080", "127.0.0.1:8081"]
    crawler.set_proxies(test_proxies)
    
    with patch.object(crawler, '_fetch_with_retry') as mock_fetch:
        mock_fetch.return_value = None
        
        content = await crawler._fetch_page("https://github.com")
        assert content is None
        assert mock_fetch.call_count == len(test_proxies)

@pytest.mark.asyncio
async def test_get_repo_details_with_invalid_content(crawler):
    """Test get_repo_details with invalid HTML content."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = None
        
        result = await crawler._get_repo_details("https://github.com/user/repo")
        assert result == {"url": "https://github.com/user/repo", "extra": {"owner": "", "language_stats": {}}}

@pytest.mark.asyncio
async def test_get_repo_details_with_missing_elements(crawler):
    """Test get_repo_details with missing HTML elements."""
    html_content = """
    <html>
        <body>
            <div>No owner or language information</div>
        </body>
    </html>
    """
    
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = html_content
        
        result = await crawler._get_repo_details("https://github.com/user/repo")
        assert result["url"] == "https://github.com/user/repo"
        assert result["extra"]["owner"] == ""
        assert result["extra"]["language_stats"] == {}

@pytest.mark.asyncio
async def test_get_repo_details_with_invalid_language_stats(crawler):
    """Test get_repo_details with invalid language statistics."""
    html_content = """
    <html>
        <body>
            <span itemprop="author">testuser</span>
            <h2>Languages</h2>
            <ul>
                <li class="d-inline">
                    <span class="text-bold">Python</span>
                    <span>invalid</span>
                </li>
            </ul>
        </body>
    </html>
    """
    
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = html_content
        
        result = await crawler._get_repo_details("https://github.com/user/repo")
        assert result["extra"]["owner"] == "testuser"
        assert result["extra"]["language_stats"] == {}

@pytest.mark.asyncio
async def test_search_with_invalid_type(crawler):
    """Test search with invalid search type."""
    with pytest.raises(ValueError):
        await crawler.search(["python"], search_type="InvalidType")

@pytest.mark.asyncio
async def test_search_with_empty_keywords(crawler):
    """Test search with empty keywords list."""
    results = await crawler.search([], search_type="Repositories")
    assert results == []

@pytest.mark.asyncio
async def test_search_with_failed_fetch(crawler):
    """Test search when page fetch fails."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = None
        
        results = await crawler.search(["python"], search_type="Repositories")
        assert results == []

@pytest.mark.asyncio
async def test_search_with_invalid_html(crawler):
    """Test search with invalid HTML content."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = "Invalid HTML"
        
        results = await crawler.search(["python"], search_type="Repositories")
        assert results == []

@pytest.mark.asyncio
async def test_search_with_no_results(crawler):
    """Test search with no results found."""
    html_content = """
    <div data-testid="results-list">
        <!-- No repository links -->
    </div>
    """
    
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = html_content
        
        results = await crawler.search(["python"], search_type="Repositories")
        assert results == []

@pytest.mark.asyncio
async def test_fetch_with_retry_connection_error(crawler):
    """Test fetch_with_retry with connection error."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = aiohttp.ClientError()
        
        content = await crawler._fetch_with_retry("https://github.com")
        assert content is None

@pytest.mark.asyncio
async def test_fetch_with_retry_timeout(crawler):
    """Test fetch_with_retry with timeout error."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = asyncio.TimeoutError()
        
        content = await crawler._fetch_with_retry("https://github.com")
        assert content is None

@pytest.mark.asyncio
async def test_fetch_with_retry_unexpected_error(crawler):
    """Test fetch_with_retry with unexpected error."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = Exception("Unexpected error")
        
        content = await crawler._fetch_with_retry("https://github.com")
        assert content is None

@pytest.mark.asyncio
async def test_fetch_page_with_session_error(crawler):
    """Test fetch_page with session error."""
    crawler.session = None
    with patch('aiohttp.ClientSession') as mock_session:
        mock_session.return_value = AsyncMock()
        mock_session.return_value.__aenter__.side_effect = Exception("Session error")
        
        content = await crawler._fetch_page("https://github.com")
        assert content is None

@pytest.mark.asyncio
async def test_get_repo_details_with_parsing_error(crawler):
    """Test get_repo_details with HTML parsing error."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = None
        
        result = await crawler._get_repo_details("https://github.com/user/repo")
        assert result == {"url": "https://github.com/user/repo", "extra": {"owner": "", "language_stats": {}}}

@pytest.mark.asyncio
async def test_parse_search_results_with_invalid_html(crawler):
    """Test parse_search_results with invalid HTML."""
    # Test with empty string
    urls = crawler._parse_search_results("")
    assert urls == []
    
    # Test with malformed HTML
    urls = crawler._parse_search_results("<div>Invalid</div>")
    assert urls == []
    
    # Test with HTML without any matching elements
    urls = crawler._parse_search_results("<html><body><div>No links here</div></body></html>")
    assert urls == []

@pytest.mark.asyncio
async def test_search_with_parsing_error(crawler):
    """Test search with HTML parsing error."""
    with patch.object(crawler, '_fetch_page') as mock_fetch:
        mock_fetch.return_value = None
        
        results = await crawler.search(["python"], search_type="Repositories")
        assert results == [] 