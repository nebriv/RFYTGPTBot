from chat_response_modules.chatgpt import ChatGPT
from yt_api import YouTubeClient
import time
import queue
import threading
import datetime
import os
# import vlc
from config import openai_key, channel_id, bot_display_name, output_device
from google.cloud import texttospeech_v1beta1 as texttospeech
import sounddevice as sd
import soundfile as sf
from prompt_config import prompt_prefix
from chat_fetchers.yt_chat_scraper import YoutubeChatScraper
from chat_fetchers.yt_api_chat import YouTubeChat
from chat_merger import ChatMerger
from logger import logger

class LiveStreamChatBot:
    def __init__(self, channel_id):
        logger.info("Starting LiveStreamChatBot")
        self.youtube_api_client = YouTubeClient(channel_id)
        self.youtube_chat = None
        self.chat_scraper = None

        if YouTubeChat:
            self.youtube_chat = YouTubeChat(self.youtube_api_client, bot_display_name)
            self.youtube_chat.start_threaded()

        if YoutubeChatScraper:
            self.chat_scraper = YoutubeChatScraper(self.youtube_api_client.get_live_id(), bot_display_name)
            self.chat_scraper.start_threaded()

        logger.info("Letting chat gather for 30 seconds")
        time.sleep(30)

        self.bot = ChatGPT()
        self.bot.setup(openai_key, prompt_prefix=prompt_prefix)
        self.message_queue = queue.Queue()

        self.all_messages_context = []
        self.max_global_context_length = 100

        self.live_chat_id = self.youtube_api_client.get_live_chat_id()
        if not self.live_chat_id:
            logger.error("Not currently live.")
            return False

        self.bot_display_name = bot_display_name
        
        # Timestamp of the last processed message
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # current UTC timestamp in YouTube's format
        self.last_timestamp = now
        
        self.stop_fetching = False  # Flag to stop the fetch thread if necessary
        self.first_run = True
        self.fetch_thread = threading.Thread(target=self.fetch_messages)

    def fetch_messages(self):
        logger.info("Fetching Messages")
        while not self.stop_fetching:

            merger = ChatMerger(self.chat_scraper, self.youtube_chat)
            messages = merger.get_unique_messages()

            if self.first_run:
                self.all_messages_context = messages
                self.first_run = False
            else:
                for message in messages:
                    logger.debug(f"Recieved Message: {message}")
                    self.message_queue.put(message)
                    self.all_messages_context.append(message)


    def process_messages(self):
        while not self.message_queue.empty():
            author, timestamp, message = self.message_queue.get()
            formatted_message = f"From: {author}, {message}"
            response = self.bot.get_response_text(author, formatted_message, self.all_messages_context)
            logger.debug(f"Recieved Response from OpenAI: {response}")
            self.all_messages_context.append({"role": "system", "content": f"{response}"})
            self.all_messages_context = self.all_messages_context[-100:]

            # Generate TTS audio from the response and give it to a file
            start_time = time.time()
            tts_audio_path = self.generate_tts_audio(response)
            end_time = time.time()  # Add timestamp at the end
            step_time = end_time - start_time
            logger.info(f"Time taken for generating TTS audio: {step_time} seconds")
            logger.debug("Playing TTS Audio")
            self.play_audio_file(tts_audio_path)

            #self.youtube_client.send_chat_message(self.live_chat_id, str(response)) commented out to remove send chat message

            # ADD TTS stuff here probably, you suck 

    def generate_tts_audio(self, text):
        logger.debug("Generating TTS")
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
        logger.debug(f"Saving TTS Return")
        tts_audio_path = "tts_audio.wav"  # Specify the path and format (e.g., .wav)        
        with open(tts_audio_path, "wb") as audio_file:
            audio_file.write(response.audio_content)
        logger.debug(f"Saving TTS Return")

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
        self.youtube_api_client.send_chat_message(self.live_chat_id, "Hopii, Wake up!")
        self.fetch_thread.start()
        logger.info("Hopii is running.")
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
