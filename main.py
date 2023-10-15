from chat_response_modules.chatgpt import ChatGPT
from lib.yt_api import YouTubeClient
import time
import queue
import threading
import os
from config import Config
from google.cloud import texttospeech_v1beta1 as texttospeech
import sounddevice as sd
import soundfile as sf
import prompt_config

from lib.chat_merger import ChatMerger
from lib.logger import logger
import json
from datetime import datetime
import importlib
from lib.context_parsing import ContextParser
import logging
from lib.utils import cleanup_folder, InputManager, get_audio_device_by_name, get_audio_device_user_prompt_selection, play_melody
from lib.speechtotext import SpeechToText

prompt_prefix = prompt_config.prompt_prefix

ContextParser.install_spacy_model()

class LiveStreamChatBot:
    def __init__(self):
        self.config = Config('config.ini')
        logger.setLevel(self.config.log_level)
        self.youtube_chat = None
        self.chat_scraper = None


        logger.info("Starting LiveStreamChatBot")
        if self.config.youtube_api_enabled:
            self.youtube_api_client = YouTubeClient(self.config.channel_id)
            self.live_id = self.youtube_api_client.get_live_id()
        else:
            logger.warning("YouTube API not enabled. Using live id from config.ini")
            self.live_id = self.config.youtube_live_id

        if not self.live_id:
            logger.error(f"Channel {self.config.channel_id} is not currently live.")
            exit()

        if self.config.stt_enabled:
            if self.config.stt_input_device_name is None:
                selection = get_audio_device_user_prompt_selection(type="input")
                logger.verbose(f"Selected input device ID: {selection['ID']}")
                logger.info(f"Selected input device Name: {selection['Name']}")
                logger.info(f"Selected input device Sample Rate: {selection['Samplerate']}")
                self.config.stt_input_device_id = selection['ID']
            else:
                self.config.stt_input_device_id = get_audio_device_by_name(self.config.stt_input_device_name, self.config.stt_input_device_sample_rate)['ID']
                logger.info(f"Selected input device name from config: {self.config.stt_input_device_name}")

            if self.config.stt_input_device_id is None:
                logger.error("STT Output device name not specified. Please specify a device name in config.ini.")
                exit()

        if self.config.tts_enabled:
            if self.config.tts_output_device_name is None:
                selection = get_audio_device_user_prompt_selection(type='output')
                logger.verbose(f"Selected output device ID: {selection['ID']}")
                logger.info(f"Selected output device name: {selection['Name']}")
                logger.info(f"Selected output device Sample Rate: {selection['Samplerate']}")
                sd.default.device = selection['ID']
            else:
                sd.default.device = get_audio_device_by_name(self.config.tts_output_device_name,
                                                             self.config.tts_output_device_sample_rate)['ID']
                logger.info(f"Selected output device name from config: {self.config.tts_output_device_name}")

            if self.config.tts_play_test_sound:

                # If stt enabled replay the test captured audio. and see if it worked. If not retry the device selection again

                logger.info("Playing test sound...")
                play_melody(sd.default.device)
                logger.verbose("Test sound played.")
                if input("Did you hear the test sound? (y/n)").lower() != 'y':
                    logger.critical("Test sound not heard. Exiting.")
                    exit()


        if not self.config.chat_fetcher_ytapi_enabled and not self.config.chat_fetcher_ytscraper_enabled:
            logger.error("No chat fetchers enabled. Please enable at least one chat fetcher in config.ini.")
            exit()

        if self.config.chat_fetcher_ytapi_enabled:
            from chat_fetchers.yt_api_chat import YouTubeChat
            self.youtube_chat = YouTubeChat(self.config, self.youtube_api_client)
        if self.config.chat_fetcher_ytscraper_enabled:
            from chat_fetchers.yt_chat_scraper import YoutubeChatScraper
            self.chat_scraper = YoutubeChatScraper(self.config, self.live_id)


        self.chat_merger = ChatMerger(self.config, self.chat_scraper, self.youtube_chat)

        self.replay_file = None
        self.manual = False

        self.bot = ChatGPT(config=self.config)
        self.context_parser = ContextParser(config=self.config)

        self.bot.setup(self.config.openai_key, prompt_prefix=prompt_prefix)
        self.message_queue = queue.Queue()

        self.all_messages_context = []
        self.live_chat_id = None
        if not self.config.youtube_api_enabled:
            logger.warning("YouTube API not enabled. Unable to get live chat ID.")
        else:
            self.live_chat_id = self.youtube_api_client.get_live_chat_id()
            if not self.live_chat_id:
                logger.error("Tried to get live chat id, but got none. Likely not live!?")

        self.bot_display_name = self.config.bot_display_name
        
        # Timestamp of the last processed message
        now = datetime.utcnow().isoformat() + 'Z'  # current UTC timestamp in YouTube's format
        self.last_timestamp = now
        
        self.stop_running = False  # Flag to stop the fetch thread if necessary
        self.first_run = True
        self.fetch_thread = threading.Thread(target=self.fetch_messages)
        if self.config.chat_logging_enabled:
            self.file_writer_thread = threading.Thread(target=self.batched_file_writer, args=(self.config.chat_logging_file_write_frequency,))
        else:
            self.file_writer_thread = None

        self.refresh_prompt_thread = threading.Thread(target=self.refresh_prompt)
        self.message_log = queue.Queue()
        self.disable_chat_save = False
        self.speech_to_text = False
        self.setup()

    def setup(self):
        if not os.path.exists(self.config.chat_logging_directory):
            os.makedirs(self.config.chat_logging_directory)
        cleanup_folder(self.config.chat_logging_directory, 10)
        # Generate the filename based on the current date and time
        current_datetime_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_file_path = f"{self.config.chat_logging_directory}/{current_datetime_str}.json"

    def refresh_prompt(self):
        while not self.stop_running:
            for _ in range(self.config.prompt_history_refresh_seconds):
                if self.stop_running:
                    return
                time.sleep(1)
            logger.info("Refreshing prompt")
            importlib.reload(prompt_config)
            self.bot.prompt_prefix = prompt_config.prompt_prefix

    def manual_message_callback(self, message_data):
        self.message_queue.put(message_data)

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
            logger.debug(f"Received Response from OpenAI: {response}")

            self.all_messages_context.append(raw_output)
            self.all_messages_context.append({"role": "system", "content": f"{response}"})
            self.all_messages_context = self.all_messages_context[self.config.message_history:]

            if self.config.tts_enabled:
                # Generate TTS audio from the response and give it to a file
                start_time = time.time()
                try:
                    tts_audio_path = self.generate_tts_audio(response)
                except Exception as e:
                    logger.error(f"Error while generating TTS audio: {e}", exc_info=True)
                    continue
                end_time = time.time()  # Add timestamp at the end
                step_time = end_time - start_time
                logger.verbose(f"Time taken for generating TTS audio: {step_time} seconds")
                logger.debug("Playing TTS Audio")
                self.play_audio_file(tts_audio_path)
                os.remove(tts_audio_path)

    def generate_tts_audio(self, text):
        logger.debug("Generating TTS")
        client = texttospeech.TextToSpeechClient()

        input_text = texttospeech.SynthesisInput(text=text)

        # Maps
        ssml_gender_map = {
            'FEMALE': texttospeech.SsmlVoiceGender.FEMALE,
            'MALE': texttospeech.SsmlVoiceGender.MALE,
            'NEUTRAL': texttospeech.SsmlVoiceGender.NEUTRAL,
        }

        audio_encoding_map = {
            'MP3': texttospeech.AudioEncoding.MP3,
            'LINEAR16': texttospeech.AudioEncoding.LINEAR16,
        }

        # Check if the provided ssml_gender is valid, if not log an error and use a default
        ssml_gender = ssml_gender_map.get(self.config.tts_ssml_gender)
        if ssml_gender is None:
            logger.error(f"Invalid SSML Gender: {self.config.tts_ssml_gender}. Using default: FEMALE")
            ssml_gender = texttospeech.SsmlVoiceGender.FEMALE

        # Check if the provided audio_encoding is valid, if not log an error and use a default
        audio_encoding = audio_encoding_map.get(self.config.tts_audio_encoding)
        if audio_encoding is None:
            logger.error(f"Invalid Audio Encoding: {self.config.tts_audio_encoding}. Using default: MP3")
            audio_encoding = texttospeech.AudioEncoding.MP3

        # Construct voice and audio_config using the verified or defaulted values
        voice = texttospeech.VoiceSelectionParams(
            language_code=self.config.tts_language_code,
            name=self.config.tts_name,
            ssml_gender=ssml_gender
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_encoding
        )

        response = client.synthesize_speech(
            input=input_text, voice=voice, audio_config=audio_config
        )

        logger.debug(f"Saving TTS Return")
        tts_audio_path = self.config.tts_file_output_path
        with open(tts_audio_path, "wb") as audio_file:
            audio_file.write(response.audio_content)
        logger.debug(f"TTS Audio saved at {tts_audio_path}")

        return tts_audio_path

    def play_audio_file(self, file_path):
        # Read file to numpy array
        data, fs = sf.read(file_path, dtype='float32')

        # Set default sample rate
        sd.default.samplerate = fs
        try:
            # Play the audio
            sd.play(data)
        except sd.PortAudioError as err:
            logger.error(f"PortAudioError: {err}")
            self.shutdown()
        except ValueError as err:
            if "No output device matching" in str(err) or "Error querying device" in str(err):
                logger.critical(f"Invalid/missing output device: {self.config.tts_output_device_name}")
                self.shutdown()

        # Block execution until audio is finished playing
        sd.wait()

    def run(self):

        if self.config.stt_enabled:
            speech_to_text = SpeechToText(config=self.config, bot=self)
            speech_to_text.start_listening()
            bot.speech_to_text = speech_to_text

        if not self.manual and not self.replay_file:
            logger.info("Not manual and not chat replay, starting chat scraper and youtube chat.")
            if self.youtube_chat:
                self.youtube_chat.start_threaded()
            if self.chat_scraper:
               self.chat_scraper.start_threaded()
            logger.info(f"Letting chat gather for {self.config.chat_fetcher_startup_delay} seconds")
            for _ in range(self.config.chat_fetcher_startup_delay):
                if self.stop_running:
                    return
                time.sleep(1)

        if self.live_chat_id and self.config.youtube_api_send_chat:
            self.youtube_api_client.send_chat_message(self.live_chat_id, "Hopii, Wake up!")
        self.fetch_thread.start()
        if self.config.chat_logging_enabled:
            self.file_writer_thread.start()
        self.refresh_prompt_thread.start()
        logger.info("Hopii is running.")
        try:
            while not self.stop_running:
                self.process_messages()
                time.sleep(1)  # Wait 1 seconds between responding to messages
        except KeyboardInterrupt:  # Graceful shutdown
            self.shutdown()

    def shutdown(self):
        logger.info("Shutting down Hopii.")
        if self.live_chat_id and self.config.youtube_api_send_chat:
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


        if self.file_writer_thread:
            if current_thread != self.file_writer_thread:
                logger.verbose("Waiting for file writer thread to join.")
                self.file_writer_thread.join()

        if current_thread != self.fetch_thread:
            logger.verbose("Waiting for fetch thread to join.")
            self.fetch_thread.join()

        if current_thread != self.refresh_prompt_thread:
            logger.verbose("Waiting for refresh prompt thread to join.")
            self.refresh_prompt_thread.join()

        if self.speech_to_text:
            self.speech_to_text.stop_event.set()
            logger.verbose("Stopping speech to text.")
            self.speech_to_text.stop_listening()

        logger.info("Hopii has shut down.")
        exit()

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'googleapi.json'

if __name__ == '__main__':
    bot = LiveStreamChatBot()
    # bot.manual = True
    # bot.replay_file = "chat_logs/20230918_143330.json"

    bot.run()
