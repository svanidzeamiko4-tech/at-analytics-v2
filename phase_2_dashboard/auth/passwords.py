"""
Password hashing (Phase 4) — bcrypt.

Legacy ``pbkdf2_sha256$...`` hashes remain verifiable; login upgrades to bcrypt.
"""

from __future__ import annotations

import hashlib
import secrets

import bcrypt

_LEGACY_PREFIX = "pbkdf2_sha256$"
_BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith(_LEGACY_PREFIX):
        return _verify_legacy_pbkdf2(password, stored)
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("ascii"))
    except (ValueError, TypeError):
        return False


def needs_rehash(stored: str) -> bool:
    return stored.startswith(_LEGACY_PREFIX) or not stored.startswith("$2")


def _verify_legacy_pbkdf2(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_hex, digest_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return secrets.compare_digest(got, expected)
