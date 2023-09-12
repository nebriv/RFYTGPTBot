import googleapiclient.discovery
import googleapiclient.errors
import time
import json
import os
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import pprint


class YouTubeClient:
    def __init__(self, channel_id):

        # Load the client secrets from the downloaded JSON
        client_secrets_file = "google_secret.json"

        # Define the scopes. For read-only access, "https://www.googleapis.com/auth/youtube.readonly" would suffice
        scopes = ["https://www.googleapis.com/auth/youtube"]

        # Get credentials and create a service object
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes)
        # Check if token.json exists
        if os.path.exists('token.json'):
            with open('token.json', 'r') as token_file:
                token_data = json.load(token_file)
                credentials = Credentials.from_authorized_user_info(token_data)
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes)
            credentials = flow.run_local_server(port=0)
            with open('token.json', 'w') as token_file:
                token_file.write(credentials.to_json())

        self.youtube = build("youtube", "v3", credentials=credentials)
        self.channel_id = channel_id

    def get_live_chat_id(self):
        request = self.youtube.liveBroadcasts().list(part="id,snippet,contentDetails,status", broadcastStatus="active")
        response = request.execute()

        if response['items'][0]['status']['lifeCycleStatus'] != 'live':
            return None
        return response['items'][0]['snippet']['liveChatId']

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