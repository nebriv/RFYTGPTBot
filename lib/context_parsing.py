import spacy
import subprocess
import sys
from lib.logger import logger
from collections import deque
import Levenshtein
import string
from textblob import TextBlob
import datetime

class Message:
    def __init__(self, message, nlp):
        self.install_textblob_corpora()
        self.text = self.clean_text(message['message'])
        self.author = message['author']
        self._nlp = nlp
        if type(message['timestamp']) == str:
            self.timestamp = datetime.datetime.strptime(message['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            self.timestamp = message['timestamp']
        self._tokens = None
        self._is_greeting = None
        self._is_question = None
        self.doc = self._nlp(self.text)
        self.blob = TextBlob(self.text)

    @classmethod
    def install_textblob_corpora(cls):
        try:
            # Try creating a TextBlob to see if the corpora are installed
            _ = TextBlob("test")
        except Exception:
            cmd = [sys.executable, "-m", "textblob.download_corpora"]
            logger.warning(f"TextBlob corpora not found. Installing using command: {' '.join(cmd)}")
            subprocess.check_call(cmd)

    @property
    def tokens(self):
        if self._tokens is None:
            self._tokens = [token.text.lower() for token in self._nlp(self.text)]
        return self._tokens

    @property
    def is_greeting(self):
        if self._is_greeting is None:
            greetings = ["hello", "hi", "hey", "greetings", "sup"]
            self._is_greeting = any(greet in self.tokens for greet in greetings)
        return self._is_greeting

    @property
    def is_question(self):
        if self._is_question is None:
            question_starts = ["what", "who", "where", "when", "why", "how"]

            self._is_question = (
                    any(sent.text.endswith('?') for sent in self.doc.sents) or
                    any(token.dep_ == "aux" for token in self.doc) and any(token.dep_ == "nsubj" for token in self.doc) or
                    any(token.text.lower() in question_starts for token in self.doc)
            )
        return self._is_question

    @property
    def is_short_message(self):
        threshold = 3  # for example
        return len(self.text.split()) < threshold

    @property
    def contains_named_entities(self):
        return len(self.named_entities) > 0

    @property
    def named_entities(self):
        return [ent.text for ent in self.doc.ents]

    @property
    def contains_url(self):
        return any(token.like_url for token in self.doc)

    @property
    def contains_email(self):
        return any(token.like_email for token in self.doc)

    @property
    def subject(self):
        # Extract nominal subjects
        nsubj_tokens = [token.text for token in self.doc if token.dep_ in ["nsubj", "nsubjpass"]]
        if nsubj_tokens:
            return nsubj_tokens[0]  # Returning the first nominal subject

        # If no nominal subject is found, fall back to any noun
        noun_tokens = [token.text for token in self.doc if token.pos_ == "NOUN"]
        if noun_tokens:
            return noun_tokens[0]  # Returning the first noun

        return None  # No subject found

    @property
    def sentiment(self):
        return self.blob.sentiment

    def clean_text(self, text):
        return ''.join(ch for ch in text if ch not in string.punctuation).lower().strip()

    def __repr__(self):
        return f"Message(text='{self.text}')"


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
        self.nlp = spacy.load(self.MODEL_NAME)
        self.message_history = deque(maxlen=self.HISTORY_SIZE)

    def is_similar(self, string1, string2, threshold=0.85):
        """Determine if two strings are similar."""
        similarity = Levenshtein.ratio(string1.lower(), string2.lower())
        return similarity >= threshold

    def is_directed_greeting(self, message, bot_name):
        """Check if the text is a greeting directed towards the bot."""
        cleaned_bot_name = message.clean_text(bot_name)
        for greeting in ["hi", "hello", "hey", "greetings", "sup", "what's up", "yo"]:
            if f"{greeting} {cleaned_bot_name}" in message.text:
                return True
        return False

    def greetings_in_history(self, limit=3, time_limit=datetime.timedelta(minutes=5)):
        """Count the number of greetings in the recent message history."""
        now = datetime.datetime.now()

        recent_greetings = 0
        for message in list(self.message_history)[-limit:]:
            if message.is_greeting:
                if now - message.timestamp < time_limit:
                    recent_greetings += 1
        return recent_greetings

    def has_named_entities(self, message):
        """Check if the current message talks about previously mentioned entities."""
        current_entities = set(message.named_entities)
        previous_entities = {ent.text for msg in self.message_history for ent in msg.doc.ents}
        return bool(current_entities & previous_entities)

    def is_relevant(self, message, bot_name="bot_username"):
        """Check if the text is relevant to the conversation."""
        message = Message(message, self.nlp)
        self.add_to_history(message)

        if message.is_greeting:
            logger.verbose(f"Message is a greeting.")
            if self.is_directed_greeting(message, bot_name):
                logger.verbose(f"Message is a directed greeting.")
                return True
            if self.greetings_in_history(limit=10) < 2:
                logger.verbose(f"Less than 2 greetings in the last 10 messages.")
                return True
            else:
                logger.verbose(f"More than 2 greetings in the last 10 messages.")
                return False

        if message.is_short_message:
            logger.verbose(f"Message is too short.")
            return False

        if self.has_named_entities(message):
            logger.verbose(f"Message contains named entities.")
            return False

        if message.is_question or message.subject:
            if message.is_question:
                logger.verbose(f"Message is a question.")
            if message.subject:
                logger.verbose(f"Message subject is {message.subject}")
            return True

        return False

    def add_to_history(self, message):
        self.message_history.append(message)
