# server.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
import sqlite3
import google.generativeai as genai
import os
from datetime import datetime, timedelta
import json
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import requests
import urllib.parse
import re
from pytube import YouTube
import io

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your-secret-key-change-this'  
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB максимальний розмір файлу

# Створюємо папки для завантажень
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'books'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)

CORS(app, resources={r"/*": {"origins": "*"}})
jwt = JWTManager(app)

genai.configure(api_key='AIzaSyDCM06eLezuNhQp3vyYBjHkvknkeoTZErY')
model = genai.GenerativeModel('gemini-1.5-flash')

def adapt_datetime(ts):
    return ts.strftime("%Y-%m-%d %H:%M:%S")

sqlite3.register_adapter(datetime, adapt_datetime)

# Розширена ініціалізація бази даних
def init_db():
    conn = sqlite3.connect('education.db')
    c = conn.cursor()
    
    # Існуючі таблиці...
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            created_at TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            profile_data TEXT,
            last_updated TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            recommendation TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Нові таблиці для відео та книг
    c.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            url TEXT,
            source TEXT,
            category TEXT,
            description TEXT,
            file_path TEXT,
            thumbnail TEXT,
            duration TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            author TEXT,
            description TEXT,
            category TEXT,
            file_path TEXT,
            cover_url TEXT,
            file_type TEXT,
            file_size INTEGER,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Функція для витягування ID відео з URL YouTube
