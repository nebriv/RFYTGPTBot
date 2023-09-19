import speech_recognition as sr
import threading
from logger import logger  # Assuming you have a logger configured
import pyaudio
import keyboard

class SpeechToText:
    def __init__(self, desired_device=None):
        self.recognizer = sr.Recognizer()
        self.listening = False
        self.listen_thread = None
        self.desired_device = desired_device
        self.device_index = None

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
                with open("recorded_audio.wav", "wb") as f:
                    f.write(audio.get_wav_data())

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
    # Create an instance of the SpeechToText class with the desired audio device
    desired_device_name = "Razer BlackShark V2 Pro 2.4"
    speech_to_text = SpeechToText(desired_device=desired_device_name)

    # Add hotkeys
    keyboard.add_hotkey('ctrl+shift+5', lambda: speech_to_text.start_listening())
    keyboard.add_hotkey('ctrl+shift+0', lambda: speech_to_text.stop_listening())

    # Start the keyboard listener
    keyboard.wait()

if __name__ == "__main__":
    run_speech_to_text()