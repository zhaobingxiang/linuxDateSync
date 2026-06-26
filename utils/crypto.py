import hashlib
import base64
import os
from cryptography.fernet import Fernet


def get_machine_key():
    """基于机器信息生成加密密钥"""
    try:
        import uuid
        machine_id = str(uuid.getnode())
    except Exception:
        machine_id = "datesync_default_key"
    
    key_material = hashlib.sha256(machine_id.encode()).digest()
    return base64.urlsafe_b64encode(key_material[:32])


def encrypt_password(password):
    """加密密码"""
    if not password:
        return ""
    try:
        key = get_machine_key()
        cipher = Fernet(key)
        encrypted = cipher.encrypt(password.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    except Exception:
        return password


def decrypt_password(encrypted_password):
    """解密密码"""
    if not encrypted_password:
        return ""
    try:
        key = get_machine_key()
        cipher = Fernet(key)
        decoded = base64.urlsafe_b64decode(encrypted_password.encode('utf-8'))
        decrypted = cipher.decrypt(decoded)
        return decrypted.decode('utf-8')
    except Exception:
        return encrypted_password
