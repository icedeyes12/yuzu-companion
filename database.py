# [FILE: database.py]
# [VERSION: 1.0.0.69.1]
# [DATE: 2025-08-12]
# [PROJECT: HKKM - Yuzu Companion]
# [DESCRIPTION: Database management with encrypted storage]
# [AUTHOR: Project Lead: Bani Baskara]
# [TEAM: Deepseek, GPT, Qwen, Aihara]
# [REPOSITORY: https://guthib.com/icedeyes12]
# [LICENSE: MIT]

import sqlite3
import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from contextlib import contextmanager
from encryption import encryptor

def get_db_path():
    return os.path.join(os.path.dirname(__file__), 'yuzu_core.db')

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(stored_password, provided_password):
    return stored_password == hashlib.sha256(provided_password.encode('utf-8')).hexdigest()

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL DEFAULT 'bani',
                partner_name TEXT NOT NULL DEFAULT 'Yuzu',
                affection INTEGER NOT NULL DEFAULT 85,
                theme TEXT NOT NULL DEFAULT 'default',
                memory_json TEXT NOT NULL DEFAULT '{}',
                session_history_json TEXT NOT NULL DEFAULT '{}',
                global_knowledge_json TEXT NOT NULL DEFAULT '{}',
                providers_config_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT 'New Chat',
                is_active BOOLEAN NOT NULL DEFAULT 0,
                message_count INTEGER NOT NULL DEFAULT 0,
                memory_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                content_encrypted BOOLEAN NOT NULL DEFAULT 0,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT NOT NULL DEFAULT 'openrouter',
                key_value TEXT NOT NULL,
                key_encrypted BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(key_name)
            )
        ''')
        
        cursor.execute('SELECT COUNT(*) FROM profiles')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO profiles (display_name, partner_name, affection, providers_config_json)
                VALUES (?, ?, ?, ?)
            ''', ('user', 'Yuzu', 50, json.dumps({
                'preferred_provider': 'ollama',
                'preferred_model': 'glm-4.6:cloud',
                'providers': {
                    'ollama': {'enabled': True, 'base_url': 'http://127.0.0.1:11434'},
                    'cerebras': {'enabled': True},
                    'openrouter': {'enabled': True}
                }
            })))
            
            cursor.execute('''
                INSERT INTO chat_sessions (name, is_active)
                VALUES (?, ?)
            ''', ('New Chat', 1))
            
            ce_key_path = 'ce.key'
            if os.path.exists(ce_key_path):
                try:
                    with open(ce_key_path, 'r') as f:
                        cerebras_key = f.read().strip()
                    if cerebras_key:
                        encrypted_key = Database._encrypt_api_key(cerebras_key)
                        cursor.execute('''
                            INSERT INTO api_keys (key_name, key_value, key_encrypted)
                            VALUES (?, ?, ?)
                        ''', ('cerebras', encrypted_key, 1))
                        print("Migrated Cerebras key from ce.key to encrypted database")
                        os.rename(ce_key_path, f"{ce_key_path}.backup")
                        print("Renamed ce.key to ce.key.backup for safety")
                except Exception as e:
                    print(f"Failed to migrate ce.key: {e}")
        
        conn.commit()

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

