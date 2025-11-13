"""Security utilities for password hashing and verification."""

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash the provided password using the configured algorithm."""

    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a stored hash."""

    return _pwd_context.verify(plain_password, hashed_password)
