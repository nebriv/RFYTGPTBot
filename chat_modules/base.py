class ChatBot:
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

    def respond_to(self, message, chat_history=None):
        # Basic logic for now: Echo the message.
        return f"Echo: {message}"