import os
from dotenv import load_dotenv
import time
import traceback
from flask import Flask, render_template, request, jsonify, send_file, Response, abort
import openai
from together import Together
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
import io
import asyncio
import aiohttp
from queue import Queue
import sqlite3
from datetime import datetime
import secrets

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)

progress_queue = Queue()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY')

if not OPENAI_API_KEY:
    raise ValueError("No OpenAI API key found. Please set the OPENAI_API_KEY environment variable.")
if not TOGETHER_API_KEY:
    raise ValueError("No Together API key found. Please set the TOGETHER_API_KEY environment variable.")

# Initialize Together client
together_client = Together(api_key=TOGETHER_API_KEY)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('pdfs.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pdfs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ip TEXT,
                  title TEXT,
                  filepath TEXT,
                  timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS api_keys
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ip TEXT,
                  api_key TEXT UNIQUE,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

async def generate_chunk(api, model, topic, current_word_count, language, is_new_chapter=False):
    if is_new_chapter:
        prompt = f"Write a detailed chapter for a book about {topic} in {language}. This is around word {current_word_count} of the book. Start with a chapter title, then write at least {current_word_count} words of content."
    else:
        prompt = f"Continue writing a detailed book about {topic} in {language}. This is around word {current_word_count} of the book. Write at least {current_word_count} words, ensuring the narrative flows smoothly from the previous section."
    
    try:
        if api == 'openai':
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": f"You are an author writing a book in {language}. Format your response as a part of a book chapter."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 3000
                    }
                ) as response:
                    result = await response.json()
                    if 'choices' not in result or len(result['choices']) == 0:
                        raise ValueError(f"Unexpected API response: {result}")
                    return result['choices'][0]['message']['content'].strip()
        elif api == 'together':
            response = together_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": f"You are an author writing a detailed book in {language}. Provide long, comprehensive responses with at least {current_word_count} words per chunk."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7,
                top_p=0.9,
                top_k=50,
                repetition_penalty=1.03,
                stop=None
            )
            generated_text = response.choices[0].message.content.strip()
            
            # Ensure minimum word count
            while len(generated_text.split()) < 500:
                additional_prompt = f"Continue the previous text, adding more details and expanding the narrative. Write at least {current_word_count} more words."
                additional_response = together_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": f"You are an author writing a detailed book in {language}. Provide long, comprehensive responses."},
                        {"role": "user", "content": generated_text},
                        {"role": "user", "content": additional_prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.7,
                    top_p=0.9,
                    top_k=50,
                    repetition_penalty=1.03,
                    stop=None
                )
                generated_text += "\n" + additional_response.choices[0].message.content.strip()
            
            return generated_text
    except Exception as e:
        print(f"An error occurred: {e}")
        await asyncio.sleep(60)
        return await generate_chunk(api, model, topic, current_word_count, language, is_new_chapter)