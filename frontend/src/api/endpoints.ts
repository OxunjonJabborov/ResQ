import { api } from './client'
import type {
  AppNotification,
  AuthResponse,
  BuyerOrder,
  Cart,
  Category,
  City,
  Impact,
  MarkdownRule,
  MarkdownStep,
  NotificationPreferences,
  OtpRequestResponse,
  Paginated,
  PaymentMethod,
  PriceChange,
  ProductDetail,
  ProductImage,
  ProductListItem,
  ProductStatus,
  PublicSeller,
  Review,
  SellerOrder,
  SellerProduct,
  SellerProfile,
  SellerStats,
  User,
} from './types'

type Params = Record<string, string | number | boolean | undefined | null>

export const authApi = {
  requestOtp: (phone: string) =>
    api<OtpRequestResponse>('/auth/otp/request/', { body: { phone } }),
  verifyOtp: (phone: string, code: string) =>
    api<AuthResponse>('/auth/otp/verify/', { body: { phone, code } }),
  logout: (refresh: string) => api<void>('/auth/logout/', { body: { refresh } }),
  me: () => api<User>('/me/'),
  updateMe: (data: Partial<User>) => api<User>('/me/', { method: 'PATCH', body: data }),
}

export const catalogApi = {
  categories: () => api<Category[]>('/categories/'),
  cities: () => api<City[]>('/cities/'),
  products: (params: Params) => api<Paginated<ProductListItem>>('/products/', { params }),
  product: (id: number | string) => api<ProductDetail>(`/products/${id}/`),
  seller: (id: number | string) => api<PublicSeller>(`/sellers/${id}/`),
  sellerReviews: (id: number | string, page = 1) =>
    api<Paginated<Review>>(`/sellers/${id}/reviews/`, { params: { page } }),
  impact: () => api<Impact>('/stats/impact/'),
}

export const favoritesApi = {
  list: (page = 1) => api<Paginated<ProductListItem>>('/favorites/', { params: { page } }),
  add: (product: number) => api<void>('/favorites/', { body: { product } }),
  remove: (product: number) => api<void>(`/favorites/${product}/`, { method: 'DELETE' }),
}

export const cartApi = {
  get: () => api<Cart>('/cart/'),
  add: (product: number, quantity = 1) => api<Cart>('/cart/items/', { body: { product, quantity } }),
  update: (itemId: number, quantity: number) =>
    api<Cart>(`/cart/items/${itemId}/`, { method: 'PATCH', body: { quantity } }),
  remove: (itemId: number) => api<Cart>(`/cart/items/${itemId}/`, { method: 'DELETE' }),
  clear: () => api<void>('/cart/', { method: 'DELETE' }),
}

export const ordersApi = {
  paymentMethods: () => api<PaymentMethod[]>('/payments/methods/'),
  checkout: (payment_method: string, note: string) =>
    api<BuyerOrder[]>('/orders/checkout/', { body: { payment_method, note } }),
  list: (params: Params) => api<Paginated<BuyerOrder>>('/orders/', { params }),
  get: (id: number | string) => api<BuyerOrder>(`/orders/${id}/`),
  cancel: (id: number, comment = '') => api<BuyerOrder>(`/orders/${id}/cancel/`, { body: { comment } }),
  review: (id: number, rating: number, comment: string) =>
    api<Review>(`/orders/${id}/review/`, { body: { rating, comment } }),
  dispute: (id: number, reason: string, description: string) =>
    api<unknown>(`/orders/${id}/dispute/`, { body: { reason, description } }),
}

