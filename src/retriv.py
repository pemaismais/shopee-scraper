import os
import sys
import time
import json
import pickle
import logging
import argparse
import re
import datetime
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from tqdm import tqdm

class ShopeeScraper:
    def __init__(self, search_term, max_products, index_only, review_limit, all_star_types=False, star_limit_per_type=10, chrome_user_data_dir=None):
        self.driver = None
        self.cookies_file = 'cookies_shopee.dat'
        self.search_term = search_term
        self.max_products = max_products
        self.index_only = index_only
        self.review_limit = review_limit
        self.all_star_types = all_star_types
        self.star_limit_per_type = star_limit_per_type
        self.chrome_user_data_dir = chrome_user_data_dir
        if not self.chrome_user_data_dir:
            self.chrome_user_data_dir = self.find_correct_chrome_user_data_dir()


        self._setup_logging()
        self.options = uc.ChromeOptions()
        self._configure_options()
        self.output_data = {}
        self.out_file = f"shopee_{re.sub(r'[^a-z0-9_]+', '', self.search_term.lower())}.json"
        self._load_existing_data()


    def find_correct_chrome_user_data_dir(self):
        #loop through all users in C:\Users if windows, and check if the Profile 1 folder exists
        if sys.platform.startswith('win'):
            users_dir = os.path.join("C:\\", "Users")
            for user in os.listdir(users_dir):
                user_data_dir = os.path.join(users_dir, user, "AppData", "Local", "Google", "Chrome", "User Data")
                if os.path.exists(os.path.join(user_data_dir, "Profile 1")):
                    return user_data_dir
        return None

    def _setup_logging(self):
        os.makedirs("logs", exist_ok=True)
        log_filename = datetime.datetime.now().strftime("shopee_%d_%m_%H_%M_%S.log")
        log_filepath = os.path.join("logs", log_filename)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_filepath),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def _configure_options(self):
        self.options.add_argument(f'--user-data-dir="{self.chrome_user_data_dir}"')
        self.options.add_argument("--profile-directory=Profile 1")
        if sys.platform.startswith('linux'):
            self.options.add_argument("--disable-gpu")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_argument("--start-maximized")

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    def _save_cookies(self):
        cookies = self.driver.get_cookies()
        with open(self.cookies_file, 'wb') as file:
            pickle.dump(cookies, file)

    def _load_cookies(self):
        if os.path.exists(self.cookies_file):
            with open(self.cookies_file, 'rb') as file:
                cookies = pickle.load(file)
            for cookie in cookies:
                self.driver.add_cookie(cookie)

    def _load_existing_data(self):
        if os.path.exists(self.out_file):
            try:
                with open(self.out_file, 'r', encoding='utf-8') as f:
                    self.output_data = {
                        item['link']: item for item in json.load(f)
                    }
            except:
                self.output_data = {}

    def _periodic_save(self):
        """Save the current output data to JSON."""
        try:
            with open(self.out_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.output_data.values()), f, ensure_ascii=False, indent=2)
            logging.info("Periodic save successful.")
        except Exception as e:
            logging.warning(f"Periodic save failed: {e}")

    def _scrape_missing_comments(self):
        """Scrape comments for already known products that have no comments."""
        logging.info("Scraping missing comments from existing data...")
        for link, product in list(self.output_data.items()):
            if product.get("comments") == []:
                try:
                    self._scrape_details(product)
                    self.output_data[link] = product
                    self._periodic_save()
                except Exception as e:
                    logging.warning(f"Error scraping comments for {link}: {e}")

    def _retrieve_products(self):
        logging.info("Retrieving product data...")
        products_container_xpath = '//*[@id="main"]/div/div[2]/div/div/div/div/div/div[2]/section/ul'
        product_elements = []
        try:
            container = self.driver.find_element(By.XPATH, products_container_xpath)
            product_elements = container.find_elements(By.XPATH, './/li')
        except NoSuchElementException:
            logging.warning("Could not locate product container.")
        result = []
        for idx, li in enumerate(product_elements):
            if idx >= self.max_products:
                break
            try:
                try:
                    link_elem = li.find_element(By.XPATH, './/a[@class="contents"]')
                    product_link = link_elem.get_attribute("href")
                except:
                    product_link = "<Link>"

                try:
                    name_elem = li.find_element(By.XPATH, './/div[@class="line-clamp-2 break-words min-h-[2.5rem] text-sm"]')
                    product_name = name_elem.text
                except:
                    product_name = "<Product name>"

                try:
                    price_elem = li.find_element(By.XPATH, './/div[@class="truncate flex items-baseline"]')
                    product_price = price_elem.text
                except:
                    product_price = "<Product price>"

                try:
                    rating_elem = li.find_element(By.XPATH, './/div[@class="text-shopee-black87 text-xs/sp14 flex-none"]')
                    product_rating = rating_elem.text
                except:
                    product_rating = "<Product rating>"

                try:
                    location_elem = li.find_element(By.XPATH, './/div[@class="flex-shrink min-w-0 truncate text-shopee-black54 font-extralight text-sp10"]')
                    location = location_elem.text
                except:
                    location = "<Location>"

                try:
                    img_elem = li.find_element(By.XPATH, './/img[@class="inset-y-0 w-full h-full pointer-events-none object-contain absolute"]')
                    product_img = img_elem.get_attribute("src")
                except:
                    product_img = "<Image>"

                try:
                    shipping_elem = li.find_elements(By.XPATH, './/div[@class="truncate text-sp10 font-normal whitespace-nowrap text-shopee-green"]')
                    shipping_text = shipping_elem[0].text if shipping_elem else ""
                except:
                    shipping_text = "<Shipping>"

                product_info = {
                    "link": product_link,
                    "name": product_name,
                    "price": product_price,
                    "rating": product_rating,
                    "img": product_img,
                    "shipping": shipping_text,
                    "location": location
                }
                result.append(product_info)
            except Exception as e:
                logging.warning(f"Skipping item due to error: {e}")
        return result

    def _check_captcha(self):
        """Check for captcha and wait if detected"""
        blacklist = ["login", "captcha","verify","security","check","auth","error"]
        if any(x in self.driver.current_url.lower() for x in blacklist):
            logging.info("Captcha/Login detected! Please solve it...")
            input("Press Enter after solving the captcha...")
            time.sleep(5)  # Wait for page to settle after captcha
            return True
        return False

    def _safe_get(self, url):
        """Wrapper for driver.get() with captcha checking"""
        self.driver.get(url)
        time.sleep(5)  # Wait for page to load
        while self._check_captcha():
            logging.info("Retrying after captcha...")
            self.driver.get(url)
            time.sleep(5)  # Wait for page to load
            self._check_captcha()
            self.driver.implicitly_wait(3)

    def _scrape_page(self):
        logging.info("Loading Shopee search page...")
        base_url = "https://shopee.vn/search?keyword="
        kw_encoded = re.sub(r'\s+', '%20', self.search_term.strip())
        url = f"{base_url}{kw_encoded}&page=0&sortBy=sales"
        self._safe_get(url)
        self._load_cookies()
        self._safe_get(url)
        self.driver.implicitly_wait(5)
        return self._retrieve_products()

    def _parse_star_text(self, text):
        """Converts strings like '1,2k' or '15k' to integer (e.g. '1,2k' -> 1200, '15k' -> 15000)."""
        text = text.lower().strip()
        if 'k' in text:
            # Remove 'k' first
            text = text.replace('k', '')
            try:
                # Handle decimal numbers with comma like '1,2'
                if ',' in text:
                    num = float(text.replace(',', '.'))
                else:
                    num = float(text)
                return int(num * 1000)
            except:
                return 0
        try:
            return int(text)
        except:
            return 0

    def _scrape_details(self, product):
        try:
            self._safe_get(product["link"])
            self.driver.implicitly_wait(3)

            # Category
            try:
                cat_xpath = '//*[@id="sll2-normal-pdp-main"]/div/div[1]/div/div[2]/div[2]/div/div[1]/div[1]/section[1]/div'
                cat_div = self.driver.find_element(By.XPATH, cat_xpath)
                product["category"] = cat_div.text
            except:
                product["category"] = ""

            # Description
            try:
                desc_xpath = '//*[@id="sll2-normal-pdp-main"]/div/div[1]/div/div[2]/div[2]/div/div[1]/div[1]/section[2]/div/div'
                desc_div = self.driver.find_element(By.XPATH, desc_xpath)
                product["description"] = desc_div.text
            except:
                product["description"] = ""

            # Rating overview & total rating
            product["detailed_rating"] = {}
            total_ratings = 0
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                overview_xpath = '//*[@id="sll2-normal-pdp-main"]/div/div/div/div[2]/div[3]/div/div[1]/div[2]/div/div/div[2]/div[2]'
                overview_elem = self.driver.find_element(By.XPATH, overview_xpath)
                filters = overview_elem.find_elements(By.XPATH, './/div[contains(@class,"product-rating-overview__filter")]')
                for f in filters:
                    text = f.text.strip()
                    match = re.match(r'(\d+|\D+)\s?(Sao)?\s?\((\d+)\)', text)
                    if match:
                        star = match.group(1).strip().lower()
                        val = int(match.group(3))
                        if star.isdigit():
                            key = f"{star}_star"
                        else:
                            key = "all" if "tất cả" in star else re.sub(r'\s+', '_', star)
                        if key == "có_bình_luận":
                            key = "commented"
                        elif key == "có_hình_ảnh_/_video":
                            key = "media"
                        product["detailed_rating"][key] = val
                        if star.isdigit():
                            total_ratings += val
            except:
                pass
            product["total_rating"] = total_ratings

            # Collect reviews with limit

            if self.all_star_types:
                # Collect reviews for each star filter separately
                all_reviews = []
                rating_panel_classes = 'product-rating-overview__filters'
                try:
                    star_filters = self.driver.find_elements(By.CLASS_NAME, 'product-rating-overview__filter')
                    # star_filters is typically: [5-star filter, 4-star filter, 3-star..., etc...]
                    
                    for filter_div in star_filters:
                        try:
                            filter_text = filter_div.text.strip()  # e.g. "5 Sao (1,2k)" or "4 Sao (100)"
                            if '(' not in filter_text:
                                continue
                        except:
                            continue
                        match = re.match(r'(\d+)\s?[S|s]ao?\s?\(([^)]*)\)', filter_text)
                        if match:
                            star_value = match.group(1)
                            star_count_text = match.group(2)
                            star_count = self._parse_star_text(star_count_text)
                            # click star filter only if there's a nonzero count
                            if star_count > 0:
                                filter_div.click()
                                time.sleep(1)
                                all_reviews += self._collect_reviews(min(star_count, self.star_limit_per_type))
                    product["comments"] = all_reviews
                except Exception as e:
                    logging.warning(f"Unable to collect star-based reviews: {e}")
            else:
                # Old approach: collect all in one pass
                all_reviews = self._collect_reviews(min(product["total_rating"], self.review_limit))
                product["comments"] = all_reviews
            
        except Exception as e:
            logging.warning(f"Detail scrape failed for {product.get('link')}: {e}")

    def _collect_reviews(self, max_reviews):
        """Helper to collect up to max_reviews from the current filtered view."""
        collected_reviews = []
        try:
            # Wait up to 2 seconds for rating list to appear
            start_time = time.time()
            rating_container = None
            while time.time() - start_time < 5:
                try:
                    rating_container = self.driver.find_element(By.CLASS_NAME, 'product-ratings__list')
                    break
                except:
                    time.sleep(0.1)
            if not rating_container:
                return collected_reviews
        except:
            return collected_reviews

        with tqdm(total=max_reviews, desc="Collecting reviews") as pbar:
            while len(collected_reviews) < max_reviews:
                rating_items = rating_container.find_elements(By.XPATH, './/div[contains(@class,"shopee-product-rating__main")]')
                for item in rating_items:
                    if len(collected_reviews) >= max_reviews:
                        break
                    review_data = {}
                    # Author
                    try:
                        auth_elem = item.find_element(By.CLASS_NAME,'shopee-product-rating__author-name')
                        review_data["author"] = auth_elem.text.strip()
                    except:
                        review_data["author"] = ""

                    # Rating
                    try:
                        star_elems = item.find_element(By.XPATH, './/div[@class="shopee-product-rating__rating"]').find_elements(By.XPATH, '*')
                        solid_stars = [s for s in star_elems if 'shopee-svg-icon icon-rating-solid--active icon-rating-solid' in s.get_attribute('class')]
                        review_data["rating"] = len(solid_stars)
                    except:
                        review_data["rating"] = 0

                    # Time
                    try:
                        time_elem = item.find_element(By.XPATH, './/div[@class="shopee-product-rating__time"]')
                        review_data["time"] = time_elem.text.strip()
                    except:
                        review_data["time"] = ""

                    # Content
                    try:
                        content_elem = item.find_element(By.XPATH, './/div[@style="position: relative; box-sizing: border-box; margin: 15px 0px; font-size: 14px; line-height: 20px; color: rgba(0, 0, 0, 0.87); word-break: break-word; white-space: pre-wrap;"]')
                        review_data["content"] = content_elem.text.strip()
                    except:
                        review_data["content"] = ""

                    # Seller respond
                    try:
                        seller_respond = item.find_element(By.XPATH, './/div[@class="TQTPT9"]//div[@class="qiTixQ"]')
                        review_data["seller_respond"] = seller_respond.text.strip()
                    except:
                        review_data["seller_respond"] = ""

                    # Like count
                    try:
                        like_elem = item.find_element(By.XPATH, './/div[@class="shopee-product-rating__like-count"]')
                        like_text = like_elem.text.strip()
                        review_data["like_count"] = int(like_text) if like_text.isdigit() else 0
                    except:
                        review_data["like_count"] = 0

                    print(f'{review_data["author"]} - {review_data["rating"]} - {review_data["time"]} - {review_data["content"]} - {review_data["seller_respond"]} - {review_data["like_count"]}')

                    collected_reviews.append(review_data)
                    pbar.update(1)
                # Try to click next page if available
                elements_to_try = [ (By.CLASS_NAME, 'shopee-svg-icon icon-arrow-right'), 
                                    (By.XPATH, '//*[@id="sll2-normal-pdp-main"]/div/div/div/div[2]/div[3]/div/div[1]/div[2]/div/div/div[3]/nav/button[8]/svg'),
                                    (By.XPATH, '//*[@id="sll2-normal-pdp-main"]/div/div/div/div[2]/div[3]/div/div[1]/div[2]/div/div/div[3]/nav/button[8]/svg'),
                                    (By.XPATH, '//*[@id="sll2-normal-pdp-main"]/div/div/div/div[2]/div[3]/div/div[1]/div[2]/div/div/div[3]/nav/button[8]'),
                                    (By.XPATH, '/html/body/div[1]/div/div[2]/div/div/div[1]/div/div/div/div[2]/div[3]/div/div[1]/div[2]/div/div/div[3]/nav/button[8]'),
                                    (By.CLASS_NAME, 'shopee-svg-icon icon-arrow-right'),
                                      ]

                for by, value in elements_to_try:
                    try:
                        next_button = self.driver.find_element(by, value)
                        next_button.click()
                        print('click next page')
                        time.sleep(1)
                        break
                    except:
                        continue
        return collected_reviews

    def execute(self):
        sys.excepthook = self._handle_exception
        if sys.platform.startswith('linux'):
            self.driver = uc.Chrome(options=self.options, enable_cdp_events=False, headless=False)
        else:
            self.driver = uc.Chrome(options=self.options, enable_cdp_events=False, headless=False)
        self.driver.maximize_window()

        # Run the missing comments scraper if we have existing data
        if self.output_data:
            self._scrape_missing_comments()

        products = []
        try:
            products = self._scrape_page()
        except Exception as e:
            logging.error(f"Error scraping: {e}")
        final_list = []
        try:
            if not products:
                return
            for prod in tqdm(products, desc="Processing products"):
                link = prod["link"]
                if link in self.output_data:
                    final_list.append(self.output_data[link])
                    continue
                if not self.index_only:
                    self._scrape_details(prod)
                final_list.append(prod)
                self.output_data[link] = prod
                # Periodic save after each product
                self._periodic_save()
        finally:
            logging.info("Saving cookies and quitting driver...")
            self._save_cookies()
            self.driver.quit()

        # Final save (redundant but safe)
        self._periodic_save()
        logging.info(f"Data saved to {self.out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", "--keyword",default='Raspbberry pi', help="Search term")
    parser.add_argument("-n", "--num", type=int, default=10, help="Number of products")
    parser.add_argument("-r", "--review-limit", type=int, default=30, help="Max reviews per product")
    parser.add_argument("--index-only", action="store_true", default=False, help="If set, only retrieve index data")
    parser.add_argument("--all-star-types", action="store_true", default=False, help="Retrieve comments by filtering each star rating.")
    parser.add_argument("--star-limit-per-type", type=int, default=10, help="Number of reviews to retrieve per star type.")
    parser.add_argument("--chrome-user-data-dir", default=None, help="User data directory for Chrome")
    args = parser.parse_args()
    scraper = ShopeeScraper(
        args.keyword, 
        args.num, 
        args.index_only, 
        args.review_limit,
        all_star_types=args.all_star_types,
        star_limit_per_type=args.star_limit_per_type,
        chrome_user_data_dir=args.chrome_user_data_dir
    )
    scraper.execute()