# Alphy - Telegram Bot with Perplexity AI

This repository contains a Telegram bot that uses Perplexity AI's Sonar model to respond to user messages. The bot maintains conversation history for each chat and provides contextual responses.

## Features

- Integration with Perplexity AI Sonar model
- Conversation history management
- Automatic history trimming when limits are reached
- Local handling of common queries for faster responses
- Multi-language support (English and Russian)
- Usage statistics tracking

## Deployment

This bot is configured to be deployed on Render.com using the included `render.yaml` file.

## Environment Variables

The following environment variables need to be set:

- `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token
- `PERPLEXITY_API_KEY`: Your Perplexity AI API key

## Setup

1. Clone this repository
2. Install the required dependencies: `pip install -r requirements.txt`
3. Set up the environment variables
4. Run the bot: `python telegram_perplexity_bot.py`

## Prerequisites

- Python 3.7 or higher
- A Telegram account
- A Perplexity API key
- A Telegram bot token (obtained from BotFather)

## Installation

1. Clone this repository or download the files

2. Create a virtual environment (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on the `.env.example` template
   ```bash
   cp .env.example .env
   ```

5. Edit the `.env` file and add your Telegram bot token and Perplexity API key
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   PERPLEXITY_API_KEY=your_perplexity_api_key_here
   ```

## How to Get API Keys

### Perplexity API Key
1. Go to [Perplexity API](https://www.perplexity.ai/settings/api)
2. Sign up or log in to your account
3. Navigate to API settings and generate a new API key

### Telegram Bot Token
1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Start a chat with BotFather and type `/newbot`
3. Follow the instructions to create a new bot
4. Once created, BotFather will give you a token for your bot

## Usage

1. Start the bot
   ```bash
   python telegram_perplexity_bot.py
   ```

2. Open Telegram and search for your bot by the username you gave it when creating it with BotFather

3. Start a conversation with your bot by sending the `/start` command

4. Ask any question or provide any input, and the bot will respond using Perplexity's Sonar model

## Customizing the Bot

### Modifying the System Prompt

To change how the bot responds, you can edit the `SYSTEM_PROMPT` variable in `telegram_perplexity_bot.py`:

```python
SYSTEM_PROMPT = """
Your custom instructions here.
"""
```

### Adjusting Response Parameters

You can modify the Perplexity API parameters in the `get_perplexity_response` function to change:

- `max_tokens`: Maximum length of the response (default: 500)
- `temperature`: Controls randomness of responses (0.0 for deterministic, 1.0 for creative, default: 0.7)

## Error Handling

The bot includes error handling for:
- API request failures
- Response parsing errors
- Unexpected exceptions

All errors are logged and a friendly error message is sent to the user.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Perplexity AI](https://www.perplexity.ai/) for providing the Sonar model API
- [Python Telegram Bot](https://github.com/python-telegram-bot/python-telegram-bot) library 