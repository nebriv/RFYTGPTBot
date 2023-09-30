from better_profanity import profanity

class ChatBot:

    def __init__(self, config):
        self.config = config
        profanity.load_censor_words(whitelist_words=self.config.profanity_filter_allowlist)

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
        if self.config.profanity_filter_enabled and author not in self.config.profanity_filter_author_allowlist:
            if profanity.contains_profanity(chat_message):
                return "Hey Mods? Someone in chat is using those sentence enhancers again."
        return self.respond_to(author, chat_message, chat_history)

    def respond_to(self, message, chat_history=None):
        # Basic logic for now: Echo the message.
        return f"Echo: {message}"
