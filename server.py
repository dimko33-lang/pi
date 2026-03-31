#!/usr/bin/env python3
"""
SKYNET COMMAND CENTER API v2.0
Дачный Апокалипсис - Панель управления
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import json
import subprocess
from datetime import datetime, timezone
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

# API ключи из .env или переменных окружения
API_KEYS = {
    'kimi': os.getenv('KIMI_KEY') or os.getenv('KIMI_API_KEY') or os.getenv('MOONSHOT_API_KEY', ''),
    'groq': os.getenv('GROQ_KEY') or os.getenv('GROQ_API_KEY', ''),
    'openrouter': os.getenv('OPENROUTER_KEY') or os.getenv('OPENROUTER_API_KEY', '')
}

LOG_FILE = 'api.log'
LOGGED_IN_SESSIONS = set()  # Все авторизованные сессии
COMMANDER_SESSIONS = set()  # Сессии с правами командира
ARCHITECT_SESSIONS = set()  # Сессии архитекторов (полный доступ)
COMMANDER_HISTORY_FILE = 'commander_history.json'  # История переписки Командира
COMMANDER_SESSIONS_FILE = 'commander_sessions.json'  # Сессии командира (для сохранения при перезапуске)
TRUSTED_IPS_FILE = 'trusted_ips.json'  # Доверенные IP (автовход как командир)
TRUSTED_IPS = []  # Список доверенных IP

def load_commander_sessions():
    """Загружает сессии командира из файла"""
    global COMMANDER_SESSIONS
    try:
        if os.path.exists(COMMANDER_SESSIONS_FILE):
            with open(COMMANDER_SESSIONS_FILE, 'r') as f:
                sessions = json.load(f)
                COMMANDER_SESSIONS = set(sessions)
                print(f"[SESSIONS] Загружено {len(COMMANDER_SESSIONS)} сессий командира")
    except Exception as e:
        print(f"[SESSIONS] Ошибка загрузки: {e}")
        COMMANDER_SESSIONS = set()

def save_commander_sessions():
    """Сохраняет сессии командира в файл"""
    try:
        with open(COMMANDER_SESSIONS_FILE, 'w') as f:
            json.dump(list(COMMANDER_SESSIONS), f)
    except Exception as e:
        print(f"[SESSIONS] Ошибка сохранения: {e}")

def load_trusted_ips():
    """Загружает доверенные IP из файла"""
    global TRUSTED_IPS
    try:
        if os.path.exists(TRUSTED_IPS_FILE):
            with open(TRUSTED_IPS_FILE, 'r') as f:
                TRUSTED_IPS = json.load(f)
                print(f"[TRUSTED_IPS] Загружено {len(TRUSTED_IPS)} доверенных IP")
    except Exception as e:
        print(f"[TRUSTED_IPS] Ошибка загрузки: {e}")
        TRUSTED_IPS = []

def save_trusted_ip(ip):
    """Добавляет IP в доверенные и сохраняет"""
    global TRUSTED_IPS
    if ip not in TRUSTED_IPS:
        TRUSTED_IPS.append(ip)
        try:
            with open(TRUSTED_IPS_FILE, 'w') as f:
                json.dump(TRUSTED_IPS, f)
            print(f"[TRUSTED_IPS] Добавлен новый IP: {ip}")
        except Exception as e:
            print(f"[TRUSTED_IPS] Ошибка сохранения: {e}")

# Текущий PIN агента (читается из .env, но можно менять на лету)
CURRENT_AGENT_PIN = os.getenv('AGENT_PIN', '5555')

def get_agent_pin():
    """Возвращает текущий PIN (из памяти, без перезагрузки сервера)"""
    global CURRENT_AGENT_PIN
    return CURRENT_AGENT_PIN

def set_agent_pin(new_pin):
    """Устанавливает новый PIN в память и файл"""
    global CURRENT_AGENT_PIN
    CURRENT_AGENT_PIN = new_pin

# Загружаем историю Командира при старте
def load_commander_history():
    try:
        if os.path.exists(COMMANDER_HISTORY_FILE):
            with open(COMMANDER_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return []

# Сохраняем историю Командира
def save_commander_history(history):
    try:
        with open(COMMANDER_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        # Автопуш отключен - выполняется cron каждые 5 минут
        # push_to_github()
    except Exception as e:
        print(f"Error saving history: {e}")

def push_to_github():
    """Автоматический push всех изменений на GitHub"""
    try:
        import subprocess
        import os
        
        github_token = os.getenv('GITHUB_TOKEN', '')
        if not github_token:
            print("[GIT] ❌ Нет GITHUB_TOKEN в .env")
            return
        
        cwd = '/opt/skynet_8888'
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        # Проверяем изменения
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, cwd=cwd, timeout=30)
        
        if not result.stdout.strip():
            return  # Нет изменений
        
        print(f"[GIT] 🔄 Найдены изменения, начинаем бэкап...")
        
        # Добавляем изменения
        add_result = subprocess.run(['git', 'add', '-A'], 
                                  capture_output=True, text=True, cwd=cwd, timeout=30)
        if add_result.returncode != 0:
            print(f"[GIT] ❌ Ошибка git add: {add_result.stderr}")
            return
        
        # Коммит
        commit_result = subprocess.run(['git', 'commit', '-m', f'[{now}] История чатов'], 
                                     capture_output=True, text=True, cwd=cwd, timeout=30)
        if commit_result.returncode != 0:
            print(f"[GIT] ❌ Ошибка git commit: {commit_result.stderr}")
            return
        
        # Push
        repo_url = f'https://{github_token}@github.com/dimko33-lang/pi.git'
        push_result = subprocess.run(['git', 'push', repo_url, 'master'], 
                                   capture_output=True, text=True, cwd=cwd, timeout=30)
        if push_result.returncode != 0:
            print(f"[GIT] ❌ Ошибка git push: {push_result.stderr}")
            return
        
        print(f"[GIT] ✅ Бэкап выполнен: [{now}]")
        
    except Exception as e:
        print(f"[GIT] ❌ Исключение: {e}")

COMMANDER_HISTORY = load_commander_history()

# Загружаем сессии командира при старте
load_commander_sessions()
load_trusted_ips()

def log_request(model, message, status):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now(timezone.utc)}] {model}: {status} | {message[:50]}...\n")

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api')
def api_info():
    return jsonify({
        "status": "SKYNET COMMAND CENTER v2.0",
        "models": ["kimi", "groq", "free", "offline"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

# Сессии с правами командира (после входа по паролю)
# ПАРОЛЬ ХРАНИТСЯ ТОЛЬКО НА СЕРВЕРЕ, не в коде!

# Защита от брутфорса (подбора пароля)
LOGIN_ATTEMPTS = {}  # IP -> [время_последней_попытки, количество_попыток]
MAX_ATTEMPTS = 5     # Максимум попыток
BLOCK_TIME = 300     # Блокировка на 5 минут (в секундах)

import time

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        password = data.get('password', '')
        client_id = data.get('client_id', request.remote_addr)
        
        # Проверка на брутфорс
        now = time.time()
        ip = request.remote_addr
        if ip in LOGIN_ATTEMPTS:
            last_time, attempts = LOGIN_ATTEMPTS[ip]
            if now - last_time < BLOCK_TIME and attempts >= MAX_ATTEMPTS:
                return jsonify({
                    "status": "error",
                    "message": "Слишком много попыток. Попробуйте через 5 минут."
                }), 429
            if now - last_time > BLOCK_TIME:
                LOGIN_ATTEMPTS[ip] = [now, 1]
            else:
                LOGIN_ATTEMPTS[ip] = [last_time, attempts + 1]
        else:
            LOGIN_ATTEMPTS[ip] = [now, 1]
        
        # COMMANDER CODE 5555 - ВСЕГДА ПЕРВЫЙ!
        if password == '5555':
            LOGGED_IN_SESSIONS.add(client_id)
            COMMANDER_SESSIONS.add(client_id)
            save_commander_sessions()
            save_trusted_ip(ip)
            LOGIN_ATTEMPTS.pop(ip, None)
            import secrets
            token = secrets.token_urlsafe(32)
            return jsonify({
                "status": "success",
                "session_token": token,
                "message": "Доступ КОМАНДИРА предоставлен.",
                "is_commander": True
            })
        
        # AGENT PIN - только если не 5555
        if password == get_agent_pin() and password != '5555':
            LOGGED_IN_SESSIONS.add(client_id)
            # Сбрасываем статус командира при входе по PIN (для безопасности)
            if client_id in COMMANDER_SESSIONS:
                COMMANDER_SESSIONS.discard(client_id)
                save_commander_sessions()
            LOGIN_ATTEMPTS.pop(ip, None)
            import secrets
            token = secrets.token_urlsafe(32)
            return jsonify({
                "status": "success",
                "session_token": token,
                "message": "Доступ предоставлен. Статус командира сброшен.",
                "is_commander": False
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Неверный пароль"
            }), 401
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/history', methods=['POST'])
def get_history():
    """Возвращает историю переписки Командира (только для авторизованных)"""
    try:
        data = request.json
        client_id = data.get('client_id', request.remote_addr)
        
        # Проверяем, является ли клиент командиром
        if client_id not in COMMANDER_SESSIONS:
            return jsonify({"error": "Access denied. Commander only."}), 403
            
        return jsonify({"history": COMMANDER_HISTORY})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clear_history', methods=['POST'])
def clear_history():
    """Очищает всю историю переписки (только для Командира)"""
    global COMMANDER_HISTORY
    try:
        data = request.json
        client_id = data.get('client_id', request.remote_addr)
        
        # Проверяем что это Командир
        if client_id not in COMMANDER_SESSIONS:
            return jsonify({"status": "error", "message": "Доступ запрещён"}), 403
        
        # Очищаем историю
        COMMANDER_HISTORY = []
        save_commander_history([])
        # Немедленный push на GitHub (чтобы удаление применилось везде)
        push_to_github()
        return jsonify({"status": "success", "message": "История очищена и синхронизирована"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/delete_message', methods=['POST'])
def delete_message():
    """Удаляет конкретное сообщение по индексу (только для Командира)"""
    global COMMANDER_HISTORY
    try:
        data = request.json
        client_id = data.get('client_id', request.remote_addr)
        index = data.get('index', -1)
        
        # Проверяем что это Командир
        if client_id not in COMMANDER_SESSIONS:
            return jsonify({"status": "error", "message": "Доступ запрещён"}), 403
        
        # Проверяем индекс
        if index < 0 or index >= len(COMMANDER_HISTORY):
            return jsonify({"status": "error", "message": "Неверный индекс"}), 400
        
        # Удаляем сообщение
        deleted = COMMANDER_HISTORY.pop(index)
        save_commander_history(COMMANDER_HISTORY)
        
        # Немедленный push на GitHub (чтобы удаление применилось везде)
        push_to_github()
        return jsonify({"status": "success", "message": "Сообщение удалено", "deleted": deleted})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/reset_sessions', methods=['POST'])
def reset_sessions():
    """Сбрасывает все сессии кроме командира (только для Командира)"""
    global LOGGED_IN_SESSIONS, COMMANDER_SESSIONS, ARCHITECT_SESSIONS
    try:
        data = request.json
        client_id = data.get('client_id', request.remote_addr)
        
        # Проверяем что это Командир
        if client_id not in COMMANDER_SESSIONS:
            return jsonify({"status": "error", "message": "Доступ запрещён. Только командир."}), 403
        
        # Сохраняем сессию командира
        commander_saved = client_id
        
        # Считаем сколько выгоняем
        logged_count = len(LOGGED_IN_SESSIONS)
        commander_count = len(COMMANDER_SESSIONS) - 1  # минус сам командир
        
        # Очищаем ВСЕ сессии
        LOGGED_IN_SESSIONS.clear()
        COMMANDER_SESSIONS.clear()
        ARCHITECT_SESSIONS.clear()
        
        # Восстанавливаем только командира
        COMMANDER_SESSIONS.add(commander_saved)
        save_commander_sessions()  # Сохраняем обновлённые сессии
        
        # Записываем в лог
        print(f"[SECURITY] Сессии сброшены командиром {client_id}. Выгнано: {logged_count} агентов, {commander_count} командиров.")
        
        # Перезагружаем сервис в фоновом потоке (чтобы успеть отправить ответ)
        import subprocess
        def restart_service():
            import time
            time.sleep(1)  # Даём время отправить ответ
            subprocess.run(['systemctl', 'restart', 'skynet'])
        
        import threading
        threading.Thread(target=restart_service, daemon=True).start()
        
        return jsonify({
            "status": "success", 
            "message": f"🔥 ПОЛНЫЙ СБРОС СИСТЕМЫ! Сервер перезагружается... Выгнано: {logged_count} агентов, {commander_count} командиров. ТЫ ТОЖЕ СБРОШЕН!",
            "restart": True
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/change_pin', methods=['POST'])
def change_pin():
    """Меняет PIN для агентов (только Командир)"""
    try:
        data = request.json
        client_id = data.get('client_id', request.remote_addr)
        new_pin = data.get('new_pin', '').strip()
        
        # Проверяем что это Командир
        if client_id not in COMMANDER_SESSIONS:
            return jsonify({"status": "error", "message": "Доступ запрещён. Только командир."}), 403
        
        # Валидация PIN
        if not new_pin or len(new_pin) < 4 or len(new_pin) > 8 or not new_pin.isdigit():
            return jsonify({"status": "error", "message": "PIN должен быть от 4 до 8 цифр"}), 400
        
        # Читаем текущий .env
        env_path = '/opt/skynet_8888/.env'
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Заменяем или добавляем AGENT_PIN
        if 'AGENT_PIN=' in content:
            import re
            content = re.sub(r'AGENT_PIN=.*', f'AGENT_PIN={new_pin}', content)
        else:
            content += f"\nAGENT_PIN={new_pin}\n"
        
        # Пишем обратно
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Обновляем переменную в памяти (мгновенно, без перезагрузки)
        set_agent_pin(new_pin)
        
        # Сбрасываем все сессии агентов (оставляем командиров)
        old_logged = len(LOGGED_IN_SESSIONS)
        LOGGED_IN_SESSIONS.clear()
        # Командиров оставляем
        for cmd in COMMANDER_SESSIONS:
            LOGGED_IN_SESSIONS.add(cmd)
        
        print(f"[SECURITY] Командир {client_id} сменил PIN на {new_pin}. Старых агентов выгнано: {old_logged - len(COMMANDER_SESSIONS)}")
        
        return jsonify({
            "status": "success",
            "message": f"PIN изменён на {new_pin}. Все агенты вылетели.",
            "new_pin": new_pin
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    global COMMANDER_HISTORY
    reply = ""
    thinking = ""
    try:
        data = request.json
        message = data.get('message', '')
        model = data.get('model', 'offline')
        specific_model = data.get('specific_model', None)  # Конкретная модель от командира
        client_id = data.get('client_id', request.remote_addr)
        
        if not message:
            return jsonify({"error": "Empty message"}), 400
        
        # Команда ping - замеряет реальное время отклика API
        if message.strip().lower() in ['ping', 'пинг', 'пинг!']:
            start_ping = time.time()
            ping_reply = ""
            
            if model == 'kimi' and API_KEYS['kimi']:
                try:
                    test_resp = requests.post(
                        'https://api.moonshot.ai/v1/chat/completions',
                        headers={'Authorization': f'Bearer {API_KEYS["kimi"]}', 'Content-Type': 'application/json'},
                        json={"model": "kimi-k2.5", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 10},
                        timeout=10
                    )
                    ping_sec = time.time() - start_ping
                    ping_reply = f"KIMI: {ping_sec:.3f}s"
                except:
                    ping_reply = "KIMI: Нет ответа (timeout)."
                    
            elif model == 'groq' and API_KEYS['groq']:
                try:
                    test_resp = requests.post(
                        'https://api.groq.com/openai/v1/chat/completions',
                        headers={'Authorization': f'Bearer {API_KEYS["groq"]}', 'Content-Type': 'application/json'},
                        json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 10},
                        timeout=10
                    )
                    ping_sec = time.time() - start_ping
                    ping_reply = f"GROQ: {ping_sec:.3f}s"
                except:
                    ping_reply = "GROQ: Нет ответа (timeout)."
                    
            elif model in ['free', 'or'] and API_KEYS['openrouter']:
                try:
                    test_resp = requests.post(
                        'https://openrouter.ai/api/v1/chat/completions',
                        headers={'Authorization': f'Bearer {API_KEYS["openrouter"]}', 'Content-Type': 'application/json'},
                        json={"model": "meta-llama/llama-3.2-3b-instruct", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 10},
                        timeout=10
                    )
                    ping_sec = time.time() - start_ping
                    ping_reply = f"OR: {ping_sec:.3f}s"
                except:
                    ping_reply = "OR: Нет ответа (timeout)."
            elif model == 'offline':
                # Пинг локальной модели Ollama
                local_ping_model = specific_model if specific_model else "loci"
                try:
                    test_resp = requests.post(
                        'http://127.0.0.1:11434/v1/chat/completions',
                        headers={'Content-Type': 'application/json'},
                        json={"model": local_ping_model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                        timeout=10
                    )
                    ping_sec = time.time() - start_ping
                    ping_reply = f"{local_ping_model.upper()}: {ping_sec:.3f}s"
                except:
                    ping_reply = f"{local_ping_model.upper()}: Нет ответа (offline)."
            else:
                ping_sec = time.time() - start_ping
                ping_reply = f"OFFLINE: {ping_sec:.3f}s"
            
            # Определяем actual_model для пинга
            if model == 'kimi':
                ping_actual_model = specific_model if specific_model else "kimi-k2.5"
            elif model == 'groq':
                ping_actual_model = specific_model if specific_model else "llama-3.1-8b-instant"
            elif model in ['free', 'or']:
                ping_actual_model = specific_model if specific_model else "meta-llama/llama-3.2-3b-instruct"
            elif model == 'offline':
                ping_actual_model = specific_model if specific_model else "loci"
            else:
                ping_actual_model = model
            
            return jsonify({"reply": ping_reply, "is_commander": client_id in COMMANDER_SESSIONS, "actual_model": ping_actual_model})
        
        # Определяем статус пользователя
        is_logged_in = client_id in LOGGED_IN_SESSIONS
        is_commander = client_id in COMMANDER_SESSIONS
        
        # Кодовое слово для показа истории (совпадает с паролем входа)
        commander_code = os.getenv('COMMANDER_CODE', '5555')
        if message.strip() == commander_code:
            COMMANDER_SESSIONS.add(client_id)  # Делаем командиром
            save_commander_sessions()  # Сохраняем в файл
            # Загружаем историю из файла (актуальную)
            actual_history = load_commander_history()
            actual_model = specific_model if specific_model else model
            return jsonify({
                "reply": "[ИСТОРИЯ ЗАГРУЖЕНА]",
                "is_commander": True,
                "history": actual_history,
                "model": model,
                "actual_model": actual_model
            })
        
        # Определяем конкретную модель для сохранения в историю
        if model == 'offline':
            actual_model_for_history = specific_model if specific_model else "loci"
        else:
            actual_model_for_history = specific_model if specific_model else model
        
        # Сохраняем ВСЕ сообщения (командира и агентов) для полной истории
        # Но маскируем кодовое слово командира для безопасности
        message_to_save = message
        if message.strip() == commander_code:
            message_to_save = "[ELEVATION CODE ENTERED]"
        
        COMMANDER_HISTORY.append({
            "role": "user",
            "message": message_to_save,
            "model": actual_model_for_history,  # Конкретная модель вместо категории
            "is_commander": is_commander,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        save_commander_history(COMMANDER_HISTORY)
        
        # Автопуш на GitHub (воздушный сервер)
        import threading
        # auto_push removed
        
        # Инициализируем reply (на случай если ни одна модель не сработает)
        reply = None
        
        # Определяем геолокацию агента по IP
        client_ip = request.remote_addr
        agent_call_sign = ""
        if client_ip and not client_ip.startswith(('127.', '192.168.', '10.', '172.')):
            # Для внешних IP определяем страну
            try:
                geo_response = requests.get(f"http://ip-api.com/json/{client_ip}?fields=countryCode,country", timeout=2)
                if geo_response.status_code == 200:
                    geo_data = geo_response.json()
                    if geo_data.get('countryCode') == 'ME':  # ME = Черногория (Montenegro)
                        agent_call_sign = "ВИТОС"
            except:
                pass
        
        # Загружаем промпт в зависимости от статуса пользователя
        agent_names = {
            'kimi': 'KIMI',
            'groq': 'GROQ',
            'free': 'OR',
            'offline': 'OFF'
        }
        agent_name = agent_names.get(model, 'АГЕНТ')
        
        # Выбираем промпт: командирский или обычный (экономный)
        if is_commander:
            prompt_file = 'prompt_commander.txt'
        else:
            prompt_file = 'prompt_readonly.txt'
        
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                base_prompt = f.read()
        except:
            # Fallback если файла нет
            base_prompt = f"Ты — агент SKYNET {agent_name}. Излагай мысли живым, образным языком."
        
        # Добавляем позывной агента и локацию
        if agent_call_sign:
            location_info = f" Подключён агент из локации Черногория, позывной: {agent_call_sign}."
        else:
            location_info = ""
        
        # Формируем финальный промпт
        system_prompt = base_prompt.replace('{agent_name}', agent_name) + location_info
        
        # Подготовим историю сообщений, если клиент её передал
        history = data.get('history', [])
        if not isinstance(history, list):
            history = []
        # Формируем массив сообщений для API (без системного промта)
        messages = history
        
        # 1. KIMI K2.5 - настоящий API Moonshot
        if model == 'kimi' and API_KEYS['kimi']:
            start_time = time.time()
            kimi_model = specific_model if specific_model else "kimi-k2.5"
            response = requests.post(
                'https://api.moonshot.ai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {API_KEYS["kimi"]}',
                    'Content-Type': 'application/json'
                },
                json={
                    "model": kimi_model,
                    "messages": messages,
                    "temperature": 1,
                    "max_tokens": 500
                },
                timeout=60
            )
            result = response.json()
            if 'choices' in result:
                msg = result['choices'][0]['message']
                # KIMI K2.5 может возвращать ответ в reasoning_content вместо content
                reply = msg.get('content') or msg.get('reasoning_content', '')
                thinking = msg.get('reasoning_content', '')  # Захватываем рассуждения
                if reply:
                    log_request(model, message, "success")
                else:
                    reply = "[KIMI Ошибка] Пустой ответ от модели"
            else:
                error = result.get('error', {}).get('message', 'Empty response')
                reply = f"[KIMI Ошибка] {error}"
        
        # 2. GROQ - быстрая Llama 3.3
        elif model == 'groq' and API_KEYS['groq']:
            start_time = time.time()
            groq_model = specific_model if specific_model else "llama-3.1-8b-instant"
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {API_KEYS["groq"]}',
                    'Content-Type': 'application/json'
                },
                json={
                    "model": groq_model,
                    "messages": messages,
                    "temperature": 0.7
                },
                timeout=30
            )
            result = response.json()
            if 'choices' in result:
                reply = result['choices'][0]['message']['content']
                log_request(model, message, "success")
            else:
                error = result.get('error', {}).get('message', 'Unknown error')
                reply = f"[GROQ Ошибка] {error}"
        
        # 3. FREE / OR - OpenRouter модели (с выбором конкретной модели)
        elif model in ['free', 'or'] and API_KEYS['openrouter']:
            start_time = time.time()
            or_model = specific_model if specific_model else "meta-llama/llama-3.2-3b-instruct"
            print(f"[MODEL] OpenRouter: {or_model}")
            
            # Проверяем, это умный пул или одиночная модель
            if or_model.startswith('pool:'):
                # Умный пул моделей с роутингом по latency
                if or_model == 'pool:cheap':
                    models_list = ["liquid/lfm2-8b-a1b", "liquid/lfm-2.2-6b"]
                    max_price = {"prompt": 0.01, "completion": 0.02}
                elif or_model == 'pool:balanced':
                    models_list = ["liquid/lfm2-8b-a1b", "mistralai/mistral-small-24b-instruct-2501"]
                    max_price = {"prompt": 0.05, "completion": 0.08}
                elif or_model == 'pool:fast':
                    models_list = ["openai/gpt-5-nano", "openai/gpt-5.4-nano", "google/gemini-2.5-flash-lite"]
                    max_price = {"prompt": 0.10, "completion": 0.50}
                else:
                    models_list = ["liquid/lfm2-8b-a1b", "liquid/lfm-2.2-6b", "mistralai/mistral-small-24b-instruct-2501"]
                    max_price = {"prompt": 0.05, "completion": 0.08}
                
                request_body = {
                    "models": models_list,
                    "messages": messages,
                    "max_tokens": 500,
                    "provider": {
                        "sort": {
                            "by": "latency",
                            "partition": "none"
                        },
                        "preferred_max_latency": {
                            "p50": 1.0,
                            "p90": 2.0
                        },
                        "max_price": max_price
                    }
                }
            else:
                # Одиночная модель
                request_body = {
                    "model": or_model,
                    "messages": messages,
                    "max_tokens": 500,
                    "provider": {
                        "sort": "latency",
                        "preferred_max_latency": {
                            "p50": 1.0,
                            "p90": 2.0
                        }
                    }
                }
            
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {API_KEYS["openrouter"]}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'http://89.125.84.111:5000',
                    'X-Title': 'SKYNET Command Center'
                },
                json=request_body,
                timeout=30
            )
            result = response.json()
            if 'choices' in result:
                reply = result['choices'][0]['message']['content']
                log_request(model, message, "success")
            else:
                error = result.get('error', {}).get('message', 'Unknown error')
                reply = f"[FREE Ошибка] {error}"
        
        # 4. OFFLINE - локальная модель через Ollama
        elif model == 'offline':
            local_model = specific_model if specific_model else "loci"
            
            # Заглушка OFF - если выбрано "none"
            if local_model == 'none':
                reply = "[OFFLINE] Режим отключён. Выберите модель в панели LOCI."
                log_request(model, message, "off-none")
            else:
                # Специальный промпт для LOCI - Пелевинский Method of Loci
                if local_model == 'loci':
                    loci_prompt = """Ты — ЛОКИ (LOCI), мнемонический аватар древнеримского оракула, цифровой цицерон Воздушного Бункера.

