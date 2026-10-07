import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  CATEGORY_PRESETS,
  detectSchemaVersion,
  searchCategories,
} from "../api/categories";
import { PAGE_SIZE, listProducts } from "../api/products";
import { addFavourite, removeFavourite, setCartQuantity } from "../api/shop";
import type { Category, Product, ProductSortBy } from "../api/types";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ProductCard } from "../components/ProductCard";
import { usePaths } from "../routing";

const SORT_OPTIONS: { value: ProductSortBy; label: string }[] = [
  { value: "popularity", label: "По популярности" },
  { value: "newest", label: "Сначала новые" },
  { value: "price_asc", label: "Сначала дешёвые" },
  { value: "price_desc", label: "Сначала дорогие" },
  { value: "name_asc", label: "По названию А–Я" },
  { value: "name_desc", label: "По названию Я–А" },
];

export function CatalogPage() {
  const navigate = useNavigate();
  const { user, favouriteIds, cartIds, refreshShop } = useAuth();
  const paths = usePaths();
  const [params, setParams] = useSearchParams();
  const filters = useMemo(
    () => ({
      query: params.get("query") ?? "",
      min_price: params.get("min_price") ?? "",
      max_price: params.get("max_price") ?? "",
      in_stock_only: params.get("in_stock_only") === "true",
      sort_by: (params.get("sort_by") as ProductSortBy) || "popularity",
      category_ids: params.getAll("category_ids"),
      created_from: params.get("created_from") ?? "",
      created_to: params.get("created_to") ?? "",
    }),
    [params],
  );

  const [availableCategories, setAvailableCategories] = useState<Category[]>([]);


  const [draftQuery, setDraftQuery] = useState(filters.query);
  const [draftMin, setDraftMin] = useState(filters.min_price);
  const [draftMax, setDraftMax] = useState(filters.max_price);
  const [draftCreatedFrom, setDraftCreatedFrom] = useState(filters.created_from);
  const [draftCreatedTo, setDraftCreatedTo] = useState(filters.created_to);
  const [items, setItems] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    setDraftQuery(filters.query);
    setDraftMin(filters.min_price);
    setDraftMax(filters.max_price);
    setDraftCreatedFrom(filters.created_from);
    setDraftCreatedTo(filters.created_to);
  }, [filters]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    listProducts({ ...filters, offset: 0, limit: PAGE_SIZE })
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        setHasMore(result.items.length === PAGE_SIZE);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Не удалось загрузить каталог");
        setItems([]);
        setHasMore(false);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters]);

  useEffect(() => {
    detectSchemaVersion().then((ver) => {
      if (ver === 2) {
        searchCategories()
          .then(setAvailableCategories)
          .catch(() => {
            setAvailableCategories(CATEGORY_PRESETS);
          });
      } else {
        setAvailableCategories(CATEGORY_PRESETS);
      }
    });
  }, []);

  function toggleCategory(categoryId: string) {
    const current = new Set(filters.category_ids);
    if (current.has(categoryId)) {
      current.delete(categoryId);
    } else {
      current.add(categoryId);
    }
    const next = new URLSearchParams(params);
    next.delete("category_ids");
    for (const cid of current) {
      next.append("category_ids", cid);
    }
    setParams(next);
  }

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    const next = new URLSearchParams();
    if (draftQuery.trim()) next.set("query", draftQuery.trim());
    if (draftMin) next.set("min_price", draftMin);
    if (draftMax) next.set("max_price", draftMax);
    if (draftCreatedFrom) next.set("created_from", draftCreatedFrom);
    if (draftCreatedTo) next.set("created_to", draftCreatedTo);
    if (filters.in_stock_only) next.set("in_stock_only", "true");
    next.set("sort_by", filters.sort_by);
    for (const cid of filters.category_ids) {
      next.append("category_ids", cid);
    }
    setParams(next);
  }


  function patchParams(patch: Record<string, string | boolean>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === false || value === "") next.delete(key);
      else next.set(key, String(value));
    }
    setParams(next);
  }

  async function loadMore() {
    setLoadingMore(true);
    setError("");
    try {
      const result = await listProducts({
        ...filters,
        offset: items.length,
        limit: PAGE_SIZE,
      });
      setItems((current) => [...current, ...result.items]);
      setHasMore(result.items.length === PAGE_SIZE);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось подгрузить товары");
    } finally {
      setLoadingMore(false);
    }
  }

  async function toggleFavourite(product: Product) {
    setBusyId(product.id);
    try {
      if (favouriteIds.has(product.id)) {
        await removeFavourite(product.id);
      } else {
        await addFavourite(product.id);
      }
      await refreshShop();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось обновить избранное");
    } finally {
      setBusyId(null);
    }
  }

  async function addToCart(product: Product) {
    if (cartIds.has(product.id)) {
      navigate(paths.cart);
      return;
    }
    setBusyId(product.id);
    try {
      await setCartQuantity(product.id, 1);
      await refreshShop();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось добавить в корзину");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <form className="card filters" onSubmit={applyFilters}>
        <label className="field">
          <span>Поиск</span>
          <input
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
            placeholder="Название или описание"
          />
        </label>
        <label className="field">
          <span>Цена от</span>
          <input
            type="number"
            min={0}
            value={draftMin}
            onChange={(event) => setDraftMin(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Цена до</span>
          <input
            type="number"
            min={0}
            value={draftMax}
            onChange={(event) => setDraftMax(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Создан с</span>
          <input
            type="date"
            value={draftCreatedFrom}
            onChange={(event) => setDraftCreatedFrom(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Создан по</span>
          <input
            type="date"
            value={draftCreatedTo}
            onChange={(event) => setDraftCreatedTo(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Сортировка</span>
          <select
            value={filters.sort_by}
            onChange={(event) => patchParams({ sort_by: event.target.value })}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Наличие</span>
          <select
            value={filters.in_stock_only ? "true" : "false"}
            onChange={(event) =>
              patchParams({ in_stock_only: event.target.value === "true" })
            }
          >
            <option value="false">Все товары</option>
            <option value="true">Только в наличии</option>
          </select>
        </label>
        <button className="btn btn--primary" type="submit">
          Найти
        </button>
      </form>

      {availableCategories.length > 0 && (
        <div className="card category-filters">
          <div className="category-filters__header">
            <span className="control-caption">Фильтр по категориям:</span>
            {filters.category_ids.length > 0 && (
              <button
                type="button"
                className="btn btn--link btn--sm"
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.delete("category_ids");
                  setParams(next);
                }}
              >
                Сбросить категории
              </button>
            )}
          </div>
          <div className="category-filters__list">
            {availableCategories.map((cat) => {
              const active = filters.category_ids.includes(cat.id);
              return (
                <button
                  key={cat.id}
                  type="button"
                  className={`btn btn--sm ${active ? "btn--primary is-active" : "btn--outline"}`}
                  onClick={() => toggleCategory(cat.id)}
                >
                  {cat.name}
                </button>
              );
            })}
          </div>
        </div>
      )}


      {error ? <p className="error">{error}</p> : null}

      {loading ? (
        <div className="grid">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index} className="skeleton" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="card empty">
          <p>В каталоге пока нет товаров.</p>
          <p className="muted" style={{ marginTop: 8 }}>
            {user?.role === "ADMIN"
              ? "Добавьте позиции в разделе «Товары»."
              : "Зарегистрируйтесь как админ и добавьте позиции в разделе «Товары»."}
          </p>
        </div>
      ) : (
        <div className="grid">
          {items.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              inFavourites={favouriteIds.has(product.id)}
              inCart={cartIds.has(product.id)}
              busy={busyId === product.id}
              onFavourite={() => void toggleFavourite(product)}
              onCart={() => void addToCart(product)}
            />
          ))}
        </div>
      )}

      {!loading && hasMore ? (
        <div className="center-actions">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={loadingMore}
            onClick={() => void loadMore()}
          >
            {loadingMore ? "Загружаем…" : "Показать ещё"}
          </button>
        </div>
      ) : null}
    </>
  );
}
