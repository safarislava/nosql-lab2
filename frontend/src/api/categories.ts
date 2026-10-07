import { api } from "./client";
import type { Category } from "./types";

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value?: string | null): boolean {
  return !!value && UUID_REGEX.test(value);
}

// Предустановленный список категорий для схемы v1 с валидными UUID
export const CATEGORY_PRESETS: Category[] = [
  { id: "e1000000-0000-4000-8000-000000000001", name: "Электроника", slug: "electronics", description: "Гаджеты и устройства" },
  { id: "e1000000-0000-4000-8000-000000000002", name: "Компьютеры", slug: "computers", description: "ПК, ноутбуки и комплектующие" },
  { id: "e1000000-0000-4000-8000-000000000003", name: "Бытовая техника", slug: "appliances", description: "Техника для кухни и дома" },
  { id: "e1000000-0000-4000-8000-000000000004", name: "Книги", slug: "books", description: "Художественная и учебная литература" },
  { id: "e1000000-0000-4000-8000-000000000005", name: "Одежда и обувь", slug: "clothing", description: "Мужская и женская одежда" },
  { id: "e1000000-0000-4000-8000-000000000006", name: "Дом и сад", slug: "home", description: "Товары для уюта и сада" },
  { id: "e1000000-0000-4000-8000-000000000007", name: "Спорт и отдых", slug: "sport", description: "Спорттовары и туризм" },
];

let cachedSchemaVersion: 1 | 2 | null = null;

/**
 * Поиск глобальных категорий (эндпоинт бэкенда GET /api/categories, доступен только в v2).
 */
export async function searchCategories(
  query?: string,
  offset = 0,
  limit = 50,
): Promise<Category[]> {
  const search = new URLSearchParams();
  if (query && query.trim()) search.set("query", query.trim());
  if (offset > 0) search.set("offset", String(offset));
  if (limit !== 50) search.set("limit", String(limit));

  const qs = search.toString();
  return api<Category[]>(`/api/categories${qs ? `?${qs}` : ""}`);
}

/**
 * Автоопределение версии схемы бэкенда (v1 vs v2).
 * В v2 запрос GET /api/categories возвращает 200 OK.
 * В v1 возвращает 400 Bad Request ("Поиск категорий доступен только для схемы версии 2...").
 */
export async function detectSchemaVersion(): Promise<1 | 2> {
  if (cachedSchemaVersion !== null) {
    return cachedSchemaVersion;
  }
  try {
    await searchCategories("", 0, 1);
    cachedSchemaVersion = 2;
  } catch {
    cachedSchemaVersion = 1;
  }
  return cachedSchemaVersion;
}

/**
 * Генерация безопасного URL-slug из названия категории.
 */
export function generateSlug(text: string): string {
  const ruMap: Record<string, string> = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "yo", ж: "zh",
    з: "z", и: "i", й: "y", к: "k", л: "l", м: "m", н: "n", о: "o",
    п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "kh", ц: "ts",
    ч: "ch", ш: "sh", щ: "shch", ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya",
  };

  const lower = text.toLowerCase().trim();
  let slug = "";
  for (const char of lower) {
    if (ruMap[char] !== undefined) {
      slug += ruMap[char];
    } else if (/[a-z0-9]/.test(char)) {
      slug += char;
    } else if (/[\s\-_]/.test(char)) {
      if (!slug.endsWith("-")) slug += "-";
    }
  }
  return slug.replace(/^-+|-+$/g, "") || "category";
}
