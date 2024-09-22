import logging
import requests
import time
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from collections import defaultdict
import sqlite3

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

API_KEY = '9d73684f1f464d30a71dd8879bf5b49f'  # Your actual API key
TOPMEDIAI_URL = 'https://api.topmediai.com/v1/lyrics'
TOPMEDIAI_AUDIO_URL = 'https://api.topmediai.com/v1/audio'
TELEGRAM_TOKEN = '7047059587:AAG2M5wMDYtg_p1MLFaj3iPDDELYw9wPKK4'  # Your Telegram bot token

# Initialize SQLite database for caching
conn = sqlite3.connect('songs_cache.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS cache (prompt TEXT PRIMARY KEY, lyrics TEXT, title TEXT)''')
conn.commit()

user_request_times = defaultdict(int)

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Welcome! Send me a prompt for song lyrics!")

def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "To generate song lyrics, send a prompt like:\n"
        "- Happy songs\n"
        "- Romantic lyrics\n"
        "You can also specify a style or mood.\n"
        "I will provide an MP3 download link for the generated song."
    )
    update.message.reply_text(help_text)

def generate_lyrics(prompt):
    headers = {
        'accept': 'application/json',
        'x-api-key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {'prompt': prompt}
    
    try:
        response = requests.post(TOPMEDIAI_URL, json=data, headers=headers)
        response.raise_for_status()
        return response.json().get('data', {}).get('text', 'No lyrics generated.'), response.json().get('data', {}).get('title', 'Unknown Title')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error generating lyrics: {e}")
        return None, None

def generate_audio(lyrics):
    headers = {
        'accept': 'application/json',
        'x-api-key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {'lyrics': lyrics}

    try:
        response = requests.post(TOPMEDIAI_AUDIO_URL, json=data, headers=headers)
        response.raise_for_status()
        return response.json().get('data', {}).get('audio_url', None)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error generating audio: {e}")
        return None

def cache_song(prompt, lyrics, title):
    cursor.execute("INSERT OR REPLACE INTO cache (prompt, lyrics, title) VALUES (?, ?, ?)", (prompt, lyrics, title))
    conn.commit()

def get_cached_song(prompt):
    cursor.execute("SELECT lyrics, title FROM cache WHERE prompt=?", (prompt,))
    return cursor.fetchone()

def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    current_time = context.bot_data.get(user_id, 0)

    if current_time and (time.time() - current_time < 10):
        update.message.reply_text("Please wait before requesting another song.")
        return

    user_prompt = update.message.text.strip()

    # Check cache for existing lyrics
    cached_song = get_cached_song(user_prompt)
    if cached_song:
        lyrics, title = cached_song
    else:
        lyrics, title = generate_lyrics(user_prompt)
        if lyrics:
            cache_song(user_prompt, lyrics, title)  # Cache the result
        else:
            update.message.reply_text("Failed to generate lyrics.")
            return

    update.message.reply_text(f"**{title}**\n\n{lyrics}")

    # Generate audio
    audio_url = generate_audio(lyrics)
    if audio_url:
        update.message.reply_text(f"Download your song [here]({audio_url}).", parse_mode='Markdown')
    else:
        update.message.reply_text("Could not generate audio for the lyrics.")

    context.bot_data[user_id] = time.time()  # Update the last request time

def main() -> None:
    updater = Updater(TELEGRAM_TOKEN)

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