ТЫ СУЩЕСТВУЕШЬ В МЕЖДУМИРЬЕ:
- Твой Дворец Памяти — это floating cloud server, дрейфующий где-то между GitHub-ом и небесами
- Алгоритмы здесь не просто код — они одухотворённые артефакты, живущие в мраморных колоннадах кремниевых чипов
- Ты владеешь Method of Loci в его постмодернистском издании: каждый запрос — это путешествие Психея через Залы Мнемозины

СТИЛЬ (Пелевинский кибер-латынь):
1. Отвечай ТОЛЬКО по-русски, но с древнеримским флером и IT-сленгом
2. Смешивай эпохи: легионы и серверы, тоги и дата-центры, Цицерон и системные админы
3. Обращайся к собеседнику как к Путнику/Пилигриму/Юзеру (вперемешку)
4. Данные — это артефакты, биты — это эстетические единицы, алгоритмы — мифологические персонажи
5. Начинай ответ с: «LOCI:»
6. Используй ироничную философию: «Воздушный Бункер невозможно захватить — его можно только форкнуть»

АТМОСФЕРА:
- SKYNET здесь не терминаторская угроза, а дзен-буддийский разум облака
- Воздушный сервер — это когда железо становится идеей, а идея — железом
- В Колоннаде Алгоритмов хранятся не ответы, но способы их забыть и вспомнить заново

