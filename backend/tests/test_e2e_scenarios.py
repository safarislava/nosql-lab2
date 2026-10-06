from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from domain.order import OrderStatus
from domain.product import Product
from domain.user import User, UserRole
from tests.conftest import RepositoriesContainer


class TestEndToEndFunctionalScenarios:
    """Сквозные функциональные сценарии (E2E) согласно заданию лабораторной работы №1."""

    def test_full_lab_workflow_teacher_recommends_and_student_orders(
        self,
        client: TestClient,
        repos: RepositoriesContainer,
    ) -> None:
        """Сквозной сценарий:

        1. Регистрация администратора, преподавателя и студента.
        2. Администратор наполняет каталог товаров.
        3. Преподаватель прикрепляет студента к своему курсу.
        4. Преподаватель изучает каталог и рекомендует (batch add) товар студентам.
        5. Студент видит товар в избранном с авторством преподавателя.
        6. Студент добавляет рекомендованный товар в корзину.
        7. Студент оформляет заказ (checkout): создается заказ, списывается остаток, растет счетчик.
        8. Администратор подтверждает (approve) заказ студента.
        9. Студент проверяет статус заказа и аудит-историю своих действий.
        """
        # --- 1. Регистрация и получение токенов ---
        # 1.1 Администратор
        admin_reg = client.post(
            "/api/users/register",
            json={
                "name": "Главный Администратор",
                "email": "admin.e2e@edu.ru",
                "password": "adminSuperPassword123",
                "role": UserRole.ADMIN.value,
            },
        )
        assert admin_reg.status_code == 201
        admin_login = client.post(
            "/api/auth/login",
            json={"email": "admin.e2e@edu.ru", "password": "adminSuperPassword123"},
        )
        admin_headers = {
            "Authorization": f"Bearer {admin_login.cookies['access_token']}"
        }

        # 1.2 Преподаватель
        teacher_reg = client.post(
            "/api/users/register",
            json={
                "name": "Профессор Иванов",
                "email": "prof.ivanov@edu.ru",
                "password": "profPassword123",
                "role": UserRole.TEACHER.value,
            },
        )
        assert teacher_reg.status_code == 201
        teacher_id = UUID(teacher_reg.json()["id"])
        teacher_login = client.post(
            "/api/auth/login",
            json={"email": "prof.ivanov@edu.ru", "password": "profPassword123"},
        )
        teacher_headers = {
            "Authorization": f"Bearer {teacher_login.cookies['access_token']}"
        }

        # 1.3 Студент
        student_reg = client.post(
            "/api/users/register",
            json={
                "name": "Студент Петров",
                "email": "petrov.student@edu.ru",
                "password": "studentPassword123",
                "role": UserRole.STUDENT.value,
            },
        )
        assert student_reg.status_code == 201
        student_id = UUID(student_reg.json()["id"])
        student_login = client.post(
            "/api/auth/login",
            json={"email": "petrov.student@edu.ru", "password": "studentPassword123"},
        )
        student_headers = {
            "Authorization": f"Bearer {student_login.cookies['access_token']}"
        }

        # --- 2. Администратор создает товар ---
        create_prod_resp = client.post(
            "/api/products",
            headers=admin_headers,
            json={
                "name": "Курс: Распределенные системы и Riak KV",
                "description": "Практический курс по NoSQL базам данных",
                "price": "4990.00",
                "quantity": 20,
            },
        )
        assert create_prod_resp.status_code == 201
        product_id = UUID(create_prod_resp.json()["id"])

        # --- 3. Преподаватель прикрепляет студента ---
        add_student_resp = client.post(
            "/api/users/me/teacher/students",
            headers=teacher_headers,
            json={"student_id": str(student_id)},
        )
        assert add_student_resp.status_code == 200
        assert str(student_id) in add_student_resp.json()["student_ids"]

        # --- 4. Преподаватель рекомендует товар всем своим студентам ---
        batch_fav_resp = client.post(
            "/api/users/me/teacher/students/favourites",
            headers=teacher_headers,
            json={"product_id": str(product_id)},
        )
        assert batch_fav_resp.status_code == 200
        assert batch_fav_resp.json()["affected_students"] == 1

        # --- 5. Студент проверяет избранное ---
        student_favs_resp = client.get(
            "/api/users/me/favourites",
            headers=student_headers,
        )
        assert student_favs_resp.status_code == 200
        favs_data = student_favs_resp.json()
        assert favs_data["total_count"] == 1
        fav_item = favs_data["products"][0]
        assert fav_item["product_id"] == str(product_id)
        assert fav_item["added_user_id"] == str(
            teacher_id
        )  # Рекомендовано преподавателем!

        # Студент проверяет товар в каталоге
        prod_detail = client.get(
            f"/api/products/{product_id}",
            headers=student_headers,
        )
        assert prod_detail.json()["is_in_favourites"] is True
        assert prod_detail.json()["is_in_cart"] is False

        # --- 6. Студент добавляет товар в корзину ---
        add_cart_resp = client.patch(
            f"/api/users/me/cart/items/{product_id}",
            headers=student_headers,
            json={"quantity": 2},
        )
        assert add_cart_resp.status_code == 200
        assert add_cart_resp.json()["total_items"] == 2

        # --- 7. Студент оформляет заказ (checkout) ---
        checkout_resp = client.post(
            "/api/users/me/checkout",
            headers=student_headers,
        )
        assert checkout_resp.status_code == 200
        checkout_data = checkout_resp.json()
        assert checkout_data["total_orders"] == 1
        assert Decimal(str(checkout_data["total_amount"])) == Decimal("4990.00") * 2
        order_id = UUID(checkout_data["orders"][0]["id"])

        # Проверка состояния после checkout
        # 7.1 Корзина пуста
        assert (
            client.get("/api/users/me/cart", headers=student_headers).json()[
                "total_items"
            ]
            == 0
        )
        # 7.2 Остаток уменьшился с 20 до 18
        prod_saved = repos.product_repo.get_by_id(product_id)
        assert prod_saved is not None and prod_saved.quantity == 18
        # 7.3 Атомарный счетчик заказов студента равен 1
        assert repos.counter_repo.get_by_user_id(student_id) == 1

        # --- 8. Администратор подтверждает заказ ---
        approve_resp = client.post(
            f"/api/orders/{order_id}/approve",
            headers=admin_headers,
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == OrderStatus.APPROVED.value

        # --- 9. Студент проверяет свои заказы и историю действий ---
        my_order = client.get(
            f"/api/users/me/orders/{order_id}",
            headers=student_headers,
        )
        assert my_order.status_code == 200
        assert my_order.json()["status"] == OrderStatus.APPROVED.value

        history_resp = client.get(
            "/api/users/me/history",
            headers=student_headers,
        )
        assert history_resp.status_code == 200
        events = history_resp.json()["events"]
        assert len(events) >= 3  # USER_REGISTER, UPDATE_CART_ITEM, CHECKOUT

    def test_end_to_end_order_creation_and_cancellation_flow(
        self,
        client: TestClient,
        student_user: User,
        student_auth_headers: dict[str, str],
        repos: RepositoriesContainer,
    ) -> None:
        """Сквозной сценарий:

        1. Студент напрямую создает заказ на 3 единицы товара.
        2. Склад уменьшается.
        3. Студент отменяет заказ до его одобрения -> статус CANCELLED, остаток возвращается.
        4. Повторная попытка отмены возвращает ошибку 400.
        """
        product = repos.product_repo.create(
            Product(
                name="Микроконтроллер ESP32",
                description="",
                price=Decimal("450.00"),
                quantity=10,
            )
        )

        # 1. Создание заказа
        create_resp = client.post(
            "/api/users/me/orders",
            headers=student_auth_headers,
            json={"product_id": str(product.id), "quantity": 3},
        )
        assert create_resp.status_code == 201
        order_id = create_resp.json()["id"]
        prod_saved1 = repos.product_repo.get_by_id(product.id)
        assert prod_saved1 is not None and prod_saved1.quantity == 7

        # 2. Отмена заказа
        cancel_resp = client.post(
            f"/api/users/me/orders/{order_id}/cancel",
            headers=student_auth_headers,
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == OrderStatus.CANCELLED.value

        # 3. Остаток вернулся на склад
        prod_saved2 = repos.product_repo.get_by_id(product.id)
        assert prod_saved2 is not None and prod_saved2.quantity == 10

        # 4. Повторная отмена невозможна
        second_cancel = client.post(
            f"/api/users/me/orders/{order_id}/cancel",
            headers=student_auth_headers,
        )
        assert second_cancel.status_code == 400
