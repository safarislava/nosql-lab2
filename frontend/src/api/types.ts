export type UserRole = "STUDENT" | "TEACHER" | "ADMIN";

export type User = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
};

export type Category = {
  id: string;
  name: string;
  slug?: string;
  description?: string;
};

export type Attachment = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  order: number;
  upload_date: string;
  checksum?: string;
  description?: string;
};

export type ProductCategoryInput = {
  id?: string;
  name: string;
  slug?: string;
  description?: string;
};

export type ProductAttachmentInput = {
  id?: string;
  filename: string;
  content_type?: string;
  size_bytes?: number;
  order?: number;
  checksum?: string;
  description?: string;
};

export type Product = {
  id: string;
  name: string;
  description: string;
  price: string;
  quantity: number;
  is_in_stock: boolean;
  is_in_cart?: boolean;
  is_in_favourites?: boolean;
  categories?: (Category | ProductCategoryInput)[];
  attachments?: (Attachment | ProductAttachmentInput)[];
};


export type ProductList = {
  items: Product[];
  offset: number;
  limit: number;
};

export type ProductSortBy =
  | "popularity"
  | "price_asc"
  | "price_desc"
  | "name_asc"
  | "name_desc"
  | "newest";

export type FavouriteItem = {
  product_id: string;
  added_user_id: string;
  updated_at: string;
  product: Product | null;
  is_available: boolean;
};

export type Favourites = {
  user_id: string;
  products: FavouriteItem[];
  total_count: number;
};

export type CartItem = {
  product_id: string;
  quantity: number;
  updated_at: string;
  product: Product | null;
  subtotal: string;
  is_available: boolean;
  available_stock: number;
};

export type Cart = {
  user_id: string;
  items: CartItem[];
  total_items: number;
  total_amount: string;
  has_unavailable_items: boolean;
};

export type OrderStatus = "CREATED" | "APPROVED" | "REJECTED" | "CANCELLED";

export type Order = {
  id: string;
  user_id: string;
  product_id: string;
  quantity: number;
  unit_price: string;
  total_amount: string;
  status: OrderStatus;
  created_at: string;
  product_snapshot: {
    id: string;
    name: string;
    description: string;
    price: string;
  };
};

export type OrderList = {
  items: Order[];
  offset: number;
  limit: number;
  total_orders_count: number;
};



export type CheckoutResult = {
  orders: Order[];
  total_orders: number;
  total_amount: string;
};

export type TeacherProfile = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  student_ids: string[];
  students: User[];
  total_students: number;
};

export type RecoveryToken = {
  token: string;
  user_id: string;
  created_at: string;
  expires_at: string;
  is_expired: boolean;
};
