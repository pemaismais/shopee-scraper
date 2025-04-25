import logging
import re
from selenium.common.exceptions import NoSuchElementException
from .browser import _safe_get, _load_cookies 
from selenium.webdriver.common.by import By

def scrape_search_page(self):
        logging.info("Loading Shopee search page...")
        base_url = "https://shopee.com.br/search?keyword="
        kw_encoded = re.sub(r'\s+', '%20', self.search_term.strip())
        url = f"{base_url}{kw_encoded}&page=0&sortBy=sales"
        _safe_get(self, url)
        _load_cookies(self)
        _safe_get(self, url)
        self.driver.implicitly_wait(5)
        return _retrieve_products(self)

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

def _retrieve_products(self):
        product_elements = _get_search_page_product_elements(self)
        if product_elements:
            return _extract_product_search_page_info(self, product_elements)
        return []
    