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