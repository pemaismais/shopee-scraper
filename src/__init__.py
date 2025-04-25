import os
import sys
import datetime
import logging

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    log_filename = datetime.datetime.now().strftime("shopee_%d_%m_%H_%M_%S.log")
    log_filepath = os.path.join("logs", log_filename)

    logger = logging.getLogger() 
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(module)s - %(message)s") 

    file_handler = logging.FileHandler(log_filepath)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO) 
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

setup_logging()
