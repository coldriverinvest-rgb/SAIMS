import re
import sqlite3
from datetime import datetime
from pathlib import Path
from backend.config import ALERT_DATABASE_PATH

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def _connect():
    path=Path(ALERT_DATABASE_PATH); path.parent.mkdir(parents=True,exist_ok=True)
    connection=sqlite3.connect(path,timeout=10); connection.row_factory=sqlite3.Row; return connection

def initialize_database():
    with _connect() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS notification_recipients (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          chat_id TEXT, email TEXT, enabled INTEGER NOT NULL DEFAULT 1,
          telegram_enabled INTEGER NOT NULL DEFAULT 1, email_enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_chat ON notification_recipients(chat_id) WHERE chat_id IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_email ON notification_recipients(email) WHERE email IS NOT NULL;
        CREATE TABLE IF NOT EXISTS notification_deliveries (
          recipient_id INTEGER NOT NULL, rcept_no TEXT NOT NULL, channel TEXT NOT NULL,
          sent_at TEXT NOT NULL, PRIMARY KEY(recipient_id,rcept_no,channel));
        """)
        old=connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='telegram_recipients'").fetchone()
        if old:
            connection.execute("""INSERT OR IGNORE INTO notification_recipients(id,name,chat_id,email,enabled,telegram_enabled,email_enabled,created_at)
              SELECT id,name,NULLIF(chat_id,''),NULL,enabled,1,0,created_at FROM telegram_recipients""")
        old_deliveries=connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alert_deliveries'").fetchone()
        if old_deliveries:
            connection.execute("""INSERT OR IGNORE INTO notification_deliveries(recipient_id,rcept_no,channel,sent_at)
              SELECT recipient_id,rcept_no,'telegram',sent_at FROM alert_deliveries""")

def _item(row):
    if not row:return None
    item=dict(row)
    for key in ('enabled','telegram_enabled','email_enabled'): item[key]=bool(item[key])
    return item

def list_recipients(enabled_only=False):
    initialize_database(); query="SELECT * FROM notification_recipients"
    if enabled_only: query+=" WHERE enabled=1 AND ((telegram_enabled=1 AND chat_id IS NOT NULL) OR (email_enabled=1 AND email IS NOT NULL))"
    query+=" ORDER BY id DESC"
    with _connect() as connection:return [_item(row) for row in connection.execute(query)]

def _normalize(chat_id='',email=''):
    chat=(chat_id or '').strip() or None; mail=(email or '').strip().lower() or None
    if not chat and not mail: raise ValueError('Telegram Chat ID 또는 이메일 주소를 하나 이상 입력해 주세요.')
    if mail and not EMAIL_PATTERN.fullmatch(mail): raise ValueError('올바른 이메일 주소를 입력해 주세요.')
    return chat,mail

def add_recipient(name,chat_id='',email='',telegram_enabled=True,email_enabled=True):
    initialize_database(); chat,mail=_normalize(chat_id,email)
    with _connect() as connection:
        cursor=connection.execute("INSERT INTO notification_recipients(name,chat_id,email,enabled,telegram_enabled,email_enabled,created_at) VALUES(?,?,?,1,?,?,?)",(name.strip(),chat,mail,int(bool(telegram_enabled and chat)),int(bool(email_enabled and mail)),datetime.now().isoformat(timespec='seconds')))
        return _item(connection.execute("SELECT * FROM notification_recipients WHERE id=?",(cursor.lastrowid,)).fetchone())

def update_recipient(recipient_id,name=None,enabled=None,chat_id=None,email=None,telegram_enabled=None,email_enabled=None):
    initialize_database(); fields=[];values=[]
    if name is not None: fields.append('name=?');values.append(name.strip())
    if enabled is not None: fields.append('enabled=?');values.append(int(enabled))
    if chat_id is not None: fields.append('chat_id=?');values.append(chat_id.strip() or None)
    if email is not None:
        mail=email.strip().lower() or None
        if mail and not EMAIL_PATTERN.fullmatch(mail): raise ValueError('올바른 이메일 주소를 입력해 주세요.')
        fields.append('email=?');values.append(mail)
    if telegram_enabled is not None: fields.append('telegram_enabled=?');values.append(int(telegram_enabled))
    if email_enabled is not None: fields.append('email_enabled=?');values.append(int(email_enabled))
    if not fields:return next((x for x in list_recipients() if x['id']==recipient_id),None)
    values.append(recipient_id)
    with _connect() as connection:
        connection.execute(f"UPDATE notification_recipients SET {', '.join(fields)} WHERE id=?",values)
        row=connection.execute("SELECT * FROM notification_recipients WHERE id=?",(recipient_id,)).fetchone()
        if row and not row['chat_id'] and not row['email']: raise ValueError('알림 채널을 하나 이상 유지해 주세요.')
        return _item(row)

def delete_recipient(recipient_id):
    initialize_database()
    with _connect() as connection:
        connection.execute('DELETE FROM notification_deliveries WHERE recipient_id=?',(recipient_id,))
        return connection.execute('DELETE FROM notification_recipients WHERE id=?',(recipient_id,)).rowcount>0

def was_delivered(recipient_id,rcept_no,channel):
    with _connect() as connection:return connection.execute('SELECT 1 FROM notification_deliveries WHERE recipient_id=? AND rcept_no=? AND channel=?',(recipient_id,rcept_no,channel)).fetchone() is not None

def mark_delivered(recipient_id,rcept_no,channel):
    with _connect() as connection:connection.execute('INSERT OR IGNORE INTO notification_deliveries VALUES(?,?,?,?)',(recipient_id,rcept_no,channel,datetime.now().isoformat(timespec='seconds')))
