from chat_modules.chatgpt import ChatGPT
from yt_chat import YouTubeClient
import time
import queue
from collections import deque
import threading
import datetime
import os
# import vlc
from config import openai_key, channel_id, bot_display_name, output_device
from google.cloud import texttospeech_v1beta1 as texttospeech
import sounddevice as sd
import soundfile as sf
import numpy as np
from prompt_config import prompt_prefix


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
        next_page_token = None
        while not self.stop_fetching:
            latest_messages = []

            # Pagination loop to fetch all the messages
            while True:
                # Double check if this is exceeding quotas. If so, increase the polling interval
                start_time = time.time()
                messages_data = self.youtube_client.get_live_chat_messages(self.live_chat_id,
                                                                           page_token=next_page_token, max_results=max_results)
                end_time = time.time()  # Add timestamp at the end
                step_time = end_time - start_time
                print(f"Got {len(messages_data['items'])} messages")
                print(f"Time taken for retrieving YouTube chat messages: {step_time} seconds")
               
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
            formatted_message = f"From: {author}, {message}"
            response = self.bot.get_response_text(author, formatted_message, self.all_messages_context)
            print(f"Recieved Response from OpenAI: {response}")
            self.all_messages_context.append({"role": "system", "content": f"{response}"})
            self.all_messages_context = self.all_messages_context[-100:]

            # Generate TTS audio from the response and give it to a file
            start_time = time.time()
            tts_audio_path = self.generate_tts_audio(response)
            end_time = time.time()  # Add timestamp at the end
            step_time = end_time - start_time
            print(f"Time taken for generating TTS audio: {step_time} seconds")
            print("Playing TTS Audio")
            self.play_audio_file(tts_audio_path)

        
            #self.youtube_client.send_chat_message(self.live_chat_id, str(response)) commented out to remove send chat message

            # ADD TTS stuff here probably, you suck 

    def generate_tts_audio(self, text):
        print("Generating TTS")
        # Initialize the Google Text-to-Speech client
        client = texttospeech.TextToSpeechClient()

        # Configure the TTS request
        input_text = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Studio-O",
            #name="en-US-Neural2-F",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Generate the TTS audio
        response = client.synthesize_speech(
            input=input_text, voice=voice, audio_config=audio_config
        )

        # Save the TTS audio to a file
        print(f"Saving TTS Return")
        tts_audio_path = "tts_audio.wav"  # Specify the path and format (e.g., .wav)        
        with open(tts_audio_path, "wb") as audio_file:
            audio_file.write(response.audio_content)
        print(f"Saving TTS Return")

        #playsound(audio_file, winsound.SND_ASYNC)

        audio_file = os.path.join(os.path.dirname(__file__), tts_audio_path)
        # media = vlc.MediaPlayer(audio_file)
        # media.play()
        

        return tts_audio_path

    def play_audio_file(self, file_path):
        # Read file to numpy array
        data, fs = sf.read(file_path, dtype='float32')

        # Set default sample rate
        sd.default.samplerate = fs
        sd.default.device = output_device

        # Play the audio
        sd.play(data)

        # Block execution until audio is finished playing
        sd.wait()

    def run(self):
        self.youtube_client.send_chat_message(self.live_chat_id, "Hopii, Wake up!")
        self.fetch_thread.start()
        print("Hopii is running.")
        try:
            while True:
                self.process_messages()
                time.sleep(1)  # Wait 1 seconds between responding to messages
        except KeyboardInterrupt:  # Graceful shutdown
            self.stop_fetching = True
            self.fetch_thread.join()

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'googleapi.json'

if __name__ == '__main__':
    bot = LiveStreamChatBot(channel_id)
    bot.run()
