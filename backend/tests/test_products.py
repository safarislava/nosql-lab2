from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from application.auth.token import ITokenService
from domain.favourites import FavouriteProduct
from domain.product import Product
from domain.user import User, UserRole
from tests.conftest import RepositoriesContainer


class TestProductsFunctional:
    """Функциональные тесты каталога и операций со складом (основной и альтернативный потоки)."""

    # -----------------------------------------------------------------------
    # Основной поток (Happy Path)
    # -----------------------------------------------------------------------

    def test_admin_create_product_success(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
        repos: RepositoriesContainer,
    ) -> None:
        """Основной поток: администратор создает новый товар в каталоге."""
        payload = {
            "name": "Ноутбук для учебы",
            "description": "Мощный и легкий ноутбук для лекций",
            "price": "54990.00",
            "quantity": 15,
        }
        response = client.post(
            "/api/products",
            headers=admin_auth_headers,
            json=payload,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Ноутбук для учебы"
        assert Decimal(str(data["price"])) == Decimal("54990.00")
        assert data["quantity"] == 15
        assert "id" in data

        # Проверка сохранения в репозитории
        product_id = data["id"]
        saved = repos.product_repo.get_by_id(UUID(product_id))
        assert saved is not None
        assert saved.name == "Ноутбук для учебы"

    def test_list_products_with_filters_and_pagination(
        self,
        client: TestClient,
        repos: RepositoriesContainer,
    ) -> None:
        """Основной поток: получение каталога с фильтрацией по тексту, цене, остатку и пагинацией."""
        p1 = Product(
            name="Python книга",
            description="Основы языка",
            price=Decimal("1000.00"),
            quantity=5,
        )
        p2 = Product(
            name="Java руководство",
            description="Продвинутый курс",
            price=Decimal("2000.00"),
            quantity=0,
        )
        p3 = Product(
            name="Алгоритмы",
            description="Python и структуры",
            price=Decimal("3000.00"),
            quantity=10,
        )
        repos.product_repo.create(p1)
        repos.product_repo.create(p2)
        repos.product_repo.create(p3)

        # 1. Поиск по слову "Python"
        resp = client.get("/api/products", params={"query": "Python"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2
        names = {item["name"] for item in items}
        assert "Python книга" in names
        assert "Алгоритмы" in names

        # 2. Фильтр по диапазону цен
        resp_price = client.get(
            "/api/products",
            params={"min_price": "1500.00", "max_price": "3500.00"},
        )
        assert resp_price.status_code == 200
        items_price = resp_price.json()["items"]
        assert len(items_price) == 2

        # 3. Фильтр in_stock_only
        resp_stock = client.get("/api/products", params={"in_stock_only": True})
        assert resp_stock.status_code == 200
        items_stock = resp_stock.json()["items"]
        assert len(items_stock) == 2
        assert all(item["quantity"] > 0 for item in items_stock)

        # 4. Пагинация
        resp_page = client.get("/api/products", params={"offset": 1, "limit": 1})
        assert resp_page.status_code == 200
        assert len(resp_page.json()["items"]) == 1

    def test_get_product_by_id_anonymous(
        self,
        client: TestClient,
        sample_product: Product,
    ) -> None:
        """Основной поток: анонимный пользователь получает товар (флаги корзины/избранного False)."""
        response = client.get(f"/api/products/{sample_product.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_product.id)
        assert data["is_in_cart"] is False
        assert data["is_in_favourites"] is False

    def test_get_product_by_id_authenticated_with_flags(
        self,
        client: TestClient,
        student_user: User,
        student_auth_headers: dict[str, str],
        sample_product: Product,
        repos: RepositoriesContainer,
    ) -> None:
        """Основной поток: авторизованный пользователь видит динамические флаги is_in_cart и is_in_favourites."""
        # Добавляем в корзину и избранное
        repos.cart_repo.set_item_quantity(
            user_id=student_user.id,
            product_id=sample_product.id,
            quantity=2,
        )
        repos.favourites_repo.add_item(
            user_id=student_user.id,
            item=FavouriteProduct(
                product_id=sample_product.id, added_user_id=student_user.id
            ),
        )

        response = client.get(
            f"/api/products/{sample_product.id}",
            headers=student_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_in_cart"] is True
        assert data["is_in_favourites"] is True

    def test_admin_update_product_success(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
        sample_product: Product,
        repos: RepositoriesContainer,
    ) -> None:
        """Основной поток: администратор обновляет информацию о товаре."""
        update_payload = {
            "name": "Новое название товара",
            "price": "1999.99",
            "quantity": 25,
        }
        response = client.patch(
            f"/api/products/{sample_product.id}",
            headers=admin_auth_headers,
            json=update_payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Новое название товара"
        assert Decimal(str(data["price"])) == Decimal("1999.99")
        assert data["quantity"] == 25

        saved = repos.product_repo.get_by_id(sample_product.id)
        assert saved is not None
        assert saved.name == "Новое название товара"

    def test_admin_reserve_and_restore_stock_success(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
        sample_product: Product,
    ) -> None:
        """Основной поток: резервирование и возврат остатков товара на складе."""
        initial_qty = sample_product.quantity  # 10

        # Резервируем 3 шт
        reserve_resp = client.post(
            f"/api/products/{sample_product.id}/reserve",
            headers=admin_auth_headers,
            json={"amount": 3},
        )
        assert reserve_resp.status_code == 200
        assert reserve_resp.json()["quantity"] == initial_qty - 3

        # Возвращаем 2 шт
        restore_resp = client.post(
            f"/api/products/{sample_product.id}/restore",
            headers=admin_auth_headers,
            json={"amount": 2},
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["quantity"] == initial_qty - 3 + 2

    def test_admin_delete_product_success(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
        sample_product: Product,
        repos: RepositoriesContainer,
    ) -> None:
        """Основной поток: администратор удаляет товар из каталога."""
        response = client.delete(
            f"/api/products/{sample_product.id}",
            headers=admin_auth_headers,
        )
        assert response.status_code == 204
        assert repos.product_repo.get_by_id(sample_product.id) is None

        # Последующий запрос должен вернуть 404
        get_resp = client.get(f"/api/products/{sample_product.id}")
        assert get_resp.status_code == 404

    # -----------------------------------------------------------------------
    # Альтернативные потоки (Alternative Flows & Errors)
    # -----------------------------------------------------------------------

    def test_create_product_forbidden_for_student(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
    ) -> None:
        """Альтернативный поток: студент пытается создать товар -> 403 Forbidden."""
        response = client.post(
            "/api/products",
            headers=student_auth_headers,
            json={"name": "Хакерский товар", "price": "100.00", "quantity": 1},
        )
        assert response.status_code == 403

    def test_admin_create_product_ignores_stale_jwt_role(
        self,
        client: TestClient,
        admin_user: User,
        token_service: ITokenService,
    ) -> None:
        """Роль в JWT может устареть; создание товара смотрит роль в профиле."""
        stale_token = token_service.create_access_token(
            user_id=admin_user.id,
            role=UserRole.STUDENT,
        )
        response = client.post(
            "/api/products",
            headers={"Authorization": f"Bearer {stale_token}"},
            json={
                "name": "Товар с устаревшим токеном",
                "description": "Роль берём из профиля",
                "price": "100.00",
                "quantity": 3,
            },
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Товар с устаревшим токеном"

    def test_create_product_forbidden_for_teacher(
        self,
        client: TestClient,
        teacher_auth_headers: dict[str, str],
    ) -> None:
        """Альтернативный поток: преподаватель пытается создать товар -> 403 Forbidden."""
        response = client.post(
            "/api/products",
            headers=teacher_auth_headers,
            json={"name": "Курс лекций", "price": "500.00", "quantity": 1},
        )
        assert response.status_code == 403

    def test_create_product_negative_price(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        """Альтернативный поток: создание товара с отрицательной ценой -> 422."""
        response = client.post(
            "/api/products",
            headers=admin_auth_headers,
            json={"name": "Товар", "price": "-10.00", "quantity": 1},
        )
        assert response.status_code == 422

    def test_create_product_negative_quantity(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        """Альтернативный поток: создание товара с отрицательным количеством -> 422."""
        response = client.post(
            "/api/products",
            headers=admin_auth_headers,
            json={"name": "Товар", "price": "10.00", "quantity": -5},
        )
        assert response.status_code == 422

    def test_get_nonexistent_product_by_id(
        self,
        client: TestClient,
    ) -> None:
        """Альтернативный поток: запрос несуществующего товара -> 404 ProductNotFound."""
        response = client.get(f"/api/products/{uuid4()}")
        assert response.status_code == 404

    def test_update_product_forbidden_for_student(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        sample_product: Product,
    ) -> None:
        """Альтернативный поток: студент пытается изменить товар -> 403."""
        response = client.patch(
            f"/api/products/{sample_product.id}",
            headers=student_auth_headers,
            json={"name": "Взлом"},
        )
        assert response.status_code == 403

    def test_update_nonexistent_product(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        """Альтернативный поток: обновление несуществующего товара -> 404."""
        response = client.patch(
            f"/api/products/{uuid4()}",
            headers=admin_auth_headers,
            json={"name": "Призрак"},
        )
        assert response.status_code == 404

    def test_reserve_stock_insufficient_amount(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
        sample_product: Product,
    ) -> None:
        """Альтернативный поток: резервирование большего количества, чем есть на складе -> 400 InsufficientStock."""
        response = client.post(
            f"/api/products/{sample_product.id}/reserve",
            headers=admin_auth_headers,
            json={"amount": sample_product.quantity + 100},
        )
        assert response.status_code == 400
        assert "Недостаточно товара" in response.json().get("detail", "")

    def test_reserve_stock_invalid_amount(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
        sample_product: Product,
    ) -> None:
        """Альтернативный поток: резервирование неположительного количества (0 или -1) -> 422."""
        response = client.post(
            f"/api/products/{sample_product.id}/reserve",
            headers=admin_auth_headers,
            json={"amount": 0},
        )
        assert response.status_code == 422

    def test_restore_stock_invalid_amount(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
        sample_product: Product,
    ) -> None:
        """Альтернативный поток: возврат неположительного количества -> 422."""
        response = client.post(
            f"/api/products/{sample_product.id}/restore",
            headers=admin_auth_headers,
            json={"amount": -2},
        )
        assert response.status_code == 422

    def test_delete_product_forbidden_for_student(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        sample_product: Product,
    ) -> None:
        """Альтернативный поток: студент пытается удалить товар -> 403."""
        response = client.delete(
            f"/api/products/{sample_product.id}",
            headers=student_auth_headers,
        )
        assert response.status_code == 403

    def test_delete_nonexistent_product(
        self,
        client: TestClient,
        admin_auth_headers: dict[str, str],
    ) -> None:
        """Альтернативный поток: удаление несуществующего товара -> 404."""
        response = client.delete(
            f"/api/products/{uuid4()}",
            headers=admin_auth_headers,
        )
        assert response.status_code == 404

    def test_repository_get_by_ids(
        self,
        repos: RepositoriesContainer,
        sample_product: Product,
    ) -> None:
        """Проверка пакетного получения товаров через get_by_ids."""
        p2 = Product(
            name="Второй товар",
            description="Описание второго товара",
            price=Decimal("2000.00"),
            quantity=5,
        )
        repos.product_repo.create(p2)

        # Пустой список
        assert repos.product_repo.get_by_ids([]) == []

        # Несколько существующих товаров
        found = repos.product_repo.get_by_ids([sample_product.id, p2.id])
        assert len(found) == 2
        found_ids = {p.id for p in found}
        assert sample_product.id in found_ids
        assert p2.id in found_ids

        # Смесь существующих и несуществующего ID
        non_existent_id = uuid4()
        found_mixed = repos.product_repo.get_by_ids(
            [sample_product.id, non_existent_id]
        )
        assert len(found_mixed) == 1
        assert found_mixed[0].id == sample_product.id