class Database:
    @staticmethod
    def _encrypt_content(content):
        try:
            return encryptor.encrypt(content)
        except Exception as e:
            print(f"Encryption failed: {e}")
            return content

    @staticmethod
    def _decrypt_content(content, is_encrypted):
        if not is_encrypted:
            return content
        
        try:
            return encryptor.decrypt(content)
        except Exception as e:
            print(f"Decryption failed: {e}")
            return "[DECRYPTION_ERROR]"
    
    @staticmethod
    def _encrypt_api_key(key_value):
        try:
            return encryptor.encrypt(key_value)
        except Exception as e:
            print(f"API key encryption failed: {e}")
            return key_value
    
    @staticmethod
    def _decrypt_api_key(key_value, is_encrypted):
        if not is_encrypted:
            return key_value
        
        try:
            return encryptor.decrypt(key_value)
        except Exception as e:
            print(f"API key decryption failed: {e}")
            return "[DECRYPTION_ERROR]"

    @staticmethod
    def get_profile():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM profiles LIMIT 1')
            row = cursor.fetchone()
            if row:
                profile = dict(row)
                profile['memory'] = json.loads(profile['memory_json'])
                profile['session_history'] = json.loads(profile['session_history_json'])
                profile['global_knowledge'] = json.loads(profile.get('global_knowledge_json', '{}'))
                profile['providers_config'] = json.loads(profile.get('providers_config_json', '{}'))
                return profile
            return None

    @staticmethod
    def update_profile(updates):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            json_updates = {}
            regular_updates = {}
            
            for key, value in updates.items():
                if key in ['memory', 'session_history', 'global_knowledge', 'providers_config']:
                    json_updates[f"{key}_json"] = json.dumps(value)
                else:
                    regular_updates[key] = value
            
            all_updates = {**regular_updates, **json_updates}
            set_clause = ', '.join([f"{key} = ?" for key in all_updates.keys()])
            values = list(all_updates.values())
            
            cursor.execute(f'''
                UPDATE profiles 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP 
            ''', values)
            conn.commit()

    @staticmethod
    def get_api_keys(key_name=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if key_name:
                cursor.execute('SELECT key_name, key_value, key_encrypted FROM api_keys WHERE key_name = ?', (key_name,))
            else:
                cursor.execute('SELECT key_name, key_value, key_encrypted FROM api_keys ORDER BY created_at')
            
            decrypted_keys = {}
            for row in cursor.fetchall():
                key_name = row['key_name']
                key_value = row['key_value']
                is_encrypted = row['key_encrypted']
                
                if is_encrypted:
                    decrypted_key = Database._decrypt_api_key(key_value, is_encrypted)
                    if decrypted_key != "[DECRYPTION_ERROR]":
                        decrypted_keys[key_name] = decrypted_key
                else:
                    decrypted_keys[key_name] = key_value
            
            return decrypted_keys

    @staticmethod
    def get_api_key(key_name):
        keys = Database.get_api_keys(key_name)
        return keys.get(key_name)

    @staticmethod
    def add_api_key(key_name, key_value):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            encrypted_key = Database._encrypt_api_key(key_value)
            is_encrypted = 1 if encrypted_key != key_value else 0
            
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO api_keys (key_name, key_value, key_encrypted) 
                    VALUES (?, ?, ?)
                ''', (key_name, encrypted_key, is_encrypted))
                conn.commit()
                print(f"Encrypted and saved {key_name} API key")
                return True
            except sqlite3.IntegrityError as e:
                print(f"Failed to save API key: {e}")
                return False

    @staticmethod
    def remove_api_key(key_name):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM api_keys WHERE key_name = ?', (key_name,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def create_session(name="New Chat"):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO chat_sessions (name, is_active, created_at, updated_at)
                VALUES (?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (name,))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_active_session():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM chat_sessions WHERE is_active = 1 LIMIT 1')
            row = cursor.fetchone()
            if row:
                session = dict(row)
                session['memory'] = json.loads(session.get('memory_json', '{}'))
                return session
            
            cursor.execute('''
                INSERT INTO chat_sessions (name, is_active)
                VALUES (?, 1)
            ''', ('New Chat',))
            conn.commit()
            session_id = cursor.lastrowid
            
            cursor.execute('SELECT * FROM chat_sessions WHERE id = ?', (session_id,))
            session = dict(cursor.fetchone())
            session['memory'] = json.loads(session.get('memory_json', '{}'))
            return session

    @staticmethod
    def get_all_sessions():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.*, COUNT(m.id) as message_count
                FROM chat_sessions s
                LEFT JOIN messages m ON s.id = m.session_id AND m.role IN ('user', 'assistant')
                GROUP BY s.id
                ORDER BY s.updated_at DESC
            ''')
            sessions = []
            for row in cursor.fetchall():
                session = dict(row)
                session['memory'] = json.loads(session.get('memory_json', '{}'))
                sessions.append(session)
            return sessions

    @staticmethod
    def switch_session(session_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('UPDATE chat_sessions SET is_active = 0')
            
            cursor.execute('UPDATE chat_sessions SET is_active = 1 WHERE id = ?', (session_id,))
            conn.commit()
            return True

    @staticmethod
    def rename_session(session_id, new_name):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE chat_sessions 
                SET name = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (new_name, session_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_session(session_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT is_active FROM chat_sessions WHERE id = ?', (session_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            was_active = row['is_active']
            
            cursor.execute('DELETE FROM chat_sessions WHERE id = ?', (session_id,))
            
            if was_active:
                cursor.execute('SELECT id FROM chat_sessions ORDER BY updated_at DESC LIMIT 1')
                row = cursor.fetchone()
                if row:
                    cursor.execute('UPDATE chat_sessions SET is_active = 1 WHERE id = ?', (row['id'],))
                else:
                    cursor.execute('''
                        INSERT INTO chat_sessions (name, is_active)
                        VALUES (?, 1)
                    ''', ('New Chat',))
            
            conn.commit()
            return True

    @staticmethod
    def get_session_memory(session_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT memory_json FROM chat_sessions WHERE id = ?', (session_id,))
            row = cursor.fetchone()
            if row and row['memory_json']:
                try:
                    return json.loads(row['memory_json'])
                except json.JSONDecodeError:
                    print(f"Invalid JSON in session {session_id} memory")
                    return {}
            return {}

    @staticmethod
    def update_session_memory(session_id, memory_data):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE chat_sessions 
                SET memory_json = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (json.dumps(memory_data), session_id))
            conn.commit()
            print(f"Updated memory for session {session_id}")

    @staticmethod
    def add_message(role, content, session_id=None):
        if session_id is None:
            active_session = Database.get_active_session()
            session_id = active_session['id']
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if role in ['user', 'assistant']:
                encrypted_content = Database._encrypt_content(content)
                is_encrypted = 1
                print(f"Encrypted {role} message for session {session_id}")
            else:
                encrypted_content = content
                is_encrypted = 0
            
            cursor.execute('''
                INSERT INTO messages (session_id, role, content, content_encrypted, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, role, encrypted_content, is_encrypted, local_time))
            
            if role in ['user', 'assistant']:
                cursor.execute('''
                    UPDATE chat_sessions 
                    SET message_count = message_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (session_id,))
            else:
                cursor.execute('''
                    UPDATE chat_sessions 
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (session_id,))
            
            conn.commit()
            print(f"Saved {role} message to session {session_id} at: {local_time}")

    @staticmethod
    def get_chat_history(session_id=None, limit=None, recent=False):
        if session_id is None:
            active_session = Database.get_active_session()
            session_id = active_session['id']
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT role, content, content_encrypted, timestamp 
                FROM messages 
                WHERE session_id = ?
            '''
            params = [session_id]
            
            if recent and limit:
                query += ' ORDER BY timestamp DESC LIMIT ?'
                params.append(limit)
                cursor.execute(query, params)
                messages = [dict(row) for row in cursor.fetchall()]
                messages = list(reversed(messages))
            elif limit:
                query += ' ORDER BY timestamp ASC LIMIT ?'
                params.append(limit)
                cursor.execute(query, params)
            else:
                query += ' ORDER BY timestamp ASC'
                cursor.execute(query, params)
            
            decrypted_messages = []
            for msg in cursor.fetchall():
                msg_dict = dict(msg)
                if msg_dict.get('content_encrypted', 0):
                    msg_dict['content'] = Database._decrypt_content(
                        msg_dict['content'], 
                        msg_dict['content_encrypted']
                    )
                decrypted_messages.append(msg_dict)
            
            return decrypted_messages

    @staticmethod
    def get_chat_history_for_ai(session_id=None, limit=None, recent=False):
        if session_id is None:
            active_session = Database.get_active_session()
            session_id = active_session['id']
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT role, content, content_encrypted, timestamp 
                FROM messages 
                WHERE session_id = ?
            '''
            params = [session_id]
            
            if recent and limit:
                query += ' ORDER BY timestamp DESC LIMIT ?'
                params.append(limit)
                cursor.execute(query, params)
                messages = [dict(row) for row in cursor.fetchall()]
                messages = list(reversed(messages))
            elif limit:
                query += ' ORDER BY timestamp ASC LIMIT ?'
                params.append(limit)
                cursor.execute(query, params)
                messages = [dict(row) for row in cursor.fetchall()]
            else:
                query += ' ORDER BY timestamp ASC'
                cursor.execute(query, params)
                messages = [dict(row) for row in cursor.fetchall()]
            
            formatted_messages = []
            for msg in messages:
                content = msg['content']
                if msg.get('content_encrypted', 0):
                    content = Database._decrypt_content(content, msg['content_encrypted'])
                
                try:
                    dt = datetime.strptime(msg['timestamp'], '%Y-%m-%d %H:%M:%S')
                    formatted_timestamp = dt.strftime('[%Y-%m-%d %H:%M:%S]')
                except:
                    formatted_timestamp = f"[{msg['timestamp']}]"
                
                if msg['role'] == 'user':
                    ai_formatted_content = f"{content} {formatted_timestamp}"
                else:
                    ai_formatted_content = f"{content}"
                
                formatted_messages.append({
                    'role': msg['role'],
                    'content': ai_formatted_content,
                    'original_content': content,
                    'timestamp': msg['timestamp']
                })
            
            return formatted_messages

    @staticmethod
    def clear_chat_history(session_id=None):
        if session_id is None:
            active_session = Database.get_active_session()
            session_id = active_session['id']
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM messages WHERE session_id = ?', (session_id,))
            cursor.execute('''
                UPDATE chat_sessions 
                SET message_count = 0, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (session_id,))
            conn.commit()

    @staticmethod
    def add_session_event(content, interface="terminal"):
        active_session = Database.get_active_session()
        session_id = active_session['id']
        
        event_content = f"*{content} on {interface}*"
        Database.add_message('system', event_content, session_id)

    @staticmethod
    def get_recent_sessions(limit=20):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT content, content_encrypted, timestamp 
                FROM messages 
                WHERE role = 'system' AND content LIKE '*%'
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            events = []
            for row in cursor.fetchall():
                event = dict(row)
                if event.get('content_encrypted', 0):
                    event['content'] = Database._decrypt_content(event['content'], event['content_encrypted'])
                events.append(event)
            
            return events

    @staticmethod
    def get_recent_sessions_for_session(session_id, limit=20):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT content, content_encrypted, timestamp 
                FROM messages 
                WHERE role = 'system' 
                AND session_id = ? 
                AND content LIKE '*%'
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (session_id, limit))
            
            events = []
            for row in cursor.fetchall():
                event = dict(row)
                if event.get('content_encrypted', 0):
                    event['content'] = Database._decrypt_content(event['content'], event['content_encrypted'])
                events.append(event)
            
            return events

    @staticmethod
    def get_session_messages_count(session_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count 
                FROM messages 
                WHERE session_id = ? 
                AND role IN ('user', 'assistant')
            ''', (session_id,))
            return cursor.fetchone()['count']

    @staticmethod
    def get_session_conversation_summary(session_id, limit=20):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT role, content, content_encrypted 
                FROM messages 
                WHERE session_id = ? 
                AND role IN ('user', 'assistant')
                ORDER BY timestamp ASC 
                LIMIT ?
            ''', (session_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                msg = dict(row)
                if msg.get('content_encrypted', 0):
                    msg['content'] = Database._decrypt_content(msg['content'], msg['content_encrypted'])
                messages.append(msg)
            
            summary_parts = []
            for msg in messages:
                role_label = "User" if msg['role'] == 'user' else "AI"
                content = msg['content'][:100]
                if len(msg['content']) > 100:
                    content += "..."
                summary_parts.append(f"{role_label}: {content}")
            
            return "\n".join(summary_parts)

    @staticmethod
    def get_encryption_status():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN content_encrypted = 1 THEN 1 ELSE 0 END) as encrypted_messages,
                    SUM(CASE WHEN role IN ('user', 'assistant') AND content_encrypted = 0 THEN 1 ELSE 0 END) as unencrypted_conversation
                FROM messages
            ''')
            msg_stats = dict(cursor.fetchone())
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_keys,
                    SUM(CASE WHEN key_encrypted = 1 THEN 1 ELSE 0 END) as encrypted_keys
                FROM api_keys
            ''')
            key_stats = dict(cursor.fetchone())
            
            return {
                'messages': msg_stats,
                'api_keys': key_stats,
                'encryption_available': True
            }

init_db()
