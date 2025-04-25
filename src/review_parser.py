import logging
import time
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm


def collect_reviews(self, max_reviews):
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
                            review_data = _extract_review_data(self, item)
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
                        content_text = content_elem.text.strip().replace('\n', ' ').strip()
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
