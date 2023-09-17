import spacy
import subprocess

def install_spacy_model(model_name):
    try:
        # Try loading the model to see if it's installed
        _ = spacy.load(model_name)
    except OSError:
        # Model not found, so install it
        print(f"{model_name} not found. Installing...")
        subprocess.check_call(["python", "-m", "spacy", "download", model_name])


class ContextParser:
    MODEL_NAME = "en_core_web_sm"

    @classmethod
    def install_spacy_model(cls):
        try:
            # Try loading the model to see if it's installed
            _ = spacy.load(cls.MODEL_NAME)
        except OSError:
            # Model not found, so install it
            print(f"{cls.MODEL_NAME} not found. Installing...")
            subprocess.check_call(["python", "-m", "spacy", "download", cls.MODEL_NAME])

    # Call the install method for the class (not for the instance)
    install_spacy_model()

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def has_subject(self, text):
        """Check if the text has a clear subject."""
        doc = self.nlp(text)
        return any(token.dep_ == "nsubj" for token in doc)

    def is_question(self, text):
        """Check if the text is a question."""
        doc = self.nlp(text)
        return any(sent.endswith('?') for sent in doc.sents) or (any(token.dep_ == "aux" for token in doc) and any(token.dep_ == "nsubj" for token in doc))

    def is_relevant(self, text):
        """Determine if the message is relevant for the chatbot to respond."""
        return self.is_question(text) or self.has_subject(text)
