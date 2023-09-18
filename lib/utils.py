import os
from lib.logger import logger
import threading
import ctypes
import logging
from datetime import datetime

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