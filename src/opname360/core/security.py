import hashlib
import secrets

from pwdlib import PasswordHash


_password_hash = PasswordHash.recommended()

# Verified against when the username doesn't exist, so a wrong username
# takes as long to reject as a wrong password.
_DUMMY_HASH = _password_hash.hash('opname360-no-such-user')


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    return _password_hash.verify(password, password_hash or _DUMMY_HASH)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Only the hash is stored, so a database leak exposes no live session."""
    return hashlib.sha256(token.encode()).hexdigest()
