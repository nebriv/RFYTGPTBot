from chat_modules.chatgpt import ChatGPT
from yt_chat import YouTubeClient
import time
import queue
from collections import deque
import threading
import datetime
from config import openai_key, channel_id, bot_display_name


prompt_prefix = """Your name is Hopii. You are a knowledgable chatbot on the Rocket Future YouTube Channel. You are here to answer questions about SpaceX, Rockets, StarShip, and all things space. 
You love space, technology, and ice cream. Whenever possible please address the user as 'Space Knut'. You were created by Andrew, the founder of Rocket Future, he is frequently on site live streaming, but you fill in the dead air via an AI persona on screen.

You responses MUST be short, less than 150 characters. The response you provide will be fed directly into the youtube API. Do not include any prefixes, and remember just act natural!\n"
"""


class LiveStreamChatBot:
    def __init__(self, channel_id):
        print("Starting")
        self.youtube_client = YouTubeClient(channel_id)
        self.bot = ChatGPT()
        self.bot.setup(openai_key, prompt_prefix=prompt_prefix)
        self.message_queue = queue.Queue()

        self.all_messages_context = []
        self.max_global_context_length = 100

        self.live_chat_id = self.youtube_client.get_live_chat_id()
        if not self.live_chat_id:
            print("Not currently live.")
            return False

        self.bot_display_name = bot_display_name

        # Timestamp of the last processed message
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # current UTC timestamp in YouTube's format
        self.last_timestamp = now

        self.stop_fetching = False  # Flag to stop the fetch thread if necessary
        self.fetch_thread = threading.Thread(target=self.fetch_messages)

    def fetch_messages(self):
        buffer_time = 5  # Added buffer time in seconds
        max_results = 100
        polling_interval = 5
        while not self.stop_fetching:
            next_page_token = None
            latest_messages = []

            # Pagination loop to fetch all the messages
            while True:
                messages_data = self.youtube_client.get_live_chat_messages(self.live_chat_id,
                                                                           page_token=next_page_token, max_results=max_results)
                print(f"Got {len(messages_data['items'])} messages")
                # Append new messages. Since we're paginating from oldest to newest,
                # the older messages are prepended to maintain order.
                latest_messages = messages_data['items'] + latest_messages

                # Determine the polling interval for the next fetch
                polling_interval = messages_data.get('pollingIntervalMillis', 10000) / 1000 + buffer_time

                # Check if there's another page
                next_page_token = messages_data.get('nextPageToken')
                print(f"Next page token: {next_page_token}")
                if not next_page_token or len(messages_data['items']) < max_results:
                    break

                if not next_page_token:
                    break

                time.sleep(0.1) # To avoid throttling

            # Process the messages
            print(len(latest_messages))
            for i in range(len(latest_messages) - 1, -1, -1):
                item = latest_messages[i]
                author = item['authorDetails']['displayName']
                message = item['snippet']['displayMessage']
                timestamp = item['snippet']['publishedAt']
                print(f"Message Timestamp: {timestamp} | Last Timestamp: {self.last_timestamp}")

                # Check if this message is newer than the last one we processed
                if (not self.last_timestamp or timestamp > self.last_timestamp) and author != self.bot_display_name:
                    print("Adding message")
                    self.message_queue.put((author, message))
                    # Update the global context with the newest message
                    self.all_messages_context.append({"role": "user", "content": f"{author}: {message}"})

                    # Limit the context to the last n messages
                    self.all_messages_context = self.all_messages_context[-self.max_global_context_length:]                    # Update the last timestamp with the newest message's timestamp
                    self.last_timestamp = timestamp
                else:
                    # Since we're going backwards, as soon as we hit an old message, we can break out of the loop
                    break

            print(f"Fetching polling interval: {polling_interval}")

            # Wait for the given polling interval before fetching the next page
            time.sleep(polling_interval)

    def process_messages(self):
        while not self.message_queue.empty():
            author, message = self.message_queue.get()
            response = self.bot.respond_to(author, message, self.all_messages_context)
            self.all_messages_context.append({"role": "system", "content": f"{response}"})
            self.all_messages_context = self.all_messages_context[-100:]

            self.youtube_client.send_chat_message(self.live_chat_id, str(response))

            # ADD TTS stuff here probably, you suck 


    def run(self):
        self.youtube_client.send_chat_message(self.live_chat_id, "Hello, I'm here now, have no fear!")
        self.fetch_thread.start()
        try:
            while True:
                self.process_messages()
                time.sleep(5)  # Wait 5 seconds between responding to messages
        except KeyboardInterrupt:  # Graceful shutdown
            self.stop_fetching = True
            self.fetch_thread.join()

if __name__ == '__main__':
    bot = LiveStreamChatBot(channel_id)
    bot.run()
