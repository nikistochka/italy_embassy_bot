import logging
import json
import random
import requests
import time
import sys
from selenium import webdriver
from selenium.common.exceptions import MoveTargetOutOfBoundsException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# Set up logging
logging.basicConfig(
    format = '%(asctime)s %(levelname)s: %(message)s',
    level = logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers = [
        logging.FileHandler('attempts.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logging.info("Starting Italy bot")

# Load configuration
with open('config.json') as config_file:
    config = json.load(config_file)
BOOKING_SCREEN_URL = config["prenotami_info"]['booking_screen_url']
USER = config["prenotami_info"]["user"]
PASSWORD = config["prenotami_info"]["password"]
TELEGRAM_CHAT_ID = config["telegram"]["chat_id"]
TELEGRAM_TOKEN = config["telegram"]["token"]
TIMEOUT = config["timeout"]

if not (USER and PASSWORD and TELEGRAM_CHAT_ID and TELEGRAM_TOKEN):
    logging.error("One or more variables are not set. Please check data.json file")
    sys.exit(1)

def send_telegram_message(message):
    """Send a message via Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }

    response = requests.post(url, data=payload)
    result = response.json()

    # Check if the request was successful
    if not result.get('ok'):
        logging.warning(f"Failed to send message: {result}")

def wait_for_element(driver, xpath, timeout=TIMEOUT):
    """Wait for the presence of an element specified by the xpath."""
    try:
        element_present = EC.presence_of_element_located((By.XPATH,xpath))
        WebDriverWait(driver, timeout).until(element_present)
    except Exception.TimeoutException:
        print (f"Timed out waiting \"{xpath}\" for page to load")

def move_mouse_to_random_position(driver):
    """Move the mouse to a random position within the browser window."""
    try:
        max_x, max_y = driver.execute_script("return [window.innerWidth, window.innerHeight];")
        body = driver.find_element(By.TAG_NAME, "body")
        actions = ActionChains(driver)
        x = random.randint(0, max_x)
        y = random.randint(0, max_y)
        actions.move_to_element_with_offset(body, x, y)
        actions.perform()
    except MoveTargetOutOfBoundsException:
        pass


def login(driver):
    """Perform login to the https://prenotami.esteri.it/"""
    logging.info("Attempting to log in.")
    try:
        driver.get('https://prenotami.esteri.it/')
        move_mouse_to_random_position(driver)
        wait_for_element(driver=driver, xpath='//*[@id="login-email"]')
        time.sleep(random.uniform(1, 4))
        driver.find_element(By.XPATH, '//*[@id="login-email"]').send_keys(USER)
        time.sleep(random.uniform(1, 4))
        driver.find_element(By.XPATH, '//*[@id="login-password"]').send_keys(PASSWORD)
        time.sleep(random.uniform(1, 3))
        driver.find_element(By.XPATH, '//*[@id="login-form"]/button').click()
        time.sleep(random.uniform(5, 15))

    except Exception as err:
        logging.error("Failure to login occurred. Exception: " + err)

def check_appointments(driver):
    """Check for available appointments and handle re-login if needed."""
    login_attempts = 0
    max_login_attempts = 5
    
    while True:
        try:
            driver.get('https://prenotami.esteri.it/Services')
            wait_for_element(driver, '/html/body')
            time.sleep(random.uniform(1, 10))

            driver.get(BOOKING_SCREEN_URL)
            wait_for_element(driver, '/html/body')
            time.sleep(random.uniform(11, 20))
            current_url = driver.current_url

            if current_url == 'https://prenotami.esteri.it' or 'https://prenotami.esteri.it/Home?ReturnUrl=' in current_url:
                if login_attempts >= max_login_attempts:
                    message = "Exceeded maximum login attempts. Exiting."
                    logging.error(message)
                    send_telegram_message(message)
                    break
                logging.info("Re-login required. Attempting to log in again.")
                login(driver)
                login_attempts += 1
                continue  # Re-attempt the process after logging in

            elif current_url == BOOKING_SCREEN_URL:
                message = f"Appointment available! Go to {BOOKING_SCREEN_URL}" 
                send_telegram_message(message)
                logging.warning(message)
                time.sleep(1800)  # Wait 30 minutes for the user to book appointment in the same Chrome Tab
                login_attempts = 0
                break  # Exit the loop as the appointment was found

            elif current_url in ['https://prenotami.esteri.it/Services', 'https://prenotami.esteri.it/UserArea']:
                logging.info("No appointments available.")
                time.sleep(random.uniform(11, 20))
                login_attempts = 0
                break  # Exit the loop to wait for the next scheduled check

            else:
                message = "Change detected on prenotami website, please check https://prenotami.esteri.it/Services/"
                send_telegram_message(message)
                logging.warning(message)
                time.sleep(1800)  # Wait for 30 minutes with opened window to check issue manually
                break  # Exit the loop due to unexpected change
        except WebDriverException as err:
            message = f"Network exception while checking for appointments: {e}"
            if login_attempts >= max_login_attempts:
                    message = "Exceeded maximum login attempts. Exiting."
                    logging.error(message)
                    send_telegram_message(message)
                    break
            logging.info("Re-login required. Attempting to log in again.")
            login(driver)
            login_attempts += 1
            continue
        except Exception as e:
            message = f"Exception while checking for appointments: {e}"
            send_telegram_message(message)
            logging.error(message)
            break  # Exit the loop due to exception


if __name__ == "__main__":
    options = Options()
    # options.add_argument("--headless")  # Running headless
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.4472.124 Safari/537.36")  # Example user-agent header

    driver = webdriver.Chrome(options=options)

    try:
        login(driver)
        attempt_counter = 1
        while True:
            logging.info(f"Attempt number {attempt_counter}:")
            check_appointments(driver)
            time.sleep(random.randint(300, 600))  # Wait for 5 to 10 minutes
            attempt_counter += 1
    finally:
        driver.quit()
