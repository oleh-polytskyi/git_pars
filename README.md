# GitHub Search Crawler

A high-performance GitHub crawler that implements GitHub search functionality and returns all links from search results. The crawler supports searching for repositories, issues, and wikis.

## Features

- Asynchronous operation for high performance
- Support for multiple search types (Repositories, Issues, Wikis)
- Random proxy selection for request distribution
- Unicode character support in search keywords
- Raw HTML parsing (no API usage)
- Comprehensive test coverage
- Command-line interface

## Requirements

- Python 3.7+
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd git_scraper
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

The crawler can be used from the command line with the following options:

```bash
python main.py --keywords KEYWORD1 KEYWORD2 [KEYWORD3 ...] \
               --proxies PROXY1 PROXY2 [PROXY3 ...] \
               --type {Repositories,Issues,Wikis} \
               --output OUTPUT_FILE
```

### Arguments

- `--keywords`: List of search keywords (required)
- `--proxies`: List of proxy servers in format `ip:port` (required)
- `--type`: Type of search (Repositories, Issues, or Wikis, default: Repositories)
- `--output`: Output file path (default: search_results.json)

### Example

```bash
python main.py \
    --keywords "openstack" "nova" "css" \
    --proxies "37.120.172.84:80" "57.128.37.47:3128" \
    --type Repositories \
    --output results.json
```

## Output

The crawler generates a JSON file containing the search results. The output format is:

```json
{
  "keyword1": [
    "https://github.com/user/repo1",
    "https://github.com/user/repo2"
  ],
  "keyword2": [
    "https://github.com/user/repo3",
    "https://github.com/user/repo4"
  ]
}
```

## Running Tests

To run the test suite:

```bash
pytest
```

To run tests with coverage report:

```bash
pytest --cov=scraper
```

## Performance Considerations

The crawler is designed to be efficient with:
- Asynchronous I/O operations
- Minimal memory usage through streaming responses
- Efficient HTML parsing
- Random proxy selection for load distribution
- Timeout handling for failed requests

## Error Handling

The crawler includes comprehensive error handling for:
- Network failures
- Invalid responses
- Proxy connection issues
- HTML parsing errors

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 