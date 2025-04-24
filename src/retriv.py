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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm
#.\venv\Scripts\activate
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
            self.chrome_user_data_dir = self.find_correct_chrome_user_data_dir()

        self._setup_logging()
        self.options = uc.ChromeOptions()
        self._configure_options()
        self.output_data = {}

        # Lógica ajustada para nome do arquivo de saída (com prioridade para o parâmetro)
        if output_file:
            self.out_file = output_file
        else:
            base_filename = "shopee_output" # Nome padrão
            if self.product_link:
                # Tenta extrair IDs do link para um nome único
                try:
                    match = re.search(r'i\.(\d+)\.(\d+)', self.product_link)
                    if match:
                        shopid, itemid = match.groups()
                        base_filename = f"shopee_{shopid}_{itemid}"
                    else: # Fallback se o padrão não for encontrado
                        base_filename = f"shopee_link"
                except Exception as e:
                    logging.warning(f"Could not extract IDs from product link for filename: {e}")
                    base_filename = f"shopee_link"
            elif self.search_term: # Usa keyword se não houver link
                safe_keyword = re.sub(r'[^a-z0-9_]+', '', self.search_term.lower())
                if safe_keyword: # Garante que não seja vazio
                    base_filename = f"shopee_{safe_keyword}"
            self.out_file = f"{base_filename}.json"
        self._load_existing_data()

    def execute(self):
        """Main execution method to orchestrate the scraping process."""
        sys.excepthook = self._handle_exception
        self._initialize_driver()

        try:
            if self.product_link:
                self._process_single_product()
            else:
                self._process_keyword_search()
        finally:
            self._finalize_scraping()

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
            updated_product = self.scrape_product_details(product_data)
            self.output_data[self.product_link] = updated_product
            self._periodic_save()
        except Exception as e:
            logging.error(f"Error scraping details for {self.product_link}: {e}")

    def _process_keyword_search(self):
        """Processes scraping based on a keyword search."""
        if self.output_data and self.continue_scrape:
            self._rescrape_missing_comments()

        products = []
        try:
            products = self._scrape_search_page()
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
                prod = self.scrape_product_details(prod)

            self.output_data[link] = prod
            self._periodic_save()  

    def _finalize_scraping(self):
        """Saves cookies and quits the WebDriver."""
        logging.info("Finalizing scraping...")
        try:
            self._save_cookies()
        except Exception as e:
            logging.warning(f"Could not save cookies: {e}")
        if self.driver:
            self.driver.quit()
        self._periodic_save()
        logging.info(f"Scraping finished. Data saved to {self.out_file}")

    def _initialize_driver(self):
        """Initializes the Chrome WebDriver."""
        logging.info("Initializing WebDriver...")
        if sys.platform.startswith('linux'):
            self.driver = uc.Chrome(options=self.options, enable_cdp_events=False, headless=False)
        else:
            self.driver = uc.Chrome(options=self.options, enable_cdp_events=False, headless=False)
        self.driver.maximize_window()
        logging.info("WebDriver initialized successfully.")

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

            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)  
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

            file_handler = logging.FileHandler(log_filepath)
            file_handler.setLevel(logging.DEBUG) 
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setLevel(logging.DEBUG)  
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)
            
            ## Selenium annoying logs
            selenium_logger = logging.getLogger('selenium.webdriver.remote.remote_connection')
            selenium_logger.setLevel(logging.INFO)  
            
            webdriver_common_logger = logging.getLogger('selenium.webdriver.common.utils')
            webdriver_common_logger.setLevel(logging.INFO)

            urllib3_logger = logging.getLogger('urllib3.connectionpool')
            urllib3_logger.setLevel(logging.INFO)

            http_client_logger = logging.getLogger('selenium.webdriver.remote.http')
            http_client_logger.setLevel(logging.INFO)



    def scrape_product_details(self, product):
        """Main function to scrape product details."""
        try:
            logging.info(f"Scraping details for: {product.get('link', 'N/A')}")
            self._safe_get(product["link"])

            self._scroll_page_for_reviews()

            product.setdefault("comments", []) 
            self._extract_basic_product_info(product)
            # product["description"] = self._scrape_product_description()
            # product["category"] = self._scrape_product_category()

            if not self._wait_for_first_review():
                product["detailed_rating"] = {}
                product["total_rating"] = 0
                return product

            filters = self._parse_rating_filters()
            detailed_rating, total_ratings = self._extract_detailed_rating(filters)
            product["detailed_rating"] = detailed_rating
            product["total_rating"] = total_ratings

            
            product.setdefault("comments", []) 
            
            if self.media_only:
                media_reviews = self._collect_media_reviews(filters, detailed_rating.get("media", 0))
                if media_reviews:
                    product["comments"].extend(media_reviews)
                    logging.info(f"Collected {len(media_reviews)} media reviews.")

            all_star_reviews = self._collect_all_star_reviews(filters)
            if all_star_reviews:
                product["comments"].extend(all_star_reviews)
                logging.info(f"Collected {len(all_star_reviews)} star-rated reviews.")

            general_reviews = self._collect_general_reviews(detailed_rating, total_ratings)
            if general_reviews:
                product["comments"].extend(general_reviews)
                logging.info(f"Collected {len(general_reviews)} general reviews.")

            logging.info(f"Finished scraping details. Collected {len(product.get('comments', []))} comments.")

        except Exception as e:
            logging.exception(f"Error scraping details for {product.get('link', 'N/A')}: {e}")
            product.setdefault("category", "")
            product.setdefault("description", "")
            product.setdefault("detailed_rating", {})
            product.setdefault("total_rating", 0)

        return product
    
    
    def _extract_basic_product_info(self, product):
        main_el = None
        try:
            main_el = self.driver.find_element(By.XPATH, '//div[contains(@role, "main")]')
            logging.debug("Found main content element.")
        except NoSuchElementException:
            logging.warning("Could not find the main content element on the product page.")
            return product  # Retorna o produto como está se não encontrar o elemento principal

        product["description"] = self._scrape_product_description()
        product["category"] = self._scrape_product_category()

        # Name
        if "name" not in product:
            try:
                name_el = main_el.find_element(By.XPATH, './/h1')
                name = name_el.text.strip()
                product["name"] = name
                logging.debug(f"Extracted product name: '{name}'")
            except NoSuchElementException:
                logging.debug("Could not find product name element.")

        # Price
        if "price" not in product:
            try:
                price_el = main_el.find_element(By.XPATH, './/section[contains(@aria-live,"polite")]/div/div[1]')
                price = price_el.text.strip()
                product["price"] = price
                logging.debug(f"Extracted product price: '{price}'")
            except NoSuchElementException:
                logging.debug("Could not find product price element.")

        # Rating
        if "rating" not in product:
            try:
                rating_el = main_el.find_element(By.XPATH, './/div[@class="F9RHbS dQEiAI jMXp4d"]')
                rating = rating_el.text.strip()
                product["rating"] = rating
                logging.debug(f"Extracted product rating: '{rating}'")
            except NoSuchElementException:
                logging.debug("Could not find product rating element.")

        # Ratings Count
        if "Ratings" not in product:
            try:
                ratings_el = main_el.find_element(By.XPATH, './/div[@class="F9RHbS"]')
                ratings = ratings_el.text.strip()
                product["Ratings"] = self._convert_shortened_number(ratings)
                logging.debug(f"Extracted product ratings count text: '{ratings}' (from '{ratings_el.text}')")
            except NoSuchElementException:
                logging.debug("Could not find product ratings count element.")

        # Sold Count
        if "sold" not in product:
            try:
                sold_el = main_el.find_element(By.XPATH, './/span[@class="AcmPRb"]')
                sold_text = sold_el.text.strip()
                product["sold"] = self._convert_shortened_number(sold_text)
                logging.debug(f"Extracted sold count: '{product['sold']}' (from '{sold_text}')")
            except NoSuchElementException:
                logging.debug("Could not find sold count element.")

        # Shop Name
        if "shop_name" not in product:
            try:
                shop_name_el = self.driver.find_element(By.XPATH, './/section[contains(@class, "page-product__shop")]//div[@class="fV3TIn"]')
                shop_name = shop_name_el.text.strip()
                product["shop_name"] = shop_name
                logging.debug(f"Extracted shop name: '{shop_name}'")
            except NoSuchElementException:
                logging.debug("Could not find shop name element.")

        # Shop url
        if "shop_profile_url" not in product:
            try:
                shop_url_el = self.driver.find_element(By.XPATH, './/section[contains(@class, "page-product__shop")]//a[1]')
                shop_url = shop_url_el.get_attribute("href")
                product["shop_profile_url"] = shop_url
                logging.debug(f"Extracted shop profile url: '{shop_name}'")
            except NoSuchElementException:
                logging.debug("Could not find shop profile url.")        

        return product   
        
    def _configure_options(self):
            self.options.add_argument(f'--user-data-dir="{self.chrome_user_data_dir}"')
            self.options.add_argument("--profile-directory=Profile 1")
            if sys.platform.startswith('linux'):
                self.options.add_argument("--disable-gpu")
                self.options.add_argument("--no-sandbox")
                self.options.add_argument("--disable-dev-shm-usage")
                self.options.add_argument("--disable-blink-features=AutomationControlled")
                self.options.add_argument("--start-maximized")
            else: 
                self.options.add_argument("--start-fullscreen")

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
                
    def _get_search_page_product_elements(self):
        logging.info("Retrieving product data...")
        products_container_xpath = '//ul[contains(@class,"shopee-search-item-result__items")]'
        product_elements = []
        try:
            logging.debug(f"Attempting to find product container using XPath: '{products_container_xpath}'")
            container = self.driver.find_element(By.XPATH, products_container_xpath)
            logging.debug("Product container found successfully.")
            
            product_elements = container.find_elements(By.XPATH, './/li')
            logging.debug(f"Found {len(product_elements)} product elements within the container.")
        except NoSuchElementException:
            logging.warning("Could not locate product container.")
            return []

        return product_elements

    def _extract_product_search_page_info(self, product_elements):
        result = []
        for idx, li in enumerate(product_elements):
            if idx >= self.max_products:
                logging.info(f"Reached maximum number of products ({self.max_products}). Stopping product retrieval.")
                break
            logging.debug(f"Processing product element at index: {idx}")
            product_info = {}
          
            # Link
            try:
                link_elem = li.find_element(By.XPATH, './/a[@class="contents"]')
                product_link = link_elem.get_attribute("href")
                product_info["link"] = product_link
                logging.debug(f"Extracted product link: {product_link}")
            except:
                product_link = "<Link>"
                product_info["link"] = product_link
                logging.warning(f"Could not extract product link for item at index {idx}. Using default: {product_link}")
            
            # Name
            try:
                name_elem = li.find_element(By.XPATH, './/div[contains(@class,"line-clamp-2 break-words min-w-0")]')
                product_name = name_elem.text
                product_info["name"] = product_name
                logging.debug(f"Extracted product name: {product_name}")
            except:
                product_name = "<Product name>"
                product_info["name"] = product_name
                logging.warning(f"Could not extract product name for item at index {idx}. Using default: {product_name}")
            
            # Price
            try:
                price_elem = li.find_element(By.XPATH, './/div[@class="truncate flex items-baseline"]')
                product_price = price_elem.text.replace('\n', ' ').strip()
                product_info["price"] = product_price
                logging.debug(f"Extracted product price: {product_price}")
            except:
                product_price = "<Product price>"
                product_info["price"] = product_price
                logging.warning(f"Could not extract product price for item at index {idx}. Using default: {product_price}")
            
            # Rating
            try:
                rating_elem = li.find_element(By.XPATH, './/div[@class="text-shopee-black87 text-xs/sp14 flex-none"]')
                product_rating = rating_elem.text
                product_info["rating"] = product_rating
                logging.debug(f"Extracted product rating: {product_rating}")
            except:
                product_rating = "<Product rating>"
                product_info["rating"] = product_rating
                logging.warning(f"Could not extract product rating for item at index {idx}. Using default: {product_rating}")
            
            # Location
            try:
                location_elem = li.find_element(By.XPATH, './/div[@class="flex-shrink min-w-0 truncate text-shopee-black54 font-extralight text-sp10"]')
                location = location_elem.text
                product_info["location"] = location
                logging.debug(f"Extracted product location: {location}")
            except:
                location = "<Location>"
                product_info["location"] = location
                logging.warning(f"Could not extract product location for item at index {idx}. Using default: {location}")
            # Image
            try:
                img_elem = li.find_element(By.XPATH, './/img[@class="inset-y-0 w-full h-full pointer-events-none object-contain absolute"]')
                product_img = img_elem.get_attribute("src")
                product_info["img"] = product_img
                logging.debug(f"Extracted product image URL: {product_img}")
            except:
                product_img = "<Image>"
                product_info["img"] = product_img
                logging.warning(f"Could not extract product image URL for item at index {idx}. Using default: {product_img}")

            # Shipping
            # try:
            #     shipping_elem = li.find_elements(By.XPATH, './/div[@class="truncate text-sp10 font-normal whitespace-nowrap text-shopee-green"]')
            #     shipping_text = shipping_elem[0].text if shipping_elem else ""
            #     product_info["shipping"] = shipping_text
            #     logging.debug(f"Extracted product shipping text: {shipping_text}")
            # except:
            #     shipping_text = "<Shipping>"
            #     product_info["shipping"] = shipping_text
            #     logging.warning(f"Could not extract product shipping text for item at index {idx}. Using default: {shipping_text}")

            result.append(product_info)
        logging.info(f"Processed {len(result)} product data items.")
        return result

    
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
                    self.scrape_product_details(product)
                    self.output_data[link] = product
                    self._periodic_save()
                except Exception as e:
                    logging.warning(f"Error scraping comments for {link}: {e}")


    def _retrieve_products(self):
        product_elements = self._get_search_page_product_elements()
        if product_elements:
            return self._extract_product_search_page_info(product_elements)
        return []
    

    
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
        time.sleep(3)  # Wait for page to load
        while self._check_captcha():
            logging.info("Retrying after captcha...")
            self.driver.get(url)
            time.sleep(3)  # Wait for page to load
            self._check_captcha()
            self.driver.implicitly_wait(3)

    def _scrape_search_page(self):
        logging.info("Loading Shopee search page...")
        base_url = "https://shopee.com.br/search?keyword="
        kw_encoded = re.sub(r'\s+', '%20', self.search_term.strip())
        url = f"{base_url}{kw_encoded}&page=0&sortBy=sales"
        self._safe_get(url)
        self._load_cookies()
        self._safe_get(url)
        self.driver.implicitly_wait(5)
        return self._retrieve_products()

    def _convert_shortened_number(self, text):
        """Converts strings like '1,2k' or '15k' or '1,2mil' or '15mil' to integer."""
        text = text.lower().strip()
        multiplier = 1
        if 'k' in text:
            multiplier = 1000
            text = text.replace('k', '')
        elif 'mil' in text:
            multiplier = 1000
            text = text.replace('mil', '')

        try:
            # Handle decimal numbers with comma like '1,2'
            if ',' in text:
                num_str = text.replace(',', '.')
            else:
                num_str = text
            num = float(num_str)
            return int(num * multiplier)
        except ValueError:
            logging.warning(f"Could not parse number from text: '{text}'")
            return 0

    def _collect_reviews(self, max_reviews):
            collected_reviews = []
            page_num = 1

            # If continue_scrape is enabled and we know the last page, try to navigate to the page AFTER the last one
            if self.continue_scrape and self.last_review_page and self.last_review_page >= 1:
                start_page = self.last_review_page + 1
                logging.info(f"Attempting to navigate to the page to continue scraping: {start_page}")
                nav_element = None
                try:
                    nav_element = self.driver.find_element(By.CLASS_NAME, 'product-ratings__page-controller')
                    buttons = nav_element.find_elements(By.TAG_NAME, 'button')
                    # Click next buttons until we reach the page to continue
                    while page_num < start_page:
                        next_button_found = False
                        for button in buttons:
                            if button.text.strip() == str(page_num + 1):
                                logging.info(f"Clicking next page to reach: {page_num + 1}")
                                button.click()
                                time.sleep(2) # Wait for the new page to load
                                page_num += 1
                                nav_element = self.driver.find_element(By.CLASS_NAME, 'product-ratings__page-controller')
                                buttons = nav_element.find_elements(By.TAG_NAME, 'button')
                                next_button_found = True
                                break
                        if not next_button_found:
                            logging.warning("Could not find the next page button while trying to continue.")
                            break
                    logging.info(f"Reached or attempted to reach page: {page_num}")
                except NoSuchElementException:
                    logging.warning("Could not find the page controller to continue.")
                except Exception as e:
                    logging.warning(f"Error navigating to the starting page: {e}")
                self.last_review_page = None # Reset so we start collecting from here

            with tqdm(total=max_reviews, desc="Collecting reviews") as pbar:
                while len(collected_reviews) < max_reviews:
                    logging.info(f"Collecting reviews from page {page_num}")
                    try:
                        rating_container = self.driver.find_element(By.CLASS_NAME, 'product-ratings__list')
                        rating_items = rating_container.find_elements(By.XPATH, './/div[contains(@class,"shopee-product-rating__main")]')
                        newly_collected = 0
                        for item in rating_items:
                            if len(collected_reviews) >= max_reviews:
                                break
                            review_data = self._extract_review_data(item)
                            collected_reviews.append(review_data)
                            pbar.update(1)
                            newly_collected += 1
                        if newly_collected == 0 or len(collected_reviews) >= max_reviews:
                            logging.info("No more reviews on this page or limit reached.")
                            break
                        # Try to click the next page button
                        next_button_found = False
                        nav_element = self.driver.find_element(By.CLASS_NAME, 'product-ratings__page-controller')
                        buttons = nav_element.find_elements(By.TAG_NAME, 'button')
                        for button in buttons:
                            if button.text.strip() == str(page_num + 1):
                                logging.info(f"Clicking next page: {page_num + 1}")
                                button.click()
                                time.sleep(2) # Wait for the new page to load
                                page_num += 1
                                self.last_review_page = page_num # Update the last visited page
                                next_button_found = True
                                self._periodic_save() # Save after each review page
                                break
                        if not next_button_found:
                            logging.info("Next page button not found or reached the end.")
                            break
                    except NoSuchElementException:
                        logging.warning("Could not find review elements or page controller on the current page.")
                        break
                    except Exception as e:
                        logging.warning(f"Error collecting reviews on page {page_num}: {e}")
                        break
            return collected_reviews


    def _extract_review_data(self, item):
            review_data = {}
            start_time = time.time()

            # Author
            try:
                auth_elem = item.find_element(By.CLASS_NAME,'shopee-product-rating__author-name')
                review_data["author"] = auth_elem.text.strip()
                logging.debug(f"Time to extract author: {time.time() - start_time:.4f} seconds")
                author_profile_url = auth_elem.get_attribute('href')
                if author_profile_url:
                    review_data["author_profile_url"] = f"{author_profile_url}"
                else:
                    review_data["author_profile_url"] = ""
                    logging.debug("Author element does not have 'href' attribute.")
            except:
                review_data["author"] = ""
                review_data["author_profile_url"] = ""
                logging.debug(f"Time to extract author (failure): {time.time() - start_time:.4f} seconds")

            # Rating
            try:
                star_elems = item.find_element(By.XPATH, './/div[@class="shopee-product-rating__rating"]').find_elements(By.XPATH, '*')
                solid_stars = [s for s in star_elems if 'shopee-svg-icon icon-rating-solid--active icon-rating-solid' in s.get_attribute('class')]
                review_data["rating"] = len(solid_stars)
                logging.debug(f"Time to extract rating: {time.time() - start_time:.4f} seconds")
            except:
                review_data["rating"] = 0
                logging.debug(f"Time to extract rating (failure): {time.time() - start_time:.4f} seconds")

            # Time
            try:
                time_elem = item.find_element(By.XPATH, './/div[@class="shopee-product-rating__time"]')
                review_data["time"] = time_elem.text.strip()
                logging.debug(f"Time to extract time: {time.time() - start_time:.4f} seconds")
            except:
                review_data["time"] = ""
                logging.debug(f"Time to extract time (failure): {time.time() - start_time:.4f} seconds")

            # Content
            try:
                content_start_time = time.time()
                possible_content_xpaths = [
                    './div[contains(@style, "position: relative")]',
                    './div/div[contains(@style, "position: relative")]',
                    './/div[3]/div[contains(@style, "margin-top: 0.75rem;")]',
                    './div[3]/div'
                ]
                content_text = ""
                xpath_used = None

                if self._last_content_xpath_found:
                    logging.debug(f"Trying cached XPath for content: '{self._last_content_xpath_found}'")
                    try:
                        content_elem = item.find_element(By.XPATH, self._last_content_xpath_found)
                        content_text = content_elem.text.strip()
                        xpath_used = self._last_content_xpath_found
                        logging.debug(f"Successfully found content using cached XPath in {time.time() - content_start_time:.4f} seconds.'")
                    except NoSuchElementException:
                        logging.debug(f"Cached XPath '{self._last_content_xpath_found}' did not find content. Trying other XPaths.")

                if not content_text:
                    for xpath in possible_content_xpaths:
                        logging.debug(f"Trying XPath for content: '{xpath}'")
                        try:
                            content_elem = item.find_element(By.XPATH, xpath)
                            content_text = content_elem.text.strip().replace('\n', ' ').strip()
                            xpath_used = xpath
                            self._last_content_xpath_found = xpath
                            logging.debug(f"Successfully found content (XPath '{xpath}') in {time.time() - content_start_time:.4f} seconds.")
                            break  # If content is found, exit the loop
                        except NoSuchElementException:
                            logging.debug(f"XPath could not be found:'{xpath}' in {time.time() - content_start_time:.4f} seconds")
                            continue  # Try the next xpath

                review_data["content"] = content_text
                logging.debug(f"Total time to extract content: {time.time() - start_time:.4f} seconds. XPath used: '{xpath_used if xpath_used else 'None'}'")

            except Exception as e:
                review_data["content"] = ""
                logging.warning(f"Error extracting content in {time.time() - start_time:.4f} seconds: {e}")


               # Seller respond
                try:
                    start_time = time.time()
                    timeout = 1.5
                    seller_respond = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, './/div[@class="TQTPT9"]//div[@class="qiTixQ"]'))
                    )
                    review_data["seller_respond"] = seller_respond.text.strip().replace('\n', ' ').strip()
                    logging.debug(f"Time to extract seller response: {time.time() - start_time:.4f} seconds")
                except TimeoutException:
                    review_data["seller_respond"] = ""
                    logging.debug(f"Time to extract seller response (timeout): {time.time() - start_time:.4f} seconds")
                except Exception as e:
                    review_data["seller_respond"] = ""
                    logging.debug(f"Time to extract seller response (other failure): {time.time() - start_time:.4f} seconds - {e}")

            # Like count
            try:
                like_elem = item.find_element(By.XPATH, './/div[@class="shopee-product-rating__like-count"]')
                like_text = like_elem.text.strip()
                review_data["like_count"] = int(like_text) if like_text.isdigit() else 0
                logging.debug(f"Time to extract like count: {time.time() - start_time:.4f} seconds")
            except:
                review_data["like_count"] = 0
                logging.debug(f"Time to extract like count (failure): {time.time() - start_time:.4f} seconds")

            # Images
            review_data["images"] = []
            try:
                images_start_time = time.time()
                image_elems = item.find_elements(By.XPATH, './/img')
                for img in image_elems:
                    img_url = img.get_attribute('src')
                    if img_url:
                        # Verificar se a imagem tem dimensões visíveis
                        if img.size['width'] > 0 and img.size['height'] > 0:
                            review_data["images"].append(img_url)
                        else:
                            logging.debug(f"Ignorando imagem invisível: {img_url}")
                logging.debug(f"Time to extract images: {time.time() - images_start_time:.4f} seconds")
            except:
                review_data["images"] = []
                logging.debug(f"Time to extract images (failure): {time.time() - start_time:.4f} seconds")

            # Videos
            review_data["videos"] = []
            try:
                videos_start_time = time.time()
                video_elems = item.find_elements(By.XPATH, './/video')
                for video in video_elems:
                    video_url = video.get_attribute('src')
                    if video_url:
                        review_data["videos"].append(video_url)
                logging.debug(f"Time to extract videos: {time.time() - videos_start_time:.4f} seconds")
            except:
                review_data["videos"] = []
                logging.debug(f"Time to extract videos (failure): {time.time() - start_time:.4f} seconds")

            logging.debug(f"Total time to extract review data: {time.time() - start_time:.4f} seconds")
            return review_data


    def _search_and_scrape(self):
        """Scrapes product links from a search page and then details."""
        self._load_search_page()
        product_links = self._get_product_links(self.max_products)
        for i, link in enumerate(tqdm(product_links, desc="Processing products")):
            product_data = {"link": link}
            if not self.index_only:
                product_data = self.scrape_product_details(product_data)
            self.all_products_data.append(product_data)
            self._periodic_save()
        logging.info("Scraping complete.")


    def _scrape_product_description(self):
        """Scrapes and returns the product description."""
        description_text = ""
        possible_desc_xpaths = [
            '//section[contains(@class, "I_DV_3")][h2[contains(text(), "Descrição")]]/div/div',
            '//*[@id="sll2-normal-pdp-main"]/div/div/div/div[2]/div[4]/div/div[1]/div[1]/section[2]/div',
            '//*[@id="sll2-normal-pdp-main"]/div/div/div/div[2]/div[3]/div/div[1]/div[1]/section[2]/div'
        ]
        wait_desc = WebDriverWait(self.driver, 3)
        for desc_xpath in possible_desc_xpaths:
            logging.debug(f"Trying xpath: {desc_xpath}")
            try:
                desc_div = wait_desc.until(EC.presence_of_element_located((By.XPATH, desc_xpath)))
                description_text = desc_div.text.replace('\n', ' ').strip()
                if description_text:
                    logging.debug("Description found.")
                    return description_text
            except (NoSuchElementException, TimeoutException):
                continue
        logging.warning("Could not find description.")
        return ""

    def _scrape_product_category(self):
        """Scrapes and returns the product category."""
        category_text = ""
        possible_desc_xpaths = [
            '//section[contains(@class, "I_DV_3")][h2[contains(text(), "Detalhes")]]/div/div[h3[contains(text(), "Categoria")]]/div',
        ]
        wait_desc = WebDriverWait(self.driver, 3)
        for desc_xpath in possible_desc_xpaths:
            logging.debug(f"Trying xpath: {desc_xpath}")
            try:
                category_div = wait_desc.until(EC.presence_of_element_located((By.XPATH, desc_xpath)))
                category_text = category_div.text.replace('\n', ' ').strip()
                if category_text:
                    logging.debug("Category found.")
                    return category_text
            except (NoSuchElementException, TimeoutException):
                continue
        logging.warning("Could not find category.")
        return ""


    def _scroll_page_for_reviews(self, num_attempts=4, scroll_fraction=0.2, pause_time=0.5):
        """Scrolls the page to help load review section."""
        try:
            logging.debug("Scrolling down to load reviews section...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            for i in range(num_attempts):
                self.driver.execute_script(f"window.scrollBy(0, {int(last_height * scroll_fraction * (i + 1))});")
                time.sleep(pause_time)
            logging.debug("Finished scrolling attempts.")
        except Exception as e:
            logging.warning(f"Error during scrolling: {e}")

    def _wait_for_first_review(self, timeout=15):
        """Waits for the first review element to be present."""
        review_item_xpath = './/div[contains(@class,"shopee-product-rating__main")]'
        wait_reviews = WebDriverWait(self.driver, timeout)
        try:
            logging.info("Waiting for the first review item...")
            wait_reviews.until(EC.presence_of_element_located((By.XPATH, review_item_xpath)))
            logging.info("First review item detected.")
            return True
        except TimeoutException:
            logging.warning("Timed out waiting for the first review item.")
            return False
        
    def _parse_rating_filters(self):
        """Parses the rating overview filters and returns them."""
        overview_xpath = '//*[@id="sll2-normal-pdp-main"]/div/div/div/div[2]/div[3]/div/div[1]/div[2]/div/div/div[2]'
        filter_locator = (By.XPATH, f"{overview_xpath}//div[contains(@class,'product-rating-overview__filter')]//div[contains(@class,'product-rating-overview__filter')]")
        filters = []
        try:
            wait_filters_text = WebDriverWait(self.driver, 15)
            wait_filters_text.until(EC.visibility_of_element_located(filter_locator))
            wait_filters_text.until(lambda driver: any(el.text.strip() for el in driver.find_elements(*filter_locator)))
            logging.info("Rating filter texts loaded.")
            overview_elem = self.driver.find_element(By.XPATH, overview_xpath)
            filters = overview_elem.find_elements(*filter_locator)
            return filters
        except TimeoutException:
            logging.warning("Timed out waiting for rating filter texts.")
            return []
        except NoSuchElementException:
            logging.warning(f"Could not find rating overview container or filters.")
            return []


    def _extract_detailed_rating(self, filters):
        """Extracts detailed rating information from the filters."""
        detailed_rating = {}
        total_ratings = 0
        if filters:
            logging.info(f"Found {len(filters)} filter elements.")
            for f in filters:
                text = f.text.strip()
                logging.debug(f"Processing filter text: '{text}'")
                match = re.match(r'(.+?)\s*\(([\d.,]+(?:k|mil)?)\)', text, re.IGNORECASE)
                if match:
                    label = match.group(1).strip().lower()
                    count_text = match.group(2)
                    value = self._convert_shortened_number(count_text)
                    key = self._normalize_rating_key(label)
                    detailed_rating[key] = value
                    if key.endswith("_star"):
                        total_ratings += value
                    logging.debug(f"Extracted rating: {key} = {value}")
                else:
                    logging.warning(f"Could not parse filter text: '{text}'")
        else:
            logging.warning("No rating filters to process.")
        return detailed_rating, total_ratings

    def _normalize_rating_key(self, label):
        """Normalizes the rating label to a consistent key."""
        if label.startswith("5"): return "5_star"
        elif label.startswith("4"): return "4_star"
        elif label.startswith("3"): return "3_star"
        elif label.startswith("2"): return "2_star"
        elif label.startswith("1"): return "1_star"
        elif "tudo" in label: return "all"
        elif "comentários" in label: return "commented"
        elif "mídia" in label or "media" in label: return "media"
        else: return re.sub(r'\s+', '_', label)

    def _collect_media_reviews(self, filters, media_count):
        """Collects reviews with media only."""
        all_reviews = []
        if self.media_only and media_count > 0 and filters:
            for filter_div in filters:
                if "mídia" in filter_div.text.strip().lower() or "media" in filter_div.text.strip().lower():
                    logging.info("Found and attempting to click 'Com Mídia' filter.")
                    try:
                        wait = WebDriverWait(self.driver, 10)
                        media_filter_element = wait.until(EC.element_to_be_clickable(filter_div))
                        media_filter_element.click()
                        time.sleep(2)
                        reviews_to_collect = min(media_count, self.review_limit)
                        all_reviews = self._collect_reviews(reviews_to_collect)
                        return all_reviews
                    except (TimeoutException, Exception) as e:
                        logging.warning(f"Error clicking media filter: {e}")
                        return []
            logging.warning("Could not find or click 'Com Mídia' filter.")
        elif self.media_only and media_count == 0:
            logging.info("No media reviews reported, skipping collection.")
        elif self.media_only and not filters:
            logging.warning("No filters found to click for media reviews.")
        return all_reviews
    

    def _collect_all_star_reviews(self, filters):
        """Collects reviews for all star types."""
        all_reviews = []
        if self.all_star_types and filters:
            star_filters = [f for f in filters if re.match(r'\d+\s*(?:[Ss]ao|[Ee]strela)[s]?\s*\(', f.text.strip())]
            if star_filters:
                for filter_div in star_filters:
                    match = re.match(r'(\d+)\s*(?:[Ss]ao|[Ee]strela)[s]?\s*\(([^)]*)\)', filter_div.text.strip())
                    if match:
                        star_value = match.group(1)
                        star_count = self._convert_shortened_number(match.group(2))
                        if star_count > 0:
                            logging.info(f"Clicking filter for {star_value} stars ({star_count} reviews)...")
                            try:
                                self.driver.execute_script("arguments[0].click();", filter_div)
                                time.sleep(2)
                                reviews_to_collect = min(star_count, self.star_limit_per_type)
                                logging.info(f"Collecting up to {reviews_to_collect} reviews for {star_value} stars.")
                                all_reviews += self._collect_reviews(reviews_to_collect)
                                # Note: We are not clicking back to "All" or navigating further for simplicity.
                            except Exception as e:
                                logging.warning(f"Error collecting {star_value}-star reviews: {e}")
                        else:
                            logging.debug(f"Skipping {star_value}-star reviews as count is zero.")
            else:
                logging.warning("No star rating filters found.")
        elif self.all_star_types and not filters:
            logging.warning("No filters found to collect all star reviews.")
        return all_reviews
            

    def _collect_general_reviews(self, detailed_rating, total_ratings):
        """Collects general reviews if no specific filter is selected."""
        if not self.media_only and not self.all_star_types:
            logging.info("Collecting general reviews.")
            total_reviews_available = detailed_rating.get("all", total_ratings)
            reviews_to_collect = min(total_reviews_available, self.review_limit)
            if reviews_to_collect > 0:
                logging.info(f"Attempting to collect up to {reviews_to_collect} general reviews.")
                return self._collect_reviews(reviews_to_collect)
            else:
                logging.info("No general reviews available or count is zero.")
        return []



    def _rescrape_missing_comments(self):
        """Rescrapes comments for products in output data that have no comments."""
        logging.info("Rescraping missing comments from existing data...")
        for link, product in list(self.output_data.items()):
            if product.get("comments") == []:
                try:
                    updated_product = self.scrape_product_details(product)
                    self.output_data[link] = updated_product
                    self._periodic_save()
                except Exception as e:
                    logging.warning(f"Error rescraping comments for {link}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True) # Make either -k or --product-link mandatory
    group.add_argument("-k", "--keyword", help="Search term (ignored if --product-link is used)")
    group.add_argument("-l","--product-link", help="Direct URL of the Shopee product to scrape reviews from")
    parser.add_argument("-n", "--num", type=int, default=10, help="Number of products")
    parser.add_argument("-r", "--review-limit", type=int, default=10, help="Max reviews per product")
    parser.add_argument("--index-only", action="store_true", default=False, help="If set, only retrieve index data")
    parser.add_argument("--all-star-types", action="store_true", default=False, help="Retrieve comments by filtering each star rating.")
    parser.add_argument("--star-limit-per-type", type=int, default=10, help="Number of reviews to retrieve per star type.")
    parser.add_argument("--chrome-user-data-dir", default=None, help="User data directory for Chrome")
    parser.add_argument("--media-only", action="store_true", default=False, help="Only retrieve reviews with media (images or videos).")
    parser.add_argument("-c", "--continue-scrape", action="store_true", default=False, help="Continue scraping reviews from the last saved page (only for single product link).")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output file.")

    args = parser.parse_args()

    if args.product_link:
        if args.index_only:
            print("Warning: --index-only is ignored when --product-link is used.")
            args.index_only = False # Force False as it doesn't make sense with a direct link
        if args.num != parser.get_default("num"): # Check if -n was changed from the default
            print(f"Warning: --num ({args.num}) is ignored when --product-link is used.")
        if args.all_star_types and args.media_only:
            parser.error("--all-star-types and --media-only cannot be used together.")
        scraper = ShopeeScraper(args.keyword,
                                args.num,
                                args.index_only,
                                args.review_limit,
                                all_star_types=args.all_star_types,
                                star_limit_per_type=args.star_limit_per_type,
                                chrome_user_data_dir=args.chrome_user_data_dir,
                                media_only=args.media_only,
                                product_link=args.product_link,
                                continue_scrape=args.continue_scrape,
                                output_file=args.output) # Pass the new parameter
        scraper.execute()
    else:
        scraper = ShopeeScraper(args.keyword,
                                args.num,
                                args.index_only,
                                args.review_limit,
                                all_star_types=args.all_star_types,
                                star_limit_per_type=args.star_limit_per_type,
                                chrome_user_data_dir=args.chrome_user_data_dir,
                                media_only=args.media_only,
                                product_link=args.product_link,
                                continue_scrape=False,
                                output_file=args.output) # continue_scrape is only relevant for a single product link
        scraper.execute()
