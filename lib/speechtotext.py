import speech_recognition as sr
import threading
from lib.logger import logger
import pyaudio
import keyboard

class SpeechToText:
    def __init__(self, desired_device=None):
        self.recognizer = sr.Recognizer()
        self.listening = False
        self.listen_thread = None
        self.desired_device = desired_device
        self.device_index = None  # Initialize device_index to None

        if self.desired_device:
            p = pyaudio.PyAudio()
            try:
                for i in range(p.get_device_count()):
                    device_info = p.get_device_info_by_index(i)
                    if self.desired_device.lower() in device_info['name'].lower():
                        self.device_index = i
                        logger.info("Using input device: %s (Index: %d)", device_info['name'], self.device_index)
                        break
                else:
                    logger.warning("Desired device '%s' not found. Using default microphone.", self.desired_device)
            finally:
                p.terminate()

    def listen_microphone(self):
        with sr.Microphone(device_index=self.device_index) as source:
            logger.info("Listening...")  # Log that we are listening
            try:
                audio = self.recognizer.listen(source)
                text = self.recognizer.recognize_google(audio)
                logger.info("You said: %s", text)  # Log the recognized text
            except sr.UnknownValueError:
                logger.info("Could not understand audio")
            except sr.RequestError as e:
                logger.error("Could not request results: %s", e)
            self.listening = False

    def start_listening(self):
        self.listening = True
        self.listen_thread = threading.Thread(target=self.listen_microphone)
        self.listen_thread.start()

    def stop_listening(self):
        self.listening = False
        if self.listen_thread:
            self.listen_thread.join()

# Define a function to run the code at the bottom of the script
def run_speech_to_text():
    # Define the key combination Ctrl + Alt + A
    listen_keys = ['shift', 'a']

    # Create a hotkey for the defined combination
    keyboard.add_hotkey('+'.join(listen_keys), lambda: speech_to_text.start_listening())

    # Create an instance of the SpeechToText class with the desired audio device
    desired_device_name = "Razer BlackShark V2 Pro 2.4"
    speech_to_text = SpeechToText(desired_device=desired_device_name)  # Replace with the actual device name

    # Start the keyboard listener
    keyboard.wait()

# Check if the script is executed directly before calling the function
if __name__ == "__main__":
    run_speech_to_text()