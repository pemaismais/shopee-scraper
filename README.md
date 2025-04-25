# Shopee Scraper

This Python application scrapes product data and reviews from Shopee. It can retrieve basic product information from search results and detailed information, including reviews, from individual product pages.

## Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/pemaismais/shopee-scraper
    cd shopee-scraper
    ```

2.  **Create a Virtual Environment (Optional But Recommended):**
    *   Linux/Mac:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   Windows:
        ```bash
        python -m venv venv
        venv\Scripts\activate
        ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Before running:

*   Ensure all Chrome windows are fully closed.
*   Be prepared to log in and solve captchas manually if prompted by Shopee in the browser.

### Basic Commands

1.  **Scraping by Keyword (Multiple Products):**
    ```bash
    python main.py -k "your_search_term" -n 10 -r 30
    ```
    This command searches for "your_search_term" and attempts to retrieve basic information and up to 30 reviews for the first 10 products found.

2.  **Scraping by Product Link (Single Product):**
    ```bash
    python main.py -l "<shopee_product_url>" -r 50
    ```
    This command directly scrapes detailed information and up to 50 reviews from the specified product page. The `-n` argument is ignored in this mode.
    *(Replace `<shopee_product_url>` with the actual product link)*

### Scraping Modes

1.  **Review Limit Mode:**
    *   Use `-r` or `--review-limit` to set the maximum number of reviews to collect per product:
        ```bash
        python main.py -k "smartphone" -n 3 -r 20
        ```
        This collects up to 20 reviews per product for the first 3 products found in the "smartphone" search.

2.  **All-Star Types Mode:**
    *   Combine `--all-star-types` with `--star-limit-per-type` to retrieve a specific number of reviews for each star rating (5-star, 4-star, etc.):
        ```bash
        python main.py -k "smartwatch" -n 2 --all-star-types --star-limit-per-type 5
        ```
        This collects 5 reviews for each star rating (5 to 1) for the first 2 smartwatches found. This mode cannot be used with `--media-only`.

3.  **Media Only Mode:**
    *   Use `--media-only` to retrieve only reviews that contain images or videos:
        ```bash
        python main.py -l "<shopee_product_url>" --media-only -r 15
        ```
        This collects up to 15 reviews with media from the specified product link. This mode cannot be used with `--all-star-types`.

4.  **Continue Scraping (Single Product Link):**
    *   Use `-c` or `--continue-scrape` to resume scraping reviews from the last saved page for a specific product link. This is useful if the scraping was interrupted:
        ```bash
        python main.py -l "<shopee_product_url>" -r 100 -c
        ```
        This attempts to continue scraping up to 100 reviews for the specified product.

### Command-Line Arguments

*   `-k`, `--keyword`: Search term (required unless `-l` is used)
*   `-l`, `--product-link`: Direct URL of the Shopee product to scrape reviews from (required unless `-k` is used)
*   `-n`, `--num`: Number of products to retrieve from search results (default: 10, ignored if `-l` is used)
*   `-r`, `--review-limit`: Maximum number of reviews to collect per product (default: 10)
*   `--index-only`: If set, only retrieve basic product information from search results without detailed scraping
*   `--all-star-types`: Retrieve comments by filtering each star rating separately. Cannot be used with `--media-only`.
*   `--star-limit-per-type`: Number of reviews to retrieve per star type when `--all-star-types` is used (default: 10)
*   `--chrome-user-data-dir`: Path to your Chrome user data directory (optional)
*   `--media-only`: Only retrieve reviews that contain images or videos. Cannot be used with `--all-star-types`.
*   `-c`, `--continue-scrape`: Continue scraping reviews from the last saved page (only applicable when `-l` is used).
*   `-o`, `--output`: Path to the output file where the scraped data will be saved (optional). If not specified, a default filename will be used.

### Example Commands

*   **Scrape basic info and 20 reviews for the first 5 results of "gaming mouse":**
    ```bash
    python main.py -k "gaming mouse" -n 5 -r 20
    ```

*   **Scrape detailed info and up to 50 reviews with media only from a specific product link:**
    ```bash
    python main.py -l "<shopee_product_url>" --media-only -r 50
    ```

*   **Scrape detailed info and 3 reviews for each star rating from a specific product link:**
    ```bash
    python main.py -l "<shopee_product_url>" --all-star-types --star-limit-per-type 3 -r 15
    ```
    *(Remember to replace `<shopee_product_url>` with actual links in the examples)*

## License

This project is licensed under the MIT License. See the LICENSE file for details.