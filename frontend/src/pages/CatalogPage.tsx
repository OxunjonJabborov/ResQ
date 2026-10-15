import { useInfiniteQuery } from '@tanstack/react-query'
import { PackageSearch, Search, SlidersHorizontal, X } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { catalogApi } from '../api/endpoints'
import type { Condition } from '../api/types'
import { ProductGrid } from '../components/ProductCard'
import { EmptyState, ErrorState, SkeletonGrid, Spinner } from '../components/States'
import { flattenCategories, useCategories, useCities } from '../hooks/queries'
import { useGeolocation } from '../lib/geo'

const FILTER_KEYS = ['category', 'city', 'min_price', 'max_price', 'min_discount', 'expiring_within', 'condition', 'near', 'radius_km'] as const
const CONDITIONS: Condition[] = ['new', 'opened_packaging', 'display_item', 'slight_defect']

function FilterBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="border-b border-line py-4 last:border-0">
      <legend className="mb-2 text-sm font-semibold">{title}</legend>
      {children}
    </fieldset>
  )
}

export default function CatalogPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const [showFilters, setShowFilters] = useState(false)
  const [search, setSearch] = useState(params.get('search') ?? '')
  const categories = useCategories()
  const cities = useCities()
  const geo = useGeolocation()
  const near = params.get('near') === '1'

  useEffect(() => {
    if (near && !geo.coords && !geo.loading && !geo.error) geo.request()
  }, [near, geo])

  const set = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value === null || value === '') next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
  }

  const apiParams = useMemo(() => {
    const p: Record<string, string | number> = {}
    params.forEach((value, key) => {
      if (key !== 'near') p[key] = value
    })
    if (near && geo.coords) {
      p.lat = geo.coords.lat
      p.lng = geo.coords.lng
      p.radius_km = params.get('radius_km') ?? 10
    } else {
      delete p.radius_km
      if (p.ordering === 'distance_km') delete p.ordering
    }
    return p
  }, [params, near, geo.coords])

  const waitingForLocation = near && !geo.coords && !geo.error
  const query = useInfiniteQuery({
    queryKey: ['products', apiParams],
    queryFn: ({ pageParam }) => catalogApi.products({ ...apiParams, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (last, all) => (last.next ? all.length + 1 : undefined),
    enabled: !waitingForLocation,
  })

  const products = query.data?.pages.flatMap((p) => p.results) ?? []
  const count = query.data?.pages[0]?.count ?? 0
  const activeFilters = FILTER_KEYS.filter((k) => params.get(k)).length
  const onSearch = (e: FormEvent) => {
    e.preventDefault()
    set('search', search.trim())
  }

  const filters = (
    <div>
      <FilterBlock title={t('catalog.category')}>
        <select className="input" value={params.get('category') ?? ''} onChange={(e) => set('category', e.target.value)}>
          <option value="">{t('catalog.allCategories')}</option>
          {flattenCategories(categories.data).map(([c, depth]) => (
            <option key={c.id} value={c.slug}>
              {'  '.repeat(depth * 2)}
              {c.name}
            </option>
          ))}
        </select>
      </FilterBlock>
      <FilterBlock title={t('catalog.city')}>
        <select className="input" value={params.get('city') ?? ''} onChange={(e) => set('city', e.target.value)}>
          <option value="">{t('catalog.allCities')}</option>
          {(cities.data ?? []).map((c) => (
            <option key={c.id} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>
      </FilterBlock>
      <FilterBlock title={t('catalog.nearMe')}>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-brand-700" checked={near} onChange={(e) => set('near', e.target.checked ? '1' : null)} />
          {t('catalog.nearMe')}
        </label>
        {near && (
          <div className="mt-2 flex flex-wrap gap-2">
            {[2, 5, 10, 25].map((km) => (
              <button
                key={km}
                type="button"
                className={(params.get('radius_km') ?? '10') === String(km) ? 'chip-active' : 'chip'}
                onClick={() => set('radius_km', String(km))}
              >
                {km} {t('common.km')}
              </button>
            ))}
          </div>
        )}
        {near && geo.error && <p className="mt-2 text-xs text-red-600">{t('catalog.locationDenied')}</p>}
      </FilterBlock>
      <FilterBlock title={t('catalog.price')}>
        <div className="flex gap-2">
          <input className="input" inputMode="numeric" placeholder={t('catalog.priceFrom')} defaultValue={params.get('min_price') ?? ''} onBlur={(e) => set('min_price', e.target.value.replace(/\D/g, ''))} />
          <input className="input" inputMode="numeric" placeholder={t('catalog.priceTo')} defaultValue={params.get('max_price') ?? ''} onBlur={(e) => set('max_price', e.target.value.replace(/\D/g, ''))} />
        </div>
      </FilterBlock>
      <FilterBlock title={t('catalog.minDiscount')}>
        <div className="flex flex-wrap gap-2">
          {['', '20', '30', '50', '70'].map((v) => (
            <button key={v} type="button" className={(params.get('min_discount') ?? '') === v ? 'chip-active' : 'chip'} onClick={() => set('min_discount', v)}>
              {v ? `${v}%+` : t('catalog.anyTime')}
            </button>
          ))}
        </div>
      </FilterBlock>
      <FilterBlock title={t('catalog.expiringWithin')}>
        <div className="flex flex-wrap gap-2">
          {['', '1', '3', '7'].map((v) => (
            <button key={v} type="button" className={(params.get('expiring_within') ?? '') === v ? 'chip-active' : 'chip'} onClick={() => set('expiring_within', v)}>
              {v ? t('catalog.withinDays', { count: Number(v) }) : t('catalog.anyTime')}
            </button>
          ))}
        </div>
      </FilterBlock>
      <FilterBlock title={t('catalog.condition')}>
        <div className="flex flex-wrap gap-2">
          {CONDITIONS.map((c) => (
            <button key={c} type="button" className={params.get('condition') === c ? 'chip-active' : 'chip'} onClick={() => set('condition', params.get('condition') === c ? null : c)}>
              {t(`product.conditions.${c}`)}
            </button>
          ))}
        </div>
      </FilterBlock>
      {activeFilters > 0 && (
        <button
          type="button"
          className="btn-ghost mt-2 w-full"
          onClick={() => {
            const next = new URLSearchParams()
            if (params.get('search')) next.set('search', params.get('search')!)
            if (params.get('ordering')) next.set('ordering', params.get('ordering')!)
            setParams(next, { replace: true })
          }}
        >
          {t('catalog.clearFilters')}
        </button>
      )}
    </div>
  )

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <h1 className="text-xl font-bold">{t('catalog.title')}</h1>
        <form onSubmit={onSearch} className="relative flex-1 sm:ml-4" role="search">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted" aria-hidden />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('home.searchPlaceholder')} className="input !pl-10" type="search" aria-label={t('common.search')} />
        </form>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" className="btn-secondary lg:hidden" onClick={() => setShowFilters(true)}>
          <SlidersHorizontal className="h-4 w-4" aria-hidden />
          {t('catalog.filters')}
          {activeFilters > 0 && <span className="rounded-full bg-brand-700 px-1.5 text-xs text-white">{activeFilters}</span>}
        </button>
        <select className="input !w-auto min-w-0 max-w-[60%]" value={params.get('ordering') ?? ''} onChange={(e) => set('ordering', e.target.value)} aria-label={t('catalog.sort')}>
          <option value="">{t('catalog.sortNewest')}</option>
          <option value="current_price">{t('catalog.sortPriceAsc')}</option>
          <option value="-current_price">{t('catalog.sortPriceDesc')}</option>
          <option value="-discount_percent">{t('catalog.sortDiscount')}</option>
          <option value="expiry_date">{t('catalog.sortExpiry')}</option>
          {near && <option value="distance_km">{t('catalog.sortDistance')}</option>}
        </select>
        {query.isSuccess && <span className="ml-auto whitespace-nowrap text-sm text-muted">{t('catalog.results', { count })}</span>}
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[260px_1fr]">
        <aside className="card hidden h-fit px-4 lg:block">{filters}</aside>

        {showFilters && (
          <div className="fixed inset-0 z-40 flex lg:hidden" role="dialog" aria-modal="true" aria-label={t('catalog.filters')}>
            <button type="button" className="flex-1 bg-black/40" aria-label={t('common.close')} onClick={() => setShowFilters(false)} />
            <div className="flex h-full w-[86%] max-w-sm flex-col bg-card">
              <div className="flex items-center justify-between border-b border-line px-4 py-3">
                <h2 className="font-semibold">{t('catalog.filters')}</h2>
                <button type="button" className="btn-ghost !p-1.5" onClick={() => setShowFilters(false)} aria-label={t('common.close')}>
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-4">{filters}</div>
              <div className="border-t border-line p-4">
                <button type="button" className="btn-primary w-full" onClick={() => setShowFilters(false)}>
                  {t('catalog.results', { count })}
                </button>
              </div>
            </div>
          </div>
        )}

        <div>
          {query.isPending || waitingForLocation ? (
            <SkeletonGrid count={8} />
          ) : query.isError ? (
            <ErrorState error={query.error} onRetry={() => void query.refetch()} />
          ) : products.length === 0 ? (
            <EmptyState icon={PackageSearch} title={t('catalog.noResults')} hint={t('catalog.noResultsHint')} />
          ) : (
            <>
              <ProductGrid products={products} />
              {query.hasNextPage && (
                <div className="mt-6 flex justify-center">
                  <button type="button" className="btn-secondary" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
                    {query.isFetchingNextPage && <Spinner className="h-4 w-4" />}
                    {t('catalog.loadMore')}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
