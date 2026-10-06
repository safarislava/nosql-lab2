-- PostgreSQL initialization script for NoSQL Store

CREATE TABLE IF NOT EXISTS users
(
    id            UUID PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(50)  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);

CREATE TABLE IF NOT EXISTS teacher_students
(
    teacher_id UUID NOT NULL,
    student_id UUID NOT NULL,
    PRIMARY KEY (teacher_id, student_id),
    FOREIGN KEY (teacher_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_teacher_students_student_id ON teacher_students (student_id);

CREATE TABLE IF NOT EXISTS products
(
    id          UUID PRIMARY KEY,
    name        VARCHAR(255)   NOT NULL,
    description TEXT           NOT NULL DEFAULT '',
    price       NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    quantity    INTEGER        NOT NULL CHECK (quantity >= 0)
);

CREATE INDEX IF NOT EXISTS idx_products_name ON products (name);
CREATE INDEX IF NOT EXISTS idx_products_price ON products (price);
CREATE INDEX IF NOT EXISTS idx_products_quantity ON products (quantity);

CREATE TABLE IF NOT EXISTS orders
(
    id               UUID PRIMARY KEY,
    user_id          UUID           NOT NULL,
    product_id       UUID           NOT NULL,
    quantity         INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price       NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    total_amount     NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0),
    product_snapshot JSONB          NOT NULL,
    status           VARCHAR(50)    NOT NULL,
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);

CREATE TABLE IF NOT EXISTS operation_history
(
    id        UUID PRIMARY KEY,
    user_id   UUID        NOT NULL,
    action    VARCHAR(50) NOT NULL,
    target_id UUID        NULL,
    details   JSONB       NOT NULL DEFAULT '{}'::jsonb,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_operation_history_user_time ON operation_history (user_id, timestamp DESC);

