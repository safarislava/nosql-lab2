import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from application.order.dto import OrderFilterDto
from application.order.repository import IOrderRepository
from domain.order import Order, OrderStatus, ProductSnapshot
from infrastructure.persistence.postgres.connection import get_postgres_pool
from infrastructure.persistence.postgres.product_mapper import ProductSnapshotMapper


class PostgresOrderRepository(IOrderRepository):
    """Репозиторий заказов для PostgreSQL."""

    def __init__(self, pool: ConnectionPool | None = None) -> None:
        self._pool: ConnectionPool = pool or get_postgres_pool()

    @staticmethod
    def _row_to_order(row: Any) -> Order:
        raw_snapshot = row.get("product_snapshot")
        snapshot = None
        if isinstance(raw_snapshot, dict) and raw_snapshot:
            snapshot = ProductSnapshotMapper.from_dict(raw_snapshot)
        elif isinstance(raw_snapshot, str) and raw_snapshot and raw_snapshot != "{}":
            try:
                parsed = json.loads(raw_snapshot)
                if isinstance(parsed, dict) and parsed:
                    snapshot = ProductSnapshotMapper.from_dict(parsed)
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                snapshot = None

        if snapshot is None:
            snapshot = ProductSnapshot(
                id=row["product_id"],
                name="",
                description="",
                price=Decimal(str(row["unit_price"])),
            )

        return Order(
            id=row["id"],
            user_id=row["user_id"],
            product_id=row["product_id"],
            quantity=row["quantity"],
            unit_price=Decimal(str(row["unit_price"])),
            total_amount=Decimal(str(row["total_amount"])),
            product_snapshot=snapshot,
            status=OrderStatus(row["status"]),
            created_at=row["created_at"],
        )

    def get_by_id(self, order_id: UUID) -> Order | None:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, user_id, product_id, quantity, unit_price, total_amount, product_snapshot, status, created_at
                FROM orders WHERE id = %s
                """,
                (order_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return self._row_to_order(row)

    def exists_by_id(self, order_id: UUID) -> bool:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM orders WHERE id = %s", (order_id,))
            return cur.fetchone() is not None

    def get_by_user_id(self, user_id: UUID) -> list[Order]:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, user_id, product_id, quantity, unit_price, total_amount, product_snapshot, status, created_at
                FROM orders WHERE user_id = %s ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            return [self._row_to_order(r) for r in rows]

    def list(
        self,
        filter_dto: OrderFilterDto | None = None,
    ) -> list[Order]:
        conditions: list[sql.SQL] = []
        params: list[Any] = []

        if filter_dto is not None:
            if filter_dto.user_id is not None:
                conditions.append(sql.SQL("user_id = %s"))
                params.append(filter_dto.user_id)
            if filter_dto.status is not None:
                conditions.append(sql.SQL("status = %s"))
                params.append(filter_dto.status.value)

        base_select: sql.SQL | sql.Composed = sql.SQL(
            "SELECT id, user_id, product_id, quantity, unit_price, total_amount, product_snapshot, status, created_at "
            "FROM orders"
        )

        if conditions:
            where_clause = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)
            base_select = base_select + where_clause

        offset = filter_dto.offset if filter_dto else 0
        limit = filter_dto.limit if filter_dto else 50

        select_query = base_select + sql.SQL(
            " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        )

        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(select_query, [*params, limit, offset])
            rows = cur.fetchall()
            return [self._row_to_order(r) for r in rows]

    def save(self, order: Order) -> Order:
        snapshot_json = json.dumps(
            ProductSnapshotMapper.to_dict(order.product_snapshot)
            if order.product_snapshot
            else {}
        )
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (id, user_id, product_id, quantity, unit_price, total_amount, product_snapshot, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    product_id = EXCLUDED.product_id,
                    quantity = EXCLUDED.quantity,
                    unit_price = EXCLUDED.unit_price,
                    total_amount = EXCLUDED.total_amount,
                    product_snapshot = EXCLUDED.product_snapshot,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at
                """,
                (
                    order.id,
                    order.user_id,
                    order.product_id,
                    order.quantity,
                    order.unit_price,
                    order.total_amount,
                    snapshot_json,
                    order.status.value,
                    order.created_at,
                ),
            )
            conn.commit()
            return order

    def update_status(
        self,
        order_id: UUID,
        new_status: OrderStatus,
        expected_status: OrderStatus | None = None,
    ) -> bool:
        with self._pool.connection() as conn, conn.cursor() as cur:
            if expected_status is not None:
                cur.execute(
                    "UPDATE orders SET status = %s WHERE id = %s AND status = %s",
                    (new_status.value, order_id, expected_status.value),
                )
            else:
                cur.execute(
                    "UPDATE orders SET status = %s WHERE id = %s",
                    (new_status.value, order_id),
                )
            conn.commit()
            return cur.rowcount > 0

    def update_status_and_get(
        self,
        order_id: UUID,
        new_status: OrderStatus,
        expected_status: OrderStatus | None = None,
    ) -> Order | None:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            if expected_status is not None:
                cur.execute(
                    """
                    UPDATE orders SET status = %s
                    WHERE id = %s AND status = %s
                    RETURNING id, user_id, product_id, quantity, unit_price, total_amount, product_snapshot, status, created_at
                    """,
                    (new_status.value, order_id, expected_status.value),
                )
            else:
                cur.execute(
                    """
                    UPDATE orders SET status = %s
                    WHERE id = %s
                    RETURNING id, user_id, product_id, quantity, unit_price, total_amount, product_snapshot, status, created_at
                    """,
                    (new_status.value, order_id),
                )
            row = cur.fetchone()
            conn.commit()
            if row is None:
                return None
            return self._row_to_order(row)
