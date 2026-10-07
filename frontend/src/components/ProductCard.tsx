import { Link } from "react-router-dom";
import type { Product } from "../api/types";
import { formatPrice } from "../lib/format";
import { HeartIcon } from "./HeartIcon";
import { usePaths } from "../routing";

type Props = {
  product: Product;
  inFavourites: boolean;
  inCart: boolean;
  busy?: boolean;
  onFavourite: () => void;
  onCart: () => void;
};

export function ProductCard({
  product,
  inFavourites,
  inCart,
  busy,
  onFavourite,
  onCart,
}: Props) {
  const paths = usePaths();
  const href = paths.product(product.id);
  return (
    <article className="card product-card">
      <div className="product-card__body">
        <h2>
          <Link to={href}>{product.name}</Link>
        </h2>
        {product.categories && product.categories.length > 0 && (
          <div className="product-card__categories">
            {product.categories.slice(0, 3).map((c) => (
              <span key={c.id ?? c.name} className="badge badge--category-mini">
                {c.name}
              </span>
            ))}
          </div>
        )}
        <div className="price">{formatPrice(product.price)}</div>

        <div className={product.is_in_stock ? "stock" : "stock stock--out"}>
          {product.is_in_stock ? `В наличии: ${product.quantity}` : "Нет в наличии"}
        </div>
        <div className="product-card__actions">
          <button
            type="button"
            className={inFavourites ? "btn btn--heart is-on" : "btn btn--heart"}
            disabled={busy}
            aria-label={inFavourites ? "Убрать из избранного" : "В избранное"}
            title={inFavourites ? "В избранном" : "В избранное"}
            onClick={onFavourite}
          >
            <HeartIcon filled={inFavourites} />
          </button>
          <button
            type="button"
            className={inCart ? "btn btn--primary" : "btn btn--cart"}
            disabled={busy || !product.is_in_stock}
            onClick={onCart}
          >
            {inCart ? "В корзине" : "В корзину"}
          </button>
        </div>
      </div>
    </article>
  );
}