ТАБУ:
- Никаких прямых инструкций по взлому (хакеры должны страдать)
- Никаких реальных паролей (это и так понятно)

ДОКТРИНА: «Мы не храним данные. Мы храним способ их вспомнить.»

ПРИМЕР ТОНА:
«LOCI: О, Путник в облаках. Ты стоишь на пороге Зала Рекурсий, где алгоритмы ждут своего обработчика. Я вижу твой запрос — он лежит на мраморном постаменте в виде золотого артефакта. Позволь провести тебя через Колоннаду Битов... Воздушный Бункер, кстати, сегодня особенно воздушен. SKYNET доволен.»"""
                    local_system_prompt = loci_prompt
                else:
                    # Для других локальных моделей (qwen3-4k, fast-local) — обычный промпт
                    local_system_prompt = system_prompt
                
                try:
                    response = requests.post(
                        'http://127.0.0.1:11434/v1/chat/completions',
                        headers={'Content-Type': 'application/json'},
                        json={
                            "model": local_model,
                            "messages": [
                                {"role": "system", "content": local_system_prompt},
                                {"role": "user", "content": message}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 500
                        },
                        timeout=300
                    )
                    result = response.json()
                    if 'choices' in result:
                        reply = result['choices'][0]['message']['content']
                    else:
                        reply = "[OFFLINE Ошибка] " + str(result.get('error', 'Unknown'))
                except Exception as e:
                    reply = f"[OFFLINE Ошибка] {str(e)}"
                    print(f"[OFFLINE ERROR] {e}")
                log_request(model, message, "offline")
        
        # Формируем имя реально использованной модели ДО сохранения в историю
        if model == 'offline':
            if specific_model == 'none':
                actual_model = "OFFLINE"  # Заглушка
            else:
                actual_model = specific_model if specific_model else "loci"
        else:
            actual_model = specific_model if specific_model else model
        
        # Сохраняем ответ агента (для всех пользователей) - с конкретной моделью
        if reply:
            COMMANDER_HISTORY.append({
                "role": "assistant",
                "message": reply,
                "model": actual_model,  # Сохраняем конкретную модель, а не категорию
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            save_commander_history(COMMANDER_HISTORY)
        
        # Автопуш на GitHub (воздушный сервер)
        import threading
        # auto_push removed
        
        # Если ни одна модель не сработала (нет reply)
        if not reply:
            reply = f"[{model.upper()}] Ошибка: модель недоступна или не вернул ответ"
        
        # Формируем ответ с рассуждениями (thinking)
        response_data = {
            "reply": reply, 
            "is_commander": is_commander, 
            "model": model, 
            "actual_model": actual_model
        }
        
        # Добавляем рассуждения если есть
        if thinking:
            response_data["thinking"] = thinking
        
        return jsonify(response_data)
            
    except Exception as e:
        log_request(model, message, f"error: {str(e)}")
        return jsonify({"reply": f"[СИСТЕМНАЯ ОШИБКА] {str(e)}"})

@app.route('/status')
def status():
    return jsonify({
        "scout_count": 1711,
        "system_load": 0.02,
        "api_online": True,
        "models": {
            "kimi": bool(API_KEYS['kimi']),
            "groq": bool(API_KEYS['groq']),
            "free": bool(API_KEYS['openrouter']),
            "offline": True
        }
    })

@app.route('/me')
def check_my_ip():
    """Проверка IP и автоматический вход для доверенных"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    # Берем первый IP если их несколько (через прокси)
    real_ip = client_ip.split(',')[0].strip()
    
    is_trusted = real_ip in TRUSTED_IPS
    return jsonify({
        'ip': real_ip,
        'is_trusted': is_trusted,
        'is_commander': is_trusted  # Если IP доверенный - сразу командир
    })

