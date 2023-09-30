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
        self.log_level_str = config.get('Logging', 'level', fallback='INFO')
        self.log_level = logging._checkLevel(self.log_level_str)

        # OpenAI
        self.openai_key = config.get('OpenAI', 'key', fallback=None)
        if self.openai_key is None:
            raise ValueError("OpenAI key not found in config.ini!")

        # YouTube
        self.channel_id = config.get('YoutubeChannelInfo', 'channel_id', fallback=None)
        if self.channel_id is None:
            raise ValueError("YouTube channel ID not found in config.ini!")
        self.bot_display_name = config.get('YoutubeChannelInfo', 'bot_display_name', fallback=None)
        if self.bot_display_name is None:
            raise ValueError("YouTube bot display name not found in config.ini!")


        # ChatFetchers
        self.chat_fetcher_ytscraper_enabled = config.getboolean('ChatFetchers.YTScraper', 'enabled', fallback=False)
        self.chat_fetcher_ytapi_enabled = config.getboolean('ChatFetchers.YTAPI', 'enabled', fallback=False)
        self.chat_fetcher_startup_delay = config.getint('ChatFetchers', 'startup_delay', fallback=30)

        # TTS
        self.tts_enabled = config.getboolean('TTS', 'enabled', fallback=False)
        if self.tts_enabled:
            self.tts_output_device = config.get('TTS', 'output_device', fallback=None)
            if self.tts_output_device is None:
                raise ValueError("Audio output device needed for TTS not found in config.ini!")
            self.tts_file_output_path = config.get('TTS', 'file_output_path', fallback='tts_output.wav')
            self.tts_language_code = config.get('TextToSpeech', 'language_code', fallback='en-US')
            self.tts_name = config.get('TextToSpeech', 'name', fallback='en-US-Studio-O')
            self.tts_ssml_gender = config.get('TextToSpeech', 'ssml_gender', fallback='FEMALE')
            self.tts_audio_encoding = config.get('TextToSpeech', 'audio_encoding', fallback='MP3')


        # ChatProcessing
        self.message_history = config.getint('ChatResponse', 'message_history', fallback=50) * -1
        self.prompt_history_refresh_seconds = config.getint('ChatResponse', 'prompt_history_refresh_seconds', fallback=300)

        self.profanity_filter_enabled = config.getboolean('ProfanityFilter', 'enabled', fallback=True)
        self.profanity_filter_allowlist = list(set([item.strip() for item in config.get('ProfanityFilter', 'word_allowlist', fallback='').split(',') if item]))
        self.profanity_filter_author_allowlist = list(set([item.strip() for item in config.get('ProfanityFilter', 'author_allowlist', fallback='').split(',') if item]))

        #ChatResponse
        chat_response_enabled = config.getboolean('ChatResponse', 'enabled', fallback=True)
        chat_response_method = config.get('ChatResponse', 'method', fallback='ChatGPT')

        # ChatGPT
        if chat_response_enabled and chat_response_method == 'ChatGPT':
            self.chatgpt_max_tokens = config.getint('ChatResponse.ChatGPT', 'max_tokens', fallback=100)
            self.chatgpt_temperature = config.getfloat('ChatResponse.ChatGPT', 'temperature', fallback=0.9)
            self.chatgpt_top_p = config.getfloat('ChatResponse.ChatGPT', 'top_p', fallback=0.9)
            self.chatgpt_model = config.get('ChatResponse.ChatGPT', 'model', fallback='gpt-4')

        # STT
        self.stt_enabled = config.getboolean('STT', 'enabled', fallback=False)
        self.stt_hotkey = config.get('STT', 'hotkey', fallback='0')
        self.stt_start_delay = config.getint('STT', 'start_delay', fallback=5)
        self.stt_stop_delay = config.getint('STT', 'stop_delay', fallback=5)
        self.stt_listen_timeout = config.getint('STT', 'listen_timeout', fallback=1)

        # Chatmerger
        self.chatmerger_message_history = config.getint('ChatMerger', 'message_history', fallback=50)

        # Chat Logging
        self.chat_logging_enabled = config.getboolean('ChatLogging', 'enabled', fallback=False)
        self.chat_logging_directory = config.get('ChatLogging', 'directory', fallback='chat_logs')
        self.chat_logging_file_write_frequency = config.getint('ChatLogging', 'file_write_frequency', fallback=30)

    @staticmethod
    def get_config(config, section, option, fallback=None):
        try:
            return config.get(section, option, fallback=fallback)
        except configparser.NoSectionError:
            raise ValueError(f"Section {section} does not exist in the configuration file.")