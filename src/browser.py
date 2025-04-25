import logging
import os
import pickle
import sys
import time
import undetected_chromedriver as uc


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
            
def _safe_get(self, url):
    """Wrapper for driver.get() with captcha checking"""
    self.driver.get(url)
    time.sleep(3)  # Wait for page to load
    while _check_captcha(self):
        logging.info("Retrying after captcha...")
        self.driver.get(url)
        time.sleep(3)  # Wait for page to load
        _check_captcha(self)
        self.driver.implicitly_wait(3)

def _check_captcha(self):
    """Check for captcha and wait if detected"""
    blacklist = ["login", "captcha","verify","security","check","auth","error"]
    if any(x in self.driver.current_url.lower() for x in blacklist):
        logging.info("Captcha/Login detected! Please solve it...")
        input("Press Enter after solving the captcha...")
        time.sleep(5)  # Wait for page to settle after captcha
        return True
    return False