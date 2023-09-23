from chat_response_modules.chatgpt import ChatGPT
from lib.yt_api import YouTubeClient
import time
import queue
import threading
import os
from config import *
from google.cloud import texttospeech_v1beta1 as texttospeech
import sounddevice as sd
import soundfile as sf
import prompt_config
from chat_fetchers.yt_chat_scraper import YoutubeChatScraper
from chat_fetchers.yt_api_chat import YouTubeChat
from lib.chat_merger import ChatMerger
from lib.logger import logger
import json
from datetime import datetime
import importlib
from lib.context_parsing import ContextParser
import logging
from lib.utils import cleanup_folder, InputManager
from lib.speechtotext import SpeechToText

prompt_prefix = prompt_config.prompt_prefix

ContextParser.install_spacy_model()

disable_tts = False

class LiveStreamChatBot:
    def __init__(self, channel_id):
        logger.info("Starting LiveStreamChatBot")
        self.youtube_api_client = YouTubeClient(channel_id)
        self.live_id = self.youtube_api_client.get_live_id()
        if not self.live_id:
            logger.error(f"Channel {channel_id} is not currently live.")
            exit()

        self.youtube_chat = None
        self.chat_scraper = None
        self.speech_to_text = SpeechToText()
        

        if YouTubeChat:
            self.youtube_chat = YouTubeChat(self.youtube_api_client, bot_display_name)

        if YoutubeChatScraper:
            self.chat_scraper = YoutubeChatScraper(self.youtube_api_client.get_live_id(), bot_display_name)

        self.chat_merger = ChatMerger(self.chat_scraper, self.youtube_chat)

        self.replay_file = None
        self.manual = False

        self.bot = ChatGPT()
        self.context_parser = ContextParser()

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
        now = datetime.utcnow().isoformat() + 'Z'  # current UTC timestamp in YouTube's format
        self.last_timestamp = now
        
        self.stop_running = False  # Flag to stop the fetch thread if necessary
        self.first_run = True
        self.prompt_refresh_interval = 300  # Seconds between refreshing the prompt
        self.fetch_thread = threading.Thread(target=self.fetch_messages)
        self.file_writer_thread = threading.Thread(target=self.batched_file_writer, args=(30,))
        self.refresh_prompt_thread = threading.Thread(target=self.refresh_prompt)
        self.message_log = queue.Queue()
        self.disable_chat_save = False
        self.setup()

    def setup(self):
        if not os.path.exists('chat_logs'):
            os.makedirs('chat_logs')
        cleanup_folder('chat_logs', 10)
        # Generate the filename based on the current date and time
        current_datetime_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_file_path = f"chat_logs/{current_datetime_str}.json"
    
    def process_speech_to_text(self):
        while not self.stop_running:
            if self.speech_to_text.is_listening:
                transcribed_text = self.speech_to_text.transcribed_text
                if transcribed_text:
                    # Process the transcribed text as if it were a message from YouTube chat
                    self.process_transcribed_text(transcribed_text)
    
    def process_transcribed_text(self, transcribed_text):
        #Process the transcribed text as needed, e.g., send it to GPT-3 for a response
        # You can use self.bot or any other processing logic here
        author = "Rocket Future"  # You can set a custom author for transcribed text
        formatted_message = f"From: {author}, {transcribed_text}"
    
        # Send the transcribed text to GPT-3 or perform any other processing
        response = self.bot.get_response_text(author, formatted_message, self.all_messages_context)
    
        # You can log or handle the response as needed
        logger.info({"author": author, "message": transcribed_text, "response": response})

    def refresh_prompt(self):
        while not self.stop_running:
            for _ in range(self.prompt_refresh_interval):
                if self.stop_running:
                    return
                time.sleep(1)
            logger.info("Refreshing prompt")
            importlib.reload(prompt_config)
            self.bot.prompt_prefix = prompt_config.prompt_prefix

    def manual_message_callback(self, message_data):
        self.message_queue.put(message_data)

    # def manual_message_prompt(self):
    #     """Manually prompt for a message to send."""
    #     current_level = logging.getLogger().getEffectiveLevel()
    #     logging.getLogger().setLevel(logging.CRITICAL)
    #     author = input("Enter author name (Bob): ")
    #     if not author:
    #         author = "Bob"
    #     message = input("Enter message to send: ")
    #     logging.getLogger().setLevel(current_level)
    #     self.message_queue.put({"author": author, "message": message, "timestamp": datetime.utcnow().isoformat() + 'Z'})

    def fetch_messages(self):

        logger.info("Fetching Messages")

        if self.manual:
            input_manager = InputManager(self.manual_message_callback, self.stop_running)
            try:
                input_manager.start()
                while not self.stop_running:
                    # Here we're simply waiting for the stop signal
                    pass
            except UnicodeDecodeError:
                logger.verbose("Caught UnicodeDecodeError. Skipping message")
            except SystemExit:
                pass
            except Exception as e:
                logger.error(f"Caught exception handling manual input:\n{str(e)}", exc_info=True)
            finally:
                input_manager.stop()  # Make sure to stop the input manager

            logger.verbose("End of manual loop.")
            return

        logger.debug("Not manual mode.")
        if self.replay_file:
            self.disable_chat_save = True # Disable chat saving if we're replaying a file
            logger.debug(f"Replay file specified, loading {self.replay_file}")
            if os.path.exists(self.replay_file):
                with open(self.replay_file, 'r') as f:
                    chat_log = json.load(f)
            else:
                logger.error(f"Replay file {self.replay_file} does not exist.")
                self.stop_running = True
                raise ValueError(f"Replay file {self.replay_file} does not exist.")


            prev_timestamp = None
            for entry in chat_log:
                if self.stop_running:
                    break
                if prev_timestamp:
                    # Calculate delay based on the difference in timestamps
                    time_diff = datetime.fromisoformat(entry['timestamp'].rstrip('Z')) - datetime.fromisoformat(prev_timestamp.rstrip('Z'))

                    delay = time_diff.total_seconds()
                    logger.debug(f"Delaying for {delay} seconds to simulate real time.")
                    for _ in range(int(delay)):
                        if self.stop_running:
                            return
                        time.sleep(1)
                self.message_queue.put({
                    "author": entry['author'],
                    "timestamp": entry['timestamp'],
                    "message": entry['message']
                })

                prev_timestamp = entry['timestamp']
            return


        while not self.stop_running:


            messages = self.chat_merger.get_unique_messages()

            if self.first_run:
                self.all_messages_context = messages
                self.first_run = False
                self.chat_merger.seen_messages_hashes.clear()
            else:
                for message in messages:
                    logger.debug(f"Recieved Message: {message}")
                    self.message_queue.put(message)

    def save_messages_to_file(self):
        """Save all messages from the queue to the file."""
        if self.disable_chat_save:
            logger.warning("Chat saving disabled (likely due to chat replay).")
            return
        try:
            with open(self.output_file_path, 'r') as f:
                messages = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            messages = []

        counter = 0
        # Add messages from the queue
        while not self.message_log.empty():
            messages.append(self.message_log.get())
            counter += 1

        if counter > 0:
            logger.info(f"Saving {counter} messages to file.")
            # Write back to the file

            with open(self.output_file_path, 'w') as f:
                json.dump(messages, f, indent=4, default=str)

    def batched_file_writer(self, interval=30):
        """Repeatedly save messages to the file in batches every `interval` seconds."""
        while not self.stop_running:
            for _ in range(interval):
                if self.stop_running:
                    return
                time.sleep(1)
            try:
                self.save_messages_to_file()
            except Exception as e:
                logger.error(f"Error while saving messages to file: {e}", exc_info=True)


    def process_messages(self):
        while not self.message_queue.empty() and not self.stop_running:

            raw_output = self.message_queue.get()
            logger.verbose(f"Processing message: {raw_output}")

            author = raw_output['author']
            timestamp = raw_output['timestamp']
            message = raw_output['message']

            if message == "":  # Ignore empty messages
                continue

            relevant = True
            try:
                relevant = self.context_parser.is_relevant(raw_output)
                logger.verbose(f"Message relevant: {relevant}")
                if not relevant:
                    continue
            except Exception as e:
                logger.error(f"Error while checking relevance of message: {e}", exc_info=True)

            formatted_message = f"From: {author}, {message}"
            response = "Oops! I've momentarily slipped into another dimension. Let's realign our cosmic frequencies and try that again."
            try:
                response = self.bot.get_response_text(author, formatted_message, self.all_messages_context)
            except Exception as e:
                logger.error(f"Error while getting response from OpenAI: {e}", exc_info=True)

            self.message_log.put({"author": author, "timestamp": timestamp, "message": message, "response": response, "relevant": relevant})
            logger.info({"author": author, "timestamp": timestamp, "message": message, "response": response})
            logger.debug(f"Recieved Response from OpenAI: {response}")

            self.all_messages_context.append(raw_output)
            self.all_messages_context.append({"role": "system", "content": f"{response}"})
            self.all_messages_context = self.all_messages_context[-100:]

            if not disable_tts:
                # Generate TTS audio from the response and give it to a file
                start_time = time.time()
                try:
                    tts_audio_path = self.generate_tts_audio(response)
                except Exception as e:
                    logger.error(f"Error while generating TTS audio: {e}", exc_info=True)
                    continue
                end_time = time.time()  # Add timestamp at the end
                step_time = end_time - start_time
                logger.info(f"Time taken for generating TTS audio: {step_time} seconds")
                logger.debug("Playing TTS Audio")
                self.play_audio_file(tts_audio_path)
                os.remove(tts_audio_path)

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

        if not self.manual and not self.replay_file:
            logger.info("Not manual and not chat replay, starting chat scraper and youtube chat.")
            if self.youtube_chat:
                self.youtube_chat.start_threaded()
            if self.chat_scraper:
                self.chat_scraper.start_threaded()
            logger.info("Letting chat gather for 30 seconds")
            for _ in range(30):
                if self.stop_running:
                    return
                time.sleep(1)

        self.youtube_api_client.send_chat_message(self.live_chat_id, "Hopii, Wake up!")
        self.fetch_thread.start()
        self.file_writer_thread.start()
        self.refresh_prompt_thread.start()
        logger.info("Hopii is running.")

         # Start a thread to process speech-to-text
        speech_thread = threading.Thread(target=self.process_speech_to_text)
        speech_thread.start()

        try:
            while not self.stop_running:
                self.process_messages()
                time.sleep(1)  # Wait 1 seconds between responding to messages
        except KeyboardInterrupt:  # Graceful shutdown
            self.shutdown()

       
    def shutdown(self):
        logger.info("Shutting down Hopii.")
        self.youtube_api_client.send_chat_message(self.live_chat_id, "Get some rest Hopii, you look tired.")
        time.sleep(1)
        self.stop_running = True
        if self.chat_scraper:
            logger.verbose("Stopping chat scraper.")
            self.chat_scraper.stop()
        if self.youtube_chat:
            logger.verbose("Stopping youtube chat.")
            self.youtube_chat.stop()
        current_thread = threading.current_thread()

        if current_thread != self.file_writer_thread:
            logger.verbose("Waiting for file writer thread to join.")
            self.file_writer_thread.join()

        if current_thread != self.fetch_thread:
            logger.verbose("Waiting for fetch thread to join.")
            self.fetch_thread.join()

        if current_thread != self.refresh_prompt_thread:
            logger.verbose("Waiting for refresh prompt thread to join.")
            self.refresh_prompt_thread.join()
        logger.info("Hopii has shut down.")
        exit()

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'googleapi.json'

if __name__ == '__main__':
    bot = LiveStreamChatBot(channel_id)
    # bot.manual = True
    # bot.replay_file = "chat_logs/20230918_143330.json"
    bot.run()
