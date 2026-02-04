import sqlite3
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_name='family_notes.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Таблица семей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS families (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                family_code TEXT UNIQUE,
                family_name TEXT,
                color_theme TEXT DEFAULT '#4CAF50',
                created_at TIMESTAMP
            )
        ''')
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                family_id INTEGER,
                role TEXT DEFAULT 'member',
                avatar_color TEXT DEFAULT '#2196F3',
                FOREIGN KEY (family_id) REFERENCES families (id)
            )
        ''')
        
        # Таблица заметок (только общие)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                family_id INTEGER,
                title TEXT NOT NULL,
                content TEXT,
                note_date DATE NOT NULL,
                note_time TIME NOT NULL,
                reminder_minutes INTEGER DEFAULT 30,
                is_important BOOLEAN DEFAULT 0,
                color_tag TEXT DEFAULT '#FF9800',
                created_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (family_id) REFERENCES families (id)
            )
        ''')
        
        self.conn.commit()
    
    # Методы для работы с пользователями
    def add_user(self, user_id, username, full_name, family_id, role='member'):
        cursor = self.conn.cursor()
        # Генерируем цвет для аватара
        import hashlib
        colors = ['#2196F3', '#4CAF50', '#FF9800', '#F44336', '#9C27B0', '#00BCD4']
        color_index = hash(str(user_id)) % len(colors)
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, full_name, family_id, role, avatar_color)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, full_name, family_id, role, colors[color_index]))
        self.conn.commit()
    
    def get_user_family(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT u.family_id, f.family_name, u.role, u.avatar_color, f.color_theme
            FROM users u
            LEFT JOIN families f ON u.family_id = f.id
            WHERE u.user_id = ?
        ''', (user_id,))
        return cursor.fetchone()
    
    def get_family_members(self, family_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user_id, full_name, role, avatar_color 
            FROM users 
            WHERE family_id = ?
            ORDER BY role DESC, full_name
        ''', (family_id,))
        return cursor.fetchall()
    
    # Методы для работы с семьями
    def create_family(self, family_code, family_name):
        cursor = self.conn.cursor()
        # Генерируем случайный цвет для темы семьи
        import random
        colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#00BCD4', '#FF5722']
        
        cursor.execute('''
            INSERT INTO families (family_code, family_name, color_theme, created_at)
            VALUES (?, ?, ?, ?)
        ''', (family_code, family_name, random.choice(colors), datetime.now()))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_family_by_code(self, family_code):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, family_name, color_theme FROM families WHERE family_code = ?', (family_code,))
        return cursor.fetchone()
    # Методы для заметок
    def add_note(self, user_id, family_id, title, content, note_date, note_time, 
                 reminder_minutes=30, is_important=False, color_tag=None):
        cursor = self.conn.cursor()
        
        if not color_tag:
            colors = ['#FF9800', '#4CAF50', '#2196F3', '#9C27B0', '#FF5722']
            color_index = hash(f"{title}{datetime.now()}") % len(colors)
            color_tag = colors[color_index]
        
        cursor.execute('''
            INSERT INTO notes (user_id, family_id, title, content, note_date, note_time, 
                             reminder_minutes, is_important, color_tag, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, family_id, title, content, note_date, note_time, 
              reminder_minutes, is_important, color_tag, datetime.now()))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_family_notes(self, family_id, date=None, user_id=None):
        cursor = self.conn.cursor()
        
        query = '''
            SELECT n.*, u.full_name as author_name, u.avatar_color
            FROM notes n
            LEFT JOIN users u ON n.user_id = u.user_id
            WHERE n.family_id = ?
        '''
        params = [family_id]
        
        if date:
            query += ' AND n.note_date = ?'
            params.append(date)
        
        if user_id:
            query += ' AND n.user_id = ?'
            params.append(user_id)
        
        query += ' ORDER BY n.is_important DESC, n.note_date, n.note_time'
        
        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    
    def get_today_notes(self, family_id):
        cursor = self.conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT n.*, u.full_name as author_name, u.avatar_color
            FROM notes n
            LEFT JOIN users u ON n.user_id = u.user_id
            WHERE n.family_id = ? AND n.note_date = ?
            ORDER BY n.note_time
        ''', (family_id, today))
        return cursor.fetchall()
    
    def get_upcoming_notes(self, family_id, days=7):
        cursor = self.conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        future_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT n.*, u.full_name as author_name, u.avatar_color
            FROM notes n
            LEFT JOIN users u ON n.user_id = u.user_id
            WHERE n.family_id = ? 
            AND n.note_date BETWEEN ? AND ?
            ORDER BY n.note_date, n.note_time
        ''', (family_id, today, future_date))
        return cursor.fetchall()
    
    def get_month_notes(self, family_id, year, month):
        cursor = self.conn.cursor()
        start_date = f"{year}-{month:02d}-01"
        
        if month == 12:
            end_date = f"{year+1}-01-01"
        else:
            end_date = f"{year}-{month+1:02d}-01"
        
        cursor.execute('''
            SELECT n.*, u.full_name as author_name, u.avatar_color
            FROM notes n
            LEFT JOIN users u ON n.user_id = u.user_id
            WHERE n.family_id = ? 
            AND n.note_date >= ? AND n.note_date < ?
            ORDER BY n.note_date, n.note_time
        ''', (family_id, start_date, end_date))
        return cursor.fetchall()
    
    def delete_note(self, note_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, user_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def update_note_color(self, note_id, color):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE notes SET color_tag = ? WHERE id = ?', (color, note_id))
        self.conn.commit()
    
    def search_notes(self, family_id, search_text):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT n.*, u.full_name as author_name, u.avatar_color
            FROM notes nLEFT JOIN users u ON n.user_id = u.user_id
            WHERE n.family_id = ? 
            AND (n.title LIKE ? OR n.content LIKE ?)
            ORDER BY n.note_date, n.note_time
        ''', (family_id, f'%{search_text}%', f'%{search_text}%'))
        return cursor.fetchall()
    
    def get_notes_for_reminder(self):
        cursor = self.conn.cursor()
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M')
        
        cursor.execute('''
            SELECT n.*, u.user_id, u.full_name, f.family_name
            FROM notes n
            JOIN users u ON n.user_id = u.user_id
            JOIN families f ON n.family_id = f.id
            WHERE n.note_date = ? 
            AND TIME(n.note_time, '-'  n.reminder_minutes  ' minutes') <= TIME(?)
        ''', (current_date, current_time))
        return cursor.fetchall()