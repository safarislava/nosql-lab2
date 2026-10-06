import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { getProduct } from "../api/products";
import { addFavourite, removeFavourite, setCartQuantity } from "../api/shop";
import type { Product } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { HeartIcon } from "../components/HeartIcon";
import { formatPrice } from "../lib/format";
import { usePaths } from "../routing";

export function ProductPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const paths = usePaths();
  const { favouriteIds, cartIds, refreshShop } = useAuth();
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!productId) return;
    getProduct(productId)
      .then(setProduct)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Товар не найден");
      });
  }, [productId]);

  if (error) {
    return (
      <div className="card empty">
        <p>{error}</p>
        <p>
          <Link to={paths.catalog}>Вернуться в каталог</Link>
        </p>
      </div>
    );
  }

  if (!product) {
    return <div className="skeleton" />;
  }

  const current = product;
  const inFavourites = favouriteIds.has(current.id) || Boolean(current.is_in_favourites);
  const inCart = cartIds.has(current.id) || Boolean(current.is_in_cart);

  async function toggleFavourite() {
    setBusy(true);
    try {
      if (inFavourites) await removeFavourite(current.id);
      else await addFavourite(current.id);
      await refreshShop();
      setProduct(await getProduct(current.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось обновить избранное");
    } finally {
      setBusy(false);
    }
  }

  async function addToCart() {
    if (inCart) {
      navigate(paths.cart);
      return;
    }
    setBusy(true);
    try {
      await setCartQuantity(current.id, 1);
      await refreshShop();
      setProduct(await getProduct(current.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось добавить в корзину");
    } finally {
      setBusy(false);
    }
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return (
    <section className="detail">
      <div className="card detail__info">
        <h1>{current.name}</h1>

        {/* Категории */}
        {current.categories && current.categories.length > 0 && (
          <div className="detail__categories">
            <span className="control-caption">Категории:</span>
            <div className="category-chips">
              {current.categories.map((c) => (
                <Link
                  key={c.id ?? c.name}
                  to={c.id ? `${paths.catalog}?category_ids=${c.id}` : paths.catalog}
                  className="badge badge-category badge-category--link"
                  title={c.description || c.name}
                >
                  {c.name}
                </Link>
              ))}
            </div>
          </div>
        )}

        <div className="price">{formatPrice(current.price)}</div>
        <p>{current.description || "Без описания"}</p>
        <div className={current.is_in_stock ? "stock" : "stock stock--out"}>
          {current.is_in_stock ? `В наличии: ${current.quantity}` : "Нет в наличии"}
        </div>
        <div className="product-card__actions">
          <button
            type="button"
            className={inFavourites ? "btn btn--heart is-on" : "btn btn--heart"}
            disabled={busy}
            aria-label={inFavourites ? "Убрать из избранного" : "В избранное"}
            title={inFavourites ? "В избранном" : "В избранное"}
            onClick={() => void toggleFavourite()}
          >
            <HeartIcon filled={inFavourites} />
          </button>
          <button
            type="button"
            className={inCart ? "btn btn--primary" : "btn btn--cart"}
            disabled={busy || !current.is_in_stock}
            onClick={() => void addToCart()}
          >
            {inCart ? "В корзине" : "В корзину"}
          </button>
        </div>

        {/* Вложения товара */}
        {current.attachments && current.attachments.length > 0 && (
          <div className="detail__attachments">
            <h3>Прикрепленные файлы и документы</h3>
            <div className="attachment-list">
              {current.attachments.map((att) => (
                <div key={att.id ?? att.filename} className="attachment-item">
                  <div className="attachment-item__icon">📎</div>
                  <div className="attachment-item__meta">
                    <span className="attachment-item__name">{att.filename}</span>
                    <span className="attachment-item__info">
                      {formatFileSize(att.size_bytes ?? 0)} • {att.content_type || "файл"}
                      {att.description ? ` • ${att.description}` : ""}
                    </span>
                  </div>
                </div>
              ))}

            </div>
          </div>
        )}
      </div>
    </section>
  );

}