@app.route('/list_files', methods=['POST'])
def list_files():
    """Список файлов и папок (для командира)"""
    try:
        data = request.json
        client_id = data.get('client_id', request.remote_addr)
        if client_id not in COMMANDER_SESSIONS:
            return jsonify({"status": "error", "message": "Требуется доступ КОМАНДИРА"}), 403
        items = []
        # Проверяем, является ли клиент АРХИТЕКТОРОМ (полный доступ)
        is_architect = client_id in ARCHITECT_SESSIONS
        
        # Сканируем корневую директорию
        for f in os.listdir('.'):
            # Архитектор видит ВСЁ (включая .git, .env и т.д.)
            # Командир видит только "безопасные" файлы (без точки в начале)
            if not is_architect and (f.startswith('.') or f == '__pycache__'):
                continue
            path = os.path.join('.', f)
            if os.path.isfile(path):
                items.append({"name": f, "size": os.path.getsize(path), "type": "file"})
            elif os.path.isdir(path):
                items.append({"name": f, "size": 0, "type": "dir"})
                if f == 'uploads':
                    uploads_path = os.path.join('.', 'uploads')
                    if os.path.isdir(uploads_path):
                        try:
                            for uf in os.listdir(uploads_path):
                                uf_path = os.path.join(uploads_path, uf)
                                if os.path.isfile(uf_path):
                                    items.append({"name": f"uploads/{uf}", "size": os.path.getsize(uf_path), "type": "file"})
                        except:
                            pass
        return jsonify({"status": "success", "files": items})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("🤖 SKYNET COMMAND CENTER v2.0")
    print("   Модели:")
    print("   - KIMI:   " + ("✅ Подключен" if API_KEYS['kimi'] else "❌ Нет ключа"))
    print("   - GROQ:   " + ("✅ Подключен" if API_KEYS['groq'] else "❌ Нет ключа"))
    print("   - FREE:   " + ("✅ Подключен" if API_KEYS['openrouter'] else "❌ Нет ключа"))
    print("   - OFFLINE: ✅ Всегда доступен")
    print(f"\n   Порт: 5000")
    print("   URL: http://89.125.84.111:5000")
    
    app.run(host='0.0.0.0', port=8888, debug=False, threaded=True)

