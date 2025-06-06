# client.py
import streamlit as st
import requests
import json
from streamlit_option_menu import option_menu
import streamlit.components.v1 as components
import base64
from pathlib import Path
import re

# Налаштування сторінки
st.set_page_config(
    page_title="EduPlatform | Навчальна платформа",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Кольорова схема з вашого зображення
COLORS = {
    'primary': '#626D71',      # Грифель
    'secondary': '#CDCDC0',    # Керамик
    'accent': '#DDBC95',       # Латте
    'coffee': '#B38867',       # Кофе
    'white': '#FFFFFF',
    'black': '#000000'
}

# CSS стилі з анімаціями та градієнтами
st.markdown(f"""
<style>
    /* Основні стилі */
    .stApp {{
        background: linear-gradient(135deg, {COLORS['secondary']} 0%, {COLORS['white']} 100%);
    }}
    
    /* Анімована кнопка */
    .stButton > button {{
        background: linear-gradient(45deg, {COLORS['primary']}, {COLORS['coffee']});
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 25px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }}
    
    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        background: linear-gradient(45deg, {COLORS['coffee']}, {COLORS['primary']});
    }}
    
    /* Карточки з анімацією */
    .css-card {{
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        border: 1px solid {COLORS['secondary']};
    }}
    
    .css-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }}
    
    /* Прогрес бар */
    .stProgress > div > div > div > div {{
        background: linear-gradient(90deg, {COLORS['accent']}, {COLORS['coffee']});
    }}
    
    /* Заголовки */
    h1, h2, h3 {{
        color: {COLORS['primary']};
    }}
    
    /* Анімація появи */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    .fade-in {{
        animation: fadeIn 0.5s ease-out;
    }}
    
    /* Таби навігації */
    .nav-link {{
        color: {COLORS['primary']} !important;
        transition: all 0.3s ease;
    }}
    
    .nav-link:hover {{
        color: {COLORS['coffee']} !important;
        transform: translateX(5px);
    }}
    
    .nav-link.active {{
        background: linear-gradient(90deg, {COLORS['accent']}, {COLORS['coffee']}) !important;
        color: white !important;
    }}
    
    /* Відео контейнер */
    .video-container {{
        position: relative;
        padding-bottom: 56.25%;
        height: 0;
        overflow: hidden;
        max-width: 100%;
        background: #000;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }}
    
    .video-container iframe {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border-radius: 15px;
    }}
</style>
""", unsafe_allow_html=True)

# Ініціалізація стану сесії
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'survey_step' not in st.session_state:
    st.session_state.survey_step = 0
if 'survey_answers' not in st.session_state:
    st.session_state.survey_answers = {}
if 'recommendations' not in st.session_state:
    st.session_state.recommendations = None

API_URL = "http://127.0.0.1:8080"

# Питання анкети
SURVEY_QUESTIONS = [
    # Базова інформація
    {"question": "Ваше ім'я:", "type": "text", "key": "name"},
    {"question": "Ваш вік:", "type": "number", "key": "age", "min_value": 16, "max_value": 100},
    {"question": "Ваша поточна професія або сфера діяльності:", "type": "text", "key": "profession"},
    {"question": "Ваш рівень освіти:", "type": "selectbox", "key": "education",
     "options": ["Середня освіта", "Неповна вища", "Бакалавр", "Магістр", "Кандидат наук", "Доктор наук"]},
    
    # Цілі навчання
    {"question": "Яка ваша основна мета навчання?", "type": "radio", "key": "goal",
     "options": ["Зміна кар'єри", "Підвищення кваліфікації", "Особистий розвиток", "Отримання нових навичок", "Підготовка до іспитів"]},
    {"question": "Яку сферу ви хочете вивчати?", "type": "selectbox", "key": "field",
     "options": ["Програмування", "Дизайн", "Маркетинг", "Бізнес", "Мови", "Наука", "Мистецтво", "Інше"]},
    
    # Досвід та навички
    {"question": "Який ваш рівень у вибраній сфері?", "type": "radio", "key": "level",
     "options": ["Початківець", "Базовий рівень", "Середній рівень", "Просунутий", "Експерт"]},
    {"question": "Які у вас є попередні знання або досвід?", "type": "text_area", "key": "experience"},
    
    # Преференції навчання
    {"question": "Який формат навчання ви переважаєте?", "type": "multiselect", "key": "format",
     "options": ["Відео-лекції", "Текстові матеріали", "Інтерактивні вправи", "Проєктна робота", "Індивідуальні заняття", "Групові заняття"]},
    {"question": "Скільки годин на тиждень ви можете приділяти навчанню?", "type": "slider", "key": "hours",
     "min_value": 1, "max_value": 40, "value": 10},
    
    # Бюджет та обмеження
    {"question": "Який ваш бюджет на навчання (грн/місяць)?", "type": "number", "key": "budget", "min_value": 0},
    {"question": "Чи є у вас часові обмеження для завершення навчання?", "type": "text", "key": "deadline"},
    
    # Додаткова інформація
    {"question": "Чи маєте ви якісь особливі потреби або обмеження?", "type": "text_area", "key": "special_needs"},
    {"question": "Які мови ви володієте?", "type": "multiselect", "key": "languages",
     "options": ["Українська", "Англійська", "Російська", "Німецька", "Французька", "Іспанська", "Інша"]},
    {"question": "Що вас найбільше мотивує в навчанні?", "type": "text_area", "key": "motivation"},
    
    # Додаткові 15 питань для детальнішого профілю
    {"question": "Який ваш стиль навчання?", "type": "radio", "key": "learning_style",
     "options": ["Візуальний", "Аудіальний", "Кінестетичний", "Читання/письмо"]},
    {"question": "В який час доби ви найбільш продуктивні?", "type": "radio", "key": "productive_time",
     "options": ["Ранок", "День", "Вечір", "Ніч"]},
    {"question": "Чи маєте ви досвід онлайн-навчання?", "type": "radio", "key": "online_experience",
     "options": ["Так, багато", "Трохи", "Ні, не маю"]},
    {"question": "Які сертифікати або дипломи ви хотіли б отримати?", "type": "text", "key": "certifications"},
    {"question": "Чи готові ви працювати з ментором?", "type": "radio", "key": "mentor",
     "options": ["Так", "Ні", "Можливо"]},
    {"question": "Які soft skills ви хочете розвинути?", "type": "multiselect", "key": "soft_skills",
     "options": ["Комунікація", "Лідерство", "Тайм-менеджмент", "Креативність", "Критичне мислення"]},
    {"question": "Який досвід роботи в команді ви маєте?", "type": "selectbox", "key": "team_experience",
     "options": ["Великий досвід", "Середній досвід", "Мінімальний досвід", "Без досвіду"]},
    {"question": "Які технічні навички ви вже маєте?", "type": "text_area", "key": "technical_skills"},
    {"question": "Чи є у вас проекти, які ви хотіли б реалізувати?", "type": "text_area", "key": "projects"},
    {"question": "Який тип кар'єри вас цікавить?", "type": "radio", "key": "career_type",
     "options": ["Корпоративна", "Фріланс", "Підприємництво", "Наукова", "Творча"]},
    {"question": "Чи готові ви до закордонних стажувань?", "type": "radio", "key": "internship_abroad",
     "options": ["Так", "Ні", "Можливо"]},
    {"question": "Який рівень англійської мови у вас?", "type": "selectbox", "key": "english_level",
     "options": ["A1", "A2", "B1", "B2", "C1", "C2", "Native"]},
    {"question": "Чи є у вас досвід публічних виступів?", "type": "radio", "key": "public_speaking",
     "options": ["Так, багато", "Трохи", "Ні"]},
    {"question": "Які галузі вам найбільш цікаві?", "type": "multiselect", "key": "industries",
     "options": ["IT", "Фінанси", "Медицина", "Освіта", "Медіа", "Виробництво", "Сільське господарство"]},
    {"question": "Який у вас досвід роботи з даними?", "type": "selectbox", "key": "data_experience",
     "options": ["Експерт", "Просунутий", "Базовий", "Початківець", "Без досвіду"]}
]

# Сайдбар навігація
with st.sidebar:
    if st.session_state.token:
        selected = option_menu(
            menu_title="EduPlatform",
            options=["Головна", "Профіль", "Анкета", "Рекомендації", "Відео", "Бібліотека", "Налаштування"],
            icons=["house", "person", "card-checklist", "star", "play-circle", "book", "gear"],
            menu_icon="mortarboard",
            default_index=0,
            styles={
                "container": {"padding": "5px", "background-color": COLORS['white']},
                "icon": {"color": COLORS['primary'], "font-size": "18px"},
                "nav-link": {
                    "font-size": "16px",
                    "text-align": "left",
                    "margin": "5px",
                    "--hover-color": COLORS['secondary']
                },
                "nav-link-selected": {"background-color": COLORS['accent']},
            }
        )
        
        if st.button("Вийти", key="logout"):
            st.session_state.token = None
            st.session_state.user_id = None
            st.rerun()
    else:
        st.title("EduPlatform")
        st.markdown("### Увійдіть або зареєструйтесь")

# Функція для відображення відео YouTube
def display_youtube_video(video_id):
    video_html = f"""
    <div class="video-container">
        <iframe src="https://www.youtube.com/embed/{video_id}" 
        frameborder="0" allow="accelerometer; autoplay; clipboard-write; 
        encrypted-media; gyroscope; picture-in-picture" allowfullscreen>
        </iframe>
    </div>
    """
    st.markdown(video_html, unsafe_allow_html=True)

# Сторінка входу/реєстрації
def auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="fade-in">', unsafe_allow_html=True)
        st.title("🎓 EduPlatform")
        st.markdown("### Ваш персональний навчальний асистент")
        
        tab1, tab2 = st.tabs(["Вхід", "Реєстрація"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="your@email.com")
                password = st.text_input("Пароль", type="password")
                submit = st.form_submit_button("Увійти")
                
                if submit:
                    response = requests.post(
                        f"{API_URL}/login",
                        json={"email": email, "password": password}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.token = data['access_token']
                        st.session_state.user_id = data['user_id']
                        st.success("Успішний вхід!")
                        st.rerun()
                    else:
                        st.error("Невірний email або пароль")
        
        with tab2:
            with st.form("register_form"):
                name = st.text_input("Ім'я", placeholder="Ваше ім'я")
                email = st.text_input("Email", placeholder="your@email.com", key="reg_email")
                password = st.text_input("Пароль", type="password", key="reg_password")
                password2 = st.text_input("Підтвердіть пароль", type="password")
                submit = st.form_submit_button("Зареєструватись")
                
                if submit:
                    if password != password2:
                        st.error("Паролі не співпадають")
                    else:
                        response = requests.post(
                            f"{API_URL}/register",
                            json={"name": name, "email": email, "password": password}
                        )
                        
                        if response.status_code == 201:
                            data = response.json()
                            st.session_state.token = data['access_token']
                            st.session_state.user_id = data['user_id']
                            st.success("Реєстрація успішна!")
                            st.rerun()
                        else:
                            st.error("Email вже використовується")
        
        st.markdown('</div>', unsafe_allow_html=True)

# Головна сторінка
def home_page():
    st.title("🏠 Головна")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="css-card fade-in">
            <h3>📚 Персоналізоване навчання</h3>
            <p>Отримайте рекомендації, які ідеально підходять саме вам</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="css-card fade-in" style="animation-delay: 0.1s">
            <h3>🎯 Досягайте цілей</h3>
            <p>Покроковий план для досягнення ваших освітніх цілей</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="css-card fade-in" style="animation-delay: 0.2s">
            <h3>🚀 Розвивайтесь</h3>
            <p>Постійно вдосконалюйте свої навички та знання</p>
        </div>
        """, unsafe_allow_html=True)

# Сторінка профілю
def profile_page():
    st.title("👤 Профіль")
    
    # Отримання даних профілю
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    response = requests.get(f"{API_URL}/get_profile", headers=headers)
    
    profile_data = {}
    if response.status_code == 200:
        profile_data = response.json().get('profile_data', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div class="css-card">
            <h3>Основна інформація</h3>
            <p><strong>Ім'я:</strong> {profile_data.get('name', 'Не вказано')}</p>
            <p><strong>Email:</strong> {profile_data.get('email', 'Не вказано')}</p>
            <p><strong>Вік:</strong> {profile_data.get('age', 'Не вказано')}</p>
            <p><strong>Професія:</strong> {profile_data.get('profession', 'Не вказано')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="css-card">
            <h3>Навчальні преференції</h3>
            <p><strong>Мета:</strong> {profile_data.get('goal', 'Не вказано')}</p>
            <p><strong>Сфера:</strong> {profile_data.get('field', 'Не вказано')}</p>
            <p><strong>Рівень:</strong> {profile_data.get('level', 'Не вказано')}</p>
            <p><strong>Години на тиждень:</strong> {profile_data.get('hours', 'Не вказано')}</p>
        </div>
        """, unsafe_allow_html=True)

# Функція для відображення питання
def display_question(q, idx):
    st.markdown(f"**Питання {idx + 1} з {len(SURVEY_QUESTIONS)}**")
    
    if q["type"] == "text":
        return st.text_input(q["question"], key=f"{q['key']}_{idx}")
    elif q["type"] == "text_area":
        return st.text_area(q["question"], key=f"{q['key']}_{idx}")
    elif q["type"] == "number":
        return st.number_input(q["question"], min_value=q.get("min_value", 0), 
                             max_value=q.get("max_value", 100), key=f"{q['key']}_{idx}")
    elif q["type"] == "selectbox":
        return st.selectbox(q["question"], q["options"], key=f"{q['key']}_{idx}")
    elif q["type"] == "multiselect":
        return st.multiselect(q["question"], q["options"], key=f"{q['key']}_{idx}")
    elif q["type"] == "radio":
        return st.radio(q["question"], q["options"], key=f"{q['key']}_{idx}")
    elif q["type"] == "slider":
        return st.slider(q["question"], min_value=q["min_value"], 
                        max_value=q["max_value"], value=q.get("value", q["min_value"]), 
                        key=f"{q['key']}_{idx}")

# Сторінка анкети
def survey_page():
    st.title("📝 Анкета")
    
    # Прогрес бар
    progress = st.progress(st.session_state.survey_step / len(SURVEY_QUESTIONS))
    st.markdown(f"Прогрес: {st.session_state.survey_step}/{len(SURVEY_QUESTIONS)}")
    
    if st.session_state.survey_step < len(SURVEY_QUESTIONS):
        current_question = SURVEY_QUESTIONS[st.session_state.survey_step]
        answer = display_question(current_question, st.session_state.survey_step)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.session_state.survey_step > 0:
                if st.button("← Назад"):
                    st.session_state.survey_step -= 1
                    st.rerun()
        
        with col3:
            if st.button("Далі →"):
                if answer or answer == 0:  # Щоб дозволити 0 як відповідь
                    st.session_state.survey_answers[current_question["key"]] = answer
                    st.session_state.survey_step += 1
                    st.rerun()
                else:
                    st.warning("Будь ласка, дайте відповідь на питання")
    else:
        st.success("Анкету заповнено! Обробляємо ваші відповіді...")
        
        # Збереження профілю
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.post(
            f"{API_URL}/save_profile",
            json={"profile_data": st.session_state.survey_answers},
            headers=headers
        )
        
        if response.status_code == 200:
            st.success("Профіль збережено!")
            
            # Отримання рекомендацій
            if st.button("Отримати рекомендації"):
                with st.spinner("Генеруємо персоналізовані рекомендації..."):
                    rec_response = requests.post(
                        f"{API_URL}/get_recommendations",
                        headers=headers
                    )
                    
                    if rec_response.status_code == 200:
                        st.session_state.recommendations = rec_response.json()['recommendation']
                        st.success("Рекомендації готові! Перейдіть на вкладку 'Рекомендації'")
                    else:
                        st.error("Помилка при отриманні рекомендацій")
        
        if st.button("Пройти анкету заново"):
            st.session_state.survey_step = 0
            st.session_state.survey_answers = {}
            st.rerun()

# Сторінка рекомендацій
def recommendations_page():
    st.title("⭐ Рекомендації")
    
    if st.session_state.recommendations:
        st.markdown(st.session_state.recommendations)
    else:
        st.info("Спочатку заповніть анкету, щоб отримати персоналізовані рекомендації")
        
        if st.button("Перейти до анкети"):
            st.session_state.page = 'survey'
            st.rerun()

# Допоміжна функція для витягування YouTube ID
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

# Сторінка відео
def video_page():
    st.title("🎥 Навчальні відео")
    
    # Вкладки для управління відео
    tab1, tab2 = st.tabs(["Перегляд відео", "Додати відео"])
    
    with tab1:
        # Отримуємо список відео
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.get(f"{API_URL}/get_videos", headers=headers)
        
        if response.status_code == 200:
            videos = response.json().get('videos', [])
            
            # Групуємо відео по категоріях
            categories = list(set([video['category'] for video in videos]))
            selected_category = st.selectbox("Оберіть категорію", ["Всі"] + categories)
            
            # Фільтруємо відео по категорії
            if selected_category != "Всі":
                filtered_videos = [v for v in videos if v['category'] == selected_category]
            else:
                filtered_videos = videos
            
            # Відображаємо відео
            for video in filtered_videos:
                with st.expander(f"📹 {video['title']}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        if video['source'] == 'youtube' and video['url']:
                            youtube_id = extract_youtube_id(video['url'])
                            if youtube_id:
                                display_youtube_video(youtube_id)
                        elif video['source'] == 'external' and video['url']:
                            st.markdown(f"🔗 [Переглянути відео за посиланням]({video['url']})")
                        
                        st.markdown(f"**Опис:** {video['description']}")
                        st.markdown(f"**Тривалість:** {video['duration']}")
                        st.markdown(f"**Категорія:** {video['category']}")
                        st.markdown(f"**Джерело:** {video['source']}")
                    
                    with col2:
                        if st.button("🗑️ Видалити", key=f"del_video_{video['id']}"):
                            del_response = requests.delete(
                                f"{API_URL}/delete_video/{video['id']}", 
                                headers=headers
                            )
                            if del_response.status_code == 200:
                                st.success("Відео видалено!")
                                st.rerun()
                            else:
                                st.error("Помилка при видаленні відео")
        else:
            st.error("Помилка при завантаженні відео")
    
    with tab2:
        st.subheader("Додати нове відео")
        
        video_source = st.radio("Джерело відео", ["YouTube URL", "Інше посилання на відео", "Завантажити файл"])
        
        if video_source == "YouTube URL":
            video_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
            video_title = st.text_input("Назва відео (необов'язково, буде взято з YouTube)")
            video_description = st.text_area("Опис відео")
            video_category = st.text_input("Категорія", value="Програмування")
            
            if st.button("Додати відео"):
                if video_url:
                    video_data = {
                        'url': video_url,
                        'title': video_title,
                        'description': video_description,
                        'category': video_category,
                        'source': 'youtube'
                    }
                    
                    response = requests.post(
                        f"{API_URL}/add_video",
                        json=video_data,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        st.success("Відео успішно додано!")
                        st.rerun()
                    else:
                        st.error("Помилка при додаванні відео")
                else:
                    st.warning("Введіть URL відео")
        
        elif video_source == "Інше посилання на відео":
            video_url = st.text_input("URL відео", placeholder="https://example.com/video.mp4")
            video_title = st.text_input("Назва відео")
            video_description = st.text_area("Опис відео")
            video_category = st.text_input("Категорія", value="Програмування")
            video_duration = st.text_input("Тривалість (наприклад: 15:30)")
            
            if st.button("Додати відео"):
                if video_url and video_title:
                    video_data = {
                        'url': video_url,
                        'title': video_title,
                        'description': video_description,
                        'category': video_category,
                        'duration': video_duration,
                        'source': 'external'
                    }
                    
                    response = requests.post(
                        f"{API_URL}/add_video",
                        json=video_data,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        st.success("Відео успішно додано!")
                        st.rerun()
                    else:
                        st.error("Помилка при додаванні відео")
                else:
                    st.warning("Введіть URL та назву відео")
        
        else:
            st.info("Функція завантаження відео файлів буде додана найближчим часом")
            st.markdown("Поки що ви можете додавати відео за посиланнями з YouTube або інших джерел")

# Сторінка бібліотеки
def library_page():
    st.title("📚 Бібліотека")
    
    # Вкладки для управління книгами
    tab1, tab2 = st.tabs(["Перегляд книг", "Додати книгу"])
    
    with tab1:
        # Отримуємо список книг
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.get(f"{API_URL}/get_books", headers=headers)
        
        if response.status_code == 200:
            books = response.json().get('books', [])
            
            # Групуємо книги по категоріях
            categories = list(set([book['category'] for book in books]))
            selected_category = st.selectbox("Оберіть категорію", ["Всі"] + categories)
            
            # Фільтруємо книги по категорії
            if selected_category != "Всі":
                filtered_books = [b for b in books if b['category'] == selected_category]
            else:
                filtered_books = books
            
            # Відображаємо книги в сітці
            cols = st.columns(3)
            for idx, book in enumerate(filtered_books):
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div class="css-card">
                        <img src="{book['cover_url'] or 'https://via.placeholder.com/200x300'}" 
                             style="width: 100%; height: 300px; object-fit: cover; border-radius: 10px;">
                        <h4>{book['title']}</h4>
                        <p><strong>Автор:</strong> {book['author']}</p>
                        <p>{book['description'][:100]}...</p>
                        <p><strong>Формат:</strong> {book['file_type']}</p>
                        <p><strong>Розмір:</strong> {book['file_size'] / 1024 / 1024:.1f} MB</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if book['file_path']:
                            download_url = f"{API_URL}/download_book/{book['id']}"
                            if st.button("⬇️ Завантажити", key=f"download_{book['id']}"):
                                with st.spinner("Завантаження..."):
                                    download_response = requests.get(
                                        download_url,
                                        headers=headers,
                                        stream=True
                                    )
                                    if download_response.status_code == 200:
                                        st.download_button(
                                            label="💾 Зберегти файл",
                                            data=download_response.content,
                                            file_name=f"{book['title']}{book['file_type']}",
                                            mime="application/octet-stream"
                                        )
                                    else:
                                        st.error("Помилка при завантаженні")
                        elif book.get('external_url'):
                            st.markdown(f"🔗 [Читати онлайн]({book['external_url']})")
                    
                    with col2:
                        if st.button("🗑️ Видалити", key=f"delete_{book['id']}"):
                            del_response = requests.delete(
                                f"{API_URL}/delete_book/{book['id']}", 
                                headers=headers
                            )
                            if del_response.status_code == 200:
                                st.success("Книгу видалено!")
                                st.rerun()
                            else:
                                st.error("Помилка при видаленні книги")
        else:
            st.error("Помилка при завантаженні бібліотеки")
    
    with tab2:
        st.subheader("Додати нову книгу")
        
        book_source = st.radio("Спосіб додавання", ["Завантажити файл", "Додати посилання на книгу"])
        
        if book_source == "Завантажити файл":
            book_file = st.file_uploader(
                "Виберіть файл книги", 
                type=['pdf', 'epub', 'mobi', 'txt', 'doc', 'docx']
            )
            book_title = st.text_input("Назва книги")
            book_author = st.text_input("Автор")
            book_description = st.text_area("Опис книги")
            book_category = st.text_input("Категорія", value="Програмування")
            book_cover_url = st.text_input("URL обкладинки (необов'язково)")
            
            if st.button("Завантажити книгу"):
                if book_file and book_title:
                    files = {
                        'file': (book_file.name, book_file, book_file.type)
                    }
                    data = {
                        'title': book_title,
                        'author': book_author,
                        'description': book_description,
                        'category': book_category,
                        'cover_url': book_cover_url
                    }
                    
                    with st.spinner("Завантаження книги..."):
                        response = requests.post(
                            f"{API_URL}/add_book",
                            files=files,
                            data=data,
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            st.success("Книга успішно додана!")
                            st.rerun()
                        else:
                            st.error("Помилка при додаванні книги")
                else:
                    st.warning("Виберіть файл та введіть назву книги")
        
        else:  # Додати посилання на книгу
            book_url = st.text_input("URL книги", placeholder="https://example.com/book.pdf")
            book_title = st.text_input("Назва книги")
            book_author = st.text_input("Автор")
            book_description = st.text_area("Опис книги")
            book_category = st.text_input("Категорія", value="Програмування")
            book_cover_url = st.text_input("URL обкладинки (необов'язково)")
            book_file_type = st.selectbox("Формат книги", ['.pdf', '.epub', '.mobi', '.txt', '.doc', '.docx', 'онлайн'])
            
            if st.button("Додати книгу"):
                if book_url and book_title:
                    data = {
                        'external_url': book_url,
                        'title': book_title,
                        'author': book_author,
                        'description': book_description,
                        'category': book_category,
                        'cover_url': book_cover_url,
                        'file_type': book_file_type
                    }
                    
                    response = requests.post(
                        f"{API_URL}/add_book_by_url",
                        json=data,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        st.success("Книга успішно додана!")
                        st.rerun()
                    else:
                        st.error("Помилка при додаванні книги")
                else:
                    st.warning("Введіть URL та назву книги")

# Головний роутинг
if not st.session_state.token:
    auth_page()
else:
    if selected == "Головна":
        home_page()
    elif selected == "Профіль":
        profile_page()
    elif selected == "Анкета":
        survey_page()
    elif selected == "Рекомендації":
        recommendations_page()
    elif selected == "Відео":
        video_page()
    elif selected == "Бібліотека":
        library_page()
    elif selected == "Налаштування":
        st.title("⚙️ Налаштування")
        st.write("Сторінка налаштувань")
