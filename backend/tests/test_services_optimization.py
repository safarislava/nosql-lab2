from decimal import Decimal
from uuid import uuid4

from application.cart.dto import UpdateCartProductDto
from application.cart.service import CartService
from application.favourites.dto import AddFavouriteDto
from application.favourites.service import FavouritesService
from application.product.service import ProductService
from application.teacher.service import TeacherService
from application.user.service import UserService
from domain.favourites import FavouriteProduct
from domain.product import Product
from domain.user import User, UserRole
from tests.conftest import RepositoriesContainer


class TestServicesHydration:
    """Тесты бизнес-логики гидрации и расчета данных в слое приложения."""

    def test_cart_service_hydration_and_totals(
        self,
        repos: RepositoriesContainer,
        student_user: User,
        sample_product: Product,
    ) -> None:
        product_service = ProductService(repos.product_repo)
        cart_service = CartService(repos.cart_repo, product_service, repos.event_bus)

        # Создаем второй товар
        p2 = Product(
            name="Второй товар",
            description="Описание",
            price=Decimal("500.00"),
            quantity=3,
        )
        repos.product_repo.create(p2)

        # Добавляем 2 шт первого товара (цена 1500) и 1 шт второго товара (цена 500)
        cart_service.update_quantity(
            student_user.id,
            UpdateCartProductDto(product_id=sample_product.id, quantity=2),
        )
        cart_dto = cart_service.update_quantity(
            student_user.id,
            UpdateCartProductDto(product_id=p2.id, quantity=1),
        )

        assert cart_dto.user_id == student_user.id
        assert cart_dto.total_items == 3
        assert cart_dto.total_amount == Decimal("3500.00")
        assert not cart_dto.has_unavailable_items
        assert len(cart_dto.items) == 2

        item_map = {item.product_id: item for item in cart_dto.items}
        assert item_map[sample_product.id].product is not None
        assert item_map[sample_product.id].product.name == sample_product.name
        assert item_map[sample_product.id].product.price == Decimal("1500.00")
        assert item_map[sample_product.id].subtotal == Decimal("3000.00")
        assert item_map[sample_product.id].is_available is True
        assert item_map[sample_product.id].available_stock == 10

        assert item_map[p2.id].product is not None
        assert item_map[p2.id].product.price == Decimal("500.00")
        assert item_map[p2.id].subtotal == Decimal("500.00")

    def test_cart_service_orphan_and_out_of_stock_products(
        self,
        repos: RepositoriesContainer,
        student_user: User,
        sample_product: Product,
    ) -> None:
        product_service = ProductService(repos.product_repo)
        cart_service = CartService(repos.cart_repo, product_service, repos.event_bus)

        # Напрямую в репозиторий Riak добавляем товар, которого нет в PostgreSQL
        fake_product_id = uuid4()
        repos.cart_repo.set_item_quantity(student_user.id, fake_product_id, 1)

        # Добавляем в Riak товар с количеством больше, чем на складе (на складе 10, заказываем 15)
        repos.cart_repo.set_item_quantity(student_user.id, sample_product.id, 15)

        cart_dto = cart_service.get_by_user_id(student_user.id)
        assert cart_dto.has_unavailable_items is True

        item_map = {item.product_id: item for item in cart_dto.items}

        # Несуществующий товар
        orphan_item = item_map[fake_product_id]
        assert orphan_item.product is None
        assert orphan_item.is_available is False
        assert orphan_item.subtotal == Decimal("0.00")

        # Товар с превышением остатка
        overstock_item = item_map[sample_product.id]
        assert overstock_item.product is not None
        assert overstock_item.is_available is False
        assert overstock_item.available_stock == 10

    def test_favourites_service_hydration(
        self,
        repos: RepositoriesContainer,
        student_user: User,
        sample_product: Product,
    ) -> None:
        product_service = ProductService(repos.product_repo)
        fav_service = FavouritesService(
            repos.favourites_repo, product_service, repos.event_bus
        )

        # Добавляем существующий товар
        fav_dto = fav_service.add_product(
            student_user.id,
            AddFavouriteDto(product_id=sample_product.id),
        )

        assert fav_dto.total_count == 1
        assert len(fav_dto.products) == 1
        fav_item = fav_dto.products[0]
        assert fav_item.product_id == sample_product.id
        assert fav_item.product is not None
        assert fav_item.product.name == sample_product.name
        assert fav_item.is_available is True

        # Несуществующий товар в Riak
        fake_id = uuid4()
        repos.favourites_repo.add_item(
            student_user.id,
            FavouriteProduct(product_id=fake_id, added_user_id=student_user.id),
        )

        fav_dto_mixed = fav_service.get_by_user_id(student_user.id)
        assert fav_dto_mixed.total_count == 2
        mixed_map = {p.product_id: p for p in fav_dto_mixed.products}
        assert mixed_map[fake_id].product is None
        assert mixed_map[fake_id].is_available is False

    def test_teacher_service_students_hydration(
        self,
        repos: RepositoriesContainer,
        teacher_user: User,
        student_user: User,
    ) -> None:
        user_service = UserService(repos.user_repo, None, repos.event_bus)  # type: ignore[arg-type]
        product_service = ProductService(repos.product_repo)
        fav_service = FavouritesService(
            repos.favourites_repo, product_service, repos.event_bus
        )
        teacher_service = TeacherService(
            repos.teacher_repo,
            user_service,
            product_service,
            fav_service,
            repos.event_bus,
        )

        # Прикрепляем студента
        teacher_dto = teacher_service.add_student(teacher_user.id, student_user.id)

        assert teacher_dto.id == teacher_user.id
        assert teacher_dto.total_students == 1
        assert student_user.id in teacher_dto.student_ids
        assert len(teacher_dto.students) == 1
        assert teacher_dto.students[0].id == student_user.id
        assert teacher_dto.students[0].name == student_user.name
        assert teacher_dto.students[0].email == student_user.email
        assert teacher_dto.students[0].role == UserRole.STUDENT
