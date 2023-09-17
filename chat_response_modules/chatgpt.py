import openai
from .base import ChatBot

class ChatGPT(ChatBot):

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
            for past_author, timestamp, past_message in chat_history:
                messages.append({"role": "user", "content": f"{past_author}: {past_message}"})

        # Add the most recent chat message
        messages.append({"role": "user", "content": f"{chat_message}"})

        print(f"Sending messages to OpenAI: {messages}")

        response = openai.ChatCompletion.create(
            model="gpt-4",  # Use the chat-based model
            messages=messages,
            max_tokens=350  # Adjust based on your needs
        )

        # Extract the message text from the response
        message_text = response.choices[0].message['content'].strip()

        return message_text
        #return self._format_response(message_text)
