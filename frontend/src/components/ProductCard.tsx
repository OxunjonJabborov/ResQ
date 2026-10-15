import { Clock, ImageOff, MapPin } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { ProductListItem } from '../api/types'
import { expiryLabel } from '../lib/format'
import { DiscountBadge, Price } from './Price'

export function ProductCard({ product }: { product: ProductListItem }) {
  const { t } = useTranslation()
  const expiry = expiryLabel(product.days_to_expiry)
  const urgent = product.days_to_expiry !== null && product.days_to_expiry <= 1
  return (
    <Link
      to={`/products/${product.id}`}
      className="card group flex flex-col overflow-hidden transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="relative aspect-[4/3] bg-surface">
        {product.main_image ? (
          <img src={product.main_image} alt="" loading="lazy" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-line">
            <ImageOff className="h-8 w-8" aria-hidden />
          </div>
        )}
        <DiscountBadge percent={product.discount_percent} className="absolute left-2 top-2" />
        {product.condition !== 'new' && (
          <span className="absolute bottom-2 left-2 rounded-md bg-black/60 px-1.5 py-0.5 text-[11px] text-white">
            {t(`product.conditions.${product.condition}`)}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3">
        <h3 className="line-clamp-2 text-sm font-medium leading-snug group-hover:text-brand-800">{product.title}</h3>
        <Price current={product.current_price} original={product.original_price} size="sm" />
        <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 text-xs text-muted">
          {expiry && (
            <span className={`inline-flex items-center gap-1 ${urgent ? 'font-semibold text-deal-700' : ''}`}>
              <Clock className="h-3.5 w-3.5" aria-hidden />
              {expiry}
            </span>
          )}
          <span className="inline-flex min-w-0 items-center gap-1">
            <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
            <span className="truncate">
              {product.distance_km != null ? `${product.distance_km.toFixed(1)} ${t('common.km')} · ` : ''}
              {product.seller.store_name}
            </span>
          </span>
        </div>
      </div>
    </Link>
  )
}

export function ProductGrid({ products }: { products: ProductListItem[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {products.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </div>
  )
}

/** Horizontally scrollable row of product cards for the home page. */
export function ProductRail({ products }: { products: ProductListItem[] }) {
  return (
    <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 [scrollbar-width:none]">
      {products.map((p) => (
        <div key={p.id} className="w-[46%] shrink-0 snap-start sm:w-56">
          <ProductCard product={p} />
        </div>
      ))}
    </div>
  )
}
