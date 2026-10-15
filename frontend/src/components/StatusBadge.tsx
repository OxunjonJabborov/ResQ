import { useTranslation } from 'react-i18next'

import type { OrderStatus, ProductStatus } from '../api/types'

const ORDER_TONES: Record<OrderStatus, string> = {
  pending: 'bg-amber-100 text-amber-800',
  confirmed: 'bg-sky-100 text-sky-800',
  ready_for_pickup: 'bg-brand-100 text-brand-800',
  completed: 'bg-gray-100 text-gray-700',
  cancelled: 'bg-red-100 text-red-700',
}

const PRODUCT_TONES: Record<ProductStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  active: 'bg-brand-100 text-brand-800',
  sold_out: 'bg-amber-100 text-amber-800',
  expired: 'bg-red-100 text-red-700',
  hidden: 'bg-gray-200 text-gray-700',
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  const { t } = useTranslation()
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${ORDER_TONES[status]}`}>{t(`orders.status.${status}`)}</span>
}

export function ProductStatusBadge({ status }: { status: ProductStatus }) {
  const { t } = useTranslation()
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${PRODUCT_TONES[status]}`}>
      {t(`sellerProducts.status.${status}`)}
    </span>
  )
}
