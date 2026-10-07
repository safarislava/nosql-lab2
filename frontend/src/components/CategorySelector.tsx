import { useEffect, useRef, useState } from "react";
import {
  CATEGORY_PRESETS,
  detectSchemaVersion,
  generateSlug,
  isUuid,
  searchCategories,
} from "../api/categories";
import type { Category, ProductCategoryInput } from "../api/types";

type Props = {
  selectedCategories: ProductCategoryInput[];
  onChange: (categories: ProductCategoryInput[]) => void;
  disabled?: boolean;
};

export function CategorySelector({
  selectedCategories,
  onChange,
  disabled,
}: Props) {
  const [schemaVersion, setSchemaVersion] = useState<1 | 2>(2);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Category[]>([]);
  const [searching, setSearching] = useState(false);

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Произвольный ввод новой категории
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customSlug, setCustomSlug] = useState("");
  const [customDesc, setCustomDesc] = useState("");
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    detectSchemaVersion().then(setSchemaVersion);
  }, []);

  // Закрытие выпадающего списка при клике вне компонента
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Поиск категорий в v2 с дебаунсом
  useEffect(() => {
    if (schemaVersion !== 2) return;
    let cancelled = false;
    setSearching(true);
    const timeout = setTimeout(() => {
      searchCategories(searchQuery)
        .then((cats) => {
          if (!cancelled) setSearchResults(cats);
        })
        .catch(() => {
          if (!cancelled) setSearchResults([]);
        })
        .finally(() => {
          if (!cancelled) setSearching(false);
        });
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [searchQuery, schemaVersion]);

  function handleNameChange(name: string) {
    setCustomName(name);
    if (!slugManuallyEdited) {
      setCustomSlug(generateSlug(name));
    }
  }

  function handleSelectExisting(cat: Category | ProductCategoryInput) {
    // Проверка на дубликат по ID или названию
    const exists = selectedCategories.some(
      (c) =>
        (cat.id && c.id === cat.id) ||
        c.name.toLowerCase() === cat.name.toLowerCase(),
    );
    if (exists) return;

    onChange([
      ...selectedCategories,
      {
        id: isUuid(cat.id) ? cat.id : undefined,
        name: cat.name,
        slug: cat.slug || generateSlug(cat.name),
        description: cat.description || "",
      },
    ]);
  }

  function handleRemove(index: number) {
    onChange(selectedCategories.filter((_, i) => i !== index));
  }

  function handleAddCustom() {
    setFormError("");
    const trimmedName = customName.trim();
    const trimmedSlug = customSlug.trim() || generateSlug(trimmedName);

    if (!trimmedName) {
      setFormError("Укажите название категории.");
      return;
    }

    if (schemaVersion === 2 && !trimmedSlug) {
      setFormError("В версии 2 поле slug обязательно для сохранения в базе.");
      return;
    }

    const exists = selectedCategories.some(
      (c) => c.name.toLowerCase() === trimmedName.toLowerCase(),
    );
    if (exists) {
      setFormError("Эта категория уже добавлена.");
      return;
    }

    onChange([
      ...selectedCategories,
      {
        name: trimmedName,
        slug: trimmedSlug,
        description: customDesc.trim(),
      },
    ]);

    setCustomName("");
    setCustomSlug("");
    setCustomDesc("");
    setSlugManuallyEdited(false);
    setShowCustomForm(false);
  }

  return (
    <div className="category-selector">
      <div className="category-selector__header">
        <label className="field-label">Категории товара</label>
        <span className="badge badge--info">
          {schemaVersion === 2 ? "Схема v2 (CouchDB)" : "Схема v1 (Пресеты)"}
        </span>
      </div>

      {/* Список уже прикрепленных категорий */}
      <div className="category-chips">
        {selectedCategories.length === 0 ? (
          <span className="category-chips__empty">Категории не выбраны</span>
        ) : (
          selectedCategories.map((cat, idx) => (
            <span key={cat.id ?? `${cat.name}-${idx}`} className="badge badge-category">
              <strong>{cat.name}</strong>
              {cat.slug ? <small> ({cat.slug})</small> : null}
              {!disabled && (
                <button
                  type="button"
                  className="badge-remove-btn"
                  onClick={() => handleRemove(idx)}
                  title="Удалить категорию"
                >
                  ×
                </button>
              )}
            </span>
          ))
        )}
      </div>

      {!disabled && (
        <div className="category-selector__controls">
          {schemaVersion === 1 ? (
            /* Режим v1: выбор из пресетов */
            <div className="preset-selector">
              <span className="control-caption">Выберите из пресетов:</span>
              <div className="preset-buttons">
                {CATEGORY_PRESETS.map((p) => {
                  const isSelected = selectedCategories.some(
                    (c) => c.name.toLowerCase() === p.name.toLowerCase(),
                  );
                  return (
                    <button
                      key={p.id}
                      type="button"
                      className={`btn btn--sm ${isSelected ? "btn--secondary is-selected" : "btn--outline"}`}
                      disabled={isSelected}
                      onClick={() => handleSelectExisting(p)}
                    >
                      + {p.name}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Режим v2: поиск из базы categories_db */
            <div className="db-category-search" ref={containerRef}>
              <input
                type="text"
                className="input input--sm"
                placeholder="Поиск по существующим категориям..."
                value={searchQuery}
                onFocus={() => setIsDropdownOpen(true)}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setIsDropdownOpen(true);
                }}
              />
              {searching && <span className="search-spinner">Поиск...</span>}
              {isDropdownOpen && searchResults.length > 0 && (
                <div className="search-dropdown">
                  {searchResults.map((cat) => {
                    const isSelected = selectedCategories.some(
                      (c) => (cat.id && c.id === cat.id) || c.name.toLowerCase() === cat.name.toLowerCase(),
                    );
                    return (
                      <div
                        key={cat.id}
                        className={`search-dropdown__item ${isSelected ? "is-selected" : ""}`}
                        onClick={() => {
                          if (!isSelected) {
                            handleSelectExisting(cat);
                            setIsDropdownOpen(false);
                            setSearchQuery("");
                          }
                        }}
                      >
                        <span className="item-name">{cat.name}</span>
                        <span className="item-slug">/{cat.slug}</span>
                        {isSelected && <span className="item-status">✓ добавлена</span>}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Кнопка и форма добавления произвольной категории */}
          <div className="custom-category-toggle">
            {!showCustomForm ? (
              <button
                type="button"
                className="btn btn--link btn--sm"
                onClick={() => setShowCustomForm(true)}
              >
                + Ввести произвольную категорию
              </button>
            ) : (
              <div className="custom-category-box">
                <h4>Новая категория</h4>
                {formError && <div className="notice notice--error">{formError}</div>}
                <div className="custom-fields">
                  <input
                    type="text"
                    className="input input--sm"
                    placeholder="Название (напр. 'Смарт-часы')"
                    value={customName}
                    onChange={(e) => handleNameChange(e.target.value)}
                  />
                  <input
                    type="text"
                    className="input input--sm"
                    placeholder="Slug (напр. 'smart-watches')"
                    value={customSlug}
                    onChange={(e) => {
                      setCustomSlug(e.target.value);
                      setSlugManuallyEdited(true);
                    }}
                  />
                  <input
                    type="text"
                    className="input input--sm"
                    placeholder="Описание (необязательно)"
                    value={customDesc}
                    onChange={(e) => setCustomDesc(e.target.value)}
                  />
                </div>
                <div className="custom-actions">
                  <button
                    type="button"
                    className="btn btn--primary btn--sm"
                    onClick={handleAddCustom}
                  >
                    Добавить
                  </button>
                  <button
                    type="button"
                    className="btn btn--secondary btn--sm"
                    onClick={() => {
                      setShowCustomForm(false);
                      setFormError("");
                    }}
                  >
                    Отмена
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
