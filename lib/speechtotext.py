import speech_recognition as sr
import threading
from lib.logger import logger  # Assuming you have a logger configured
import keyboard

class SpeechToText:
    def __init__(self, bot):
        self.bot = bot
        self.recognizer = sr.Recognizer()
        self.listening = False
        self.stop_listening = False  # Shared variable to signal when to stop
        self.listen_thread = None

    def listen_microphone(self):
        with sr.Microphone() as source:
            logger.info("Waiting for hotkey to start listening...")
            keyboard.wait('ctrl+shift+5')  # Wait for the hotkey to start listening
            logger.info("Listening...")
            self.listening = True

            while not self.stop_listening:  # Continue listening until signaled to stop
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
                        
                        # Send the recognized text to OpenAI using your main script's functionality
                        self.bot.send_message_to_openai("Rocket Future", text)
                    except sr.UnknownValueError:
                        logger.info("Could not understand audio")
                    except sr.RequestError as e:
                        logger.error("Could not request results: %s", e)

            logger.info("Stopped listening.")
            
    def start_listening(self):
        if not self.listening:
            self.stop_listening = False  # Reset the stop flag
            self.listen_thread = threading.Thread(target=self.listen_microphone)
            self.listen_thread.start()

    def stop_listening(self):
        self.stop_listening = True  # Signal the thread to stop
