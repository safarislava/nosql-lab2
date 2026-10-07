import { useState } from "react";
import { ApiError } from "../api/client";
import { getProductAnalytics } from "../api/products";
import type { ProductAnalytics, ProductStockState } from "../api/types";

const STATE_LABEL: Record<ProductStockState, string> = {
  in_stock: "В наличии",
  out_of_stock: "Нет в наличии",
};

const STATE_ORDER: ProductStockState[] = ["in_stock", "out_of_stock"];

function formatAverage(value: number): string {
  return value.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

export function AdminAnalyticsPage() {
  const [result, setResult] = useState<ProductAnalytics | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function calculate() {
    setError("");
    setLoading(true);
    try {
      setResult(await getProductAnalytics());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось посчитать аналитику");
    } finally {
      setLoading(false);
    }
  }

  const byState = new Map(result?.by_state.map((item) => [item.state, item]));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Аналитика</h1>
          <p className="muted">Среднее число правок товара по наличию</p>
        </div>
        <button
          type="button"
          className="btn btn--primary"
          disabled={loading}
          onClick={() => void calculate()}
        >
          {loading ? "Считаем…" : "Посчитать"}
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {result ? (
        <div className="analytics-grid">
          {STATE_ORDER.map((state) => {
            const item = byState.get(state);
            return (
              <article key={state} className="card analytics-card">
                <h2>{STATE_LABEL[state]}</h2>
                <strong className="analytics-card__value">
                  {item ? formatAverage(item.average_changes) : "—"}
                </strong>
                <p className="muted">
                  {item
                    ? `Товаров: ${item.product_count}`
                    : "Нет данных по этому состоянию"}
                </p>
              </article>
            );
          })}
        </div>
      ) : null}
    </>
  );
}
