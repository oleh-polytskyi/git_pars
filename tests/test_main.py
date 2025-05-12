import pytest
import json
import os
from unittest.mock import patch, AsyncMock
from main import main

@pytest.fixture
def sample_args():
    """Create sample command line arguments."""
    class Args:
        def __init__(self):
            self.keywords = ["python", "django"]
            self.proxies = ["127.0.0.1:8080", "127.0.0.1:8081"]
            self.type = "Repositories"
            self.output = "test_results.json"
    return Args()

@pytest.mark.asyncio
async def test_main_success(sample_args):
    """Test successful execution of main function."""
    mock_results = [
        {"url": "https://github.com/user/repo1", "extra": {"stars": 100}},
        {"url": "https://github.com/user/repo2", "extra": {"stars": 200}}
    ]
    
    with patch('argparse.ArgumentParser.parse_args', return_value=sample_args), \
         patch('main.GitHubCrawler') as mock_crawler_class:
        
        # Setup mock crawler
        mock_crawler = AsyncMock()
        mock_crawler.__aenter__.return_value = mock_crawler
        mock_crawler.search.return_value = mock_results
        mock_crawler_class.return_value = mock_crawler
        
        # Run main function
        await main()
        
        # Verify crawler was initialized and used correctly
        mock_crawler.set_proxies.assert_called_once_with(sample_args.proxies)
        mock_crawler.search.assert_called_once_with(
            keywords=sample_args.keywords,
            search_type=sample_args.type
        )
        
        # Verify output file was created with correct content
        assert os.path.exists(sample_args.output)
        with open(sample_args.output, 'r', encoding='utf-8') as f:
            saved_results = json.load(f)
            assert saved_results == mock_results
        
        # Cleanup
        os.remove(sample_args.output)

@pytest.mark.asyncio
async def test_main_with_different_search_type(sample_args):
    """Test main function with different search type."""
    sample_args.type = "Issues"
    mock_results = [
        {"url": "https://github.com/user/repo/issues/1", "extra": {"state": "open"}},
        {"url": "https://github.com/user/repo/issues/2", "extra": {"state": "closed"}}
    ]
    
    with patch('argparse.ArgumentParser.parse_args', return_value=sample_args), \
         patch('main.GitHubCrawler') as mock_crawler_class:
        
        mock_crawler = AsyncMock()
        mock_crawler.__aenter__.return_value = mock_crawler
        mock_crawler.search.return_value = mock_results
        mock_crawler_class.return_value = mock_crawler
        
        await main()
        
        mock_crawler.search.assert_called_once_with(
            keywords=sample_args.keywords,
            search_type="Issues"
        )
        
        # Cleanup
        if os.path.exists(sample_args.output):
            os.remove(sample_args.output)

@pytest.mark.asyncio
async def test_main_with_empty_results(sample_args):
    """Test main function with empty search results."""
    mock_results = []
    
    with patch('argparse.ArgumentParser.parse_args', return_value=sample_args), \
         patch('main.GitHubCrawler') as mock_crawler_class:
        
        mock_crawler = AsyncMock()
        mock_crawler.__aenter__.return_value = mock_crawler
        mock_crawler.search.return_value = mock_results
        mock_crawler_class.return_value = mock_crawler
        
        await main()
        
        # Verify empty results were saved correctly
        assert os.path.exists(sample_args.output)
        with open(sample_args.output, 'r', encoding='utf-8') as f:
            saved_results = json.load(f)
            assert saved_results == []
        
        # Cleanup
        os.remove(sample_args.output)

@pytest.mark.asyncio
async def test_main_with_custom_output_path(sample_args):
    """Test main function with custom output path."""
    sample_args.output = "custom_results.json"
    mock_results = [{"url": "https://github.com/user/repo", "extra": {}}]
    
    with patch('argparse.ArgumentParser.parse_args', return_value=sample_args), \
         patch('main.GitHubCrawler') as mock_crawler_class:
        
        mock_crawler = AsyncMock()
        mock_crawler.__aenter__.return_value = mock_crawler
        mock_crawler.search.return_value = mock_results
        mock_crawler_class.return_value = mock_crawler
        
        await main()
        
        # Verify custom output file was created
        assert os.path.exists(sample_args.output)
        
        # Cleanup
        os.remove(sample_args.output) 