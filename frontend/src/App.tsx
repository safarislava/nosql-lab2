import { BrowserRouter, Navigate, useRoutes, type RouteObject } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedLayout } from "./components/ProtectedLayout";
import { RoleLayout } from "./components/RoleGate";
import { AdminAnalyticsPage } from "./pages/AdminAnalyticsPage";
import { AdminOrdersPage } from "./pages/AdminOrdersPage";
import { AdminProductsPage } from "./pages/AdminProductsPage";
import { AdminUserPage } from "./pages/AdminUserPage";
import { CartPage } from "./pages/CartPage";
import { CatalogPage } from "./pages/CatalogPage";
import { FavouritesPage } from "./pages/FavouritesPage";
import { LoginPage } from "./pages/LoginPage";
import { OrdersPage } from "./pages/OrdersPage";
import { ProductPage } from "./pages/ProductPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RecoveryPage } from "./pages/RecoveryPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { TeacherPage } from "./pages/TeacherPage";

function shopChildren(): RouteObject[] {
  return [
    { index: true, element: <Navigate to="catalog" replace /> },
    { path: "catalog", element: <CatalogPage /> },
    { path: "catalog/:productId", element: <ProductPage /> },
    { path: "favourites", element: <FavouritesPage /> },
    { path: "cart", element: <CartPage /> },
    { path: "orders", element: <OrdersPage /> },
    { path: "profile", element: <ProfilePage /> },
  ];
}

function AppRoutes() {
  return useRoutes([
    { path: "/", element: <LoginPage /> },
    { path: "/login", element: <LoginPage /> },
    { path: "/register", element: <RegisterPage /> },
    { path: "/recovery", element: <RecoveryPage /> },
    { path: "/reset-password", element: <ResetPasswordPage /> },
    {
      element: <ProtectedLayout />,
      children: [
        {
          path: "student",
          element: <RoleLayout role="STUDENT" />,
          children: shopChildren(),
        },
        {
          path: "teacher",
          element: <RoleLayout role="TEACHER" />,
          children: [...shopChildren(), { path: "students", element: <TeacherPage /> }],
        },
        {
          path: "admin",
          element: <RoleLayout role="ADMIN" />,
          children: [
            ...shopChildren(),
            { path: "students", element: <TeacherPage /> },
            { path: "products", element: <AdminProductsPage /> },
            { path: "all-orders", element: <AdminOrdersPage /> },
            { path: "user", element: <AdminUserPage /> },
            { path: "analytics", element: <AdminAnalyticsPage /> },
          ],
        },
      ],
    },
    { path: "*", element: <LoginPage /> },
  ]);
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
