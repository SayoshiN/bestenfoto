import os
import json
import sqlite3
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
)
app.secret_key = 'bestenfoto-secret-key-2024'

# Config
DB_PATH     = os.path.join(BASE_DIR, 'data', 'bestenfoto.db')
PHOTOS_DIR  = os.path.join(BASE_DIR, 'static', 'photos')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ADMIN_PASSWORD = 'user228lol'

# Database
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email    TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS candidates (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            tagline  TEXT,
            photo    TEXT,
            created  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS votes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            voted_at     TEXT NOT NULL,
            UNIQUE(user_id),
            FOREIGN KEY(user_id)      REFERENCES users(id),
            FOREIGN KEY(candidate_id) REFERENCES candidates(id)
        );
    """)
    cur = conn.execute("SELECT COUNT(*) FROM candidates")
    if cur.fetchone()[0] == 0:
        now = datetime.now().isoformat()
        conn.execute("INSERT INTO candidates (name, tagline, photo, created) VALUES (?, ?, ?, ?)",
                     ("Анна", "Любит природу и закаты в двоем.", None, now))
        conn.execute("INSERT INTO candidates (name, tagline, photo, created) VALUES (?, ?, ?, ?)",
                     ("Даня", "Борец за справедливость!", None, now))
        conn.commit()
        
        # Add fake votes: left candidate (Anna, id=1) gets 350-450 votes
        # right candidate (Ivan, id=2) gets 200-280 votes
        import random
        anna_votes = random.randint(350, 450)
        ivan_votes = random.randint(200, 280)
        
        # Create fake users and votes for Anna (left/winner)
        for i in range(anna_votes):
            fake_user = f"user_anna_{i}"
            fake_email = f"anna{i}@fake.com"
            try:
                c = conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                                 (fake_user, fake_email, "fakepass"))
                user_id = c.lastrowid
                conn.execute("INSERT INTO votes (user_id, candidate_id, voted_at) VALUES (?, ?, ?)",
                             (user_id, 1, datetime.now().isoformat()))
            except:
                pass
        
        # Create fake users and votes for Ivan (right)
        for i in range(ivan_votes):
            fake_user = f"user_ivan_{i}"
            fake_email = f"ivan{i}@fake.com"
            try:
                c = conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                                 (fake_user, fake_email, "fakepass"))
                user_id = c.lastrowid
                conn.execute("INSERT INTO votes (user_id, candidate_id, voted_at) VALUES (?, ?, ?)",
                             (user_id, 2, datetime.now().isoformat()))
            except:
                pass
        
        print(f"  [INIT] Fake votes added: Anna={anna_votes}, Ivan={ivan_votes}", flush=True)
    
    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Для голосования необходимо зарегистрироваться', 'info')
            return redirect(url_for('register'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('admin') != True:
            flash('Доступ запрещен', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def log_event(event_type, details):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] [{event_type.upper():12}] {details}"
    print(line, flush=True)

def get_stats():
    conn = get_db()
    candidates = conn.execute("""
        SELECT c.*, COUNT(v.id) as vote_count
        FROM candidates c
        LEFT JOIN votes v ON v.candidate_id = c.id
        GROUP BY c.id
        ORDER BY vote_count DESC
    """).fetchall()
    total_votes = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return [dict(c) for c in candidates], total_votes, total_users

def get_all_users():
    conn = get_db()
    users = conn.execute("""
        SELECT u.id, u.username, u.email, u.password,
               (SELECT candidate_id FROM votes WHERE user_id = u.id) as voted_for,
               (SELECT c.name FROM votes v JOIN candidates c ON c.id = v.candidate_id WHERE v.user_id = u.id) as voted_for_name
        FROM users u
        ORDER BY u.id DESC
    """).fetchall()
    conn.close()
    return [dict(u) for u in users]

os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
init_db()

# Routes
@app.route('/')
def index():
    candidates, total_votes, total_users = get_stats()
    voted_for = None
    if 'user_id' in session:
        conn = get_db()
        row = conn.execute("SELECT candidate_id FROM votes WHERE user_id = ?",
                           (session['user_id'],)).fetchone()
        conn.close()
        if row:
            voted_for = row['candidate_id']
    return render_template('index.html',
                           candidates=candidates,
                           total_votes=total_votes,
                           total_users=total_users,
                           voted_for=voted_for)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email    = request.form['email'].strip()
        password = request.form['password']

        if not username or not email or not password:
            flash('Заполните все поля', 'error')
            return render_template('register.html')

        if len(password) < 4:
            flash('Пароль должен быть не менее 4 символов', 'error')
            return render_template('register.html')

        try:
            conn = get_db()
            conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                         (username, email, password))
            conn.commit()
            conn.close()
            log_event('REGISTER', f"New user: {username} ({email})")
            flash('Регистрация успешна! Войдите в аккаунт.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Имя пользователя или email уже занят', 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn     = get_db()
        user     = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user and user['password'] == password:
            session['user_id']  = user['id']
            session['username'] = user['username']
            log_event('LOGIN', f"User logged in: {username}")
            flash(f'Добро пожаловать, {username}!', 'success')
            return redirect(url_for('index'))
        flash('Неверное имя пользователя или пароль', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', '?')
    session.clear()
    log_event('LOGOUT', f"User logged out: {username}")
    return redirect(url_for('index'))

@app.route('/vote', methods=['POST'])
@login_required
def vote():
    candidate_id = request.form.get('candidate_id', type=int)
    if not candidate_id:
        flash('Выберите кандидата', 'error')
        return redirect(url_for('index'))

    conn = get_db()
    existing = conn.execute("SELECT id FROM votes WHERE user_id = ?",
                            (session['user_id'],)).fetchone()
    if existing:
        conn.close()
        flash('Вы уже проголосовали!', 'error')
        return redirect(url_for('index'))

    candidate = conn.execute("SELECT name FROM candidates WHERE id = ?",
                             (candidate_id,)).fetchone()
    if not candidate:
        conn.close()
        flash('Кандидат не найден', 'error')
        return redirect(url_for('index'))

    now = datetime.now().isoformat()
    conn.execute("INSERT INTO votes (user_id, candidate_id, voted_at) VALUES (?, ?, ?)",
                 (session['user_id'], candidate_id, now))
    conn.commit()
    conn.close()

    log_event('VOTE', f"User '{session['username']}' voted for '{candidate['name']}'")
    print_stats()
    flash(f'Вы проголосовали за {candidate["name"]}!', 'success')
    return redirect(url_for('index'))

@app.route('/stats')
def stats():
    candidates, total_votes, total_users = get_stats()
    conn = get_db()
    recent = conn.execute("""
        SELECT u.username, c.name as candidate_name, v.voted_at
        FROM votes v
        JOIN users u ON u.id = v.user_id
        JOIN candidates c ON c.id = v.candidate_id
        ORDER BY v.voted_at DESC
        LIMIT 20
    """).fetchall()
    conn.close()
    return render_template('stats.html',
                           candidates=candidates,
                           total_votes=total_votes,
                           total_users=total_users,
                           recent=[dict(r) for r in recent])

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'login':
            password = request.form.get('password', '')
            if password == ADMIN_PASSWORD:
                session['admin'] = True
                flash('Вход в админ-панель выполнен', 'success')
                return redirect(url_for('admin'))
            else:
                flash('Неверный пароль', 'error')
                return redirect(url_for('admin'))

        if action == 'logout':
            session.pop('admin', None)
            flash('Вы вышли из админ-панели', 'success')
            return redirect(url_for('admin'))

        if session.get('admin') != True:
            flash('Доступ запрещен', 'error')
            return redirect(url_for('admin'))

        if action == 'add_candidate':
            name    = request.form['name'].strip()
            tagline = request.form['tagline'].strip()
            photo   = None
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(PHOTOS_DIR, filename)
                    file.save(filepath)
                    photo = filename
                    log_event('PHOTO', f"Photo uploaded: {filename}")
            conn = get_db()
            conn.execute("INSERT INTO candidates (name, tagline, photo, created) VALUES (?, ?, ?, ?)",
                         (name, tagline, photo, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            log_event('ADMIN', f"New candidate added: {name}")
            flash(f'Кандидат {name} добавлен!', 'success')

        elif action == 'upload_photo':
            candidate_id = request.form.get('candidate_id', type=int)
            if 'photo' in request.files:
                file = request.files['photo']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(PHOTOS_DIR, filename)
                    file.save(filepath)
                    conn = get_db()
                    conn.execute("UPDATE candidates SET photo = ? WHERE id = ?",
                                 (filename, candidate_id))
                    conn.commit()
                    conn.close()
                    log_event('PHOTO', f"Updated photo for candidate #{candidate_id}: {filename}")
                    flash('Фото обновлено!', 'success')

        elif action == 'delete_candidate':
            candidate_id = request.form.get('candidate_id', type=int)
            conn = get_db()
            name = conn.execute("SELECT name FROM candidates WHERE id=?", (candidate_id,)).fetchone()
            conn.execute("DELETE FROM votes WHERE candidate_id = ?", (candidate_id,))
            conn.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
            conn.commit()
            conn.close()
            if name:
                log_event('ADMIN', f"Deleted candidate: {name['name']}")
            flash('Кандидат удален', 'success')

        elif action == 'reset_votes':
            conn = get_db()
            conn.execute("DELETE FROM votes")
            conn.commit()
            conn.close()
            log_event('ADMIN', "All votes reset")
            flash('Все голоса сброшены!', 'success')

        return redirect(url_for('admin'))

    candidates, total_votes, total_users = get_stats()
    photos = os.listdir(PHOTOS_DIR) if os.path.exists(PHOTOS_DIR) else []
    is_admin = session.get('admin') == True
    users_list = get_all_users() if is_admin else []
    return render_template('admin.html',
                           candidates=candidates,
                           total_votes=total_votes,
                           total_users=total_users,
                           photos=photos,
                           is_admin=is_admin,
                           users=users_list)

def print_stats():
    candidates, total_votes, total_users = get_stats()
    print("\n" + "="*50, flush=True)
    print("  BESTENFOTO - STATISTIKA GOLOSOVANIYA", flush=True)
    print("="*50, flush=True)
    for c in candidates:
        pct = round(c['vote_count'] / total_votes * 100) if total_votes else 0
        bar = '#' * (pct // 5) + '-' * (20 - pct // 5)
        print(f"  {c['name']:15} {bar} {pct}%  ({c['vote_count']} gol.)", flush=True)
    print(f"  Vsego golosov: {total_votes}  |  Polzovateley: {total_users}", flush=True)
    print("="*50 + "\n", flush=True)

if __name__ == '__main__':
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)
    init_db()
    print("\n" + "="*50, flush=True)
    print("  BESTENFOTO - SERVER ZAPUSHCHEN", flush=True)
    print("  Foto papka: static/photos/", flush=True)
    print("  Baza dannykh: data/bestenfoto.db", flush=True)
    print("  Adres: http://localhost:5000", flush=True)
    print("="*50 + "\n", flush=True)
    app.run(debug=False, host='0.0.0.0', port=5000)
