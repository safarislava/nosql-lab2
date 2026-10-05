from functools import cache
from typing import Annotated

from fastapi import Depends, HTTPException, status

from application.auth.service import AuthService
from application.auth.token import ITokenService
from application.session.repository import ISessionRepository
from application.session.service import SessionService
from domain.user import UserRole
from infrastructure.environment.settings import settings
from infrastructure.http.middleware.authentication_middleware import (
    AuthUser,
    CurrentUserDep,
)
from infrastructure.http.user.dependencies import (
    PasswordHasherDep,
    UserServiceDep,
)
from infrastructure.persistence.riak.session_repository import (
    RiakSessionRepository,
)
from infrastructure.security.jwt_service import JwtTokenService


@cache
def get_token_service() -> ITokenService:
    return JwtTokenService(
        secret_key=settings.auth.jwt_secret_key,
        algorithm=settings.auth.jwt_algorithm,
        expire_minutes=settings.auth.access_token_expire_minutes,
    )


TokenServiceDep = Annotated[ITokenService, Depends(get_token_service)]


@cache
def get_session_repository() -> ISessionRepository:
    return RiakSessionRepository()


SessionRepositoryDep = Annotated[ISessionRepository, Depends(get_session_repository)]


def get_session_service(
    session_repository: SessionRepositoryDep,
) -> SessionService:
    return SessionService(session_repository=session_repository)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]


def get_auth_service(
    user_service: UserServiceDep,
    session_service: SessionServiceDep,
    password_hasher: PasswordHasherDep,
    token_service: TokenServiceDep,
) -> AuthService:
    return AuthService(
        user_service=user_service,
        session_service=session_service,
        password_hasher=password_hasher,
        token_service=token_service,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


class RoleChecker:
    """Проверяет соответствие роли пользователя списку разрешенных ролей."""

    def __init__(self, allowed_roles: tuple[UserRole, ...]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(
        self,
        user: CurrentUserDep,
        user_service: UserServiceDep,
    ) -> AuthUser:
        db_user = user_service.get_by_id(user.id)
        if self.allowed_roles and db_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав доступа для выполнения данной операции.",
            )
        return AuthUser(id=db_user.id, role=db_user.role)


def require_roles(*allowed_roles: UserRole):
    """Фабрика зависимости для проверки ролевого доступа пользователя."""
    return Depends(RoleChecker(allowed_roles))
