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
            keyboard.wait('0')  # Wait for the '0' key to start listening
            self.listening = not self.listening  # Toggle the listening state
            logger.info("Listening..." if self.listening else "Stopped listening")

            while not self.stop_listening_thread:  # Continue listening until signaled to stop
                try:
                    audio = self.recognizer.listen(source, timeout=2)  # Listen in 2-second chunks
                except sr.WaitTimeoutError:
                    continue  # No speech detected, continue listening
                except Exception as e:
                    logger.error("An error occurred: %s", e)
                    break

                if audio and self.listening:  # Only process audio when listening
                    try:
                        text = self.recognizer.recognize_google(audio)
                        logger.info("You said: %s", text)

                        # Send the recognized speech with author and timestamp to the message queue
                        message_data = {
                            "author": "Rocket Future",
                            "timestamp": datetime.now().isoformat(),
                            "message": text
                        }
                        self.bot.message_queue.put(message_data)
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
    
    # Start listening when the script is run
    speech_to_text.start_listening()