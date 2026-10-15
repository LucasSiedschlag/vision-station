"""Access levels and sessions (FR-ADM-1, NFR-SEC-1).

Operator: no login. Supervisor and Maintainer: a password each. The Maintainer can do everything the
Supervisor can. Passwords are stored only as scrypt hashes in `system/users.json` (they are verified,
never read back), and a login that fails five times locks that role for 30 seconds.
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROLES = ("operator", "supervisor", "maintainer")  # in increasing order of rights
MIN_PASSWORD_LENGTH = 8
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


class AuthError(Exception):
    pass


class LockedOut(AuthError):
    def __init__(self, seconds: float):
        super().__init__(f"too many failed attempts, try again in {seconds:.0f} s")
        self.seconds = seconds


def at_least(role: str, needed: str) -> bool:
    return ROLES.index(role) >= ROLES.index(needed)


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, dklen=32, **_SCRYPT)


@dataclass
class Session:
    role: str
    expires: float


class AuthService:
    def __init__(
        self,
        users_file: Path | str,
        clock: Callable[[], float] = time.monotonic,
        session_s: float = 8 * 3600,
        max_failures: int = 5,
        lockout_s: float = 30.0,
    ):
        self._file = Path(users_file)
        self._clock = clock
        self._session_s = session_s
        self._max_failures = max_failures
        self._lockout_s = lockout_s
        self._sessions: dict[str, Session] = {}
        self._failures: dict[str, int] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def set_password(self, role: str, password: str) -> None:
        if role not in ROLES[1:]:
            raise AuthError("only supervisor and maintainer have passwords")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AuthError(f"the password needs at least {MIN_PASSWORD_LENGTH} characters")
        users = self._read()
        salt = os.urandom(16)
        users[role] = {"salt": salt.hex(), "hash": _hash(password, salt).hex(), **_SCRYPT, "changed_at": datetime.now().astimezone().isoformat(timespec="seconds")}
        self._file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_name(f".{self._file.name}.{secrets.token_hex(4)}")
        tmp.write_text(json.dumps(users, indent=2), encoding="utf-8")
        os.replace(tmp, self._file)
        with self._lock:
            self._sessions = {t: s for t, s in self._sessions.items() if s.role != role}  # a new password ends old sessions

    def has_password(self, role: str) -> bool:
        return role in self._read()

    def users(self) -> list[dict[str, Any]]:
        """The protected roles: whether a password is set and when it last changed. Never the hash."""
        stored = self._read()
        return [{"role": r, "has_password": r in stored, "changed_at": stored.get(r, {}).get("changed_at")} for r in ROLES[1:]]

    def check_password(self, role: str, password: str) -> bool:
        """Like a login (failures count towards the lock) but opens no session."""
        try:
            token, _ = self.login(role, password)
        except LockedOut:
            raise
        except AuthError:
            return False
        self.logout(token)
        return True

    def revoke_all(self) -> int:
        """End every session; returns how many there were."""
        with self._lock:
            n = len(self._sessions)
            self._sessions = {}
        return n

    def login(self, role: str, password: str) -> tuple[str, float]:
        """Returns (token, seconds the session lasts). Raises AuthError, or LockedOut after repeated failures."""
        if role not in ROLES[1:]:
            raise AuthError("unknown role")
        now = self._clock()
        with self._lock:
            until = self._locked_until.get(role, 0.0)
            if now < until:
                raise LockedOut(until - now)
        entry = self._read().get(role)
        ok = False
        if entry:
            salt = bytes.fromhex(entry["salt"])
            ok = hmac.compare_digest(_hash(password, salt), bytes.fromhex(entry["hash"]))
        with self._lock:
            if not ok:
                n = self._failures.get(role, 0) + 1
                self._failures[role] = n
                if n >= self._max_failures:
                    self._locked_until[role] = now + self._lockout_s
                    self._failures[role] = 0
                raise AuthError("wrong password")
            self._failures[role] = 0
            token = secrets.token_urlsafe(32)
            self._sessions[hashlib.sha256(token.encode()).hexdigest()] = Session(role, now + self._session_s)
            return token, self._session_s

    def role_of(self, token: str | None) -> str:
        """The role behind a token; 'operator' when there is none or it expired."""
        if not token:
            return "operator"
        key = hashlib.sha256(token.encode()).hexdigest()
        with self._lock:
            session = self._sessions.get(key)
            if session is None or session.expires <= self._clock():
                self._sessions.pop(key, None)
                return "operator"
            return session.role

    def logout(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)

    def _read(self) -> dict:
        if not self._file.is_file():
            return {}
        return json.loads(self._file.read_text(encoding="utf-8"))
