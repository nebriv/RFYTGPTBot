import spacy
import subprocess
import sys
from lib.logger import logger
from collections import deque
import Levenshtein
import string


class ContextParser:
    MODEL_NAME = "en_core_web_sm"
    HISTORY_SIZE = 10

    @classmethod
    def install_spacy_model(cls):
        try:
            # Try loading the model to see if it's installed
            _ = spacy.load(cls.MODEL_NAME)
        except OSError:
            cmd = [sys.executable, "-m", "spacy", "download", cls.MODEL_NAME]
            logger.warning(f"{cls.MODEL_NAME} not found. Installing using command: {' '.join(cmd)}")
            subprocess.check_call(cmd)

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.message_history = deque(maxlen=self.HISTORY_SIZE)
        self.greeting_seen = False
        self.greeting_count = 0

    def clean_text(self, text):
        return ''.join(ch for ch in text if ch not in string.punctuation).lower().strip()

    def is_similar(self, string1, string2, threshold=0.85):
        """Determine if two strings are similar."""
        similarity = Levenshtein.ratio(string1.lower(), string2.lower())
        return similarity >= threshold

    def has_subject(self, text):
        """Check if the text has a clear subject."""
        doc = self.nlp(text)
        return any(token.dep_ == "nsubj" for token in doc)

    def is_question(self, text):
        """Check if the text is a question."""
        doc = self.nlp(text)
        return any(sent.text.endswith('?') for sent in doc.sents) or (
                    any(token.dep_ == "aux" for token in doc) and any(token.dep_ == "nsubj" for token in doc))

    def is_short_message(self, text, threshold=10):
        """Check if the text is a short message."""
        return len(text) <= threshold

    def is_directed_greeting(self, text, bot_name):
        """Check if the text is a greeting directed towards the bot."""
        greetings = ["hi", "hello", "hey", "greetings", "sup", "what's up", "yo"]

        cleaned_text = self.clean_text(text)
        cleaned_bot_name = self.clean_text(bot_name)

        for greeting in greetings:
            # Greeting immediately followed by bot name (e.g., "hello botname")
            if f"{greeting} {cleaned_bot_name}" in cleaned_text:
                return True

        return False

    def greetings_in_history(self, limit=3):
        """Count the number of greetings in the recent message history."""
        return sum(1 for message in list(self.message_history)[-limit:] if self.is_greeting(message))

    def is_greeting(self, text):
        """Check if the text is a greeting."""
        greetings = ["hello", "hi", "hey", "greetings", "sup"]
        tokens = [token.text.lower() for token in self.nlp(text)]
        logger.info(f"Tokens for text '{text}': {tokens}")
        if any(greet in tokens for greet in greetings):
            logger.info(f"Greeting detected in text '{text}'. Incremented greeting count to {self.greeting_count}.")
            return True
        logger.info(f"No greeting detected in text '{text}'. Resetting greeting count.")
        return False

    def has_named_entities(self, text, previous_messages):
        """Check if the current message talks about previously mentioned entities."""
        current_entities = {ent.text for ent in self.nlp(text).ents}
        logger.info(f"Current entities: {current_entities}")
        previous_entities = {ent.text for msg in previous_messages for ent in self.nlp(msg).ents}
        logger.info(f"Previous entities: {previous_entities}")
        return bool(current_entities & previous_entities)

    def is_relevant(self, text, bot_name="bot_username"):
        """Check if the text is relevant to the conversation."""
        self.add_to_history(text)

        if self.is_greeting(text):

            # High Priority Checks
            if self.is_directed_greeting(text, bot_name):
                return True

            if self.greetings_in_history(limit=10) < 2:
                return True
            else:
                logger.verbose(f"Too many greetings in history. Not responding to '{text}'")

        # Initial Filtering
        if self.is_short_message(text):
            return False

        # Fallback Checks
        if self.has_named_entities(text, list(self.message_history)):
            return False

        if self.is_question(text) or self.has_subject(text):
            return True

        # If no other checks catch the message, default to not responding
        return False

    def add_to_history(self, text):
        self.message_history.append(text)