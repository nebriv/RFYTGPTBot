import configparser
import os
import logging
try:
    from lib import custom_log_levels
except ImportError:
    import custom_log_levels


class Config:
    def __init__(self, config_file):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(current_dir, config_file)
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file {config_file} does not exist!")

        config = configparser.ConfigParser()
        config.read(config_file)

        # Logging
        try:
            self.log_level_str = config.get('Logging', 'level', fallback='INFO')
            self.log_level = logging._checkLevel(self.log_level_str)
        except configparser.NoSectionError:
            logging.error("Logging section not found in config.ini!")

        # OpenAI
        try:
            self.openai_key = config.get('OpenAI', 'key', fallback=None)
            if self.openai_key is None:
                raise ValueError("OpenAI key not found in config.ini!")
        except configparser.NoSectionError:
            logging.error("OpenAI section not found in config.ini!")

        # YouTube
        try:
            self.youtube_api_enabled = config.getboolean('Youtube', 'enabled', fallback=False)
            if self.youtube_api_enabled:
                self.channel_id = config.get('Youtube.ChannelInfo', 'channel_id', fallback=None)
                if self.channel_id is None:
                    raise ValueError("YouTube channel ID not found in config.ini!")
            else:
                self.youtube_live_id = config.get('Youtube', 'live_id', fallback=None)

            self.youtube_api_send_chat = config.getboolean('Youtube', 'send_chat', fallback=False)
            self.bot_display_name = config.get('Youtube.ChannelInfo', 'bot_display_name', fallback=None)
            if self.bot_display_name is None:
                raise ValueError("YouTube bot display name not found in config.ini!")
        except configparser.NoSectionError:
            logging.error("YoutubeChannelInfo section not found in config.ini!")

        # ChatFetchers
        try:
            self.chat_fetcher_ytscraper_enabled = config.getboolean('ChatFetchers.YTScraper', 'enabled', fallback=False)
            self.chat_fetcher_ytapi_enabled = config.getboolean('ChatFetchers.YTAPI', 'enabled', fallback=False)
            self.chat_fetcher_startup_delay = config.getint('ChatFetchers', 'startup_delay', fallback=30)
        except configparser.NoSectionError:
            logging.error("ChatFetchers section not found in config.ini!")

        # TTS
        try:
            self.tts_enabled = config.getboolean('TTS', 'enabled', fallback=False)
            if self.tts_enabled:
                self.tts_output_device_name = config.get('TTS', 'output_device_name', fallback=None)
                self.tts_output_device_sample_rate = config.getfloat('TTS', 'output_device_sample_rate', fallback=None)
                self.tts_file_output_path = config.get('TTS', 'file_output_path', fallback='tts_output.mp3')
                self.tts_language_code = config.get('TTS', 'language_code', fallback='en-US')
                self.tts_name = config.get('TTS', 'name', fallback='en-US-Studio-O')
                self.tts_ssml_gender = config.get('TTS', 'ssml_gender', fallback='FEMALE')
                self.tts_audio_encoding = config.get('TTS', 'audio_encoding', fallback='MP3')
                self.tts_play_test_sound = config.getboolean('TTS', 'play_test_sound', fallback=False)
        except configparser.NoSectionError:
            logging.error("TTS section not found in config.ini!")

        try:
            self.message_history = config.getint('ChatResponse', 'message_history', fallback=50) * -1
            self.prompt_history_refresh_seconds = config.getint('ChatResponse', 'prompt_history_refresh_seconds', fallback=300)
            self.chat_response_enabled = config.getboolean('ChatResponse', 'enabled', fallback=True)
            self.chat_response_method = config.get('ChatResponse', 'method', fallback='ChatGPT')
        except configparser.NoSectionError:
            logging.error("ChatResponse section not found in config.ini!")

        try:
            self.profanity_filter_enabled = config.getboolean('ChatResponse.ProfanityFilter', 'enabled', fallback=True)
            self.profanity_filter_allowlist = list(set([item.strip() for item in config.get('ChatResponse.ProfanityFilter', 'word_allowlist', fallback='').split(',') if item]))
            self.profanity_filter_author_allowlist = list(set([item.strip() for item in config.get('ChatResponse.ProfanityFilter', 'author_allowlist', fallback='').split(',') if item]))
        except configparser.NoSectionError:
            logging.error("ProfanityFilter section not found in config.ini!")

        try:
            self.context_parser_enabled = config.getboolean('ChatResponse.ContextParser', 'enabled', fallback=True)
            self.context_parser_greeting_limit = config.getint('ChatResponse.ContextParser', 'greeting_limit', fallback=3)
            self.context_parser_greeting_time_limit = config.getint('ChatResponse.ContextParser', 'greeting_time_limit', fallback=300)
            self.context_parser_reply_time_limit = config.getint('ChatResponse.ContextParser', 'reply_time_limit', fallback=30)
            self.context_parser_greeting_words = list(set([item.strip() for item in config.get('ChatResponse.ContextParser', 'greeting_words', fallback='').split(',') if item]))
            self.context_parser_question_starts = list(set([item.strip() for item in config.get('ChatResponse.ContextParser', 'question_starts', fallback='').split(',') if item]))
            self.context_parser_short_message_threshold = config.getint('ChatResponse.ContextParser', 'short_message_threshold', fallback=3)
            self.context_parser_author_allowlist = list(set([item.strip() for item in
                                                            config.get('ChatResponse.ContextParser', 'author_allowlist',
                                                                       fallback='').split(',') if item]))
        except configparser.NoSectionError:
            logging.error("ContextParser section not found in config.ini!")

        # ChatGPT
        try:
            if self.chat_response_enabled and self.chat_response_method == 'ChatGPT':
                self.chatgpt_max_tokens = config.getint('ChatResponse.ChatGPT', 'max_tokens', fallback=100)
                self.chatgpt_temperature = config.getfloat('ChatResponse.ChatGPT', 'temperature', fallback=0.9)
                self.chatgpt_top_p = config.getfloat('ChatResponse.ChatGPT', 'top_p', fallback=0.9)
                self.chatgpt_model = config.get('ChatResponse.ChatGPT', 'model', fallback='gpt-4')
        except configparser.NoSectionError:
            logging.error("ChatGPT section not found in config.ini!")

        # STT
        try:
            self.stt_enabled = config.getboolean('STT', 'enabled', fallback=False)
            self.stt_hotkey = config.get('STT', 'hotkey', fallback='0')
            self.stt_start_delay = config.getint('STT', 'start_delay', fallback=5)
            self.stt_stop_delay = config.getint('STT', 'stop_delay', fallback=5)
            self.stt_listen_timeout = config.getint('STT', 'listen_timeout', fallback=1)
        except configparser.NoSectionError:
            logging.error("STT section not found in config.ini!")

        # Chatmerger
        try:
            self.chatmerger_message_history = config.getint('ChatMerger', 'message_history', fallback=50)
        except configparser.NoSectionError:
            logging.error("ChatMerger section not found in config.ini!")

        # Chat Logging
        try:
            self.chat_logging_enabled = config.getboolean('ChatLogging', 'enabled', fallback=False)
            self.chat_logging_directory = config.get('ChatLogging', 'directory', fallback='chat_logs')
            self.chat_logging_file_write_frequency = config.getint('ChatLogging', 'file_write_frequency', fallback=30)
        except configparser.NoSectionError:
            logging.error("ChatLogging section not found in config.ini!")


def generate_example_config(file_path='example_config.ini'):
    default_config = {
        'Logging': {'level': 'INFO'},
        'OpenAI': {'key': 'Your OpenAI Key Here'},
        'YoutubeChannelInfo': {'channel_id': 'Your Channel ID Here', 'bot_display_name': 'Your Bot Display Name Here'},
    }

    config = configparser.ConfigParser()

    for section, options in default_config.items():
        config.add_section(section)
        for option, value in options.items():
            config.set(section, option, str(value))

    with open(file_path, 'w') as configfile:
        config.write(configfile)

    print(f"Example config written to {file_path}")

if __name__ == "__main__":
    generate_example_config()