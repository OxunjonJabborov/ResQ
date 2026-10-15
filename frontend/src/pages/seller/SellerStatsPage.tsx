import { useQuery } from '@tanstack/react-query'
import { BarChart3, Star } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { sellerApi } from '../../api/endpoints'
import type { OrderStatus } from '../../api/types'
import { RevenueChart } from '../../components/RevenueChart'
import { EmptyState, ErrorState, PageSpinner } from '../../components/States'
import { OrderStatusBadge } from '../../components/StatusBadge'
import { formatKg, formatMoney } from '../../lib/format'

const PERIODS = [7, 30, 90] as const

export default function SellerStatsPage() {
  const { t } = useTranslation()
  const [days, setDays] = useState<(typeof PERIODS)[number]>(30)
  const query = useQuery({ queryKey: ['seller-stats', days], queryFn: () => sellerApi.stats(days) })

  return (
    <div className="space-y-5">
      <div className="flex gap-2" role="group" aria-label={t('stats.title')}>
        {PERIODS.map((p) => (
          <button key={p} type="button" className={days === p ? 'chip-active' : 'chip'} aria-pressed={days === p} onClick={() => setDays(p)}>
            {t(`stats.last${p}`)}
          </button>
        ))}
      </div>
      {query.isPending ? (
        <PageSpinner />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        (() => {
          const s = query.data
          const tiles = [
            { label: t('stats.revenue'), value: formatMoney(s.revenue) },
            { label: t('stats.orders'), value: String(s.orders_completed) },
            { label: t('stats.itemsSold'), value: String(s.items_sold) },
            { label: t('stats.kgSaved'), value: formatKg(s.kg_saved) },
            { label: t('stats.buyerSavings'), value: formatMoney(s.buyer_savings) },
          ]
          return (
            <>
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {tiles.map((tile) => (
                  <div key={tile.label} className="card p-4">
                    <dt className="text-xs text-muted">{tile.label}</dt>
                    <dd className="mt-1 text-lg font-bold tabular-nums">{tile.value}</dd>
                  </div>
                ))}
                <div className="card p-4">
                  <dt className="text-xs text-muted">{t('stats.rating')}</dt>
                  <dd className="mt-1 flex items-center gap-1 text-lg font-bold">
                    <Star className="h-4 w-4 fill-amber-400 text-amber-400" aria-hidden />
                    {s.rating_count ? Number(s.rating_avg).toFixed(1) : '—'}
                    <span className="text-xs font-normal text-muted">({s.rating_count})</span>
                  </dd>
                </div>
              </dl>

              <section className="card p-4">
                <h2 className="mb-3 text-sm font-semibold">{t('stats.revenueChart')}</h2>
                {s.revenue === 0 ? (
                  <EmptyState icon={BarChart3} title={t('stats.noData')} />
                ) : (
                  <RevenueChart data={s.series} label={t('stats.revenueChart')} ordersLabel={t('stats.orders')} />
                )}
              </section>

              <div className="grid gap-4 md:grid-cols-2">
                <section className="card p-4">
                  <h2 className="mb-2 text-sm font-semibold">{t('stats.topProducts')}</h2>
                  {s.top_products.length === 0 ? (
                    <p className="text-sm text-muted">{t('stats.noData')}</p>
                  ) : (
                    <ol className="divide-y divide-line text-sm">
                      {s.top_products.map((p, i) => (
                        <li key={p.product_id} className="flex items-center gap-3 py-2">
                          <span className="w-5 text-muted tabular-nums">{i + 1}</span>
                          <span className="min-w-0 flex-1 truncate">{p.title}</span>
                          <span className="text-muted">{t('stats.units', { count: p.units_sold })}</span>
                          <span className="font-medium tabular-nums">{formatMoney(p.revenue)}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </section>
                <section className="card p-4">
                  <h2 className="mb-2 text-sm font-semibold">{t('stats.statusCounts')}</h2>
                  <ul className="space-y-2 text-sm">
                    {(Object.entries(s.status_counts) as [OrderStatus, number][]).map(([status, n]) => (
                      <li key={status} className="flex items-center justify-between">
                        <OrderStatusBadge status={status} />
                        <span className="font-semibold tabular-nums">{n}</span>
                      </li>
                    ))}
                    {Object.keys(s.status_counts).length === 0 && <li className="text-muted">{t('stats.noData')}</li>}
                  </ul>
                </section>
              </div>
            </>
          )
        })()
      )}
    </div>
  )
}
