import os
import subprocess
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

# Ensure environment variables point to test containers before application imports
os.environ["POSTGRES__HOST"] = os.getenv("POSTGRES__HOST", "localhost")
os.environ["POSTGRES__PORT"] = os.getenv("POSTGRES__PORT", "5433")
os.environ["POSTGRES__USER"] = os.getenv("POSTGRES__USER", "postgres")
os.environ["POSTGRES__PASSWORD"] = os.getenv("POSTGRES__PASSWORD", "postgres")
os.environ["POSTGRES__DB"] = os.getenv("POSTGRES__DB", "nosql_store_test")
os.environ["POSTGRES__MIN_CONNECTIONS"] = "1"
os.environ["POSTGRES__MAX_CONNECTIONS"] = "10"
os.environ["RIAK__BASE_URL"] = os.getenv("RIAK__BASE_URL", "http://localhost:8099")
os.environ["RIAK__TIMEOUT"] = "5.0"
os.environ["AUTH__JWT_SECRET_KEY"] = "test-secret-key-12345678901234567890"
os.environ["AUTH__JWT_ALGORITHM"] = "HS256"
os.environ["AUTH__ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["AUTH__REFRESH_TOKEN_EXPIRE_DAYS"] = "60"
os.environ["AUTH__COOKIE_SECURE"] = "false"
os.environ["AUTH__COOKIE_HTTPONLY"] = "true"
os.environ["AUTH__COOKIE_SAMESITE"] = "lax"
os.environ["COUCHDB__NODE0_URL"] = os.getenv(
    "COUCHDB__NODE0_URL", "http://localhost:5984"
)
os.environ["COUCHDB__NODE1_URL"] = os.getenv(
    "COUCHDB__NODE1_URL", "http://localhost:5985"
)
os.environ["COUCHDB__USER"] = os.getenv("COUCHDB__USER", "admin")
os.environ["COUCHDB__PASSWORD"] = os.getenv("COUCHDB__PASSWORD", "password")
os.environ["COUCHDB__PRODUCTS_DB"] = os.getenv("COUCHDB__PRODUCTS_DB", "products_test")
os.environ["COUCHDB__CATEGORIES_DB"] = os.getenv(
    "COUCHDB__CATEGORIES_DB", "categories_test"
)
os.environ["COUCHDB__TIMEOUT"] = "5.0"


from application.auth.service import AuthService
from application.auth.token import ITokenService
from application.cart.service import CartService
from application.checkout.service import CheckoutService
from application.favourites.service import FavouritesService
from application.history.service import HistoryService
from application.order.service import OrderService
from application.product.service import ProductService
from application.recovery.service import RecoveryService
from application.session.service import SessionService
from application.teacher.service import TeacherService
from application.user.hasher import IPasswordHasher
from application.user.service import UserService
from domain.product import Product
from domain.teacher import Teacher
from domain.user import User, UserRole
from infrastructure.environment.settings import settings
from infrastructure.event_bus.dependencies import get_event_bus
from infrastructure.event_bus.in_memory_event_bus import InMemoryEventBus
from infrastructure.http.auth.dependencies import (
    get_auth_service,
    get_session_repository,
    get_session_service,
    get_token_service,
)
from infrastructure.http.cart.dependencies import (
    get_cart_repository,
    get_cart_service,
)
from infrastructure.http.checkout.dependencies import get_checkout_service
from infrastructure.http.favourites.dependencies import (
    get_favourites_repository,
    get_favourites_service,
)
from infrastructure.http.history.dependencies import (
    get_history_repository,
    get_history_service,
    get_postgres_history_repository,
    get_riak_history_cache_repository,
)
from infrastructure.http.order.dependencies import (
    get_counter_repository,
    get_order_repository,
    get_order_service,
)
from infrastructure.http.product.dependencies import (
    get_product_repository,
    get_product_service,
)
from infrastructure.http.recovery.dependencies import (
    get_recovery_service,
    get_recovery_token_repository,
)
from infrastructure.http.teacher.dependencies import (
    get_teacher_repository,
    get_teacher_service,
)
from infrastructure.http.user.dependencies import (
    get_password_hasher,
    get_user_repository,
    get_user_service,
)
from infrastructure.persistence.composite.history_repository import (
    CompositeHistoryRepository,
)
from infrastructure.persistence.couchdb.client import get_couchdb_client
from infrastructure.persistence.couchdb.product_repository import (
    CouchDbProductRepository,
)
from infrastructure.persistence.postgres.connection import (
    get_postgres_pool,
    init_db,
)
from infrastructure.persistence.postgres.history_repository import (
    PostgresHistoryRepository,
)
from infrastructure.persistence.postgres.order_repository import (
    PostgresOrderRepository,
)
from infrastructure.persistence.postgres.teacher_repository import (
    PostgresTeacherRepository,
)
from infrastructure.persistence.postgres.user_repository import (
    PostgresUserRepository,
)
from infrastructure.persistence.riak.cart_repository import RiakCartRepository
from infrastructure.persistence.riak.client import (
    get_riak_client,
)
from infrastructure.persistence.riak.favourites_repository import (
    RiakFavouritesRepository,
)
from infrastructure.persistence.riak.history_cache_repository import (
    RiakHistoryCacheRepository,
)
from infrastructure.persistence.riak.order_counter_repository import (
    RiakOrderCounterRepository,
)
from infrastructure.persistence.riak.recovery_token_repository import (
    RiakRecoveryTokenRepository,
)
from infrastructure.persistence.riak.session_repository import (
    RiakSessionRepository,
)
from infrastructure.security.jwt_service import JwtTokenService
from infrastructure.security.password_hasher import BcryptPasswordHasher
from main import app

# ---------------------------------------------------------------------------
# Test Containers Management & Verification
# ---------------------------------------------------------------------------


def _is_postgres_ready() -> bool:
    try:
        pool = get_postgres_pool()
        with pool.connection(timeout=3.0) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1;")
            return cur.fetchone() is not None
    except Exception:  # noqa: BLE001
        return False


def _is_riak_ready() -> bool:
    try:
        client = get_riak_client()
        if not client.ping():
            return False
        client.get("kv", "healthcheck", "test")
        return True
    except Exception:  # noqa: BLE001
        return False


def _is_couchdb_ready() -> bool:
    try:
        client = get_couchdb_client()
        return client.ping(node=0)
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="session", autouse=True)
def setup_docker_test_containers() -> Generator[None]:
    """Гарантирует, что тестовые контейнеры PostgreSQL, Riak KV и CouchDB запущены и готовы к работе."""
    if not _is_postgres_ready() or not _is_riak_ready() or not _is_couchdb_ready():
        # Start docker-compose.test.yml
        compose_file = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "..", "..", "docker-compose.test.yml"
            )
        )
        if os.path.exists(compose_file):
            subprocess.run(
                ["docker", "compose", "-f", compose_file, "up", "-d", "--wait"],
                check=False,
                capture_output=True,
            )

    # Wait for readiness
    for _ in range(60):
        if _is_postgres_ready() and _is_riak_ready() and _is_couchdb_ready():
            break
        time.sleep(1.0)

    # Initialize PostgreSQL schema
    init_db()

    yield


