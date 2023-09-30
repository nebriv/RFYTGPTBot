import openai
from .base import ChatBot
from lib.logger import logger

class ChatGPT(ChatBot):
    def __init__(self, config):
        super(ChatBot, self).__init__(config)

    def setup(self, api_key, prompt_prefix=None):
        openai.api_key = api_key
        self.prompt_prefix = prompt_prefix

    def respond_to(self, author, chat_message, chat_history=None):
        messages = []

        # If there's a prompt prefix, use it as a system message
        if self.prompt_prefix:
            messages.append({"role": "system", "content": self.prompt_prefix})

        # Add the chat history
        if chat_history:
            for message in chat_history:
                if "author" in message:
                    past_author = message['author']
                    past_message = message['message']
                    past_timestamp = message['timestamp']

                    messages.append({"role": "user", "content": f"{past_author}: {past_message}"})
                elif "role" in message:
                    messages.append(message)

        # Add the most recent chat message
        messages.append({"role": "user", "content": f"{chat_message}"})

        logger.debug(f"Sending messages to OpenAI: {messages}")

        response = openai.ChatCompletion.create(
            model=self.config.chatgpt_model,  # Use the chat-based model
            messages=messages,
            max_tokens=self.config.chatgpt_max_tokens,  # Adjust based on your needs
            temperature=self.config.chatgpt_temperature,  # Adjust based on your needs
            top_p=self.config.chatgpt_top_p  # Adjust based on your needs
        )

        # Extract the message text from the response
        message_text = response.choices[0].message['content'].strip()

        return message_text
        #return self._format_response(message_text)
