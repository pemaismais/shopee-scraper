import json
import os
import sys
import re
import undetected_chromedriver as uc
import logging
from tqdm import tqdm
from .browser import (
    find_correct_chrome_user_data_dir,
    _initialize_driver,
    _configure_options,
    _save_cookies,
)
from .search_page_parser import scrape_search_page
from .product_page_parser import scrape_product_details

class ShopeeScraper:
    def __init__(self, search_term, max_products, index_only, review_limit, all_star_types=False, star_limit_per_type=10, chrome_user_data_dir=None, media_only=False, product_link=None, continue_scrape=False, output_file=None):
        self.driver = None
        self.cookies_file = 'cookies_shopee.dat'
        self.search_term = search_term
        self.max_products = max_products
        self.index_only = index_only
        self.review_limit = review_limit
        self.all_star_types = all_star_types
        self.star_limit_per_type = star_limit_per_type
        self.chrome_user_data_dir = chrome_user_data_dir
        self.media_only = media_only
        self.product_link = product_link
        self.continue_scrape = continue_scrape
        self.last_review_page = None # To track the last scraped review page

        self._last_content_xpath_found = None

        if not self.chrome_user_data_dir:
            self.chrome_user_data_dir = find_correct_chrome_user_data_dir(self)

        self.options = uc.ChromeOptions()
        _configure_options(self)
        self.output_data = {}

        # Lógica ajustada para nome do arquivo de saída (com prioridade para o parâmetro)
        if output_file:
            self.out_file = output_file
        else:
            base_filename = "shopee_output" 
            if self.product_link:
                try:
                    match = re.search(r'i\.(\d+)\.(\d+)', self.product_link)
                    if match:
                        shopid, itemid = match.groups()
                        base_filename = f"shopee_{shopid}_{itemid}"
                    else: 
                        base_filename = f"shopee_link"
                except Exception as e:
                    logging.warning(f"Could not extract IDs from product link for filename: {e}")
                    base_filename = f"shopee_link"
            elif self.search_term: 
                safe_keyword = re.sub(r'[^a-z0-9_]+', '', self.search_term.lower())
                if safe_keyword: 
                    base_filename = f"shopee_{safe_keyword}"
            self.out_file = f"{base_filename}.json"
        self._load_existing_data()

    def execute(self):
        """Main execution method to orchestrate the scraping process."""
        sys.excepthook = self._handle_exception
        _initialize_driver(self)

        try:
            if self.product_link:
                self._process_single_product()
            else:
                self._process_keyword_search()
        finally:
            self._finalize_scraping()

    def _rescrape_missing_comments(self):
        """Rescrapes comments for products in output data that have no comments."""
        logging.info("Rescraping missing comments from existing data...")
        for link, product in list(self.output_data.items()):
            if product.get("comments") == []:
                try:
                    updated_product = scrape_product_details(self, product)
                    self.output_data[link] = updated_product
                    self._periodic_save()
                except Exception as e:
                    logging.warning(f"Error rescraping comments for {link}: {e}")

    def _load_existing_data(self):
        if os.path.exists(self.out_file):
            try:
                with open(self.out_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.output_data = {item['link']: item for item in data if 'link' in item}
                logging.debug(f"_load_existing_data - Loaded {len(self.output_data)} products from {self.out_file}")
                # Attempt to load the last review page if continue_scrape is True and it's a single product
                if self.continue_scrape and self.product_link and data and data[0].get('last_review_page'):
                    self.last_review_page = data[0]['last_review_page']
                    logging.info(f"Continuing scrape from review page: {self.last_review_page + 1} ")
                elif self.continue_scrape and self.product_link and data:
                    logging.info("Continue scrape requested, but no last_review_page found in existing data.")
            except json.JSONDecodeError:
                logging.warning(f"Error decoding JSON from {self.out_file}. Starting with empty data.")
                self.output_data = {}
            except FileNotFoundError:
                logging.info(f"Output file {self.out_file} not found. Starting with empty data.")
                self.output_data = {}
        else:
            self.output_data = {}

    def _periodic_save(self):
        """Save the current output data to JSON, including the last review page."""
        try:
            all_data = []

            if os.path.exists(self.out_file):
                with open(self.out_file, 'r', encoding='utf-8') as f:
                    try:
                        all_data = json.load(f)
                    except json.JSONDecodeError:
                        logging.warning("Could not decode existing JSON file. Starting with empty data.")

            updated_data = list(self.output_data.values())

            existing_products = {item.get('link'): item for item in all_data if item.get('link')}

            for product in updated_data:
                link = product.get('link')
                if link:
                    existing_products[link] = product
                else:
                    all_data.append(product)

            final_data = list(existing_products.values())

            if self.product_link and final_data and self.last_review_page is not None:
                for item in final_data:
                    if item.get('link') == self.product_link:
                        item['last_review_page'] = self.last_review_page
                        break

            with open(self.out_file, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)
            logging.info("Periodic save successful.")
        except Exception as e:
            logging.warning(f"Periodic save failed: {e}")

    def _scrape_missing_comments(self):
        """Scrape comments for already known products that have no comments."""
        logging.info("Scraping missing comments from existing data...")
        for link, product in list(self.output_data.items()):
            if product.get("comments") == []:
                try:
                    scrape_product_details(self, product)
                    self.output_data[link] = product
                    self._periodic_save()
                except Exception as e:
                    logging.warning(f"Error scraping comments for {link}: {e}")

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    def _finalize_scraping(self):
        """Saves cookies and quits the WebDriver."""
        logging.info("Finalizing scraping...")
        try:
            _save_cookies(self)
        except Exception as e:
            logging.warning(f"Could not save cookies: {e}")
        if self.driver:
            self.driver.quit()
        self._periodic_save()
        logging.info(f"Scraping finished. Data saved to {self.out_file}")

    def _process_keyword_search(self):
        """Processes scraping based on a keyword search."""
        if self.output_data and self.continue_scrape:
            self._rescrape_missing_comments()

        products = []
        try:
            products = scrape_search_page(self)
        except Exception as e:
            logging.error(f"Error scraping search page: {e}")

        if not products:
            logging.warning("No products found or error during search page scraping.")
            return

        for prod in tqdm(products, desc="Processing products"):
            link = prod["link"]
            if link in self.output_data and self.output_data[link].get("comments"):
                logging.debug(f"Skipping already processed product: {link}")
                continue

            if not self.index_only:
                prod = scrape_product_details(self, prod)

            self.output_data[link] = prod
            self._periodic_save()

    def _process_single_product(self):
        """Processes scraping for a single product link."""
        logging.info(f"Processing single product link: {self.product_link}")

        if self.product_link in self.output_data:
            logging.info("Product data found in existing file. Rescraping details.")
            product_data = self.output_data[self.product_link]
            if "link" not in product_data:
                logging.debug("Product link not found in existing file.")
                product_data["link"] = self.product_link
            if "comments" not in product_data:
                logging.debug("Product comments not found in existing file.")
                product_data["comments"] = []
        else:
            product_data = {"link": self.product_link, "comments": []}
        try:
            updated_product = scrape_product_details(self, product_data)
            self.output_data[self.product_link] = updated_product
            self._periodic_save()
        except Exception as e:
            logging.error(f"Error scraping details for {self.product_link}: {e}")
