import speech_recognition as sr
import threading
from lib.logger import logger  # Assuming you have a logger configured
import pyaudio
import keyboard

class SpeechToText:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.listening = False
        self.listen_thread = None

    def listen_microphone(self):
        with sr.Microphone() as source:  # Note that we're not setting device_index here
            logger.info("Listening...")
            audio = None
            while self.listening:
                try:
                    audio = self.recognizer.listen(source, timeout=2)  # Listen in 2-second chunks
                except sr.WaitTimeoutError:
                    continue  # No speech detected, continue listening
                except Exception as e:
                    logger.error("An error occurred: %s", e)
                    break

            if audio:
                try:
                    text = self.recognizer.recognize_google(audio)
                    logger.info("You said: %s", text)
                except sr.UnknownValueError:
                    logger.info("Could not understand audio")
                except sr.RequestError as e:
                    logger.error("Could not request results: %s", e)

    def start_listening(self):
        if not self.listening:
            self.listening = True
            self.listen_thread = threading.Thread(target=self.listen_microphone)
            self.listen_thread.start()

    def stop_listening(self):
        self.listening = False
        if self.listen_thread:
            self.listen_thread.join()

def run_speech_to_text():
    # Create an instance of the SpeechToText class
    speech_to_text = SpeechToText()

    # Add hotkeys
    keyboard.add_hotkey('ctrl+shift+5', lambda: speech_to_text.start_listening())
    keyboard.add_hotkey('ctrl+shift+0', lambda: speech_to_text.stop_listening())

    # Start the keyboard listener
    keyboard.wait()

if __name__ == "__main__":
    run_speech_to_text()