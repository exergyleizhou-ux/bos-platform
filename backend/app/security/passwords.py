"""
Password hashing compatibility helpers.

Passlib 1.7.x expects ``bcrypt.__about__.__version__``, but bcrypt 4.1+
removed that attribute. We restore a tiny compatibility shim so password
hashing and verification work without noisy startup warnings.
"""

from __future__ import annotations

from types import SimpleNamespace

import bcrypt
from passlib.context import CryptContext


def _ensure_bcrypt_about() -> None:
    if hasattr(bcrypt, "__about__"):
        return
    version = getattr(bcrypt, "__version__", None)
    bcrypt.__about__ = SimpleNamespace(__version__=version or "unknown")


_ensure_bcrypt_about()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
