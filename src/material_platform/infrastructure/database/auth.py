from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from material_platform.infrastructure.database.models import SessionRow, UserRow
from material_platform.infrastructure.database.repositories import BaseRepository

_PBKDF2_ROUNDS = 120_000
_SESSION_DAYS = 30


@dataclass(frozen=True)
class StoredUser:
    user_id: UUID
    email: str
    name: str


class AuthRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_user(self, user_id: UUID) -> StoredUser | None:
        row = self._session.get(UserRow, user_id)
        return None if row is None else _user(row)

    def get_user_by_email(self, email: str) -> UserRow | None:
        return self._session.scalar(
            select(UserRow).where(UserRow.email == email.strip().lower())
        )

    def create_user(self, *, name: str, email: str, password: str) -> StoredUser:
        now = datetime.now(UTC)
        row = UserRow(
            user_id=uuid4(),
            email=email.strip().lower(),
            name=name.strip(),
            password_hash=hash_password(password),
            created_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return _user(row)

    def create_session(self, user_id: UUID) -> str:
        now = datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        self._session.add(
            SessionRow(
                session_id=uuid4(),
                user_id=user_id,
                token_hash=hash_token(token),
                expires_at=now + timedelta(days=_SESSION_DAYS),
                created_at=now,
            )
        )
        return token

    def user_for_token(self, token: str) -> StoredUser | None:
        digest = hash_token(token)
        row = self._session.scalar(
            select(SessionRow).where(SessionRow.token_hash == digest)
        )
        if row is None or _expired(row.expires_at):
            return None
        return self.get_user(row.user_id)

    def delete_session(self, token: str) -> None:
        digest = hash_token(token)
        row = self._session.scalar(
            select(SessionRow).where(SessionRow.token_hash == digest)
        )
        if row is not None:
            self._session.delete(row)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        _PBKDF2_ROUNDS,
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    salt, _, digest = stored.partition("$")
    if not salt or not digest:
        return False
    check = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        _PBKDF2_ROUNDS,
    ).hex()
    return hmac.compare_digest(digest, check)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _expired(expires_at: datetime) -> bool:
    now = datetime.now(UTC)
    if expires_at.tzinfo is None:
        return expires_at < now.replace(tzinfo=None)
    return expires_at < now


def _user(row: UserRow) -> StoredUser:
    return StoredUser(user_id=row.user_id, email=row.email, name=row.name)
