import googleapiclient.discovery
import googleapiclient.errors
import time
import json
import os
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import pprint
from google.auth.transport.requests import Request
from oauth2client.client import flow_from_clientsecrets, AccessTokenCredentials
from oauth2client.file import Storage
from oauth2client.tools import run_flow
import queue
import threading
import logging
import queue
import threading
import time
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class YouTubeChat:

    def __init__(self, youtube_client, bot_display_name):
        self.bot_display_name = bot_display_name
        self.live_chat_id = None
        self.next_page_token = None

        # YouTube API client setup
        self.youtube = youtube_client

        # Similar attributes to YoutubeChatScraper
        self.seen_messages = set()
        self.message_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.error_count = 0
        self.MAX_ERRORS = 5

    def fetch_messages(self):
        if not self.live_chat_id:
            self.live_chat_id = self.youtube.get_live_chat_id()

        try:
            response = self.youtube.get_live_chat_messages(self.live_chat_id, max_results=100, page_token=self.next_page_token)

            # Storing the next page token and resetting error_count
            self.next_page_token = response.get('nextPageToken')
            self.error_count = 0

            for chat_item in response.get('items', []):
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
                time.sleep(10)
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
