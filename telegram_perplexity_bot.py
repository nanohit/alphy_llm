#!/usr/bin/env python3
"""
Telegram Bot with Perplexity AI Sonar Integration

This script creates a Telegram bot that responds to user messages using 
Perplexity's Sonar model API for information retrieval and natural language processing.
It maintains conversation history for each chat.

Usage:
  python telegram_perplexity_bot.py
"""

import os
import logging
import requests
import time
import json
from dotenv import load_dotenv
from telegram import ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram.error import TimedOut, NetworkError, TelegramError

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get API keys from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

if not TELEGRAM_BOT_TOKEN or not PERPLEXITY_API_KEY:
    raise ValueError("Please set both TELEGRAM_BOT_TOKEN and PERPLEXITY_API_KEY in your .env file")

# Configuration
MAX_OUTPUT_TOKENS = 200  # Maximum tokens in the response
MAX_OUTPUT_LENGTH = 1000  # Maximum characters in the message sent to Telegram
MAX_HISTORY_MESSAGES = 30 # Max user/assistant messages to keep (excluding system prompt)
MAX_HISTORY_TOKENS_ESTIMATE = 3500 # Estimated max tokens before resetting history

# Cost tracking
REQUEST_COST = 0.005  # Cost per request in dollars (low search mode)
TOKEN_COST_PER_MILLION = 1.0  # Cost per million tokens
total_requests = 0
total_tokens = 0
estimated_cost = 0.0

# The system prompt that guides the AI's behavior
SYSTEM_PROMPT = """
You are Alphy, an AI assistant. Provide neutral, brief, and straightforward information.
Focus on directly answering the user's request based on the provided context and conversation history.
Avoid speculation, opinions, or unnecessary elaboration.

DO NOT PROVIDE SEARCH RESULTS UNTILL YOURE ASKED TO DO SO.

IMPORTANT FORMAT GUIDELINES:
1. Keep answers extremely concise.
2. Use basic Markdown formatting (**bold**, *italic*) sparingly for clarity only.
3. Do not include citations.
4. Avoid lists unless essential for clarity, keep them very short.
"""
SYSTEM_PROMPT_MESSAGE = {"role": "system", "content": SYSTEM_PROMPT}

# Greeting message for start and restart commands
GREETING_MESSAGE = "Hi {}! Ask your question and Alphy will try to answer it. The model is not deisgned for personal human interaction, it is a search and reasoning engine. Do not greet or thank it."

# --- Helper Function ---
def estimate_tokens(messages: list[dict]) -> int:
    """Roughly estimate token count based on character length."""
    total_chars = sum(len(m.get('content', '')) for m in messages)
    # Approximation: 1 token ~ 4 characters
    return total_chars // 4

