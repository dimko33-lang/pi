#!/usr/bin/env python3
"""
Pi Chat API - Minimal interface for GROQ models
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

API_KEYS = {
    'groq': os.getenv('GROQ_API_KEY', '')
}

def get_groq_response(message, model, history=None):
    """Get response from GROQ API"""
    if not API_KEYS['groq']:
        return "[ERROR] GROQ_API_KEY not set"
    
    headers = {
        'Authorization': f'Bearer {API_KEYS["groq"]}',
        'Content-Type': 'application/json'
    }
    
    messages = []
    if history:
        messages = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in history]
    
    messages.append({"role": "user", "content": message})
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048
    }
    
    try:
        resp = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=60
        )
        result = resp.json()
        if 'choices' in result:
            return result['choices'][0]['message']['content']
        return f"[ERROR] {result.get('error', {}).get('message', 'Unknown error')}"
    except Exception as e:
        return f"[ERROR] {str(e)}"

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '')
    model = data.get('model', 'llama-3.1-8b-instant')
    history = data.get('history', [])
    
    if not message:
        return jsonify({"error": "Empty message"}), 400
    
    reply = get_groq_response(message, model, history)
    
    return jsonify({
        "reply": reply,
        "model": "groq"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=False)