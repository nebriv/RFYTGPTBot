from better_profanity import profanity
class ChatBot:
    profanity.load_censor_words()
    def __init__(self):
        pass

    def setup(self):
        raise NotImplemented("ChatBot.setup() must be implemented by subclass.")

    def _format_response(self, text):
        # Initial truncation
        truncated = text[:195]

        # Trim to the last full word
        last_space = truncated.rfind(' ')
        if last_space != -1:
            truncated = truncated[:last_space]

        # Add ellipses if the message is truncated
        if len(text) > len(truncated):
            truncated += "..."

        return truncated

    def get_response_text(self, author, chat_message, chat_history=None):
        if profanity.contains_profanity(chat_message):
            return "Please don't use profanity."
        return self.respond_to(author, chat_message, chat_history)

    def respond_to(self, message, chat_history=None):
        # Basic logic for now: Echo the message.
        return f"Echo: {message}"
