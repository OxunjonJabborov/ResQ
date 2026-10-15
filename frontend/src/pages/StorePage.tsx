import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Clock, MapPin, Phone, Store } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { catalogApi } from '../api/endpoints'
import type { WorkingHours } from '../api/types'
import { ProductGrid } from '../components/ProductCard'
import { EmptyState, ErrorState, PageSpinner, SkeletonGrid, Spinner } from '../components/States'
import { Stars } from '../components/Stars'
import { formatDate, formatPhone, mapsUrl } from '../lib/format'

const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const

function Hours({ hours }: { hours: WorkingHours }) {
  const { t } = useTranslation()
  if (!Object.keys(hours).length) return null
  return (
    <ul className="space-y-1 text-sm">
      {DAYS.filter((d) => d in hours).map((d) => (
        <li key={d} className="flex justify-between gap-4">
          <span className="text-muted">{t(`store.weekdays.${d}`)}</span>
          <span>{hours[d] ? `${hours[d]!.open}–${hours[d]!.close}` : t('store.closed')}</span>
        </li>
      ))}
    </ul>
  )
}

export default function StorePage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const store = useQuery({ queryKey: ['store', id], queryFn: () => catalogApi.seller(id) })
  const products = useQuery({ queryKey: ['products', { seller: id }], queryFn: () => catalogApi.products({ seller: id, page_size: 48 }) })
  const reviews = useInfiniteQuery({
    queryKey: ['reviews', id],
    queryFn: ({ pageParam }) => catalogApi.sellerReviews(id, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last, all) => (last.next ? all.length + 1 : undefined),
  })

  if (store.isPending) return <PageSpinner />
  if (store.isError) return <ErrorState error={store.error} onRetry={() => void store.refetch()} />
  const s = store.data
  const reviewList = reviews.data?.pages.flatMap((p) => p.results) ?? []

  return (
    <div className="space-y-8">
      <section className="card flex flex-col gap-4 p-5 sm:flex-row">
        {s.logo ? (
          <img src={s.logo} alt="" className="h-20 w-20 rounded-2xl object-cover" />
        ) : (
          <span className="flex h-20 w-20 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
            <Store className="h-9 w-9" aria-hidden />
          </span>
        )}
        <div className="flex-1 space-y-2">
          <h1 className="text-2xl font-bold">{s.store_name}</h1>
          {s.rating_count > 0 && (
            <p className="flex items-center gap-2 text-sm">
              <Stars value={Number(s.rating_avg)} /> {Number(s.rating_avg).toFixed(1)} · {t('store.reviews', { count: s.rating_count })}
            </p>
          )}
          {s.description && <p className="text-sm text-ink/80">{s.description}</p>}
          <p className="flex items-start gap-2 text-sm">
            <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden />
            <a className="underline-offset-2 hover:underline" href={mapsUrl(s.latitude, s.longitude)} target="_blank" rel="noreferrer">
              {s.city.name}, {s.address}
            </a>
          </p>
          <p className="flex items-center gap-2 text-sm">
            <Phone className="h-4 w-4 text-muted" aria-hidden />
            <a href={`tel:${s.phone}`}>{formatPhone(s.phone)}</a>
          </p>
        </div>
        {Object.keys(s.working_hours).length > 0 && (
          <div className="sm:w-64">
            <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <Clock className="h-4 w-4" aria-hidden /> {t('store.workingHours')}
            </h2>
            <Hours hours={s.working_hours} />
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold">{t('store.products')}</h2>
        {products.isPending ? (
          <SkeletonGrid />
        ) : products.isError ? (
          <ErrorState error={products.error} onRetry={() => void products.refetch()} />
        ) : products.data.results.length === 0 ? (
          <EmptyState icon={Store} title={t('catalog.noResults')} />
        ) : (
          <ProductGrid products={products.data.results} />
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold">{t('store.rating')}</h2>
        {reviews.isPending ? (
          <Spinner />
        ) : reviewList.length === 0 ? (
          <p className="text-sm text-muted">{t('store.noReviews')}</p>
        ) : (
          <ul className="space-y-3">
            {reviewList.map((r) => (
              <li key={r.id} className="card p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{r.buyer_name}</span>
                  <span className="text-xs text-muted">{formatDate(r.created_at)}</span>
                </div>
                <Stars value={r.rating} />
                {r.comment && <p className="mt-1 text-sm text-ink/80">{r.comment}</p>}
              </li>
            ))}
          </ul>
        )}
        {reviews.hasNextPage && (
          <button type="button" className="btn-secondary mt-3" onClick={() => void reviews.fetchNextPage()}>
            {t('catalog.loadMore')}
          </button>
        )}
      </section>
    </div>
  )
}
