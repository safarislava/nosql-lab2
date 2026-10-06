from decimal import Decimal

from fastapi.testclient import TestClient

from domain.product import Product
from domain.user import User
from tests.conftest import RepositoriesContainer


class TestCheckoutFunctional:
    """Функциональные тесты оформления заказа из корзины (основной и альтернативный потоки)."""

    # -----------------------------------------------------------------------
    # Основной поток (Happy Path)
    # -----------------------------------------------------------------------

    def test_checkout_cart_me_success(
        self,
        client: TestClient,
        student_user: User,
        student_auth_headers: dict[str, str],
        repos: RepositoriesContainer,
    ) -> None:
        """Основной поток: успешное оформление заказа из корзины с несколькими товарами."""
        p1 = repos.product_repo.create(
            Product(
                name="Учебник 1", description="", price=Decimal("1000.00"), quantity=10
            )
        )
        p2 = repos.product_repo.create(
            Product(
                name="Учебник 2", description="", price=Decimal("500.00"), quantity=5
            )
        )

        # Добавляем 2 шт p1 и 3 шт p2 в корзину
        client.patch(
            f"/api/users/me/cart/items/{p1.id}",
            headers=student_auth_headers,
            json={"quantity": 2},
        )
        client.patch(
            f"/api/users/me/cart/items/{p2.id}",
            headers=student_auth_headers,
            json={"quantity": 3},
        )

        # Оформляем заказ
        response = client.post(
            "/api/users/me/checkout",
            headers=student_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_orders"] == 2
        # Итоговая сумма: 2 * 1000 + 3 * 500 = 3500.00
        assert Decimal(str(data["total_amount"])) == Decimal("3500.00")
        assert len(data["orders"]) == 2
        for order_item in data["orders"]:
            assert "product_snapshot" in order_item
            assert order_item["product_snapshot"] is not None
            assert order_item["product_snapshot"]["id"] in (str(p1.id), str(p2.id))

        # 1. Корзина должна быть очищена
        cart_resp = client.get("/api/users/me/cart", headers=student_auth_headers)
        assert cart_resp.json()["total_items"] == 0

        # 2. Остатки на складе должны быть уменьшены
        p1_saved = repos.product_repo.get_by_id(p1.id)
        assert p1_saved is not None and p1_saved.quantity == 8
        p2_saved = repos.product_repo.get_by_id(p2.id)
        assert p2_saved is not None and p2_saved.quantity == 2

        # 3. Атомарный счетчик заказов пользователя инкрементирован
        assert repos.counter_repo.get_by_user_id(student_user.id) == 2

    def test_admin_checkout_by_user_id_success(
        self,
        client: TestClient,
        student_user: User,
        admin_auth_headers: dict[str, str],
        sample_product: Product,
        repos: RepositoriesContainer,
    ) -> None:
        """Основной поток: администратор оформляет заказ из корзины студента по его ID."""
        repos.cart_repo.set_item_quantity(
            user_id=student_user.id,
            product_id=sample_product.id,
            quantity=1,
        )

        response = client.post(
            f"/api/users/{student_user.id}/checkout",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_orders"] == 1
        assert Decimal(str(data["total_amount"])) == sample_product.price

    # -----------------------------------------------------------------------
    # Альтернативные потоки (Alternative Flows & Errors)
    # -----------------------------------------------------------------------

    def test_checkout_empty_cart(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
    ) -> None:
        """Альтернативный поток: попытка оформить заказ из пустой корзины -> 400 EmptyCartCheckout."""
        response = client.post(
            "/api/users/me/checkout",
            headers=student_auth_headers,
        )
        assert response.status_code == 400
        assert "корзина пуста" in response.json().get("detail", "")

    def test_checkout_insufficient_stock(
        self,
        client: TestClient,
        student_user: User,
        student_auth_headers: dict[str, str],
        sample_product: Product,
        repos: RepositoriesContainer,
    ) -> None:
        """Альтернативный поток: оформление заказа, когда количество в корзине превышает склад -> 400."""
        # Устанавливаем в корзине количество больше наличия
        repos.cart_repo.set_item_quantity(
            user_id=student_user.id,
            product_id=sample_product.id,
            quantity=sample_product.quantity + 50,
        )

        response = client.post(
            "/api/users/me/checkout",
            headers=student_auth_headers,
        )
        assert response.status_code == 400
        assert "Недостаточно товара на складе" in response.json().get("detail", "")

    def test_checkout_unauthenticated(
        self,
        client: TestClient,
    ) -> None:
        """Альтернативный поток: оформление заказа без авторизации -> 401."""
        response = client.post("/api/users/me/checkout")
        assert response.status_code == 401

    def test_checkout_by_user_id_forbidden_for_student(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        teacher_user: User,
    ) -> None:
        """Альтернативный поток: студент пытается оформить заказ за другого пользователя -> 403."""
        response = client.post(
            f"/api/users/{teacher_user.id}/checkout",
            headers=student_auth_headers,
        )
        assert response.status_code == 403
