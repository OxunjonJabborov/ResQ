import { useInfiniteQuery } from '@tanstack/react-query'
import { ChevronRight, Package } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ordersApi } from '../api/endpoints'
import type { BuyerOrder } from '../api/types'
import { EmptyState, ErrorState, PageSpinner } from '../components/States'
import { OrderStatusBadge } from '../components/StatusBadge'
import { formatDateTime, formatMoney } from '../lib/format'

const ACTIVE = new Set(['pending', 'confirmed', 'ready_for_pickup'])

function OrderRow({ order }: { order: BuyerOrder }) {
  const { t } = useTranslation()
  return (
    <Link to={`/orders/${order.id}`} className="card flex items-center gap-3 p-4 transition hover:border-brand-600">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{order.number}</span>
          <OrderStatusBadge status={order.status} />
        </div>
        <p className="truncate text-sm text-muted">
          {order.seller.store_name} · {order.items.map((i) => i.title).join(', ')}
        </p>
        <p className="text-sm">
          <span className="font-semibold">{formatMoney(order.subtotal)}</span>
          <span className="text-muted"> · {formatDateTime(order.created_at)}</span>
        </p>
        {order.status === 'ready_for_pickup' && order.pickup_code && (
          <p className="text-sm font-medium text-brand-700">
            {t('orders.pickupCode')}: <span className="font-mono tracking-widest">{order.pickup_code}</span>
          </p>
        )}
      </div>
      <ChevronRight className="h-5 w-5 text-muted" aria-hidden />
    </Link>
  )
}

export default function OrdersPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<'active' | 'past'>('active')
  const query = useInfiniteQuery({
    queryKey: ['orders', 'list'],
    queryFn: ({ pageParam }) => ordersApi.list({ page: pageParam, page_size: 50 }),
    initialPageParam: 1,
    getNextPageParam: (last, all) => (last.next ? all.length + 1 : undefined),
    refetchInterval: 60_000,
  })
  if (query.isPending) return <PageSpinner />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const all = query.data.pages.flatMap((p) => p.results)
  const shown = all.filter((o) => (tab === 'active') === ACTIVE.has(o.status))

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-xl font-bold">{t('orders.title')}</h1>
      <div className="flex gap-2">
        {(['active', 'past'] as const).map((key) => (
          <button key={key} type="button" className={tab === key ? 'chip-active' : 'chip'} onClick={() => setTab(key)}>
            {t(`orders.${key}`)}
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <EmptyState
          icon={Package}
          title={t('orders.empty')}
          hint={t('orders.emptyHint')}
          action={<Link to="/catalog" className="btn-primary">{t('cart.browse')}</Link>}
        />
      ) : (
        <div className="space-y-3">
          {shown.map((o) => (
            <OrderRow key={o.id} order={o} />
          ))}
        </div>
      )}
      {query.hasNextPage && (
        <button type="button" className="btn-secondary w-full" onClick={() => void query.fetchNextPage()}>
          {t('catalog.loadMore')}
        </button>
      )}
    </div>
  )
}
