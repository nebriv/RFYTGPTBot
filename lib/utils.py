import os
from lib.logger import logger
import threading
import ctypes
import logging
from datetime import datetime
import sounddevice as sd
import soundfile as sf
import numpy as np

def cleanup_folder(directory, max_files):
    """
    Ensure that the number of files in the given directory does not exceed max_files.
    If it does, delete the oldest ones until the count is down to max_files.
    """
    # List all files in the directory
    files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]

    # If there are more files than max_files
    if len(files) > max_files:
        # Sort files by creation time
        sorted_files = sorted(files, key=os.path.getctime)

        # Delete the oldest ones
        files_to_delete = sorted_files[:-max_files]
        for file in files_to_delete:
            os.remove(file)
            logger.verbose(f"Deleted {file}")



class InputManager:
    def __init__(self, manual_message_callback, stop_flag):
        self.input_thread = None
        self.stop_flag = stop_flag
        self.manual_message_callback = manual_message_callback

    def get_input(self):
        while not self.stop_flag:
            try:
                current_level = logging.getLogger().getEffectiveLevel()
                logging.getLogger().setLevel(logging.CRITICAL)
                author = input("Enter author name (Bob): ")
                if not author:
                    author = "Bob"
                message = input("Enter message to send: ")
                logging.getLogger().setLevel(current_level)
                self.manual_message_callback({"author": author, "message": message, "timestamp": datetime.utcnow().isoformat() + 'Z'})
            except UnicodeDecodeError as err:
                logger.error(f"UnicodeDecodeError: {err}")
                continue

    def start(self):
        self.input_thread = threading.Thread(target=self.get_input)
        self.input_thread.start()

    def stop(self):
        if self.input_thread and self.input_thread.is_alive():
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(self.input_thread.ident), ctypes.py_object(SystemExit))
            self.input_thread.join()

def list_audio_devices():
    devices = sd.query_devices()
    device_list = []
    for idx, device in enumerate(devices):
        device_info = {
            "ID": idx,
            "Name": device['name'],
            "Type": device['hostapi'],
            "Samplerate": device['default_samplerate']
        }
        device_list.append(device_info)
    return device_list


def play_note(frequency, duration=0.5, samplerate=44100):
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    note = 0.5 * np.sin(2 * np.pi * frequency * t)
    sd.play(note, samplerate)
    sd.wait()


def play_melody(device=None):
    import time
    sd.default.device = device
    note_frequencies = {
        'C4': 261.63,
        'D4': 293.66,
        'E4': 329.63,
        'F4': 349.23,
        'G4': 392.00,
        'A4': 440.00,
        'B4': 493.88
    }

    melody = ['C4', 'C4', 'G4', 'G4', 'A4', 'A4', 'G4']

    for note in melody:
        play_note(note_frequencies[note], duration=0.2, samplerate=44100)
        # time.sleep(0.01)  # a small pause between notes


def play_sample_audio(duration=2, frequency=440):
    # Sample rate

    samplerate = 44100  # Hz
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)  # Time array
    x = 0.5 * np.sin(2 * np.pi * frequency * t)  # 0.5 is the amplitude
    sd.play(x, samplerate)
    sd.wait()  # Wait until the audio is finished playing

def get_audio_device_user_prompt_selection(type=None):
    device_list = list_audio_devices()
    for device in device_list:
        print(f"Device ID: {device['ID']} --- Device Name: {device['Name']} --- Sample Rate: {device['Samplerate']} --- Type: {device['Type']}")
    if type:
        selected_id = input("Enter the ID of the desired %s device: " % type)
    else:
        selected_id = input("Enter the ID of the desired device: ")
    try:
        selected_id = int(selected_id)
        if 0 <= selected_id < len(device_list):
            return device_list[selected_id]
        else:
            print("Invalid ID. Please enter a valid ID.")
            return get_audio_device_user_prompt_selection(device_list)
    except ValueError:
        print("Please enter a valid integer ID.")
        return get_audio_device_user_prompt_selection(device_list)

def get_audio_device_by_name(name, sample_rate=None, device_list=None):
    if device_list is None:
        device_list = list_audio_devices()
    for device in device_list:
        if sample_rate is None:
            if device['Name'] == name:
                return device
        if device['Name'] == name and int(device['Samplerate']) == int(sample_rate):
            return device
    return None  # Return None if no device is found with the given name