# ---------------------------------------------------------------------------
# Database & Riak Cleanup Helpers
# ---------------------------------------------------------------------------


def _truncate_postgres() -> None:
    try:
        pool = get_postgres_pool()
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "TRUNCATE TABLE teacher_students, operation_history, orders, products, users CASCADE;"
            )
            conn.commit()
    except Exception:  # noqa: BLE001, S110
        pass


def _cleanup_riak() -> None:
    try:
        client = get_riak_client()
        buckets_to_clean = [
            ("default", "sessions"),
            ("sets", "user_sessions"),
            ("default", "recovery_tokens"),
            ("maps", "carts"),
            ("maps", "favourites"),
            ("counters", "order_counters"),
            ("default", "history_cache"),
        ]
        for btype, bname in buckets_to_clean:
            try:
                resp = client._request(
                    "GET", f"/types/{btype}/buckets/{bname}/keys?keys=true"
                )
                if resp.status_code == 200:
                    keys = resp.json().get("keys", [])
                    for k in keys:
                        client.delete(bname, k, btype)
            except (httpx.HTTPError, Exception):  # noqa: BLE001, S110
                pass
    except Exception:  # noqa: BLE001, S110
        pass


def _cleanup_couchdb() -> None:
    try:
        client = get_couchdb_client()
        for db in [settings.couchdb.products_db, settings.couchdb.categories_db]:
            try:
                all_docs = client.get_all_docs(db, include_docs=False)
                for item in all_docs:
                    doc_id = item["id"]
                    if not doc_id.startswith("_design/"):
                        client.delete_doc(db, doc_id, item["value"]["rev"])
            except Exception:  # noqa: BLE001, S110
                pass
    except Exception:  # noqa: BLE001, S110
        pass


