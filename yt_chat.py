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


class YouTubeClient:
    def __init__(self, channel_id):
        # Load the client secrets from the downloaded JSON
        client_secrets_file = "google_secret.json"

        # Define the scopes. For read-only access, "https://www.googleapis.com/auth/youtube.readonly" would suffice
        scopes = ["https://www.googleapis.com/auth/youtube"]

        # Initialize the storage object for our token
        storage = Storage('token.json')
        self.credentials = storage.get()

        if not self.credentials or self.credentials.invalid:
            flow = flow_from_clientsecrets(client_secrets_file, scope=scopes)
            # Setting access_type to offline here
            flow.params['access_type'] = 'offline'
            flow.params['prompt'] = 'consent'
            self.credentials = run_flow(flow, storage)

        self.youtube = build("youtube", "v3", credentials=self.credentials)
        self.channel_id = channel_id

    def get_live_chat_id(self):
        request = self.youtube.liveBroadcasts().list(part="id,snippet,contentDetails,status", broadcastStatus="active")
        response = request.execute()

        if len(response['items']) == 0:
            print("No active live streams found.")
            return None
        print(response['items'])
        if response['items'][0]['status']['lifeCycleStatus'] != 'live':
            return None
        return response['items'][0]['snippet']['liveChatId']

    def get_live_id(self):
        request = self.youtube.liveBroadcasts().list(part="id,snippet,contentDetails,status", broadcastStatus="active")
        response = request.execute()

        if len(response['items']) == 0:
            print("No active live streams found.")
            return None
        if response['items'][0]['status']['lifeCycleStatus'] != 'live':
            return None
        return response['items'][0]['id']

    def get_live_chat_messages(self, live_chat_id, max_results=15, page_token=None):
        request = self.youtube.liveChatMessages().list(
            liveChatId=live_chat_id,
            part="id,snippet,authorDetails",
            maxResults=max_results,
            pageToken=page_token
        )
        return request.execute()

    def send_chat_message(self, live_chat_id, message):
        request = self.youtube.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {
                        "messageText": message
                    }
                }
            }
        )
        return request.execute()


if __name__ == '__main__':
    from config import *
    yt = YouTubeClient("UC_x5XG1OV2P6uZZ5FSM9Ttw")
    scraper = YouTubeChat(yt, bot_display_name)
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
