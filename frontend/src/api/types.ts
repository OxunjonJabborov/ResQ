// Types mirror the DRF serializers (see /api/docs/ for the full schema).

export type Lang = 'uz' | 'ru'

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface City {
  id: number
  slug: string
  name: string
  name_uz: string
  name_ru: string
  latitude: string
  longitude: string
}

export type VerificationStatus = 'pending' | 'verified' | 'rejected'

export interface User {
  id: number
  phone: string
  first_name: string
  last_name: string
  email: string
  language: Lang
  city: number | null
  latitude: string | null
  longitude: string | null
  is_seller: boolean
  seller_profile: { id: number; store_name: string; verification_status: VerificationStatus } | null
  date_joined: string
  order_blocked_until: string | null
}

export interface AuthResponse {
  access: string
  refresh: string
  is_new: boolean
  user: User
}

export interface OtpRequestResponse {
  detail: string
  expires_in: number
  resend_in: number
  debug_code?: string
}

export interface Category {
  id: number
  slug: string
  name: string
  name_uz: string
  name_ru: string
  icon: string
  parent: number | null
  requires_expiry_date: boolean
  children?: Category[]
}

export type WorkingHours = Partial<
  Record<'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun', { open: string; close: string } | null>
>

export interface SellerBrief {
  id: number
  store_name: string
  city: City
  address: string
  latitude: string
  longitude: string
  rating_avg: string
  rating_count: number
}

export interface PublicSeller extends SellerBrief {
  description: string
  logo: string | null
  phone: string
  working_hours: WorkingHours
  created_at: string
}

export interface SellerProfile {
  id: number
  store_name: string
  description: string
  logo: string | null
  phone: string
  city: number
  city_detail: City
  address: string
  latitude: string
  longitude: string
  working_hours: WorkingHours
  verification_status: VerificationStatus
  verification_note: string
  verified_at: string | null
  rating_avg: string
  rating_count: number
  created_at: string
}

export type Condition = 'new' | 'opened_packaging' | 'display_item' | 'slight_defect'
export type ProductStatus = 'draft' | 'active' | 'sold_out' | 'expired' | 'hidden'
export type Unit = 'piece' | 'kg' | 'g' | 'l' | 'ml' | 'pack' | 'box' | 'set'

export interface ProductImage {
  id: number
  image: string
  sort_order: number
}

export interface ProductListItem {
  id: number
  title: string
  category: { id: number; slug: string; name: string }
  seller: SellerBrief
  original_price: number
  current_price: number
  discount_percent: number
  quantity: number
  unit: Unit
  expiry_date: string | null
  days_to_expiry: number | null
  condition: Condition
  main_image: string | null
  distance_km?: number | null
  created_at: string
}

export interface ProductDetail extends Omit<ProductListItem, 'seller'> {
  seller: PublicSeller
  description: string
  condition_note: string
  unit_weight_kg: string | null
  images: ProductImage[]
  is_favorite: boolean
}

export interface SellerProduct {
  id: number
  category: number
  category_detail: { id: number; slug: string; name: string }
  title: string
  description: string
  original_price: number
  current_price: number
  discount_percent: number
  quantity: number
  unit: Unit
  unit_weight_kg: string | null
  expiry_date: string | null
  condition: Condition
  condition_note: string
  status: ProductStatus
  is_public: boolean
  published_at: string | null
  images: ProductImage[]
  created_at: string
  updated_at: string
}

export interface MarkdownStep {
  days_before_expiry: number
  discount_percent: number
}

export interface MarkdownRule {
  is_active: boolean
  min_price: number
  steps: MarkdownStep[]
  last_applied_at: string | null
  preview: { date: string; price: number }[]
}

export interface PriceChange {
  old_price: number
  new_price: number
  reason: 'manual' | 'markdown' | 'admin'
  created_at: string
}

export interface CartLine {
  id: number
  product: ProductListItem
  quantity: number
  available: boolean
  problem: '' | 'unavailable' | 'insufficient_stock'
  line_total: number
}

export interface Cart {
  groups: {
    seller: { id: number; store_name: string; city: City; address: string; rating_avg: string }
    lines: CartLine[]
    subtotal: number
    original_total: number
  }[]
  total: number
  original_total: number
  item_count: number
}

export type OrderStatus = 'pending' | 'confirmed' | 'ready_for_pickup' | 'completed' | 'cancelled'
export type CancelReason = '' | 'buyer' | 'seller' | 'not_confirmed' | 'not_picked_up' | 'admin'

export interface OrderItem {
  id: number
  product: number
  title: string
  unit: Unit
  quantity: number
  unit_price: number
  original_unit_price: number
  line_total: number
}

export interface Review {
  id: number
  order: number
  seller: number
  rating: number
  comment: string
  buyer_name: string
  created_at: string
  updated_at: string
}

interface OrderBase {
  id: number
  number: string
  status: OrderStatus
  status_display: string
  items: OrderItem[]
  subtotal: number
  original_total: number
  savings: number
  payment_method: string
  payment_status: string | null
  buyer_note: string
  confirm_deadline: string
  pickup_deadline: string | null
  created_at: string
  confirmed_at: string | null
  ready_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  cancel_reason: CancelReason
  cancel_comment: string
}

export interface BuyerOrder extends OrderBase {
  seller: {
    id: number
    store_name: string
    phone: string
    city: City
    address: string
    latitude: string
    longitude: string
    working_hours: WorkingHours
  }
  pickup_code: string | null
  can_cancel: boolean
  can_review: boolean
  review: Review | null
  pickup_qr?: string | null
}

export interface SellerOrder extends OrderBase {
  buyer: { id: number; first_name: string; phone: string }
}

export interface PaymentMethod {
  code: string
  name: string
  is_online: boolean
}

export interface AppNotification {
  id: number
  kind: string
  title: string
  body: string
  url: string
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface NotificationPreferences {
  telegram_enabled: boolean
  email_enabled: boolean
  deals_enabled: boolean
  favorite_categories: number[]
  telegram_connected: boolean
}

export interface Impact {
  date: string
  items_rescued: number
  kg_prevented: string
  orders_completed: number
  buyer_savings: number
  active_sellers: number
}

export interface SellerStats {
  days: number
  orders_completed: number
  revenue: number
  buyer_savings: number
  items_sold: number
  kg_saved: string
  status_counts: Partial<Record<OrderStatus, number>>
  series: { date: string; revenue: number; orders: number }[]
  top_products: { product_id: number; title: string; units_sold: number; revenue: number }[]
  rating_avg: string
  rating_count: number
}
