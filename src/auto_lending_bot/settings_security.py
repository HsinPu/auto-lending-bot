import base64
import hashlib
import hmac
import os


PREFIX = "enc:v1"


def encrypt_secret(value: str, encryption_key: str) -> str:
    if not value:
        return ""
    key = _key(encryption_key)
    nonce = os.urandom(16)
    stream = _stream(key, nonce, len(value.encode("utf-8")))
    payload = value.encode("utf-8")
    cipher = bytes(left ^ right for left, right in zip(payload, stream, strict=True))
    signature = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    return ":".join(
        [
            PREFIX,
            _b64(nonce),
            _b64(cipher),
            _b64(signature),
        ]
    )


def decrypt_secret(value: str, encryption_key: str) -> str:
    if not value:
        return ""
    if not value.startswith(f"{PREFIX}:"):
        return value

    _, _, raw_nonce, raw_cipher, raw_signature = value.split(":", 4)
    key = _key(encryption_key)
    nonce = _unb64(raw_nonce)
    cipher = _unb64(raw_cipher)
    signature = _unb64(raw_signature)
    expected_signature = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        msg = "Encrypted setting signature is invalid."
        raise ValueError(msg)

    stream = _stream(key, nonce, len(cipher))
    payload = bytes(left ^ right for left, right in zip(cipher, stream, strict=True))
    return payload.decode("utf-8")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "********"
    return f"********{value[-4:]}"


def _key(encryption_key: str) -> bytes:
    if not encryption_key:
        msg = "SETTINGS_ENCRYPTION_KEY is required for managed secrets."
        raise ValueError(msg)
    return hashlib.sha256(encryption_key.encode("utf-8")).digest()


def _stream(key: bytes, nonce: bytes, length: int) -> bytes:
    chunks = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < length:
        chunks.append(hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return b"".join(chunks)[:length]


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))
