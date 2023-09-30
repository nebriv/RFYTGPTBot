import threading
import time
from datetime import datetime
import speech_recognition as sr
from speech_recognition import exceptions as speech_recognition_exceptions
from pynput import keyboard as pynput_keyboard
try:
    from lib.logger import logger
except ImportError:
    from logger import logger

class SpeechToText:
    def __init__(self, bot=None):
        self.bot = bot
        self.recognizer = sr.Recognizer()
        self.listening = False
        self.audio_listener_running = False
        self.keep_listening = threading.Event()
        self.stop_event = threading.Event()
        self.audio_stop_event = threading.Event()
        self.listen_thread = None

    def start_listening(self):
        if not self.listening:
            self.keep_listening.set()
            self.stop_event.clear()
            self.audio_stop_event.clear()
            self.listen_thread = threading.Thread(target=self.listen_microphone)
            self.listen_thread.start()

    def stop_listening(self):
        if self.listening:
            self.listening = False
            self.keep_listening.clear()
            self.audio_stop_event.set()  # Ensure audio_listener thread stops.
            self.stop_event.set()  # Ensure listen_microphone thread stops.
            if self.listen_thread is not None and self.listen_thread.is_alive():
                if threading.current_thread() != self.listen_thread:
                    self.listen_thread.join()
            self.listen_thread = None

    def process_audio(self, audio):
        try:
            text = self.recognizer.recognize_google(audio)
            logger.info(f"You said: {text}")  # Replace print with logger.info
            message_data = {
                "author": "Rocket Future",
                "timestamp": datetime.now().isoformat(),
                "message": text
            }
            if self.bot:
                self.bot.message_queue.put(message_data)
        except Exception as e:
            logger.error(f"Error processing audio: {e}")  # Replace print with logger.error

    def audio_listener(self):
        self.audio_listener_running = True
        with sr.Microphone() as source:
            while not self.audio_stop_event.is_set() and self.listening:
                try:
                    audio = self.recognizer.listen(source, timeout=2)
                    self.process_audio(audio)
                except speech_recognition_exceptions.WaitTimeoutError as e:
                    logger.debug(f"Timeout listening to audio: {e}")
                except Exception as e:
                    logger.error(f"Error listening to audio: {e}")
        self.audio_listener_running = False

    def on_press(self, key):
        try:
            if key.char == '0':
                self.pressed_count += 1
                self.unpressed_count = 0  # Reset unpressed_count when '0' key is pressed
        except AttributeError:
            pass

    def listen_microphone(self):
        self.unpressed_count = 0
        self.pressed_count = 0
        listener = pynput_keyboard.Listener(on_press=self.on_press)
        listener.start()
        try:
            while not self.stop_event.is_set():
                if not self.keep_listening.is_set():
                    continue

                self.unpressed_count += 1

                logger.debug(f"Pressed count: {self.pressed_count}, Unpressed count: {self.unpressed_count}, Listening: {self.listening}, Audio listener running: {self.audio_listener_running}")
                if self.pressed_count > 5 and not self.listening and not self.audio_listener_running:
                    logger.info("Start listening...")
                    self.listening = True
                    self.audio_stop_event.clear()
                    threading.Thread(target=self.audio_listener).start()

                if self.unpressed_count > 5 and self.listening and self.audio_listener_running:
                    self.pressed_count = 0
                    logger.info("Stop listening...")
                    self.audio_stop_event.set()
                    self.listening = False

                time.sleep(0.1)
        finally:
            listener.stop()


if __name__ == "__main__":
    bot = None  # Replace with your bot instance
    speech_to_text = SpeechToText(bot)
    speech_to_text.start_listening()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        speech_to_text.stop_event.set()
        print("Ctrl+C pressed. Exiting...")
    finally:
        speech_to_text.stop_listening()
