import sounddevice as sd
import soundfile as sf
import numpy as np

def list_audio_devices():
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        print(f"ID: {idx}, Name: {device['name']}, Type: {device['hostapi']}, Samplerate: {device['default_samplerate']}")

list_audio_devices()