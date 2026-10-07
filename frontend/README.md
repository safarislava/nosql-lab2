Фронтенд витрины: Vite + React.

## Запуск

Backend на `http://localhost:8000`.

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173` — Vite проксирует `/api`.

## Экраны

- `/` и `/login` — вход
- `/register` (роль), `/recovery`, `/reset-password`
- `/{role}/catalog`, `/{role}/catalog/:id`, `/{role}/favourites`, `/{role}/cart`, `/{role}/orders`, `/{role}/history`, `/{role}/profile`
- `/teacher/students`, `/admin/students` — ученики
- `/admin/products`, `/admin/all-orders`, `/admin/user`, `/admin/analytics` — только админ

`role`: `student` | `teacher` | `admin`
