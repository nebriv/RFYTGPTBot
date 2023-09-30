import spacy
import subprocess
import sys
from lib.logger import logger
from collections import deque
import Levenshtein
import string
from textblob import TextBlob
import datetime
from dateutil.parser import parse
from dateutil.tz import gettz

class Message:
    def __init__(self, config, message, nlp):
        self.config = config
        self.install_textblob_corpora()
        self.text = self.clean_text(message['message'])
        self.author = message['author']
        self._nlp = nlp
        if type(message['timestamp']) == str:
            self.timestamp = parse(message['timestamp'], ignoretz=True)
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
            greetings = self.config.context_parser_greeting_words
            self._is_greeting = any(greet in self.tokens for greet in greetings)
        return self._is_greeting

    @property
    def is_question(self):
        if self._is_question is None:
            question_starts = self.config.context_parser_question_starts

            self._is_question = (
                    any(sent.text.endswith('?') for sent in self.doc.sents) or
                    any(token.dep_ == "aux" for token in self.doc) and any(token.dep_ == "nsubj" for token in self.doc) or
                    any(token.text.lower() in question_starts for token in self.doc)
            )
        return self._is_question

    @property
    def is_short_message(self):
        threshold = self.config.context_parser_short_message_threshold
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
        return self.blob.sentiment.polarity

    def clean_text(self, text):
        return ''.join(ch for ch in text if ch not in string.punctuation).lower().strip()

    def __repr__(self):
        return f"Message(text='{self.text}')"

    def get_properties(self):
        properties_dict = {}
        # Iterate through each attribute of the object
        for name, attribute in self.__class__.__dict__.items():
            # Check if the attribute name doesn't start with an underscore
            if not name.startswith("_") and isinstance(attribute, property):
                value = getattr(self, name)
                properties_dict[name] = value
        return properties_dict

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

    def __init__(self, config):
        self.config = config
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

    def greetings_in_history(self, limit=3, time_limit=None):
        """Count the number of greetings in the recent message history."""
        if time_limit is None:
            datetime.timedelta(minutes=self.config.context_parser_greeting_time_limit)

        now = datetime.datetime.utcnow()

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

    def is_reply(self, new_message):
        # If the message history is empty, it's not a reply
        if not self.message_history:
            return False

        if not self.message_history or new_message.author == self.message_history[-1].author:
            return False

        # Temporal Proximity (for this, we'll consider a time window of 5 minutes)
        time_window = datetime.timedelta(seconds=self.config.context_parser_reply_time_limit)
        if new_message.timestamp - self.message_history[-1].timestamp <= time_window:
            logger.verbose(f"Message '{new_message.text}' is likely a reply as it was sent within {time_window} of the previous message.")
            return True

        # Named Entity Matching
        current_entities = set(new_message.named_entities)
        previous_entities = {ent.text for msg in self.message_history for ent in msg.doc.ents}
        if current_entities & previous_entities:
            return True

        # Levenshtein Similarity (we'll consider a similarity threshold of 0.6 for replies)
        for previous_message in self.message_history:
            if self.is_similar(new_message.text, previous_message.text, threshold=0.6):
                return True

        # Dependency Matching - checking for unresolved pronouns
        pronouns = ["it", "he", "she", "they"]
        if any(token.text.lower() in pronouns for token in new_message.doc):
            return True

        return False

    def is_relevant(self, message, bot_name="bot_username"):
        """Check if the text is relevant to the conversation."""
        message = Message(self.config, message, self.nlp)
        logger.verbose(f"Message properties: {message.get_properties()}")
        self.add_to_history(message)

        logger.debug("self.config.context_parser_author_allowlist: " + str(self.config.context_parser_author_allowlist))
        if message.author in self.config.context_parser_author_allowlist:
            logger.verbose(f"Message author is in the allowlist. Ignoring context parser.")
            return True

        if message.is_greeting:
            logger.verbose(f"Message is a greeting.")
            if self.is_directed_greeting(message, bot_name):
                logger.verbose(f"Message is a directed greeting.")
                return True
            if self.greetings_in_history(limit=self.config.context_parser_greeting_limit) < 2:
                logger.verbose(f"Less than 2 greetings in the last 10 messages.")
                return True
            else:
                logger.verbose(f"More than 2 greetings in the last 10 messages.")
                return False

        if message.is_short_message and not message.is_question:
            logger.verbose(f"Message is too short.")
            return False

        if self.is_reply(message):
            logger.verbose(f"Message is a reply.")
            return False

        if self.has_named_entities(message):
            logger.verbose(f"Message contains named entities.")
            return True

        if message.is_question or message.subject:
            if message.is_question:
                logger.verbose(f"Message is a question.")
            if message.subject:
                logger.verbose(f"Message subject is {message.subject}")
            return True

        return False

    def add_to_history(self, message):
        self.message_history.append(message)
