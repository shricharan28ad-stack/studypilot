import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def db():
    path=os.getenv('STUDYPILOT_DB','backend/data/studypilot.db')
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path,timeout=30)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,expires REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS user_preferences(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS rate_limits(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,name TEXT NOT NULL,text TEXT NOT NULL,date TEXT NOT NULL,user_id TEXT REFERENCES users(id));
      CREATE TABLE IF NOT EXISTS kits(id TEXT PRIMARY KEY,document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS quizzes(id TEXT PRIMARY KEY,kit_id TEXT REFERENCES kits(id) ON DELETE CASCADE,retest INTEGER NOT NULL,payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,kit_id TEXT REFERENCES kits(id) ON DELETE CASCADE,payload TEXT NOT NULL);
    ''')
    if 'user_id' not in [r['name'] for r in conn.execute('PRAGMA table_info(documents)')]:
        conn.execute('ALTER TABLE documents ADD COLUMN user_id TEXT REFERENCES users(id)')
    conn.execute('CREATE INDEX IF NOT EXISTS documents_owner ON documents(user_id)')
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
