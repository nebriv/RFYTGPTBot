import speech_recognition as sr
import threading

class SpeechToText:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.is_listening = False
        self.transcribed_text = ""

    def start_listening(self):
        self.is_listening = True
        with sr.Microphone() as source:
            while self.is_listening:
                try:
                    audio = self.recognizer.listen(source)
                    self.transcribed_text = self.recognizer.recognize_google(audio)
                except sr.WaitTimeoutError:
                    pass

    def stop_listening(self):
        self.is_listening = False

if __name__ == "__main__":
    speech_to_text = SpeechToText()

    # Start speech-to-text in a separate thread
    speech_thread = threading.Thread(target=speech_to_text.start_listening)
    speech_thread.start()

    while True:
        user_input = input("Press 'S' to start speech-to-text, 'Q' to quit: ")
        if user_input.lower() == 's':
            print("Starting speech-to-text...")
            speech_to_text.start_listening()
        elif user_input.lower() == 'q':
            print("Quitting...")
            speech_to_text.stop_listening()
            speech_thread.join()
            break
