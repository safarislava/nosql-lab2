import { FormEvent, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  addProductAttachment,
  createProduct,
  deleteProduct,
  deleteProductAttachment,
  listProducts,
  reserveStock,
  restoreStock,
  updateProduct,
} from "../api/products";
import type {
  Product,
  ProductAttachmentInput,
  ProductCategoryInput,
} from "../api/types";
import { CategorySelector } from "../components/CategorySelector";
import { generateRandomAttachment } from "../lib/attachmentGenerator";
import { formatBytes, formatPrice } from "../lib/format";

type SavedProduct = {
  name: string;
  description: string;
  price: string;
  quantity: number;
  categories: ProductCategoryInput[];
};

function isDirty(product: Product, saved: SavedProduct | undefined): boolean {
  if (!saved) return false;
  const catsChanged =
    JSON.stringify((product.categories || []).map((c) => c.name)) !==
    JSON.stringify((saved.categories || []).map((c) => c.name));
  return (
    saved.name !== product.name ||
    saved.description !== product.description ||
    saved.price !== product.price ||
    saved.quantity !== product.quantity ||
    catsChanged
  );
}

export function AdminProductsPage() {
  const [items, setItems] = useState<Product[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [saved, setSaved] = useState<Record<string, SavedProduct>>({});
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
  const [loading, setLoading] = useState(true);

  // Фильтрация и пагинация для админа
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(50);

  // Форма создания товара
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [quantity, setQuantity] = useState("0");
  const [createCategories, setCreateCategories] = useState<ProductCategoryInput[]>([]);
  const [createAttachments, setCreateAttachments] = useState<ProductAttachmentInput[]>([]);

  // Поле для ручного добавления вложения в форму создания
  const [manualAttFilename, setManualAttFilename] = useState("");
  const [manualAttDesc, setManualAttDesc] = useState("");

  // Состояние развернутых секций для редактирования
  const [expandedCats, setExpandedCats] = useState<Record<string, boolean>>({});
  const [expandedAtts, setExpandedAtts] = useState<Record<string, boolean>>({});

  // Новое вложение для существующего товара
  const [newAttFilename, setNewAttFilename] = useState<Record<string, string>>({});

  async function load() {
    setLoading(true);
    try {
      const result = await listProducts({
        query: searchQuery.trim() || undefined,
        offset: page * limit,
        limit,
        sort_by: "name_asc",
      });
      setItems(result.items);
      setHasMore(result.items.length === limit);
      setSaved(
        Object.fromEntries(
          result.items.map((item) => [
            item.id,
            {
              name: item.name,
              description: item.description,
              price: item.price,
              quantity: item.quantity,
              categories: item.categories || [],
            },
          ]),
        ),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось загрузить товары");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [page, limit]);

  function handleSearchSubmit(e: FormEvent) {
    e.preventDefault();
    setPage(0);
    void load();
  }

  // Генерация случайного вложения для формы создания товара
  function handleGenerateRandomAttachmentForCreate() {
    const randomAttachment = generateRandomAttachment();
    setCreateAttachments((prev) => [...prev, randomAttachment]);
  }

  // Ручное добавление вложения в форму создания товара
  function handleAddManualAttachmentForCreate() {
    const filename = manualAttFilename.trim();
    if (!filename) return;
    setCreateAttachments((prev) => [
      ...prev,
      {
        filename,
        content_type: "application/octet-stream",
        size_bytes: 2048,
        description: manualAttDesc.trim() || "Пользовательский файл",
      },
    ]);
    setManualAttFilename("");
    setManualAttDesc("");
  }

  function handleRemoveCreateAttachment(index: number) {
    setCreateAttachments((prev) => prev.filter((_, i) => i !== index));
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setError("");
    setWarning("");
    try {
      const created = await createProduct({
        name,
        description,
        price,
        quantity: Number(quantity) || 0,
        categories: createCategories.length > 0 ? createCategories : undefined,
        attachments: createAttachments.length > 0 ? createAttachments : undefined,
      });

      // Мгновенно отображаем созданный товар во главе списка и фиксируем baseline
      setItems((prev) => [created, ...prev.filter((p) => p.id !== created.id)]);
      setSaved((prev) => ({
        ...prev,
        [created.id]: {
          name: created.name,
          description: created.description,
          price: created.price,
          quantity: created.quantity,
          categories: created.categories || [],
        },
      }));

      // Проверка применения категорий (_resolve_v2_category_ids)
      if (createCategories.length > 0) {
        const appliedNames = new Set(
          (created.categories || []).map((c) => c.name.toLowerCase()),
        );
        const unapplied = createCategories.filter(
          (c) => !appliedNames.has(c.name.toLowerCase()),
        );
        if (unapplied.length > 0) {
          setWarning(
            `Внимание: категория(и) "${unapplied.map((c) => c.name).join(", ")}" не применились к товару. В схеме v2 категория должна существовать в базе или иметь корректные name/slug.`,
          );
        }
      }

      setName("");
      setDescription("");
      setPrice("");
      setQuantity("0");
      setCreateCategories([]);
      setCreateAttachments([]);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Конфликт версий CouchDB (409 Conflict). Пожалуйста, обновите список товаров.");
      } else {
        setError(err instanceof ApiError ? err.message : "Не удалось создать товар");
      }
    }
  }

  async function onSave(product: Product) {
    setError("");
    setWarning("");
    try {
      const updated = await updateProduct(product.id, {
        name: product.name,
        description: product.description,
        price: product.price,
        quantity: product.quantity,
        categories: product.categories,
      });

      // Мгновенно обновляем товар в локальном состоянии и сбрасываем dirty-флаг
      setItems((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item)),
      );
      setSaved((prev) => ({
        ...prev,
        [updated.id]: {
          name: updated.name,
          description: updated.description,
          price: updated.price,
          quantity: updated.quantity,
          categories: updated.categories || [],
        },
      }));

      // Проверка применения категорий при обновлении
      if (product.categories && product.categories.length > 0) {
        const appliedNames = new Set(
          (updated.categories || []).map((c) => c.name.toLowerCase()),
        );
        const unapplied = product.categories.filter(
          (c) => !appliedNames.has(c.name.toLowerCase()),
        );
        if (unapplied.length > 0) {
          setWarning(
            `Внимание: категория(и) "${unapplied.map((c) => c.name).join(", ")}" не применились к товару "${product.name}".`,
          );
        }
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(
          "Конфликт версий документа (409 Conflict). Другой администратор изменил товар. Обновите страницу.",
        );
      } else {
        setError(err instanceof ApiError ? err.message : "Не удалось сохранить");
      }
    }
  }

  function onReset(productId: string) {
    const orig = saved[productId];
    if (!orig) return;
    patch(productId, {
      name: orig.name,
      description: orig.description,
      price: orig.price,
      quantity: orig.quantity,
      categories: [...orig.categories],
    });
  }

  async function onDelete(productId: string) {
    if (!window.confirm("Вы уверены, что хотите удалить товар?")) return;
    try {
      await deleteProduct(productId);
      setItems((prev) => prev.filter((item) => item.id !== productId));
      setSaved((prev) => {
        const next = { ...prev };
        delete next[productId];
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось удалить");
    }
  }

  function patch(id: string, patchValue: Partial<Product>) {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patchValue } : item)),
    );
  }

  async function onAddAttachment(productId: string) {
    const filename = (newAttFilename[productId] || "").trim();
    if (!filename) return;
    try {
      const added = await addProductAttachment(productId, {
        filename,
        content_type: "application/octet-stream",
        size_bytes: 1024,
      });
      setNewAttFilename((prev) => ({ ...prev, [productId]: "" }));
      setItems((prev) =>
        prev.map((item) =>
          item.id === productId
            ? { ...item, attachments: [...(item.attachments || []), added] }
            : item,
        ),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось прикрепить файл");
    }
  }

  async function onGenerateRandomAttachmentForProduct(productId: string) {
    try {
      const generated = generateRandomAttachment();
      const added = await addProductAttachment(productId, generated);
      setItems((prev) =>
        prev.map((item) =>
          item.id === productId
            ? { ...item, attachments: [...(item.attachments || []), added] }
            : item,
        ),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сгенерировать вложение");
    }
  }

  async function onDeleteAttachment(productId: string, attachmentId: string) {
    try {
      await deleteProductAttachment(productId, attachmentId);
      setItems((prev) =>
        prev.map((item) =>
          item.id === productId
            ? {
                ...item,
                attachments: (item.attachments || []).filter((a) => a.id !== attachmentId),
              }
            : item,
        ),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось удалить файл");
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Товары</h1>
          <span className="muted">
            Страница {page + 1} (показано на странице: {items.length} товаров)
          </span>
        </div>
      </div>

      {error ? <div className="notice notice--error">{error}</div> : null}
      {warning ? <div className="notice notice--warning">{warning}</div> : null}

      {/* Форма создания товара */}
      <form className="card admin-create-card" onSubmit={onCreate}>
        <div className="admin-create-card__header">
          <h3>Добавить новый товар</h3>
          <span className="muted">Заполните поля, чтобы добавить товар в базу данных</span>
        </div>

        <div className="admin-create-fields">
          <label className="field">
            <span>Название товара *</span>
            <input
              required
              placeholder="Название товара"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Краткое описание</span>
            <input
              placeholder="Описание товара"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Цена (₽) *</span>
            <input
              required
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Остаток на складе</span>
            <input
              type="number"
              min="0"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
            />
          </label>
        </div>

        {/* Выбор категорий при создании */}
        <div className="admin-create-section">
          <CategorySelector
            selectedCategories={createCategories}
            onChange={setCreateCategories}
          />
        </div>

        {/* Секция вложений при создании товара (с генератором эмуляции) */}
        <div className="admin-create-section admin-attachments-section">
          <div className="admin-section-header">
            <span className="control-caption">
              Вложения товара ({createAttachments.length}):
            </span>
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              onClick={handleGenerateRandomAttachmentForCreate}
              title="Сгенерировать случайное вложение (PDF, изображение, спецификация и т.д.)"
            >
              🎲 Сгенерировать случайное вложение
            </button>
          </div>

          {createAttachments.length > 0 ? (
            <div className="attachment-chips-list">
              {createAttachments.map((att, idx) => (
                <div key={idx} className="attachment-chip">
                  <span className="attachment-chip__title">📎 {att.filename}</span>
                  <span className="attachment-chip__meta">
                    ({formatBytes(att.size_bytes || 0)} · {att.description || att.content_type})
                  </span>
                  <button
                    type="button"
                    className="badge-remove-btn"
                    onClick={() => handleRemoveCreateAttachment(idx)}
                    title="Удалить"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <span className="muted" style={{ fontSize: 13, display: "block", margin: "6px 0" }}>
              Вложения не выбраны. Вы можете сгенерировать случайный файл или добавить вручную ниже.
            </span>
          )}

          {/* Ручное добавление файла в форму создания */}
          <div className="add-att-row" style={{ marginTop: 10 }}>
            <input
              type="text"
              className="input input--sm"
              style={{ flex: 1 }}
              placeholder="Имя файла (напр. manual.pdf)"
              value={manualAttFilename}
              onChange={(e) => setManualAttFilename(e.target.value)}
            />
            <input
              type="text"
              className="input input--sm"
              style={{ flex: 1.5 }}
              placeholder="Описание файла (напр. Инструкция)"
              value={manualAttDesc}
              onChange={(e) => setManualAttDesc(e.target.value)}
            />
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={handleAddManualAttachmentForCreate}
            >
              + Добавить
            </button>
          </div>
        </div>

        <div className="admin-create-actions">
          <button className="btn btn--primary" type="submit">
            Создать товар
          </button>
        </div>
      </form>

      {/* Панель поиска и фильтрации каталога для админа */}
      <form className="card admin-search-card" onSubmit={handleSearchSubmit}>
        <label className="field" style={{ flex: 1, margin: 0 }}>
          <span>Поиск по каталогу</span>
          <input
            placeholder="Введите название или описание для поиска..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </label>
        <label className="field" style={{ width: 140, margin: 0 }}>
          <span>На страницу</span>
          <select
            value={limit}
            onChange={(e) => {
              setLimit(Number(e.target.value));
              setPage(0);
            }}
          >
            <option value="20">20 товаров</option>
            <option value="50">50 товаров</option>
            <option value="100">100 товаров</option>
          </select>
        </label>
        <button type="submit" className="btn btn--primary">
          Найти
        </button>
      </form>

      {/* Пагинация */}
      {(page > 0 || hasMore) && (
        <div className="pagination" style={{ margin: "12px 0" }}>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            ← Предыдущая
          </button>
          <span className="muted">
            Страница {page + 1}
          </span>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={!hasMore}
            onClick={() => setPage((p) => p + 1)}
          >
            Следующая →
          </button>
        </div>
      )}

      {loading ? <div className="skeleton" /> : null}

      {!loading && items.length === 0 && (
        <div className="card" style={{ padding: 24, textAlign: "center" }}>
          <p className="muted">Товары не найдены.</p>
        </div>
      )}

      {/* Список товаров для редактирования */}
      <div className="list">
        {items.map((product) => {
          const dirty = isDirty(product, saved[product.id]);
          const catsOpen = expandedCats[product.id];
          const attsOpen = expandedAtts[product.id];

          return (
            <article
              key={product.id}
              className={dirty ? "card card--dirty" : "card"}
              style={{ padding: 18 }}
            >
              {/* Верхняя строка: Название, текущая цена и кнопки действий */}
              <div className="row" style={{ padding: 0 }}>
                <div className="row__main" style={{ gap: 10 }}>
                  <label className="field" style={{ flex: 1, margin: 0 }}>
                    <span className="muted" style={{ fontSize: 12 }}>Название товара</span>
                    <input
                      className="input"
                      value={product.name}
                      onChange={(event) => patch(product.id, { name: event.target.value })}
                    />
                  </label>
                  <span className="muted" style={{ alignSelf: "center", whiteSpace: "nowrap" }}>
                    {formatPrice(product.price)} · ID: {product.id}
                  </span>
                </div>
                <div className="row__actions">
                  {dirty ? <span className="unsaved">Не сохранено</span> : null}
                  <button
                    type="button"
                    className={dirty ? "btn btn--primary" : "btn btn--ghost"}
                    disabled={!dirty}
                    onClick={() => void onSave(product)}
                  >
                    Сохранить
                  </button>
                  {dirty && (
                    <button
                      type="button"
                      className="btn btn--secondary btn--sm"
                      onClick={() => onReset(product.id)}
                      title="Отменить несохраненные изменения"
                    >
                      Сброс
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn--danger"
                    onClick={() => void onDelete(product.id)}
                  >
                    Удалить
                  </button>
                </div>
              </div>

              {/* Вторая строка: Описание, Цена, Остаток на складе */}
              <div className="row admin-product-details-row" style={{ padding: "12px 0 0", gap: 12 }}>
                <label className="field" style={{ flex: 2, margin: 0 }}>
                  <span className="muted" style={{ fontSize: 12 }}>Описание товара</span>
                  <input
                    className="input"
                    value={product.description}
                    onChange={(event) => patch(product.id, { description: event.target.value })}
                    placeholder="Описание товара"
                  />
                </label>
                <label className="field" style={{ width: 140, margin: 0 }}>
                  <span className="muted" style={{ fontSize: 12 }}>Цена (₽)</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    className="input"
                    value={product.price}
                    onChange={(event) => patch(product.id, { price: event.target.value })}
                  />
                </label>
                <label className="field" style={{ width: 180, margin: 0 }}>
                  <span className="muted" style={{ fontSize: 12 }}>Остаток на складе</span>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input
                      type="number"
                      min="0"
                      className="input"
                      style={{ width: 70 }}
                      value={product.quantity}
                      onChange={(event) =>
                        patch(product.id, { quantity: Number(event.target.value) || 0 })
                      }
                    />
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      onClick={async () => {
                        try {
                          const updated = await reserveStock(product.id, 1);
                          setItems((prev) =>
                            prev.map((item) => (item.id === updated.id ? updated : item)),
                          );
                          setSaved((prev) => ({
                            ...prev,
                            [updated.id]: {
                              ...(prev[updated.id] || {
                                name: updated.name,
                                description: updated.description,
                                price: updated.price,
                                categories: updated.categories || [],
                              }),
                              quantity: updated.quantity,
                            },
                          }));
                        } catch (err) {
                          setError(err instanceof ApiError ? err.message : "Не удалось уменьшить остаток");
                        }
                      }}
                      title="Уменьшить остаток на 1"
                    >
                      −1
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      onClick={async () => {
                        try {
                          const updated = await restoreStock(product.id, 1);
                          setItems((prev) =>
                            prev.map((item) => (item.id === updated.id ? updated : item)),
                          );
                          setSaved((prev) => ({
                            ...prev,
                            [updated.id]: {
                              ...(prev[updated.id] || {
                                name: updated.name,
                                description: updated.description,
                                price: updated.price,
                                categories: updated.categories || [],
                              }),
                              quantity: updated.quantity,
                            },
                          }));
                        } catch (err) {
                          setError(err instanceof ApiError ? err.message : "Не удалось увеличить остаток");
                        }
                      }}
                      title="Увеличить остаток на 1"
                    >
                      +1
                    </button>
                  </div>
                </label>
              </div>

              {/* Секция категорий товара */}
              <div className="admin-product__sub-block">
                <div className="sub-block__header">
                  <span className="control-caption">
                    Категории ({product.categories?.length || 0}):
                  </span>
                  <button
                    type="button"
                    className="btn btn--link btn--sm"
                    onClick={() =>
                      setExpandedCats((prev) => ({ ...prev, [product.id]: !prev[product.id] }))
                    }
                  >
                    {catsOpen ? "Скрыть редактор" : "Редактировать категории"}
                  </button>
                </div>

                {!catsOpen ? (
                  <div className="category-chips">
                    {(product.categories || []).map((c, i) => (
                      <span key={c.id ?? `${c.name}-${i}`} className="badge badge-category">
                        {c.name}
                        {c.slug ? <small> ({c.slug})</small> : null}
                      </span>
                    ))}
                    {!product.categories?.length && (
                      <span className="muted">Категории не назначены</span>
                    )}
                  </div>
                ) : (
                  <div style={{ marginTop: 8 }}>
                    <CategorySelector
                      selectedCategories={product.categories || []}
                      onChange={(newCats) => patch(product.id, { categories: newCats })}
                    />
                  </div>
                )}
              </div>

              {/* Секция вложений товара */}
              <div className="admin-product__sub-block">
                <div className="sub-block__header">
                  <span className="control-caption">
                    Вложения ({product.attachments?.length || 0}):
                  </span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      className="btn btn--secondary btn--sm"
                      onClick={() => void onGenerateRandomAttachmentForProduct(product.id)}
                      title="Сгенерировать и прикрепить случайный файл"
                    >
                      🎲 + Случайный файл
                    </button>
                    <button
                      type="button"
                      className="btn btn--link btn--sm"
                      onClick={() =>
                        setExpandedAtts((prev) => ({ ...prev, [product.id]: !prev[product.id] }))
                      }
                    >
                      {attsOpen ? "Скрыть файлы" : "Управление файлами"}
                    </button>
                  </div>
                </div>

                {attsOpen && (
                  <div className="admin-attachments-box">
                    <div className="attachment-list">
                      {(product.attachments || []).map((att) => (
                        <div key={att.id ?? att.filename} className="attachment-item">
                          <span className="attachment-item__name">📎 {att.filename}</span>
                          <span className="attachment-item__info">
                            {formatBytes(att.size_bytes || 0)} · {att.content_type}
                            {att.description ? ` · ${att.description}` : ""}
                          </span>
                          {att.id && (
                            <button
                              type="button"
                              className="btn btn--danger btn--sm"
                              style={{ marginLeft: "auto" }}
                              onClick={() => void onDeleteAttachment(product.id, att.id!)}
                            >
                              Удалить
                            </button>
                          )}
                        </div>
                      ))}
                      {!product.attachments?.length && (
                        <span className="muted" style={{ padding: "6px 0" }}>
                          Вложений нет.
                        </span>
                      )}
                    </div>
                    <div className="add-att-row">
                      <input
                        type="text"
                        className="input input--sm"
                        placeholder="Имя файла (напр. manual.pdf)"
                        value={newAttFilename[product.id] || ""}
                        onChange={(e) =>
                          setNewAttFilename((prev) => ({ ...prev, [product.id]: e.target.value }))
                        }
                      />
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        onClick={() => void onAddAttachment(product.id)}
                      >
                        + Прикрепить файл
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </div>

      {/* Пагинация внизу списка */}
      {(page > 0 || hasMore) && (
        <div className="pagination" style={{ margin: "16px 0" }}>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            ← Предыдущая
          </button>
          <span className="muted">
            Страница {page + 1}
          </span>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={!hasMore}
            onClick={() => setPage((p) => p + 1)}
          >
            Следующая →
          </button>
        </div>
      )}
    </>
  );
}
