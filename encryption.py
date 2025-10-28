# [FILE: encryption.py]
# [VERSION: 1.0.0.69.1]
# [DATE: 2025-08-12]
# [PROJECT: HKKM - Yuzu Companion]
# [DESCRIPTION: AES-256 encryption for data security]
# [AUTHOR: Project Lead: Bani Baskara]
# [TEAM: Deepseek, GPT, Qwen, Aihara]
# [REPOSITORY: https://guthib.com/icedeyes12]
# [LICENSE: MIT]

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64
import os
import json
import sys

class AES256Encryptor:
    def __init__(self, key_path="encryption.key"):
        self.key_path = key_path
        self.key = self._load_or_generate_key()
    
    def _load_or_generate_key(self):
        if os.path.exists(self.key_path):
            print(f"Loading encryption key from {self.key_path}")
            with open(self.key_path, 'rb') as f:
                key = f.read()
            if len(key) != 32:
                raise ValueError(f"Invalid key length in key file: {len(key)} bytes (expected 32)")
            return key
        else:
            print("Generating new encryption key...")
            key = get_random_bytes(32)
            with open(self.key_path, 'wb') as f:
                f.write(key)
            print(f"New key saved to {self.key_path}")
            print(f"Key fingerprint: {key.hex()[:16]}...")
            print("BACKUP THIS KEY FILE IMMEDIATELY!")
            print("Run: python key_manager.py --backup")
            return key
    
    def encrypt(self, plaintext):
        if not plaintext or not plaintext.strip():
            return plaintext
            
        try:
            iv = get_random_bytes(16)
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            padded_data = pad(plaintext.encode('utf-8'), AES.block_size)
            encrypted_data = cipher.encrypt(padded_data)
            combined = iv + encrypted_data
            return base64.b64encode(combined).decode('utf-8')
        except Exception as e:
            print(f"Encryption failed for text '{plaintext[:50]}...': {e}")
            return plaintext
    
    def decrypt(self, encrypted_text):
        if not encrypted_text or not encrypted_text.strip():
            return encrypted_text
            
        if len(encrypted_text) < 24 or ' ' in encrypted_text:
            return encrypted_text
            
        try:
            combined = base64.b64decode(encrypted_text)
            if len(combined) < 16:
                return encrypted_text
                
            iv = combined[:16]
            encrypted_data = combined[16:]
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            decrypted_padded = cipher.decrypt(encrypted_data)
            decrypted_data = unpad(decrypted_padded, AES.block_size)
            return decrypted_data.decode('utf-8')
        except Exception as e:
            return encrypted_text
    
    def backup_key(self, backup_path="backup_encryption.key"):
        if not os.path.exists(self.key_path):
            print("No encryption key found to backup")
            return False
        
        try:
            with open(self.key_path, 'rb') as source:
                with open(backup_path, 'wb') as target:
                    target.write(source.read())
            print(f"Key backed up to {backup_path}")
            return True
        except Exception as e:
            print(f"Backup failed: {e}")
            return False

    def restore_key(self, backup_path="backup_encryption.key"):
        if not os.path.exists(backup_path):
            print("Backup key not found")
            return False
        
        try:
            with open(backup_path, 'rb') as source:
                with open(self.key_path, 'wb') as target:
                    target.write(source.read())
            print("Key restored from backup")
            self.key = self._load_or_generate_key()
            return True
        except Exception as e:
            print(f"Restore failed: {e}")
            return False
    
    def get_key_info(self):
        if not os.path.exists(self.key_path):
            return {"status": "no_key", "message": "No encryption key found"}
        
        with open(self.key_path, 'rb') as f:
            key = f.read()
        
        return {
            "status": "loaded",
            "key_size": len(key),
            "key_fingerprint": key.hex()[:16] + "...",
            "key_path": os.path.abspath(self.key_path)
        }

encryptor = AES256Encryptor()

if __name__ == "__main__":
    test_text = "Hello, World! This is a test message."
    print("Testing encryption system...")
    
    encrypted = encryptor.encrypt(test_text)
    decrypted = encryptor.decrypt(encrypted)
    
    print(f"Original: {test_text}")
    print(f"Encrypted: {encrypted[:50]}...")
    print(f"Decrypted: {decrypted}")
    
    if test_text == decrypted:
        print("Encryption test PASSED!")
    else:
        print("Encryption test FAILED!")
        sys.exit(1)
