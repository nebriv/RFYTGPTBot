from selenium import webdriver
import chromedriver_autoinstaller
from selenium.webdriver.common.by import By
import time
import random
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timezone, timedelta
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException, MoveTargetOutOfBoundsException
import logging
import threading
import queue

chromedriver_autoinstaller.install()

logging.basicConfig(level=logging.INFO)


def is_element_in_viewport(driver, element, padding=10):
    return driver.execute_script("""
        let rect = arguments[0].getBoundingClientRect();
        return (
            rect.top >= {0} &&
            rect.left >= {0} &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) - {0} &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth) - {0}
        );
    """.format(padding), element)


def move_mouse_smoothly(actions, target_element, steps=10):
    start_x, start_y = actions._driver.get_window_position().values()  # get the current position
    target_x, target_y = target_element.location.values()

    step_x = (target_x - start_x) / steps
    step_y = (target_y - start_y) / steps

    for i in range(steps):
        actions.move_by_offset(step_x + random.uniform(-10, 10), step_y + random.uniform(-10, 10))
        actions.pause(random.uniform(0.01, 0.05))

    actions.move_to_element(target_element)


def random_interactions(driver, delay=2.0):
    try:
        actions = ActionChains(driver)

        # 1. Randomly scroll
        scroll_amount = random.randint(-100, 100)  # Random value for scroll
        driver.execute_script(f"window.scrollBy(0,{scroll_amount});")

        # 2. Random pause
        time.sleep(delay)

        # 3. Move mouse cursor to random elements
        chat_containers = driver.find_elements(By.CSS_SELECTOR, "yt-live-chat-text-message-renderer")
        visible_containers = [container for container in chat_containers if is_element_in_viewport(driver, container)]

        if visible_containers:
            random_message = random.choice(visible_containers)
            move_mouse_smoothly(actions, random_message)
            actions.perform()
    except MoveTargetOutOfBoundsException:
        logging.warning("MoveTargetOutOfBoundsException while performing random interactions.")

def scroll_to_bottom(driver):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")


def convert_timestamp(ts):
    current_time = datetime.now(timezone.utc)
    hour, minute_ampm = ts.split()
    hour, minute = map(int, hour.split(":"))
    if "PM" in minute_ampm and hour != 12:
        hour += 12
    if "AM" in minute_ampm and hour == 12:
        hour = 0
    converted_time = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return converted_time.isoformat()


