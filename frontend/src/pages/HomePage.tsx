import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Leaf, LocateFixed, Search, Store } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { catalogApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { CategoryIcon } from '../components/CategoryIcon'
import { ProductRail } from '../components/ProductCard'
import { ErrorState, SkeletonGrid } from '../components/States'
import { useCategories } from '../hooks/queries'
import { formatKg, formatMoney } from '../lib/format'
import { useGeolocation } from '../lib/geo'

function Section({ title, to, params }: { title: string; to: string; params: Record<string, string | number> }) {
  const { t } = useTranslation()
  const query = useQuery({
    queryKey: ['products', 'rail', params],
    queryFn: () => catalogApi.products({ page_size: 10, ...params }),
  })
  if (query.isSuccess && query.data.results.length === 0) return null
  return (
    <section className="mt-8">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-bold">{title}</h2>
        <Link to={to} className="inline-flex items-center gap-1 text-sm font-medium text-brand-700">
          {t('common.viewAll')} <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </div>
      {query.isPending ? (
        <SkeletonGrid count={4} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <ProductRail products={query.data.results} />
      )}
    </section>
  )
}

export default function HomePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const categories = useCategories()
  const impact = useQuery({ queryKey: ['impact'], queryFn: catalogApi.impact, staleTime: 10 * 60 * 1000 })
  const geo = useGeolocation()

  const onSearch = (e: FormEvent) => {
    e.preventDefault()
    navigate(`/catalog?search=${encodeURIComponent(search.trim())}`)
  }

  return (
    <div>
      <section className="overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 to-brand-800 px-5 py-7 text-white sm:px-8 sm:py-10">
        <h1 className="max-w-xl text-2xl font-extrabold leading-tight sm:text-4xl">{t('home.heroTitle')}</h1>
        <p className="mt-2 max-w-xl text-sm text-white/85 sm:text-base">{t('home.heroSubtitle')}</p>
        <form onSubmit={onSearch} className="mt-5 flex max-w-xl gap-2" role="search">
          <label className="relative flex-1">
            <span className="sr-only">{t('common.search')}</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted" aria-hidden />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('home.searchPlaceholder')}
              className="input !pl-10 text-ink"
              type="search"
            />
          </label>
          <button className="btn rounded-xl bg-deal-500 px-5 text-white hover:bg-deal-600" type="submit">
            {t('common.search')}
          </button>
        </form>
        {impact.data && impact.data.items_rescued > 0 && (
          <dl className="mt-6 grid max-w-xl grid-cols-3 gap-3 text-center">
            {[
              { value: impact.data.items_rescued.toLocaleString('ru-RU'), label: t('home.impactItems') },
              { value: formatKg(impact.data.kg_prevented), label: t('home.impactKg') },
              { value: formatMoney(impact.data.buyer_savings), label: t('home.impactSavings') },
            ].map((s) => (
              <div key={s.label} className="rounded-2xl bg-white/10 px-2 py-3">
                <dt className="sr-only">{s.label}</dt>
                <dd className="text-base font-bold sm:text-xl">{s.value}</dd>
                <dd className="text-[11px] leading-tight text-white/80 sm:text-xs">{s.label}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section className="mt-7">
        <h2 className="mb-3 text-lg font-bold">{t('home.categories')}</h2>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {(categories.data ?? []).map((c) => (
            <Link
              key={c.id}
              to={`/catalog?category=${c.slug}`}
              className="card flex flex-col items-center gap-2 px-2 py-4 text-center transition hover:border-brand-600"
            >
              <span className="rounded-xl bg-brand-50 p-2.5 text-brand-700">
                <CategoryIcon name={c.icon} />
              </span>
              <span className="text-xs font-medium leading-tight sm:text-sm">{c.name}</span>
            </Link>
          ))}
          {categories.isPending &&
            Array.from({ length: 6 }, (_, i) => <div key={i} className="card h-24 animate-pulse bg-line/40" />)}
        </div>
      </section>

      {geo.coords ? (
        <Section
          title={t('home.nearYou')}
          to={`/catalog?near=1&ordering=distance_km`}
          params={{ lat: geo.coords.lat, lng: geo.coords.lng, radius_km: 10, ordering: 'distance_km' }}
        />
      ) : (
        <div className="card mt-8 flex flex-col items-start gap-3 p-4 sm:flex-row sm:items-center">
          <LocateFixed className="h-6 w-6 shrink-0 text-brand-700" aria-hidden />
          <p className="flex-1 text-sm text-muted">{geo.error === 'denied' ? t('catalog.locationDenied') : t('home.locationHint')}</p>
          <button type="button" className="btn-secondary" onClick={geo.request} disabled={geo.loading}>
            {t('home.enableLocation')}
          </button>
        </div>
      )}

      <Section
        title={t('home.endingSoon')}
        to="/catalog?expiring_within=2&ordering=expiry_date"
        params={{ expiring_within: 2, ordering: 'expiry_date' }}
      />
      <Section title={t('home.bestDiscounts')} to="/catalog?ordering=-discount_percent" params={{ ordering: '-discount_percent' }} />

      {!user?.is_seller && (
        <section className="card mt-10 flex flex-col items-start gap-4 p-5 sm:flex-row sm:items-center">
          <span className="rounded-2xl bg-deal-100 p-3 text-deal-700">
            <Store className="h-7 w-7" aria-hidden />
          </span>
          <div className="flex-1">
            <h2 className="font-bold">{t('home.forSellers')}</h2>
            <p className="text-sm text-muted">{t('home.forSellersText')}</p>
          </div>
          <Link to="/seller/store" className="btn-primary">
            <Leaf className="h-4 w-4" aria-hidden />
            {t('home.forSellersCta')}
          </Link>
        </section>
      )}
    </div>
  )
}
