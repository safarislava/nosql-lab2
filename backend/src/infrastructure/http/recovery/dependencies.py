from functools import cache
from typing import Annotated

from fastapi import Depends

from application.recovery.repository import IRecoveryTokenRepository
from application.recovery.service import RecoveryService
from infrastructure.http.user.dependencies import UserServiceDep
from infrastructure.persistence.riak.recovery_token_repository import (
    RiakRecoveryTokenRepository,
)


@cache
def get_recovery_token_repository() -> IRecoveryTokenRepository:
    return RiakRecoveryTokenRepository()


RecoveryTokenRepositoryDep = Annotated[
    IRecoveryTokenRepository, Depends(get_recovery_token_repository)
]


def get_recovery_service(
    recovery_token_repository: RecoveryTokenRepositoryDep,
    user_service: UserServiceDep,
) -> RecoveryService:
    return RecoveryService(
        recovery_token_repository=recovery_token_repository,
        user_service=user_service,
    )


RecoveryServiceDep = Annotated[RecoveryService, Depends(get_recovery_service)]
