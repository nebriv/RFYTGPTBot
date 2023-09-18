from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

from lib.logger import logger
import pickle

class YouTubeClient:
    def __init__(self, channel_id):
        # Load the client secrets from the downloaded JSON
        client_secrets_file = "google_secret.json"

        # Define the scopes. For read-only access, "https://www.googleapis.com/auth/youtube.readonly" would suffice
        scopes = ["https://www.googleapis.com/auth/youtube"]

        # Check if token.pickle file exists
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        else:
            creds = None

        # If there are no (valid) credentials available, prompt the user to log in
        if not creds or not creds.valid or not creds.refresh_token:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes)

            # Explicitly request offline access
            flow.authorization_url(prompt='consent', access_type='offline')

            creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        self.youtube = build("youtube", "v3", credentials=creds)
        self.channel_id = channel_id

    def get_live_chat_id(self):
        request = self.youtube.liveBroadcasts().list(part="id,snippet,contentDetails,status", broadcastStatus="active")
        response = request.execute()

        if len(response['items']) == 0:
            logger.error("No active live streams found.")
            return None
        if response['items'][0]['status']['lifeCycleStatus'] != 'live':
            return None
        return response['items'][0]['snippet']['liveChatId']

    def get_live_id(self):
        request = self.youtube.liveBroadcasts().list(part="id,snippet,contentDetails,status", broadcastStatus="active")
        response = request.execute()

        if len(response['items']) == 0:
            logger.error("No active live streams found.")
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
        r = None
        try:
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
            r = request.execute()
        except Exception as e:
            logger.error(f'Error sending message: {e}', exc_info=True)

        return r


if __name__ == '__main__':
    from config import *
    yt = YouTubeClient(channel_id)
    live_chat_id = yt.get_live_chat_id()
    logger.info(live_chat_id)