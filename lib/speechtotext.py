import speech_recognition as sr

# Initialize the speech recognizer
recognizer = sr.Recognizer()

# Create a function to start and stop listening
def listen_microphone():
    with sr.Microphone() as source:
        print("Listening...")
        try:
            audio = recognizer.listen(source)
            text = recognizer.recognize_google(audio)  # You can use other recognition engines too
            print("You said:", text)
        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results: {e}")

# Create a flag to indicate whether to listen or not
listening = False

# Define the key that you want to hold down to start and stop listening
listen_key = keyboard.KeyCode.from_char('L')

# Create a function to handle key press events
def on_key_press(key):
    global listening
    if key == listen_key:
        if not listening:
            listening = True
            listen_microphone()

# Create a function to handle key release events
def on_key_release(key):
    global listening
    if key == listen_key:
        listening = False

# Create a listener for keyboard events
with keyboard.Listener(on_press=on_key_press, on_release=on_key_release) as listener:
    listener.join()