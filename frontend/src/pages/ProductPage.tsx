import { useQuery } from '@tanstack/react-query'
import { Clock, Heart, ImageOff, Info, MapPin, ShoppingBag, Star, Store } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { catalogApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { DiscountBadge, Price } from '../components/Price'
import { QtyStepper } from '../components/QtyStepper'
import { EmptyState, ErrorState, InlineError, PageSpinner, Spinner } from '../components/States'
import { toast } from '../components/Toast'
import { useAddToCart, useToggleFavorite } from '../hooks/queries'
import { expiryLabel, formatDate, formatMoney, mapsUrl } from '../lib/format'

export default function ProductPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { isAuthenticated, user } = useAuth()
  const [qty, setQty] = useState(1)
  const [active, setActive] = useState(0)
  const query = useQuery({ queryKey: ['product', id], queryFn: () => catalogApi.product(id) })
  const addToCart = useAddToCart()
  const favorite = useToggleFavorite(Number(id))

  if (query.isPending) return <PageSpinner />
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 404) {
      return <EmptyState icon={ImageOff} title={t('product.notFound')} action={<Link to="/catalog" className="btn-primary">{t('nav.catalog')}</Link>} />
    }
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  }

  const p = query.data
  const own = user?.seller_profile?.id === p.seller.id
  const expiry = expiryLabel(p.days_to_expiry)
  const unit = t(`product.units.${p.unit}`)

  const onAdd = () => {
    if (!isAuthenticated) {
      navigate(`/login?next=/products/${p.id}`)
      return
    }
    addToCart.mutate(
      { product: p.id, quantity: qty },
      { onSuccess: () => toast(t('product.added')) },
    )
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div>
        <div className="card relative aspect-square overflow-hidden">
          {p.images.length ? (
            <div
              className="flex h-full snap-x snap-mandatory overflow-x-auto [scrollbar-width:none]"
              onScroll={(e) => setActive(Math.round(e.currentTarget.scrollLeft / e.currentTarget.clientWidth))}
            >
              {p.images.map((img) => (
                <img key={img.id} src={img.image} alt={p.title} className="h-full w-full shrink-0 snap-center object-cover" />
              ))}
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-line">
              <ImageOff className="h-12 w-12" aria-hidden />
            </div>
          )}
          <DiscountBadge percent={p.discount_percent} className="absolute left-3 top-3 !text-sm" />
          {p.images.length > 1 && (
            <div className="absolute inset-x-0 bottom-3 flex justify-center gap-1.5">
              {p.images.map((img, i) => (
                <span key={img.id} className={`h-1.5 w-1.5 rounded-full ${i === active ? 'bg-white' : 'bg-white/50'}`} />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <Link to={`/catalog?category=${p.category.slug}`} className="text-sm text-brand-700">
            {p.category.name}
          </Link>
          <div className="mt-1 flex items-start gap-3">
            <h1 className="flex-1 text-2xl font-bold leading-tight">{p.title}</h1>
            {isAuthenticated && (
              <button
                type="button"
                className="btn-ghost !p-2"
                onClick={() => favorite.mutate(p.is_favorite)}
                aria-pressed={p.is_favorite}
                aria-label={p.is_favorite ? t('product.removeFavorite') : t('product.addFavorite')}
              >
                <Heart className={`h-6 w-6 ${p.is_favorite ? 'fill-red-500 text-red-500' : ''}`} />
              </button>
            )}
          </div>
        </div>

        <div>
          <Price current={p.current_price} original={p.original_price} size="lg" />
          <p className="mt-1 text-sm font-medium text-brand-700">
            {t('product.youSave', { amount: formatMoney(p.original_price - p.current_price) })} · {unit}
          </p>
        </div>

        <div className="flex flex-wrap gap-2 text-sm">
          {expiry && (
            <span className={`chip ${p.days_to_expiry !== null && p.days_to_expiry <= 1 ? '!border-deal-500 !text-deal-700' : ''}`}>
              <Clock className="h-4 w-4" aria-hidden />
              {expiry} · {formatDate(p.expiry_date)}
            </span>
          )}
          <span className="chip">{t('product.left', { count: p.quantity })}</span>
          <span className="chip">{t(`product.conditions.${p.condition}`)}</span>
        </div>
        {p.condition_note && (
          <p className="flex gap-2 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            {p.condition_note}
          </p>
        )}

        {!own && (
          <div className="flex items-center gap-3">
            <QtyStepper value={qty} max={p.quantity} onChange={setQty} />
            <button type="button" className="btn-primary flex-1 !py-3" onClick={onAdd} disabled={addToCart.isPending}>
              {addToCart.isPending ? <Spinner className="h-4 w-4 !text-white" /> : <ShoppingBag className="h-5 w-5" aria-hidden />}
              {t('product.addToCart')} · {formatMoney(p.current_price * qty)}
            </button>
          </div>
        )}
        {addToCart.isSuccess && (
          <Link to="/cart" className="text-center text-sm font-medium text-brand-700">
            {t('product.goToCart')} →
          </Link>
        )}
        <InlineError error={addToCart.error} />
        <p className="text-xs text-muted">{t('product.pickupOnly')}</p>

        {p.description && (
          <section>
            <h2 className="mb-1 font-semibold">{t('product.description')}</h2>
            <p className="whitespace-pre-line text-sm text-ink/80">{p.description}</p>
          </section>
        )}

        <Link to={`/stores/${p.seller.id}`} className="card flex items-center gap-3 p-4 transition hover:border-brand-600">
          {p.seller.logo ? (
            <img src={p.seller.logo} alt="" className="h-12 w-12 rounded-xl object-cover" />
          ) : (
            <span className="rounded-xl bg-brand-50 p-3 text-brand-700">
              <Store className="h-6 w-6" aria-hidden />
            </span>
          )}
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{p.seller.store_name}</p>
            <p className="truncate text-sm text-muted">
              {p.seller.city.name}, {p.seller.address}
            </p>
            {p.seller.rating_count > 0 && (
              <p className="mt-0.5 flex items-center gap-1 text-sm">
                <Star className="h-4 w-4 fill-amber-400 text-amber-400" aria-hidden />
                {Number(p.seller.rating_avg).toFixed(1)} · {t('store.reviews', { count: p.seller.rating_count })}
              </p>
            )}
          </div>
        </Link>
        <a href={mapsUrl(p.seller.latitude, p.seller.longitude)} target="_blank" rel="noreferrer" className="btn-secondary">
          <MapPin className="h-4 w-4" aria-hidden />
          {t('product.openMap')}
        </a>
      </div>
    </div>
  )
}
