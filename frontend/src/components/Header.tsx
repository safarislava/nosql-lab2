import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { usePaths } from "../routing";

export function Header() {
  const { user, cart, logout } = useAuth();
  const paths = usePaths();
  const cartCount = cart?.total_items ?? 0;
  const isTeacher = user?.role === "TEACHER" || user?.role === "ADMIN";
  const isAdmin = user?.role === "ADMIN";

  return (
    <header className="header">
      <NavLink to={paths.catalog} className="header__brand">
        Лавка
      </NavLink>
      <nav className="nav">
        <NavLink to={paths.catalog} end>
          Каталог
        </NavLink>
        <NavLink to={paths.favourites}>Избранное</NavLink>
        <NavLink to={paths.cart}>
          Корзина
          {cartCount > 0 ? <span className="badge">{cartCount}</span> : null}
        </NavLink>
        <NavLink to={paths.orders}>Заявки</NavLink>
        {isTeacher ? <NavLink to={paths.students}>Ученики</NavLink> : null}
        {isAdmin ? <NavLink to={paths.products}>Товары</NavLink> : null}
        {isAdmin ? <NavLink to={paths.allOrders}>Все заявки</NavLink> : null}
        {isAdmin ? <NavLink to={paths.user}>Пользователь</NavLink> : null}
        {isAdmin ? <NavLink to={paths.analytics}>Аналитика</NavLink> : null}
      </nav>
      <div className="header__user">
        <NavLink to={paths.profile}>{user?.name}</NavLink>
        <button type="button" className="btn btn--ghost" onClick={() => void logout()}>
          Выйти
        </button>
      </div>
    </header>
  );
}