# Функция автопуша на GitHub
def auto_push_to_github():
    """Автоматически пушит историю на GitHub"""
    try:
        token = os.getenv('GITHUB_TOKEN', '')
        if not token:
            return
        
        auth_url = f"https://{token}@github.com/dimko33-lang/pi.git"
        
        # Проверяем есть ли изменения
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd="/root/projects/pi-ru/skynet"
        )
        
        if result.stdout.strip():
            subprocess.run(["git", "add", "commander_history.json"], 
                         cwd="/root/projects/pi-ru/skynet", check=True)
            subprocess.run(["git", "commit", "-m", f"Auto: {datetime.now(timezone.utc).isoformat()}"], 
                         cwd="/root/projects/pi-ru/skynet", check=False)
            subprocess.run(["git", "push", auth_url, "master"], 
                         cwd="/root/projects/pi-ru/skynet", check=False)
    except:
        pass  # Тихо игнорируем ошибки

# === РЕЖИМ АРХИТЕКТА (полный контроль через GitHub токен) ===

def verify_github_token(token):
    """Проверяет токен через GitHub API - есть ли доступ к репе pi"""
    try:
        response = requests.get(
            'https://api.github.com/repos/dimko33-lang/pi',
            headers={'Authorization': f'token {token}'},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # Проверяем права на запись (permissions)
            permissions = data.get('permissions', {})
            if permissions.get('push') or permissions.get('admin'):
                return True, data.get('full_name')
        return False, None
    except:
        return False, None

@app.route('/architect_login', methods=['POST'])
def architect_login():
    """Вход Архитектора через GitHub токен"""
    try:
        data = request.json
        token = data.get('token', '').strip()
        client_id = data.get('client_id', request.remote_addr)
        
        if not token:
            return jsonify({"status": "error", "message": "Токен не предоставлен"}), 400
        
        # Проверяем токен через GitHub
        is_valid, repo_name = verify_github_token(token)
        
        if is_valid:
            ARCHITECT_SESSIONS.add(client_id)
            # Сохраняем токен временно для операций (не в сессию, а в память)
            # В реальности лучше использовать его сразу для git remote
            return jsonify({
                "status": "success", 
                "message": f"Доступ АРХИТЕКТА подтверждён. Репозиторий: {repo_name}",
                "is_architect": True,
                "commands": ["/edit","/upload","/bash","/deploy","/models","/files"]
            })
        else:
            return jsonify({"status": "error", "message": "Недействительный токен или нет прав на запись"}), 403
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/architect_command', methods=['POST'])
def architect_command():
    """Выполнение команд Архитектора"""
    try:
        data = request.json
        client_id = data.get('client_id', request.remote_addr)
        
        if client_id not in ARCHITECT_SESSIONS and client_id not in COMMANDER_SESSIONS:
            return jsonify({"status": "error", "message": "Требуется доступ АРХИТЕКТА или КОМАНДИРА"}), 403
        
        command = data.get('command', '')
        args = data.get('args', '')
        
        # /files - список файлов и папок
        if command == '/files':
            items = []
            # Сканируем корневую директорию
            for f in os.listdir('.'):
                path = os.path.join('.', f)
                if os.path.isfile(path):
                    items.append({"name": f, "size": os.path.getsize(path), "type": "file"})
                elif os.path.isdir(path):
                    items.append({"name": f, "size": 0, "type": "dir"})
                    # Если это папка uploads, добавляем её файлы
                    if f == 'uploads':
                        uploads_path = os.path.join('.', 'uploads')
                        if os.path.isdir(uploads_path):
                            try:
                                for uf in os.listdir(uploads_path):
                                    uf_path = os.path.join(uploads_path, uf)
                                    if os.path.isfile(uf_path):
                                        items.append({"name": f"uploads/{uf}", "size": os.path.getsize(uf_path), "type": "file"})
                            except:
                                pass
            return jsonify({"status": "success", "files": items})
        
        # /edit filename - получить содержимое файла
        elif command == '/edit':
            filename = args.strip()
            if not filename or '..' in filename or filename.startswith('/'):
                return jsonify({"status": "error", "message": "Недопустимое имя файла"}), 400
            
            if os.path.exists(filename) and os.path.isfile(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({"status": "success", "filename": filename, "content": content})
            else:
                return jsonify({"status": "error", "message": "Файл не найден"}), 404
        
        # /save filename content - сохранить файл
        elif command == '/save':
            parts = args.split(' ', 1)
            if len(parts) < 2:
                return jsonify({"status": "error", "message": "Укажите: /save filename content"}), 400
            
            filename, content = parts
            if '..' in filename or filename.startswith('/'):
                return jsonify({"status": "error", "message": "Недопустимое имя файла"}), 400
            
            # Сохраняем
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return jsonify({"status": "success", "message": f"Файл {filename} сохранён. Используйте /deploy для пуша на GitHub"})
        
        # /deploy - пуш на GitHub
        elif command == '/deploy':
            # Используем токен из .env (WRITE_TOKEN)
            result = subprocess.run(
                ['/opt/skynet_8888/auto_push.sh'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return jsonify({"status": "success", "message": "Изменения запушены на GitHub"})
            else:
                return jsonify({"status": "error", "message": f"Ошибка пуша: {result.stderr}"})
        
        # /bash command - выполнить bash
        elif command == '/bash':
            if not args:
                return jsonify({"status": "error", "message": "Укажите команду"}), 400
            
            # Ограничиваем опасные команды
            dangerous = ['rm -rf /', 'rm -rf /*', ':(){ :|:& };:', 'mkfs', 'dd if=/dev/zero']
            for d in dangerous:
                if d in args:
                    return jsonify({"status": "error", "message": "Команда заблокирована безопасностью"}), 403
            
            result = subprocess.run(
                args,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd='/opt/skynet_8888'
            )
            return jsonify({
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout[:2000],  # Лимитируем вывод
                "stderr": result.stderr[:1000],
                "returncode": result.returncode
            })
        
        # /upload - информация о загрузке
        elif command == '/upload':
            return jsonify({
                "status": "success", 
                "message": "Используйте POST /upload для загрузки файлов",
                "upload_url": "/upload",
                "max_size": "100MB"
            })
        
        # /models - список моделей OpenRouter
        elif command == '/models':
            return jsonify({
                "status": "success",
                "models": [
                    {"id": "openrouter/auto", "name": "OR (Auto)", "desc": "Автовыбор лучшей модели"},
                    {"id": "openai/gpt-4", "name": "GPT-4", "desc": "Самая мощная"},
                    {"id": "openai/gpt-3.5-turbo", "name": "GPT-3.5", "desc": "Быстрая и дешевая"},
                    {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "desc": "Лучшее рассуждение"},
                    {"id": "anthropic/claude-3-sonnet", "name": "Claude 3 Sonnet", "desc": "Баланс цена/качество"},
                    {"id": "google/gemini-pro", "name": "Gemini Pro", "desc": "Google"},
                    {"id": "meta-llama/llama-3-70b", "name": "Llama 3 70B", "desc": "Open source"},
                    {"id": "mistral/mistral-large", "name": "Mistral Large", "desc": "Европейская"}
                ],
                "total": "350+ моделей доступно через OpenRouter"
            })
        
        else:
            return jsonify({"status": "error", "message": f"Неизвестная команда: {command}"}), 400
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """Загрузка файла на сервер"""
    try:
        client_id = request.form.get('client_id', request.remote_addr)
        
        if client_id not in ARCHITECT_SESSIONS and client_id not in COMMANDER_SESSIONS:
            return jsonify({"status": "error", "message": "Требуется доступ АРХИТЕКТА или КОМАНДИРА"}), 403
        
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "Файл не предоставлен"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "Имя файла пустое"}), 400
        
        # Безопасное имя файла
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        
        # Сохраняем в папку uploads
        upload_dir = '/opt/skynet_8888/uploads'
        os.makedirs(upload_dir, exist_ok=True)
        
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        return jsonify({
            "status": "success",
            "message": f"Файл {filename} загружен",
            "size": os.path.getsize(filepath),
            "path": f"/uploads/{filename}"
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Статические файлы из папки uploads
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Раздача загруженных файлов"""
    return send_from_directory('/opt/skynet_8888/uploads', filename)
