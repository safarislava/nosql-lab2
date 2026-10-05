from functools import cache
from typing import Annotated

from fastapi import Depends

from application.teacher.repository import ITeacherRepository
from application.teacher.service import TeacherService
from infrastructure.event_bus.dependencies import EventBusDep
from infrastructure.http.favourites.dependencies import FavouritesServiceDep
from infrastructure.http.product.dependencies import ProductServiceDep
from infrastructure.http.user.dependencies import UserServiceDep
from infrastructure.persistence.postgres.teacher_repository import (
    PostgresTeacherRepository,
)


@cache
def get_teacher_repository() -> ITeacherRepository:
    return PostgresTeacherRepository()


TeacherRepositoryDep = Annotated[ITeacherRepository, Depends(get_teacher_repository)]


def get_teacher_service(
    teacher_repository: TeacherRepositoryDep,
    user_service: UserServiceDep,
    product_service: ProductServiceDep,
    favourites_service: FavouritesServiceDep,
    event_bus: EventBusDep,
) -> TeacherService:
    return TeacherService(
        teacher_repository=teacher_repository,
        user_service=user_service,
        product_service=product_service,
        favourites_service=favourites_service,
        event_bus=event_bus,
    )


TeacherServiceDep = Annotated[TeacherService, Depends(get_teacher_service)]