export const notificationsApi = {
  list: (page = 1) => api<Paginated<AppNotification>>('/notifications/', { params: { page } }),
  unreadCount: () => api<{ count: number }>('/notifications/unread-count/'),
  markRead: (ids?: number[]) =>
    api<{ updated: number }>('/notifications/mark-read/', { body: ids ? { ids } : {} }),
  preferences: () => api<NotificationPreferences>('/notifications/preferences/'),
  updatePreferences: (data: Partial<NotificationPreferences>) =>
    api<NotificationPreferences>('/notifications/preferences/', { method: 'PATCH', body: data }),
  telegramLink: () => api<{ url: string | null; token: string }>('/notifications/telegram/link/', { method: 'POST' }),
  telegramUnlink: () => api<void>('/notifications/telegram/link/', { method: 'DELETE' }),
}

export type SellerProductInput = Partial<
  Pick<
    SellerProduct,
    | 'category'
    | 'title'
    | 'description'
    | 'original_price'
    | 'current_price'
    | 'quantity'
    | 'unit'
    | 'unit_weight_kg'
    | 'expiry_date'
    | 'condition'
    | 'condition_note'
  >
> & { status?: 'draft' | 'active' }

export const sellerApi = {
  profile: () => api<SellerProfile>('/seller/profile/'),
  createProfile: (data: FormData | Record<string, unknown>) =>
    api<SellerProfile>('/seller/profile/', { method: 'POST', body: data }),
  updateProfile: (data: FormData | Record<string, unknown>) =>
    api<SellerProfile>('/seller/profile/', { method: 'PATCH', body: data }),

  products: (params: Params) => api<Paginated<SellerProduct>>('/seller/products/', { params }),
  product: (id: number | string) => api<SellerProduct>(`/seller/products/${id}/`),
  createProduct: (data: SellerProductInput) => api<SellerProduct>('/seller/products/', { body: data }),
  updateProduct: (id: number, data: SellerProductInput) =>
    api<SellerProduct>(`/seller/products/${id}/`, { method: 'PATCH', body: data }),
  deleteProduct: (id: number) => api<void>(`/seller/products/${id}/`, { method: 'DELETE' }),
  setStatus: (id: number, status: Extract<ProductStatus, 'draft' | 'active' | 'hidden'>) =>
    api<SellerProduct>(`/seller/products/${id}/status/`, { body: { status } }),
  uploadImage: (id: number, file: File) => {
    const form = new FormData()
    form.append('image', file)
    return api<ProductImage>(`/seller/products/${id}/images/`, { method: 'POST', body: form })
  },
  deleteImage: (id: number, imageId: number) =>
    api<void>(`/seller/products/${id}/images/${imageId}/`, { method: 'DELETE' }),
  markdown: (id: number) => api<MarkdownRule>(`/seller/products/${id}/markdown/`),
  saveMarkdown: (id: number, data: { is_active: boolean; min_price: number; steps: MarkdownStep[] }) =>
    api<MarkdownRule>(`/seller/products/${id}/markdown/`, { method: 'PUT', body: data }),
  deleteMarkdown: (id: number) => api<void>(`/seller/products/${id}/markdown/`, { method: 'DELETE' }),
  priceHistory: (id: number) => api<PriceChange[]>(`/seller/products/${id}/price-history/`),

  orders: (params: Params) => api<Paginated<SellerOrder>>('/seller/orders/', { params }),
  order: (id: number | string) => api<SellerOrder>(`/seller/orders/${id}/`),
  confirm: (id: number) => api<SellerOrder>(`/seller/orders/${id}/confirm/`, { method: 'POST' }),
  ready: (id: number) => api<SellerOrder>(`/seller/orders/${id}/ready/`, { method: 'POST' }),
  cancel: (id: number, comment = '') =>
    api<SellerOrder>(`/seller/orders/${id}/cancel/`, { body: { comment } }),
  complete: (id: number, code: string) =>
    api<SellerOrder>(`/seller/orders/${id}/complete/`, { body: { code } }),
  completeByCode: (code: string) =>
    api<SellerOrder>('/seller/orders/complete-by-code/', { body: { code } }),
  stats: (days = 30) => api<SellerStats>('/seller/stats/', { params: { days } }),
}
