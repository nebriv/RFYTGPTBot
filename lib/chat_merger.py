import hashlib
import queue
from lib.logger import logger

class ChatMerger:

    def __init__(self, chat_scraper=None, youtube_chat=None):
        self.chat_scraper = chat_scraper
        self.youtube_chat = youtube_chat

    def _hash_message(self, message):
        """Generate a unique hash for the message based on its content."""
        hasher = hashlib.md5()
        hasher.update(message['author'].encode())
        hasher.update(message['message'].encode())
        return hasher.hexdigest()

    def get_unique_messages(self):
        seen_messages_content = set()
        unique_messages = []

        # Extract from scraper's message_queue
        if self.chat_scraper:
            while not self.chat_scraper.message_queue.empty():
                message = self.chat_scraper.message_queue.get()
                content = message.get("message", "")

                if content not in seen_messages_content:
                    seen_messages_content.add(content)
                    unique_messages.append(message)

        # Extract from youtube chat's message_queue
        if self.youtube_chat:
            while not self.youtube_chat.message_queue.empty():
                message = self.youtube_chat.message_queue.get()
                content = message.get("message", "")

                if content not in seen_messages_content:
                    seen_messages_content.add(content)
                    unique_messages.append(message)
        logger.debug(f"Found {len(unique_messages)} unique messages")
        return unique_messages

    def _extract_messages_from_queue(self, q):
        """Extract all messages from a queue until it's empty."""
        messages = []
        while not q.empty():
            try:
                messages.append(q.get_nowait())
            except queue.Empty:
                break
        return messages
