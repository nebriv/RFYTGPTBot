import speech_recognition as sr
import threading
from lib.logger import logger
import keyboard
from datetime import datetime

class SpeechToText:
    def __init__(self, bot):
        self.bot = bot
        self.recognizer = sr.Recognizer()
        self.listening = False
        self.stop_listening_thread = False  # Shared variable to signal when to stop the listening thread
        self.listen_thread = None

    def listen_microphone(self):
        with sr.Microphone() as source:
            logger.info("Waiting for hotkey to start listening...")
            keyboard.wait('ctrl+shift+5')  # Wait for the hotkey to start listening
            logger.info("Listening...")
            self.listening = True

            while not self.stop_listening_thread:  # Continue listening until signaled to stop
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

                        # Pass the recognized text to Script A's process_messages method
                        self.bot.process_messages({"author": "Speech", "timestamp": datetime.now().isoformat(), "message": text})
                    except sr.UnknownValueError:
                        logger.info("Could not understand audio")
                    except sr.RequestError as e:
                        logger.error("Could not request results: %s", e)

            logger.info("Stopped listening.")

    def start_listening(self):
        if not self.listening:
            self.stop_listening_thread = False  # Reset the stop flag
            self.listen_thread = threading.Thread(target=self.listen_microphone)
            self.listen_thread.start()

    def stop_listening(self):
        self.stop_listening_thread = True  # Signal the thread to stop
        if self.listen_thread is not None:
            self.listen_thread.join()  # Wait for the thread to finish

if __name__ == "__main__":
    # Replace 'YOUR_BOT_INSTANCE' with the actual instance of your bot.
    bot_instance = YOUR_BOT_INSTANCE
    speech_to_text = SpeechToText(bot_instance)

    # Replace 'ctrl+shift+0' with your desired hotkey for stopping listening.
    keyboard.add_hotkey('ctrl+shift+0', lambda: speech_to_text.stop_listening())