@pytest.fixture(autouse=True)
def clean_db_and_riak_between_tests() -> Generator[None]:
    """Очищает таблицы PostgreSQL, бакеты Riak KV и CouchDB перед и после каждого теста."""
    _truncate_postgres()
    _cleanup_riak()
    _cleanup_couchdb()
    yield
    _truncate_postgres()
    _cleanup_riak()
    _cleanup_couchdb()


# ---------------------------------------------------------------------------
# Repositories Container
# ---------------------------------------------------------------------------


@dataclass
class RepositoriesContainer:
    user_repo: PostgresUserRepository = field(default_factory=PostgresUserRepository)
    session_repo: RiakSessionRepository = field(default_factory=RiakSessionRepository)
    product_repo: CouchDbProductRepository = field(
        default_factory=lambda: CouchDbProductRepository(client=get_couchdb_client())
    )
    cart_repo: RiakCartRepository = field(default_factory=RiakCartRepository)
    favourites_repo: RiakFavouritesRepository = field(
        default_factory=RiakFavouritesRepository
    )
    order_repo: PostgresOrderRepository = field(default_factory=PostgresOrderRepository)
    counter_repo: RiakOrderCounterRepository = field(
        default_factory=RiakOrderCounterRepository
    )
    recovery_repo: RiakRecoveryTokenRepository = field(
        default_factory=RiakRecoveryTokenRepository
    )
    postgres_history_repo: PostgresHistoryRepository = field(
        default_factory=PostgresHistoryRepository
    )
    riak_history_cache_repo: RiakHistoryCacheRepository = field(
        default_factory=RiakHistoryCacheRepository
    )
    history_repo: CompositeHistoryRepository = field(init=False)
    teacher_repo: PostgresTeacherRepository = field(
        default_factory=PostgresTeacherRepository
    )
    event_bus: InMemoryEventBus = field(default_factory=InMemoryEventBus)

    def __post_init__(self) -> None:
        self.history_repo = CompositeHistoryRepository(
            postgres_repo=self.postgres_history_repo,
            riak_repo=self.riak_history_cache_repo,
        )


@pytest.fixture
def repos() -> RepositoriesContainer:
    return RepositoriesContainer()


@pytest.fixture
def password_hasher() -> IPasswordHasher:
    return BcryptPasswordHasher(rounds=4)


@pytest.fixture
def token_service() -> ITokenService:
    return JwtTokenService(
        secret_key=settings.auth.jwt_secret_key,
        algorithm=settings.auth.jwt_algorithm,
        expire_minutes=settings.auth.access_token_expire_minutes,
    )


