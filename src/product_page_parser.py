import logging
import re
import time
from .utils import _convert_shortened_number
from .review_parser import collect_reviews  # Import review-related functions
from .browser import _safe_get
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC

def scrape_product_details(self, product):
    """Main function to scrape product details."""
    try:
        logging.info(f"Scraping details for: {product.get('link', 'N/A')}")
        _safe_get(self, product["link"])

        _scroll_page_for_reviews(self)

        product.setdefault("comments", []) 
        _extract_basic_product_info(self, product)

        if not _wait_for_first_review(self):
            product["detailed_rating"] = {}
            product["total_rating"] = 0
            return product

        filters = _parse_rating_filters(self)
        detailed_rating, total_ratings = _extract_detailed_rating(filters)
        product["detailed_rating"] = detailed_rating
        product["total_rating"] = total_ratings

        
        product.setdefault("comments", []) 
        
        if self.media_only:
            media_reviews = _collect_media_reviews(self, filters, detailed_rating.get("media", 0))
            if media_reviews:
                product["comments"].extend(media_reviews)
                logging.info(f"Collected {len(media_reviews)} media reviews.")

        all_star_reviews = _collect_all_star_reviews(self ,filters)
        if all_star_reviews:
            product["comments"].extend(all_star_reviews)
            logging.info(f"Collected {len(all_star_reviews)} star-rated reviews.")

        general_reviews = _collect_general_reviews(self, detailed_rating, total_ratings)
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

    product["description"] = _scrape_product_description(self)
    product["category"] = _scrape_product_category(self)

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
            product["Ratings"] = _convert_shortened_number(ratings)
            logging.debug(f"Extracted product ratings count text: '{ratings}' (from '{ratings_el.text}')")
        except NoSuchElementException:
            logging.debug("Could not find product ratings count element.")

    # Sold Count
    if "sold" not in product:
        try:
            sold_el = main_el.find_element(By.XPATH, './/span[@class="AcmPRb"]')
            sold_text = sold_el.text.strip()
            product["sold"] = _convert_shortened_number(sold_text)
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

def _extract_detailed_rating(filters):
    """Extracts detailed rating information from the filters."""
    detailed_rating = {}
    total_ratings = 0
    if filters:
        logging.info(f"Found {len(filters)} filter elements.")
        for f in filters:
            text = f.text.strip()
            logging.debug(f"Processing filter text: '{text}'")
            if text.lower() == 'tudo':
                logging.debug("Ignoring Filter 'Tudo'.")
            else:
                match = re.match(r'(.+?)\s*\(([\d.,]+(?:k|mil)?)\)', text, re.IGNORECASE)
                if match:
                    label = match.group(1).strip().lower()
                    count_text = match.group(2)
                    value = _convert_shortened_number(count_text)
                    key = _normalize_rating_key(label)
                    detailed_rating[key] = value
                    if key.endswith("_star"):
                        total_ratings += value
                    logging.debug(f"Extracted rating: {key} = {value}")
                else:
                    logging.warning(f"Could not parse filter text: '{text}'")
    else:
        logging.warning("No rating filters to process.")
    return detailed_rating, total_ratings

def _normalize_rating_key(label):
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
                    all_reviews = collect_reviews(self, reviews_to_collect)
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
                    star_count = _convert_shortened_number(match.group(2))
                    if star_count > 0:
                        logging.info(f"Clicking filter for {star_value} stars ({star_count} reviews)...")
                        try:
                            self.driver.execute_script("arguments[0].click();", filter_div)
                            time.sleep(2)
                            reviews_to_collect = min(star_count, self.star_limit_per_type)
                            logging.info(f"Collecting up to {reviews_to_collect} reviews for {star_value} stars.")
                            all_reviews += collect_reviews(self, reviews_to_collect)
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
            return collect_reviews(self, reviews_to_collect)
        else:
            logging.info("No general reviews available or count is zero.")
    return []

