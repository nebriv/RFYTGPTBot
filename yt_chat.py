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