class YoutubeChatScraper:

    def __init__(self, live_id, bot_display_name, driver_options=None):
        self.bot_display_name = bot_display_name
        self.url = f"https://www.youtube.com/live_chat?is_popout=1&v={live_id}"
        print(self.url)
        self.driver = self._initialize_driver(driver_options)
        self.seen_messages = set()
        self.message_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.running = False

        self.error_count = 0
        self.MAX_ERRORS = 5
        self.restart_attempt = False

    def _initialize_driver(self, driver_options=None):
        if driver_options is None:
            driver_options = webdriver.ChromeOptions()
            # Adding argument to disable the AutomationControlled flag
            driver_options.add_argument("--disable-blink-features=AutomationControlled")

            # Exclude the collection of enable-automation switches
            driver_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            driver_options.add_argument("--window-size=383,600")
            # Turn-off userAutomationExtension
            driver_options.add_experimental_option("useAutomationExtension", False)

        driver = webdriver.Chrome(options=driver_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        return driver


    def check_page_changed(self):
        # Depending on what happens when access is blocked,
        # you may want to check the page's title, the URL, or for the presence of a specific error message.
        current_title = self.driver.title
        if current_title != self.original_title:
            return True
        # Optionally check for specific error messages or elements
        try:
            blocked_message = self.driver.find_element(By.XPATH, "//div[text()='Access Blocked']")
            if blocked_message:
                return True
        except NoSuchElementException:
            pass
        return False


    def check_for_page_errors(self):
        # Optionally check for specific error messages or elements
        try:
            error_messages = ["Access Blocked", "Error 404", "Not Found", "Forbidden"]
            for message in error_messages:
                if self.driver.find_element(By.XPATH, f"//div[text()='{message}']"):
                    print(f"Error detected on page: {message}")
                    return True
        except NoSuchElementException:
            pass
        return False


    def start(self):
        print(f"Starting to scrape chat messages from {self.url}")
        self.driver.get(self.url)
        self.actions = ActionChains(self.driver)
        time.sleep(2)
        self.original_title = self.driver.title


        print("Locating Top chat dropdown...")
        try:
            dropdown_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[text()='Top chat']"))
            )
            print("Found Top chat dropdown... Clicking...")
            self.actions.move_to_element(dropdown_button).perform()
            time.sleep(1)  # You can adjust this sleep if needed
            dropdown_button.click()
        except TimeoutException:
            raise Exception("Timeout while trying to click on the dropdown button with text 'Top chat'.")

        time.sleep(1)
        try:
            desired_option = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//div[contains(text(),'All messages are visible')]/../.."))
                # /.. goes to the parent
            )
            self.actions.move_to_element(desired_option).perform()
            time.sleep(1)  # You can adjust this sleep if needed
            desired_option.click()
        except TimeoutException:
            raise Exception("Timeout while trying to click on the div with text 'All messages are visible'.")

        time.sleep(2)

        print("Done waiting... loading chat...")
        # This will wait until at least one chat message renderer is present
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "yt-live-chat-text-message-renderer"))
        )

    def get_chat_data(self):
        self.running = True
        print("Getting chat data...")
        # Find all chat container elements
        chat_containers = self.driver.find_elements(By.CSS_SELECTOR, "yt-live-chat-text-message-renderer")
        if not chat_containers:
            raise Exception("No chat containers found. The page might not have loaded properly or there's an issue with the live chat.")
            return

        new_messages = []

        for container in chat_containers:
            try:
                message_id = container.get_attribute("id")
                if message_id not in self.seen_messages:
                    author_name = self.driver.execute_script("return arguments[0].innerText;",
                                                        container.find_element(By.CSS_SELECTOR,
                                                                               "span#author-name")).strip()
                    timestamp = convert_timestamp(self.driver.execute_script("return arguments[0].innerText;",
                                                                        container.find_element(By.CSS_SELECTOR,
                                                                                               "span#timestamp")).strip())
                    message = self.driver.execute_script("return arguments[0].innerText;",
                                                    container.find_element(By.CSS_SELECTOR, "span#message")).strip()

                    self.seen_messages.add(message_id)

                    # print(f"SCRAPED: {message}")
                    if author_name == self.bot_display_name:
                        continue

                    self.message_queue.put({
                        'author': author_name,
                        'timestamp': timestamp,
                        'message': message
                    })
            except StaleElementReferenceException:
                print("Stale element encountered...")
                continue
        # # Print the extracted data
        # for item in new_messages:
        #     print(f"Author: {item['author']}, Timestamp: {item['timestamp']}, Message: {item['message']}")

        # Emulate random interactions
        if random.random() < 0.33:
            random_sleep = random.uniform(0.1, 2.0)
            random_interactions(self.driver, random_sleep)

        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        scrollable_element = self.driver.find_element(By.ID, 'item-scroller')
        self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_element)


    def run_scraper(self):
        try:
            self.start()
        except Exception as e:
            logging.error(f"Error while starting: {e}")
            self.stop_event.set()
            return
        while not self.stop_event.is_set() and self.error_count < self.MAX_ERRORS:
            try:
                self.get_chat_data()
            except Exception as e:
                logging.error(f"Error while getting chat data: {e}")
                self.error_count += 1

                if self.error_count >= self.MAX_ERRORS and not self.restart_attempt:
                    logging.error("Max errors reached. Restarting scraper...")
                    self.restart()

                # After restarting, if there are still errors, exit
                if self.error_count >= self.MAX_ERRORS and self.restart_attempt:
                    logging.error("Max errors reached after restart. Exiting scraper.")
                    self.stop_event.set()


    def start_threaded(self):
        self.scraper_thread = threading.Thread(target=self.run_scraper)
        self.scraper_thread.start()


    def stop(self):
        self.stop_event.set()
        self.scraper_thread.join()  # Wait for the thread to finish
        self.driver.quit()
        self.running = False


    def restart(self):
        if not self.restart_attempt:
            self.restart_attempt = True
        else:
            # If this isn't the first restart attempt (i.e., errors persist after a restart), reset the error count
            self.error_count = 0

        # Reset error count and restart the scraper
        self.error_count = 0
        self.stop_event.clear()
        self.stop_event.set()
        self.running = False
        self.driver.quit()
        self.driver = self._initialize_driver()
        self.start_threaded()

if __name__ == '__main__':
    scraper = YoutubeChatScraper("https://www.youtube.com/live_chat?is_popout=1&v=mhJRzQsLZGg")
    try:
        scraper.start_threaded()
        while True:
            message = scraper.message_queue.get()  # Blocking call, will wait until a new message is available
            print(f"Author: {message['author']}, Timestamp: {message['timestamp']}, Message: {message['message']}")
    except KeyboardInterrupt:
        scraper.stop()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        scraper.stop()
