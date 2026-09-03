from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from material_platform.infrastructure.database.auth import (
    AuthRepository,
    StoredUser,
    verify_password,
)


class AuthError(ValueError):
    def __init__(self, message: str, *, status: int = 401) -> None:
        super().__init__(message)
        self.status = status


class AuthService:
    def __init__(self, session: Session) -> None:
        self._repo = AuthRepository(session)

    def signup(self, *, name: str, email: str, password: str) -> tuple[StoredUser, str]:
        if self._repo.get_user_by_email(email):
            raise AuthError("email already in use", status=409)
        user = self._repo.create_user(name=name, email=email, password=password)
        return user, self._repo.create_session(user.user_id)

    def signin(self, *, email: str, password: str) -> tuple[StoredUser, str]:
        row = self._repo.get_user_by_email(email)
        if row is None or not verify_password(password, row.password_hash):
            raise AuthError("wrong email or password", status=401)
        user = StoredUser(user_id=row.user_id, email=row.email, name=row.name)
        return user, self._repo.create_session(user.user_id)

    def user_for_token(self, token: str | None) -> StoredUser | None:
        if not token:
            return None
        return self._repo.user_for_token(token)

    def signout(self, token: str | None) -> None:
        if token:
            self._repo.delete_session(token)

    def get(self, user_id: UUID) -> StoredUser | None:
        return self._repo.get_user(user_id)
