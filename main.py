import asyncio
import json
import argparse
from scraper import GitHubCrawler

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='GitHub Search Crawler')
    parser.add_argument('--keywords', nargs='+', required=True, help='List of search keywords')
    parser.add_argument('--proxies', nargs='+', help='List of proxy servers (ip:port)')
    parser.add_argument('--type', choices=['Repositories', 'Issues', 'Wikis'], default='Repositories',
                      help='Type of search (default: Repositories)')
    parser.add_argument('--output', default='search_results.json',
                      help='Output file path (default: search_results.json)')
    
    args = parser.parse_args()
    
    # Initialize the crawler
    async with GitHubCrawler() as crawler:
        # Set proxies if provided
        if args.proxies:
            crawler.set_proxies(args.proxies)
        
        # Perform search
        results = await crawler.search(
            keywords=args.keywords,
            search_type=args.type
        )
        
        # Save results to JSON file
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(
                results,  # Convert sets to lists for JSON serialization
                f,
                indent=2,
                ensure_ascii=False
            )
        
        # Print summary
        total_urls = len(results)
        print(f"\nSearch completed:")
        print(f"Type: {args.type}")
        print(f"Total URLs found: {total_urls}")
        print(f"Results saved to: {args.output}")
    

if __name__ == "__main__":
    asyncio.run(main()) 