async def start(update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued and clear history."""
    user = update.effective_user
    # Clear history on start
    context.chat_data.pop('history', None)
    await update.message.reply_text(GREETING_MESSAGE.format(user.first_name))

async def restart(update, context: CallbackContext) -> None:
    """Send the greeting message again when the command /restart is issued and clear history."""
    user = update.effective_user
    # Clear history on restart
    context.chat_data.pop('history', None)
    await update.message.reply_text(GREETING_MESSAGE.format(user.first_name))

async def clear_command(update, context: CallbackContext) -> None:
    """Clears the conversation history for the current chat."""
    context.chat_data.pop('history', None)
    await update.message.reply_text("Conversation history cleared.")

async def help_command(update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "I'm an AI assistant powered by Perplexity's Sonar model, maintaining conversation history.\n\n"
        "Just send me a message with your question or topic, and I'll respond contextually.\n\n"
        "Commands:\n"
        "/start - Start a new conversation (clears history)\n"
        "/restart - Restart the conversation (clears history)\n"
        "/clear - Clear the current conversation history\n"
        "/help - Show this help message\n"
        "/stats - Show usage statistics and estimated costs"
    )

async def stats_command(update, context: CallbackContext) -> None:
    """Send usage statistics and estimated costs."""
    stats_message = (
        "📊 **Usage Statistics**\n\n"
        f"Total API requests: {total_requests}\n"
        f"Total tokens used: {total_tokens}\n\n"
        f"Estimated cost so far: ${estimated_cost:.4f}\n"
        f"Cost per request: ${REQUEST_COST:.4f}\n"
        f"Cost per million tokens: ${TOKEN_COST_PER_MILLION:.2f}"
    )
    await update.message.reply_text(stats_message, parse_mode=ParseMode.MARKDOWN)

async def get_perplexity_response(messages: list[dict], max_retries=3) -> str:
    """
    Get a response from Perplexity API using the Sonar model based on message history.
    
    Args:
        messages: The list of message objects representing the conversation history.
        max_retries: Maximum number of retry attempts
        
    Returns:
        The AI's response as a string
    """
    global total_requests, total_tokens, estimated_cost
    
    # Skip if messages list is empty or only contains system prompt
    if not messages or len(messages) <= 1:
        logger.warning("get_perplexity_response called with empty or system-only messages.")
        return "I need a message from you to respond!"

    url = "https://api.perplexity.ai/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Use the provided message history
    data = {
        "model": "sonar",
        "messages": messages,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "temperature": 0.7,
    }
    
    # Implement retry logic with exponential backoff
    retry_count = 0
    while retry_count < max_retries:
        try:
            # Log only the last user message for brevity, but indicate history is included
            last_user_message = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), None)
            logger.info(f"Making Perplexity API request with history. Last query: '{last_user_message}'")
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            # Update statistics
            total_requests += 1
            
            # Try to get token usage if available
            if "usage" in result:
                input_tokens = result["usage"].get("prompt_tokens", 0)
                output_tokens = result["usage"].get("completion_tokens", 0)
                total_tokens += (input_tokens + output_tokens)
                
                # Calculate cost (per request + token cost)
                token_cost = (input_tokens + output_tokens) / 1_000_000 * TOKEN_COST_PER_MILLION
                estimated_cost += (REQUEST_COST + token_cost)
                
                logger.info(f"Request cost: ${REQUEST_COST:.4f}, Token cost: ${token_cost:.6f}, " +
                           f"Total cost: ${estimated_cost:.4f}")
            else:
                # If token usage not available, just count the request cost
                estimated_cost += REQUEST_COST
                logger.info(f"Request cost: ${REQUEST_COST:.4f}, Total cost: ${estimated_cost:.4f}")
            
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            retry_count += 1
            if retry_count >= max_retries:
                return "Sorry, the request timed out. Please try again later."
            logger.warning(f"Timeout occurred. Retrying ({retry_count}/{max_retries})...")
            # Exponential backoff
            time.sleep(2 ** retry_count)
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e} - Payload: {json.dumps(data)}") # Log payload on error
            return f"Sorry, I encountered an error when trying to process your request. Please try again later."
        except (KeyError, IndexError) as e:
            logger.error(f"API response parsing error: {e} - Response: {response.text}") # Log response text on error
            return "Sorry, I had trouble understanding the response. Please try again later."
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "Sorry, an unexpected error occurred. Please try again later."

def truncate_text(text, max_length=MAX_OUTPUT_LENGTH):
    """Truncate text to max_length and add ellipsis if truncated."""
    if len(text) <= max_length:
        return text
    
    # Try to truncate at a sentence or paragraph break
    for char in ['.', '!', '?', '\n']:
        last_complete = text[:max_length].rfind(char)
        if last_complete > max_length * 0.7:  # Only if we're at least 70% into the text
            return text[:last_complete+1] + "\n\n*[Response truncated due to length...]*"
    
    # If no good break point, truncate at max_length
    return text[:max_length] + "\n\n*[Response truncated due to length...]*"

async def handle_message(update, context: CallbackContext) -> None:
    """Process user messages, maintain history, handle potential reset, and respond."""
    user_message = update.message.text
    chat_id = update.effective_chat.id

    # Send typing action
    await update.message.chat.send_action(action="typing")

    # Log incoming message
    logger.info(f"Received message from chat {chat_id}: '{user_message}'")

    # Retrieve or initialize conversation history
    history = context.chat_data.setdefault('history', [SYSTEM_PROMPT_MESSAGE])

    # Append the new user message temporarily to check limits *before* saving
    potential_next_history = history + [{"role": "user", "content": user_message}]

    # --- Check History Limits ---
    
    # 1. Check estimated token count
    estimated_tokens_count = estimate_tokens(potential_next_history)
    logger.info(f"Chat {chat_id}: Estimated tokens with new message: {estimated_tokens_count}")
    
    history_reset_needed = False
    if estimated_tokens_count > MAX_HISTORY_TOKENS_ESTIMATE:
        logger.warning(f"Chat {chat_id}: Estimated token count ({estimated_tokens_count}) exceeds limit ({MAX_HISTORY_TOKENS_ESTIMATE}). Resetting history.")
        history_reset_needed = True
        
    # 2. Check message count (apply trimming *before* reset if only message count is exceeded)
    elif len(potential_next_history) > MAX_HISTORY_MESSAGES + 1: # +1 for system prompt
        logger.info(f"Chat {chat_id}: Message count ({len(potential_next_history)}) exceeds limit ({MAX_HISTORY_MESSAGES + 1}). Trimming history.")
        # Trim potential_next_history before saving it as the new history
        potential_next_history = [potential_next_history[0]] + potential_next_history[-(MAX_HISTORY_MESSAGES):]
        # Recalculate token count after trimming - might still be too high
        estimated_tokens_count = estimate_tokens(potential_next_history)
        logger.info(f"Chat {chat_id}: Estimated tokens after trimming by count: {estimated_tokens_count}")
        if estimated_tokens_count > MAX_HISTORY_TOKENS_ESTIMATE:
             logger.warning(f"Chat {chat_id}: Estimated token count ({estimated_tokens_count}) STILL exceeds limit ({MAX_HISTORY_TOKENS_ESTIMATE}) after trimming by count. Resetting history.")
             history_reset_needed = True

    # Perform reset if needed
    if history_reset_needed:
        context.chat_data['history'] = [SYSTEM_PROMPT_MESSAGE] # Reset history
        await update.message.reply_text(
            "⚠️ Conversation history became too long and has been reset. Please send your message again to continue."
        )
        return # Stop processing this message, wait for the user to send again

    # If no reset needed, save the potentially trimmed history (which includes the new user message)
    history = potential_next_history
    context.chat_data['history'] = history

    # --- Process Message (Local Handlers or API) ---
    try:
        lower_query = user_message.lower().strip()
        handled_locally = False
        response_text = "" # Initialize response_text

        # Special case: Гойда
        if "гойда" in lower_query:
            response_text = "Гойда, брат!"
            logger.info(f"Using special response for 'Гойда' for chat {chat_id}")
            handled_locally = True
            # Note: We still add this Гойда interaction to history below

        # Identity/Capability Questions
        elif any(phrase in lower_query for phrase in [
            "who are you", "what are you", "tell me about yourself", "what's your name", "your purpose",
            "кто ты", "ты кто", "что ты такое", "как тебя зовут", "расскажи о себе",
            "что ты умеешь", "what can you do", "твои возможности", "твои функции",
            "что ты делаешь", "для чего ты нужна", "для чего ты нужен", "какова твоя цель",
            "твоя задача", "твое предназначение"
        ]):
            if any(russian_phrase in lower_query for russian_phrase in [
                "кто ты", "ты кто", "что ты такое", "как тебя зовут", "расскажи о себе", "что ты умеешь",
                "твои возможности", "твои функции", "что ты делаешь", "для чего ты нужна", "для чего ты нужен",
                "какова твоя цель", "твоя задача", "твое предназначение"
            ]):
                response_text = "Я модель-трансформер, созданная на основе Llama 3.3 70B и дополненная фунциями поиска в интернете. Я отвечаю на ваши вопросы используя поиск в интернете."
            else:
                response_text = "I am an AI assistant. I can answer questions and provide information based on my available data and conversation history."
            logger.info(f"Using canned response for identity/capability question for chat {chat_id}")
            handled_locally = True
        
        # Basic Greetings (English & Russian)
        elif lower_query in ["hello", "hi", "hey", "howdy", "hola", "greetings", 
                           "good morning", "good afternoon", "good evening", 
                           "привет", "прив", "здарова", "здравствуй", "Здравствуй!", "здравствуйте", 
                           "доброе утро", "добрый день", "добрый вечер"] or lower_query.startswith("hello"):
            response_text = "Привет!" if any(word in lower_query for word in ["привет", "здравствуй", "доброе", "добрый"]) else "Hello!"
            logger.info(f"Using canned response for greeting for chat {chat_id}")
            handled_locally = True

        # Basic Farewells (English & Russian)
        elif lower_query in ["bye", "goodbye", "see you", "see ya", "later", "cya",
                           "пока", "до свидания", "увидимся", "прощай", "до встречи"]:
            response_text = "До свидания!" if any(word in lower_query for word in ["пока", "до свидания", "прощай"]) else "Goodbye!"
            logger.info(f"Using canned response for farewell for chat {chat_id}")
            handled_locally = True

        # Basic Thanks (English & Russian)
        elif lower_query in ["thanks", "thank you", "thx", "ty", "thank you very much", "thanks a lot",
                           "спасибо", "спс", "благодарю", "спасибо большое", "огромное спасибо"]:
            response_text = "Пожалуйста." if any(word in lower_query for word in ["спасибо", "спс", "благодарю"]) else "You're welcome."
            logger.info(f"Using canned response for thanks for chat {chat_id}")
            handled_locally = True
            
        # Simple Affirmations/Acknowledgements (English & Russian)
        elif lower_query in ["ok", "okay", "got it", "understood", "fine", "alright", "yes", "yep", "yeah",
                           "хорошо", "окей", "ладно", "понял", "поняла", "понятно", "да", "ага"]:
            response_text = "Ок." if any(word in lower_query for word in ["хорошо", "окей", "ладно", "понял", "поняла", "понятно", "да", "ага"]) else "Okay."
            logger.info(f"Using canned response for affirmation/acknowledgement for chat {chat_id}")
            handled_locally = True

        # Simple Negations (English & Russian)
        elif lower_query in ["no", "nope", "nah", "not really",
                           "нет", "неа", "не"]:
            response_text = "Понятно." if any(word in lower_query for word in ["нет", "неа", "не"]) else "Understood."
            logger.info(f"Using canned response for negation for chat {chat_id}")
            handled_locally = True

        # Simple Statements of Fact (Name, Location, etc.) - Just acknowledge
        elif (lower_query.startswith("my name is") or lower_query.startswith("i am") or 
              lower_query.startswith("i live in") or lower_query.startswith("i'm") or
              lower_query.startswith("меня зовут") or lower_query.startswith("я живу в") or 
              lower_query.startswith("мне") and ("лет" in lower_query or "год" in lower_query) or
              lower_query.startswith("я -") or lower_query.startswith("я —")
             ):
            if any(word in lower_query for word in ["меня", "зовут", "живу", "лет", "год"]):
                response_text = "Понятно." 
            else: 
                response_text = "Noted."
            logger.info(f"Using canned acknowledgement for simple statement for chat {chat_id}")
            handled_locally = True

        # --- If not handled locally, use the API --- 
        if not handled_locally:
            logger.info(f"Calling Perplexity API for chat {chat_id} with {len(history)} messages in history (estimated tokens: {estimate_tokens(history)}).")
            response_text = await get_perplexity_response(messages=history)
        
        # Append assistant's response to history *after* successful processing/generation
        # Don't save if API call failed internally in get_perplexity_response and returned an error message
        if not response_text.startswith("Sorry,"): 
             history.append({"role": "assistant", "content": response_text})
             context.chat_data['history'] = history # Save updated history including assistant response

        # Truncate if too long for Telegram
        response_text_truncated = truncate_text(response_text) 

        # Send the response
        await update.message.reply_text(
            response_text_truncated, 
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error handling message for chat {chat_id}: {e}")
        # Attempt to inform the user about the error
        try:
            await update.message.reply_text(
                "Conversation history became too long, please reset chat to continue."
            )
        except Exception as send_error:
            logger.error(f"Failed to send error message to chat {chat_id}: {send_error}")

def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token
    updater = Updater(TELEGRAM_BOT_TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Add handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("restart", restart))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("stats", stats_command))
    dispatcher.add_handler(CommandHandler("clear", clear_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Start the Bot
    logger.info("Starting bot...")
    try:
        updater.start_polling()
        updater.idle()
    except (TimedOut, NetworkError) as e:
        logger.error(f"Network error: {e}")
        logger.info("Restarting bot...")
        time.sleep(5)
        main()  # Restart the bot
    except TelegramError as e:
        logger.error(f"Telegram error: {e}")
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.info("Bot stopped")

if __name__ == "__main__":
    main() 