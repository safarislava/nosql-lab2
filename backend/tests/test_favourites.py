from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from domain.product import Product
from domain.user import User
from tests.conftest import RepositoriesContainer


class TestFavouritesFunctional:
    """Функциональные тесты списка избранного (основной и альтернативный потоки)."""

    # -----------------------------------------------------------------------
    # Основной поток (Happy Path)
    # -----------------------------------------------------------------------

    def test_get_empty_favourites_me(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        student_user: User,
    ) -> None:
        """Основной поток: получение пустого списка избранного текущего пользователя."""
        response = client.get(
            "/api/users/me/favourites",
            headers=student_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(student_user.id)
        assert data["products"] == []
        assert data["total_count"] == 0

    def test_add_and_remove_favourites_me(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        student_user: User,
        sample_product: Product,
    ) -> None:
        """Основной поток: добавление и удаление товара из избранного."""
        # 1. Добавляем в избранное
        add_resp = client.post(
            "/api/users/me/favourites",
            headers=student_auth_headers,
            json={"product_id": str(sample_product.id)},
        )
        assert add_resp.status_code == 200
        data = add_resp.json()
        assert data["total_count"] == 1
        assert len(data["products"]) == 1
        fav_item = data["products"][0]
        assert fav_item["product_id"] == str(sample_product.id)
        assert fav_item["added_user_id"] == str(student_user.id)
        assert fav_item["product"] is not None
        assert fav_item["product"]["name"] == sample_product.name
        assert fav_item["is_available"] is True

        # 2. Удаляем из избранного
        del_resp = client.delete(
            f"/api/users/me/favourites/{sample_product.id}",
            headers=student_auth_headers,
        )

        assert del_resp.status_code == 200
        assert del_resp.json()["total_count"] == 0
        assert del_resp.json()["products"] == []

    def test_add_multiple_favourites_and_clear_me(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        repos: RepositoriesContainer,
    ) -> None:
        """Основной поток: добавление нескольких товаров и последующая очистка избранного."""
        p1 = repos.product_repo.create(
            Product(name="Книга 1", description="", price=Decimal(100), quantity=5)
        )
        p2 = repos.product_repo.create(
            Product(name="Книга 2", description="", price=Decimal(200), quantity=5)
        )

        client.post(
            "/api/users/me/favourites",
            headers=student_auth_headers,
            json={"product_id": str(p1.id)},
        )
        resp = client.post(
            "/api/users/me/favourites",
            headers=student_auth_headers,
            json={"product_id": str(p2.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 2

        # Очистка избранного
        clear_resp = client.delete(
            "/api/users/me/favourites",
            headers=student_auth_headers,
        )
        assert clear_resp.status_code == 200
        assert clear_resp.json()["total_count"] == 0
        assert clear_resp.json()["products"] == []

    def test_admin_manage_user_favourites_success(
        self,
        client: TestClient,
        student_user: User,
        admin_auth_headers: dict[str, str],
        sample_product: Product,
    ) -> None:
        """Основной поток: администратор просматривает, добавляет и очищает избранное пользователя."""
        # Админ добавляет товар в избранное студента
        add_resp = client.post(
            f"/api/users/{student_user.id}/favourites",
            headers=admin_auth_headers,
            json={"product_id": str(sample_product.id)},
        )
        assert add_resp.status_code == 200
        assert add_resp.json()["total_count"] == 1

        # Админ получает список избранного студента
        get_resp = client.get(
            f"/api/users/{student_user.id}/favourites",
            headers=admin_auth_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["total_count"] == 1

        # Админ удаляет товар
        del_resp = client.delete(
            f"/api/users/{student_user.id}/favourites/{sample_product.id}",
            headers=admin_auth_headers,
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["total_count"] == 0

    # -----------------------------------------------------------------------
    # Альтернативные потоки (Alternative Flows & Errors)
    # -----------------------------------------------------------------------

    def test_get_favourites_me_unauthenticated(
        self,
        client: TestClient,
    ) -> None:
        """Альтернативный поток: получение избранного без авторизации -> 401."""
        response = client.get("/api/users/me/favourites")
        assert response.status_code == 401

    def test_get_favourites_by_user_id_forbidden_for_student(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        teacher_user: User,
    ) -> None:
        """Альтернативный поток: студент пытается получить избранное другого пользователя -> 403."""
        response = client.get(
            f"/api/users/{teacher_user.id}/favourites",
            headers=student_auth_headers,
        )
        assert response.status_code == 403

    def test_add_nonexistent_product_to_favourites(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
    ) -> None:
        """Альтернативный поток: добавление несуществующего товара -> 404 ProductNotFound."""
        response = client.post(
            "/api/users/me/favourites",
            headers=student_auth_headers,
            json={"product_id": str(uuid4())},
        )
        assert response.status_code == 404
        assert "не найден" in response.json().get("detail", "")

    def test_add_favourite_by_user_id_forbidden_for_student(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        teacher_user: User,
        sample_product: Product,
    ) -> None:
        """Альтернативный поток: студент пытается добавить в избранное другому пользователю -> 403."""
        response = client.post(
            f"/api/users/{teacher_user.id}/favourites",
            headers=student_auth_headers,
            json={"product_id": str(sample_product.id)},
        )
        assert response.status_code == 403

    def test_remove_product_not_in_favourites(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        sample_product: Product,
    ) -> None:
        """Альтернативный поток: удаление товара, которого нет в избранном -> 404 FavouriteProductNotFound."""
        response = client.delete(
            f"/api/users/me/favourites/{sample_product.id}",
            headers=student_auth_headers,
        )
        assert response.status_code == 404
        assert "не найден в избранном" in response.json().get("detail", "")

    def test_remove_favourite_by_user_id_forbidden_for_student(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        teacher_user: User,
        sample_product: Product,
    ) -> None:
        """Альтернативный поток: студент пытается удалить из избранного другого пользователя -> 403."""
        response = client.delete(
            f"/api/users/{teacher_user.id}/favourites/{sample_product.id}",
            headers=student_auth_headers,
        )
        assert response.status_code == 403

    def test_clear_favourites_by_user_id_forbidden_for_student(
        self,
        client: TestClient,
        student_auth_headers: dict[str, str],
        teacher_user: User,
    ) -> None:
        """Альтернативный поток: студент пытается очистить чужое избранное -> 403."""
        response = client.delete(
            f"/api/users/{teacher_user.id}/favourites",
            headers=student_auth_headers,
        )
        assert response.status_code == 403
