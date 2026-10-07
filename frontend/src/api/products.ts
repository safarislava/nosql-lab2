import { api } from "./client";
import { isUuid } from "./categories";
import type {
  Attachment,
  Category,
  Product,
  ProductAttachmentInput,
  ProductCategoryInput,
  ProductAnalytics,
  ProductList,
  ProductSortBy,
} from "./types";

export const PAGE_SIZE = 12;

function sanitizeCategories(
  categories?: ProductCategoryInput[],
): ProductCategoryInput[] | undefined {
  if (!categories) return undefined;
  return categories.map((c) => ({
    id: isUuid(c.id) ? c.id : undefined,
    name: c.name,
    slug: c.slug,
    description: c.description,
  }));
}

function sanitizeAttachments(
  attachments?: ProductAttachmentInput[],
): ProductAttachmentInput[] | undefined {
  if (!attachments) return undefined;
  return attachments.map((a) => ({
    id: isUuid(a.id) ? a.id : undefined,
    filename: a.filename,
    content_type: a.content_type,
    size_bytes: a.size_bytes,
    order: a.order,
    checksum: a.checksum,
    description: a.description,
  }));
}

export type ProductQuery = {
  query?: string;
  min_price?: string;
  max_price?: string;
  in_stock_only?: boolean;
  sort_by?: ProductSortBy;
  category_ids?: string[];
  offset?: number;
  limit?: number;
};

export function listProducts(params: ProductQuery): Promise<ProductList> {
  const search = new URLSearchParams();
  if (params.query) search.set("query", params.query);
  if (params.min_price) search.set("min_price", params.min_price);
  if (params.max_price) search.set("max_price", params.max_price);
  if (params.in_stock_only) search.set("in_stock_only", "true");
  search.set("sort_by", params.sort_by ?? "popularity");
  search.set("offset", String(params.offset ?? 0));
  search.set("limit", String(params.limit ?? PAGE_SIZE));
  search.set("_t", String(Date.now()));
  if (params.category_ids && params.category_ids.length > 0) {
    for (const cid of params.category_ids) {
      search.append("category_ids", cid);
    }
  }
  return api<ProductList>(`/api/products?${search.toString()}`, {
    cache: "no-store",
    headers: { "Cache-Control": "no-cache" },
  });
}

export function getProduct(productId: string): Promise<Product> {
  return api<Product>(`/api/products/${productId}?_t=${Date.now()}`, {
    cache: "no-store",
    headers: { "Cache-Control": "no-cache" },
  });
}

export function createProduct(payload: {
  name: string;
  description: string;
  price: string;
  quantity: number;
  categories?: ProductCategoryInput[];
  attachments?: ProductAttachmentInput[];
}): Promise<Product> {
  const sanitized = {
    ...payload,
    categories: sanitizeCategories(payload.categories),
    attachments: sanitizeAttachments(payload.attachments),
  };
  return api<Product>("/api/products", {
    method: "POST",
    body: JSON.stringify(sanitized),
  });
}

export function updateProduct(
  productId: string,
  payload: {
    name?: string;
    description?: string;
    price?: string;
    quantity?: number;
    categories?: ProductCategoryInput[];
    attachments?: ProductAttachmentInput[];
  },
): Promise<Product> {
  const sanitized = {
    ...payload,
    categories: sanitizeCategories(payload.categories),
    attachments: sanitizeAttachments(payload.attachments),
  };
  return api<Product>(`/api/products/${productId}`, {
    method: "PATCH",
    body: JSON.stringify(sanitized),
  });
}

export function deleteProduct(productId: string): Promise<void> {
  return api<void>(`/api/products/${productId}`, { method: "DELETE" });
}

// Суб-эндпоинты категорий товара
export function listProductCategories(productId: string): Promise<Category[]> {
  return api<Category[]>(`/api/products/${productId}/categories`);
}

export function addProductCategory(
  productId: string,
  payload: ProductCategoryInput,
): Promise<Category> {
  const sanitized = {
    ...payload,
    id: isUuid(payload.id) ? payload.id : undefined,
  };
  return api<Category>(`/api/products/${productId}/categories`, {
    method: "POST",
    body: JSON.stringify(sanitized),
  });
}

export function updateProductCategory(
  productId: string,
  categoryId: string,
  payload: Partial<ProductCategoryInput>,
): Promise<Category> {
  return api<Category>(`/api/products/${productId}/categories/${categoryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteProductCategory(
  productId: string,
  categoryId: string,
): Promise<void> {
  return api<void>(`/api/products/${productId}/categories/${categoryId}`, {
    method: "DELETE",
  });
}

// Суб-эндпоинты вложений товара
export function listProductAttachments(productId: string): Promise<Attachment[]> {
  return api<Attachment[]>(`/api/products/${productId}/attachments`);
}

export function addProductAttachment(
  productId: string,
  payload: ProductAttachmentInput,
): Promise<Attachment> {
  const sanitized = {
    ...payload,
    id: isUuid(payload.id) ? payload.id : undefined,
  };
  return api<Attachment>(`/api/products/${productId}/attachments`, {
    method: "POST",
    body: JSON.stringify(sanitized),
  });
}

export function updateProductAttachment(
  productId: string,
  attachmentId: string,
  payload: Partial<ProductAttachmentInput>,
): Promise<Attachment> {
  return api<Attachment>(`/api/products/${productId}/attachments/${attachmentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteProductAttachment(
  productId: string,
  attachmentId: string,
): Promise<void> {
  return api<void>(`/api/products/${productId}/attachments/${attachmentId}`, {
    method: "DELETE",
  });
}


export function reserveStock(productId: string, amount: number): Promise<Product> {
  return api<Product>(`/api/products/${productId}/reserve`, {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
}

export function restoreStock(productId: string, amount: number): Promise<Product> {
  return api<Product>(`/api/products/${productId}/restore`, {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
}

export function getProductAnalytics(): Promise<ProductAnalytics> {
  return api<ProductAnalytics>("/api/products/analytics");
}