@pytest.fixture
def client(
    repos: RepositoriesContainer,
    password_hasher: IPasswordHasher,
    token_service: ITokenService,
) -> Generator[TestClient]:
    user_service = UserService(
        user_repository=repos.user_repo,
        password_hasher=password_hasher,
        event_bus=repos.event_bus,
    )
    session_service = SessionService(
        session_repository=repos.session_repo,
    )
    auth_service = AuthService(
        user_service=user_service,
        session_service=session_service,
        password_hasher=password_hasher,
        token_service=token_service,
    )
    product_service = ProductService(
        product_repository=repos.product_repo,
    )
    cart_service = CartService(
        cart_repository=repos.cart_repo,
        product_service=product_service,
        event_bus=repos.event_bus,
    )
    favourites_service = FavouritesService(
        favourites_repository=repos.favourites_repo,
        product_service=product_service,
        event_bus=repos.event_bus,
    )
    order_service = OrderService(
        order_repository=repos.order_repo,
        counter_repository=repos.counter_repo,
        product_service=product_service,
        event_bus=repos.event_bus,
    )
    checkout_service = CheckoutService(
        cart_service=cart_service,
        order_service=order_service,
        event_bus=repos.event_bus,
    )
    history_service = HistoryService(
        history_repository=repos.history_repo,
        event_bus=repos.event_bus,
    )
    teacher_service = TeacherService(
        teacher_repository=repos.teacher_repo,
        user_service=user_service,
        product_service=product_service,
        favourites_service=favourites_service,
        event_bus=repos.event_bus,
    )
    recovery_service = RecoveryService(
        recovery_token_repository=repos.recovery_repo,
        user_service=user_service,
    )

    overrides = {
        get_user_repository: lambda: repos.user_repo,
        get_password_hasher: lambda: password_hasher,
        get_user_service: lambda: user_service,
        get_token_service: lambda: token_service,
        get_session_repository: lambda: repos.session_repo,
        get_session_service: lambda: session_service,
        get_auth_service: lambda: auth_service,
        get_product_repository: lambda: repos.product_repo,
        get_product_service: lambda: product_service,
        get_cart_repository: lambda: repos.cart_repo,
        get_cart_service: lambda: cart_service,
        get_favourites_repository: lambda: repos.favourites_repo,
        get_favourites_service: lambda: favourites_service,
        get_order_repository: lambda: repos.order_repo,
        get_counter_repository: lambda: repos.counter_repo,
        get_order_service: lambda: order_service,
        get_checkout_service: lambda: checkout_service,
        get_postgres_history_repository: lambda: repos.postgres_history_repo,
        get_riak_history_cache_repository: lambda: repos.riak_history_cache_repo,
        get_history_repository: lambda: repos.history_repo,
        get_history_service: lambda: history_service,
        get_teacher_repository: lambda: repos.teacher_repo,
        get_teacher_service: lambda: teacher_service,
        get_recovery_token_repository: lambda: repos.recovery_repo,
        get_recovery_service: lambda: recovery_service,
        get_event_bus: lambda: repos.event_bus,
    }

    app.dependency_overrides = overrides  # type: ignore[assignment]
    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers & Pre-seeded User Fixtures
# ---------------------------------------------------------------------------


def make_user(
    repos: RepositoriesContainer,
    password_hasher: IPasswordHasher,
    name: str,
    email: str,
    password: str,
    role: UserRole,
    user_id: UUID | None = None,
) -> User:
    uid = user_id or uuid4()
    user: User
    if role == UserRole.TEACHER:
        user = Teacher(
            id=uid,
            name=name,
            email=email.lower().strip(),
            password_hash=password_hasher.hash(password),
            role=role,
            student_ids=set(),
        )
        repos.teacher_repo.save(user)
    else:
        user = User(
            id=uid,
            name=name,
            email=email.lower().strip(),
            password_hash=password_hasher.hash(password),
            role=role,
        )
        repos.user_repo.save(user)
    return user


def get_auth_headers_for_user(
    token_service: ITokenService,
    user: User,
) -> dict[str, str]:
    token = token_service.create_access_token(user_id=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_user(
    repos: RepositoriesContainer,
    password_hasher: IPasswordHasher,
) -> User:
    return make_user(
        repos=repos,
        password_hasher=password_hasher,
        name="Иван Студент",
        email="student@edu.ru",
        password="password123",
        role=UserRole.STUDENT,
    )


@pytest.fixture
def student_auth_headers(
    token_service: ITokenService,
    student_user: User,
) -> dict[str, str]:
    return get_auth_headers_for_user(token_service, student_user)


@pytest.fixture
def teacher_user(
    repos: RepositoriesContainer,
    password_hasher: IPasswordHasher,
) -> Teacher:
    user = make_user(
        repos=repos,
        password_hasher=password_hasher,
        name="Петр Преподаватель",
        email="teacher@edu.ru",
        password="password123",
        role=UserRole.TEACHER,
    )
    assert isinstance(user, Teacher)
    return user


@pytest.fixture
def teacher_auth_headers(
    token_service: ITokenService,
    teacher_user: Teacher,
) -> dict[str, str]:
    return get_auth_headers_for_user(token_service, teacher_user)


@pytest.fixture
def admin_user(
    repos: RepositoriesContainer,
    password_hasher: IPasswordHasher,
) -> User:
    return make_user(
        repos=repos,
        password_hasher=password_hasher,
        name="Администратор",
        email="admin@edu.ru",
        password="adminPassword123",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def admin_auth_headers(
    token_service: ITokenService,
    admin_user: User,
) -> dict[str, str]:
    return get_auth_headers_for_user(token_service, admin_user)


@pytest.fixture
def sample_product(repos: RepositoriesContainer) -> Product:
    product = Product(
        name="Учебник по алгоритмам",
        description="Книга по алгоритмам и структурам данных",
        price=Decimal("1500.00"),
        quantity=10,
    )
    return repos.product_repo.create(product)
