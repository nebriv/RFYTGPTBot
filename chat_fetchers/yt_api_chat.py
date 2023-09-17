import queue
import threading
import time
from googleapiclient.errors import HttpError

class YouTubeChat:

    def __init__(self, youtube_client, bot_display_name):
        self.bot_display_name = bot_display_name
        self.live_chat_id = None
        self.next_page_token = None

        # YouTube API client setup
        self.youtube = youtube_client

        self.wait_time = 1  # Time to wait between API requests

        # Similar attributes to YoutubeChatScraper
        self.seen_messages = set()
        self.message_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.error_count = 0
        self.MAX_ERRORS = 5
        self.running = True

    def fetch_messages(self):
        if not self.live_chat_id:
            self.live_chat_id = self.youtube.get_live_chat_id()

        try:
            latest_messages = []
            max_results = 100
            while self.running:
                messages_data = self.youtube.get_live_chat_messages(self.live_chat_id, max_results=max_results, page_token=self.next_page_token)

                # Storing the next page token and resetting error_count
                self.error_count = 0

                # Looping through each item in the response
                latest_messages = messages_data['items'] + latest_messages
                polling_interval = messages_data.get('pollingIntervalMillis', 10000) / 1000 + 1
                # Check if there's another page
                self.next_page_token = messages_data.get('nextPageToken')
                print(f"Next page token: {self.next_page_token}")
                if not self.next_page_token or len(messages_data['items']) < max_results:
                    print("No more pages")
                    break

                if not self.next_page_token:
                    print("No next page token")
                    break

                time.sleep(polling_interval)

            for chat_item in latest_messages:
                message_id = chat_item['id']
                if message_id not in self.seen_messages:
                    # print(f"Recieved Message: {chat_item}")
                    author_name = chat_item['authorDetails']['displayName']
                    if author_name == self.bot_display_name:
                        continue
                    timestamp = chat_item['snippet']['publishedAt']
                    message = chat_item['snippet']['displayMessage']

                    self.message_queue.put({
                        'author': author_name,
                        'timestamp': timestamp,
                        'message': message
                    })
                    self.seen_messages.add(message_id)
        except HttpError as e:
            print(f"An error occurred: {e}")
            self.error_count += 1

    def run_chat(self):
        while not self.stop_event.is_set() and self.error_count < self.MAX_ERRORS:
            try:
                self.fetch_messages()
                time.sleep(60)
            except Exception as e:
                print(f"An error occurred: {e}")
                self.error_count += 1

        if self.error_count >= self.MAX_ERRORS:
            print("Max errors reached. Exiting scraper.")
            self.stop_event.set()

    def start_threaded(self):
        self.api_thread = threading.Thread(target=self.run_chat)
        self.api_thread.start()

    def stop(self):
        self.stop_event.set()
        self.api_thread.join()  # Wait for the thread to finish
