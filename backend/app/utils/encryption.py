import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.core.config import settings
import json


def get_encryption_key() -> bytes:
    """Derive encryption key from SECRET_KEY."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'micro-drama-saas-salt',  # In production, use a random salt stored securely
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
    return key


_cipher_suite = None


def get_cipher():
    global _cipher_suite
    if _cipher_suite is None:
        _cipher_suite = Fernet(get_encryption_key())
    return _cipher_suite


def encrypt_data(data: dict) -> str:
    """Encrypt dictionary data to string."""
    cipher = get_cipher()
    json_data = json.dumps(data)
    encrypted = cipher.encrypt(json_data.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_data(encrypted_str: str) -> dict:
    """Decrypt string back to dictionary."""
    cipher = get_cipher()
    encrypted = base64.urlsafe_b64decode(encrypted_str.encode())
    decrypted = cipher.decrypt(encrypted)
    return json.loads(decrypted.decode())


def encrypt_string(value: str) -> str:
    """Encrypt a simple string value."""
    cipher = get_cipher()
    encrypted = cipher.encrypt(value.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_string(encrypted_str: str) -> str:
    """Decrypt a simple string value."""
    cipher = get_cipher()
    encrypted = base64.urlsafe_b64decode(encrypted_str.encode())
    decrypted = cipher.decrypt(encrypted)
    return decrypted.decode()