"""
Zero-Knowledge sync cryptography services.
Uses AES-GCM-256 for authenticated encryption and Scrypt for key derivation.
"""
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit encryption key from user passphrase using Scrypt."""
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=2**14,
        r=8,
        p=1
    )
    return kdf.derive(passphrase.encode('utf-8'))

def encrypt_database_payload(db_bytes: bytes, passphrase: str) -> dict:
    """Encrypt the raw SQLite database bytes using AES-GCM-256."""
    salt = os.urandom(16)
    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)

    encrypted_data = aesgcm.encrypt(nonce, db_bytes, None)

    return {
        "salt": base64.b64encode(salt).decode('utf-8'),
        "nonce": base64.b64encode(nonce).decode('utf-8'),
        "payload": base64.b64encode(encrypted_data).decode('utf-8')
    }

def decrypt_database_payload(encrypted_package: dict, passphrase: str) -> bytes:
    """Decrypt the received database package."""
    salt = base64.b64decode(encrypted_package["salt"])
    nonce = base64.b64decode(encrypted_package["nonce"])
    encrypted_data = base64.b64decode(encrypted_package["payload"])

    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)

    return aesgcm.decrypt(nonce, encrypted_data, None)