def extract_youtube_id(url):
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^?]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^?]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        name = data.get('name', '')
        
        hashed_password = generate_password_hash(password)
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO users (email, password, name, created_at)
            VALUES (?, ?, ?, ?)
        ''', (email, hashed_password, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        
        access_token = create_access_token(identity=str(user_id))
        
        return jsonify({
            'status': 'success',
            'access_token': access_token,
            'user_id': user_id
        }), 201
        
    except sqlite3.IntegrityError:
        return jsonify({
            'status': 'error',
            'message': 'Email вже існує'
        }), 400
    except Exception as e:
        print(f"Помилка реєстрації: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('SELECT id, password FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            access_token = create_access_token(identity=str(user[0]))
            return jsonify({
                'status': 'success',
                'access_token': access_token,
                'user_id': user[0]
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Невірні дані для входу'
            }), 401
            
    except Exception as e:
        print(f"Помилка входу: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/get_profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        user_id = get_jwt_identity()
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('SELECT name, email FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        
        c.execute('SELECT profile_data FROM profiles WHERE user_id = ?', (user_id,))
        profile = c.fetchone()
        
        conn.close()
        
        result = {}
        if user:
            result['name'] = user[0]
            result['email'] = user[1]
        
        if profile and profile[0]:
            try:
                profile_data = json.loads(profile[0])
                result.update(profile_data)
            except:
                pass
        
        return jsonify({
            'status': 'success',
            'profile_data': result
        })
        
    except Exception as e:
        print(f"Помилка отримання профілю: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/save_profile', methods=['POST'])
@jwt_required()
def save_profile():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        print(f"Отримані дані: {data}")  # Для відладки
        
        if not data or 'profile_data' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Дані профілю не надані'
            }), 400
        
        profile_data = json.dumps(data['profile_data'])
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('SELECT id FROM profiles WHERE user_id = ?', (user_id,))
        existing = c.fetchone()
        
        if existing:
            c.execute('''
                UPDATE profiles 
                SET profile_data = ?, last_updated = ?
                WHERE user_id = ?
            ''', (profile_data, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        else:
            c.execute('''
                INSERT INTO profiles (user_id, profile_data, last_updated)
                VALUES (?, ?, ?)
            ''', (user_id, profile_data, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        print(f"Помилка збереження профілю: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def create_detailed_prompt(profile_data):
    profile = json.loads(profile_data)
    
    prompt = f"""
    Ти - експертний консультант з навчання та професійного розвитку. Проаналізуй детальний профіль користувача та надай персоналізовані рекомендації щодо навчання.

    ДЕТАЛЬНИЙ ПРОФІЛЬ КОРИСТУВАЧА:
    
    Особиста інформація:
    - Ім'я: {profile.get('name', 'Не вказано')}
    - Вік: {profile.get('age', 'Не вказано')}
    - Освіта: {profile.get('education', 'Не вказано')}
    - Професія: {profile.get('profession', 'Не вказано')}
    
    Цілі та мотивація:
    - Основна мета: {profile.get('goal', 'Не вказано')}
    - Бажана сфера: {profile.get('field', 'Не вказано')}
    - Мотивація: {profile.get('motivation', 'Не вказано')}
    
    Досвід та навички:
    - Поточний рівень: {profile.get('level', 'Не вказано')}
    - Попередній досвід: {profile.get('experience', 'Не вказано')}
    - Мови: {', '.join(profile.get('languages', ['Не вказано']))}
    - Рівень англійської: {profile.get('english_level', 'Не вказано')}
    - Технічні навички: {profile.get('technical_skills', 'Не вказано')}
    
    Преференції навчання:
    - Формати: {', '.join(profile.get('format', ['Не вказано']))}
    - Час на навчання: {profile.get('hours', 'Не вказано')} годин/тиждень
    - Бюджет: {profile.get('budget', 'Не вказано')} грн/місяць
    - Стиль навчання: {profile.get('learning_style', 'Не вказано')}
    - Продуктивний час: {profile.get('productive_time', 'Не вказано')}
    
    Кар'єрні плани:
    - Тип кар'єри: {profile.get('career_type', 'Не вказано')}
    - Проекти: {profile.get('projects', 'Не вказано')}
    - Індустрії: {', '.join(profile.get('industries', ['Не вказано']))}
    
    Надай ДЕТАЛЬНІ рекомендації українською мовою:

    1. РЕКОМЕНДОВАНИЙ КУРС/ПРОГРАМА
    - Конкретна назва курсу
    - Платформа
    - Тривалість
    - Вартість
    - Чому підходить

    2. НАВЧАЛЬНІ ВІДЕО (5-7 штук)
    - Назва
    - Канал/Автор
    - Посилання на YouTube
    - Тривалість
    - Опис

    3. РЕКОМЕНДОВАНА ЛІТЕРАТУРА (5-7 книг)
    - Назва
    - Автор
    - Рік
    - Мова
    - Де знайти

    4. ПОКРОКОВИЙ ПЛАН НАВЧАННЯ
    - По тижнях/місяцях
    - Конкретні завдання
    - Контрольні точки

    5. КОРИСНІ РЕСУРСИ
    - Онлайн-спільноти
    - Вебсайти
    - Форуми
    - Практичні проекти

    6. ПОРАДИ ДЛЯ УСПІХУ
    - Як мотивувати себе
    - Як вимірювати прогрес
    - Типові помилки початківців

    Використовуй markdown для форматування.
    """
    return prompt

@app.route('/get_recommendations', methods=['POST'])
@jwt_required()
def get_recommendations():
    try:
        user_id = get_jwt_identity()
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('SELECT profile_data FROM profiles WHERE user_id = ?', (user_id,))
        profile = c.fetchone()
        
        if not profile or not profile[0]:
            return jsonify({
                'status': 'error',
                'message': 'Профіль не знайдено'
            }), 404
        
        prompt = create_detailed_prompt(profile[0])
        response = model.generate_content(prompt)
        recommendation = response.text
        
        c.execute('''
            INSERT INTO recommendations (user_id, recommendation, created_at)
            VALUES (?, ?, ?)
        ''', (user_id, recommendation, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'recommendation': recommendation
        })
        
    except Exception as e:
        print(f"Помилка отримання рекомендацій: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/add_video', methods=['POST'])
@jwt_required()
def add_video():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        title = data.get('title')
        url = data.get('url')
        category = data.get('category', 'Загальне')
        description = data.get('description', '')
        source = data.get('source', 'youtube')
        
        thumbnail = ''
        duration = ''
        youtube_id = None
        
        if source == 'youtube' and url:
            youtube_id = extract_youtube_id(url)
            if youtube_id:
                thumbnail = f"https://img.youtube.com/vi/{youtube_id}/hqdefault.jpg"
                try:
                    yt = YouTube(url)
                    duration = str(timedelta(seconds=yt.length))
                    if not title:
                        title = yt.title
                    if not description:
                        description = yt.description[:500]
                except:
                    pass
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO videos (user_id, title, url, source, category, description, 
                              thumbnail, duration, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, title, url, source, category, description, 
              thumbnail, duration, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        video_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'video_id': video_id,
            'youtube_id': youtube_id
        })
        
    except Exception as e:
        print(f"Помилка додавання відео: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/get_videos', methods=['GET'])
@jwt_required()
def get_videos():
    try:
        user_id = get_jwt_identity()
        category = request.args.get('category', None)
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        if category:
            c.execute('''
                SELECT id, title, url, source, category, description, 
                       thumbnail, duration, created_at
                FROM videos 
                WHERE (user_id = ? OR user_id IS NULL) AND category = ?
                ORDER BY created_at DESC
            ''', (user_id, category))
        else:
            c.execute('''
                SELECT id, title, url, source, category, description, 
                       thumbnail, duration, created_at
                FROM videos 
                WHERE user_id = ? OR user_id IS NULL
                ORDER BY created_at DESC
            ''', (user_id,))
        
        videos = []
        for row in c.fetchall():
            videos.append({
                'id': row[0],
                'title': row[1],
                'url': row[2],
                'source': row[3],
                'category': row[4],
                'description': row[5],
                'thumbnail': row[6],
                'duration': row[7],
                'created_at': row[8]
            })
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'videos': videos
        })
        
    except Exception as e:
        print(f"Помилка отримання відео: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/add_book', methods=['POST'])
@jwt_required()
def add_book():
    try:
        user_id = get_jwt_identity()
        
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'Файл не наданий'
            }), 400
        
        file = request.files['file']
        title = request.form.get('title', file.filename)
        author = request.form.get('author', '')
        description = request.form.get('description', '')
        category = request.form.get('category', 'Загальне')
        cover_url = request.form.get('cover_url', '')
        
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'Файл не обраний'
            }), 400
        
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        allowed_extensions = {'.pdf', '.epub', '.mobi', '.txt', '.doc', '.docx'}
        if file_ext not in allowed_extensions:
            return jsonify({
                'status': 'error',
                'message': 'Тип файлу не дозволений'
            }), 400
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'books', safe_filename)
        file.save(file_path)
        
        file_size = os.path.getsize(file_path)
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO books (user_id, title, author, description, category, 
                             file_path, cover_url, file_type, file_size, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, title, author, description, category, 
              file_path, cover_url, file_ext, file_size,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        book_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'book_id': book_id
        })
        
    except Exception as e:
        print(f"Помилка додавання книги: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/get_books', methods=['GET'])
@jwt_required()
def get_books():
    try:
        user_id = get_jwt_identity()
        category = request.args.get('category', None)
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        if category:
            c.execute('''
                SELECT id, title, author, description, category, 
                       file_path, cover_url, file_type, file_size, created_at
                FROM books 
                WHERE (user_id = ? OR user_id IS NULL) AND category = ?
                ORDER BY created_at DESC
            ''', (user_id, category))
        else:
            c.execute('''
                SELECT id, title, author, description, category, 
                       file_path, cover_url, file_type, file_size, created_at
                FROM books 
                WHERE user_id = ? OR user_id IS NULL
                ORDER BY created_at DESC
            ''', (user_id,))
        
        books = []
        for row in c.fetchall():
            books.append({
                'id': row[0],
                'title': row[1],
                'author': row[2],
                'description': row[3],
                'category': row[4],
                'file_path': row[5],
                'cover_url': row[6],
                'file_type': row[7],
                'file_size': row[8],
                'created_at': row[9]
            })
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'books': books
        })
        
    except Exception as e:
        print(f"Помилка отримання книг: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/download_book/<int:book_id>', methods=['GET'])
@jwt_required()
def download_book(book_id):
    try:
        user_id = get_jwt_identity()
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT title, file_path, file_type 
            FROM books 
            WHERE id = ? AND (user_id = ? OR user_id IS NULL)
        ''', (book_id, user_id))
        
        book = c.fetchone()
        conn.close()
        
        if not book:
            return jsonify({
                'status': 'error',
                'message': 'Книга не знайдена'
            }), 404
        
        title, file_path, file_type = book
        
        if not os.path.exists(file_path):
            return jsonify({
                'status': 'error',
                'message': 'Файл не знайдено'
            }), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"{title}{file_type}"
        )
        
    except Exception as e:
        print(f"Помилка завантаження книги: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/delete_video/<int:video_id>', methods=['DELETE'])
@jwt_required()
def delete_video(video_id):
    try:
        user_id = get_jwt_identity()
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('SELECT file_path FROM videos WHERE id = ? AND user_id = ?', (video_id, user_id))
        video = c.fetchone()
        
        if not video:
            return jsonify({
                'status': 'error',
                'message': 'Відео не знайдено або доступ заборонено'
            }), 404
        
        if video[0] and os.path.exists(video[0]):
            os.remove(video[0])
        
        c.execute('DELETE FROM videos WHERE id = ? AND user_id = ?', (video_id, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        print(f"Помилка видалення відео: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/add_book_by_url', methods=['POST'])
@jwt_required()
def add_book_by_url():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        title = data.get('title')
        author = data.get('author', '')
        description = data.get('description', '')
        category = data.get('category', 'Загальне')
        cover_url = data.get('cover_url', '')
        external_url = data.get('external_url')
        file_type = data.get('file_type', 'онлайн')
        
        if not title or not external_url:
            return jsonify({
                'status': 'error',
                'message': 'Назва та URL обов\'язкові'
            }), 400
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        # Модифицируем таблицу books для поддержки внешних URL
        c.execute('''
            ALTER TABLE books ADD COLUMN external_url TEXT
        ''')
        
        c.execute('''
            INSERT INTO books (user_id, title, author, description, category, 
                             external_url, cover_url, file_type, file_size, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, title, author, description, category, 
              external_url, cover_url, file_type, 0,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        book_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'book_id': book_id
        })
        
    except Exception as e:
        print(f"Помилка додавання книги за URL: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/delete_book/<int:book_id>', methods=['DELETE'])
@jwt_required()
def delete_book(book_id):
    try:
        user_id = get_jwt_identity()
        
        conn = sqlite3.connect('education.db')
        c = conn.cursor()
        
        c.execute('SELECT file_path FROM books WHERE id = ? AND user_id = ?', (book_id, user_id))
        book = c.fetchone()
        
        if not book:
            return jsonify({
                'status': 'error',
                'message': 'Книга не знайдена або доступ заборонено'
            }), 404
        
        if book[0] and os.path.exists(book[0]):
            os.remove(book[0])
        
        c.execute('DELETE FROM books WHERE id = ? AND user_id = ?', (book_id, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        print(f"Помилка видалення книги: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=8080)
