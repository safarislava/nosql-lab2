import { useAuth } from "./auth/AuthContext";
import type { UserRole } from "./api/types";

export type RoleSlug = "student" | "teacher" | "admin";

export const ROLE_SLUG: Record<UserRole, RoleSlug> = {
  STUDENT: "student",
  TEACHER: "teacher",
  ADMIN: "admin",
};

export function pathsFor(role: UserRole) {
  const base = `/${ROLE_SLUG[role]}`;
  return {
    catalog: `${base}/catalog`,
    product: (id: string) => `${base}/catalog/${id}`,
    favourites: `${base}/favourites`,
    cart: `${base}/cart`,
    orders: `${base}/orders`,
    profile: `${base}/profile`,
    students: `${base}/students`,
    products: `${base}/products`,
    allOrders: `${base}/all-orders`,
    user: `${base}/user`,
    analytics: `${base}/analytics`,
  };
}

export function homePath(role: UserRole): string {
  return pathsFor(role).catalog;
}

export function usePaths() {
  const { user } = useAuth();
  return pathsFor(user?.role ?? "STUDENT");
}
