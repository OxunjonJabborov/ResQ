import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { EyeOff, ImageOff, PackagePlus, Pencil, Rocket, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { sellerApi } from '../../api/endpoints'
import type { ProductStatus, SellerProduct } from '../../api/types'
import { Price } from '../../components/Price'
import { EmptyState, ErrorState, InlineError, PageSpinner } from '../../components/States'
import { ProductStatusBadge } from '../../components/StatusBadge'
import { toast } from '../../components/Toast'
import { formatDate } from '../../lib/format'

const FILTERS: ('' | ProductStatus)[] = ['', 'active', 'draft', 'sold_out', 'expired', 'hidden']

export default function SellerProductsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [status, setStatus] = useState<'' | ProductStatus>('')
  const query = useQuery({
    queryKey: ['seller-products', status],
    queryFn: () => sellerApi.products({ status, page_size: 100 }),
  })
  const invalidate = () => void qc.invalidateQueries({ queryKey: ['seller-products'] })
  const setProductStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'draft' | 'active' | 'hidden' }) => sellerApi.setStatus(id, status),
    onSuccess: () => {
      invalidate()
      toast(t('common.saved'))
    },
  })
  const remove = useMutation({ mutationFn: sellerApi.deleteProduct, onSuccess: invalidate })

  const actions = (p: SellerProduct) => (
    <div className="flex flex-wrap gap-1">
      <Link to={`/seller/products/${p.id}`} className="btn-ghost !px-2.5 !py-1.5" aria-label={t('common.edit')}>
        <Pencil className="h-4 w-4" />
      </Link>
      {p.status !== 'active' && p.status !== 'sold_out' && (
        <button type="button" className="btn-ghost !px-2.5 !py-1.5 text-brand-700" onClick={() => setProductStatus.mutate({ id: p.id, status: 'active' })}>
          <Rocket className="h-4 w-4" aria-hidden /> <span className="text-xs">{t('sellerProducts.publish')}</span>
        </button>
      )}
      {(p.status === 'active' || p.status === 'sold_out') && (
        <button type="button" className="btn-ghost !px-2.5 !py-1.5" onClick={() => setProductStatus.mutate({ id: p.id, status: 'hidden' })}>
          <EyeOff className="h-4 w-4" aria-hidden /> <span className="text-xs">{t('sellerProducts.hide')}</span>
        </button>
      )}
      <button
        type="button"
        className="btn-ghost !px-2.5 !py-1.5 text-red-600"
        aria-label={t('common.delete')}
        onClick={() => window.confirm(t('sellerProducts.deleteConfirm')) && remove.mutate(p.id)}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4">
          {FILTERS.map((f) => (
            <button key={f || 'all'} type="button" className={status === f ? 'chip-active' : 'chip'} onClick={() => setStatus(f)}>
              {f ? t(`sellerProducts.status.${f}`) : t('sellerProducts.all')}
            </button>
          ))}
        </div>
        <Link to="/seller/products/new" className="btn-primary">
          <PackagePlus className="h-4 w-4" aria-hidden /> {t('sellerProducts.new')}
        </Link>
      </div>
      <InlineError error={setProductStatus.error ?? remove.error} />
      {query.isPending ? (
        <PageSpinner />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.results.length === 0 ? (
        <EmptyState
          icon={PackagePlus}
          title={t('sellerProducts.empty')}
          hint={t('sellerProducts.emptyHint')}
          action={<Link to="/seller/products/new" className="btn-primary">{t('sellerProducts.new')}</Link>}
        />
      ) : (
        <ul className="space-y-3">
          {query.data.results.map((p) => (
            <li key={p.id} className="card flex gap-3 p-3">
              <Link to={`/seller/products/${p.id}`} className="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-surface">
                {p.images[0] ? (
                  <img src={p.images[0].image} alt="" className="h-full w-full object-cover" />
                ) : (
                  <span className="flex h-full items-center justify-center text-line">
                    <ImageOff className="h-6 w-6" aria-hidden />
                  </span>
                )}
              </Link>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Link to={`/seller/products/${p.id}`} className="truncate font-medium">
                    {p.title}
                  </Link>
                  <ProductStatusBadge status={p.status} />
                  {p.status === 'active' && !p.is_public && <span className="text-xs text-amber-700">{t('sellerProducts.notPublic')}</span>}
                </div>
                <Price current={p.current_price} original={p.original_price} size="sm" />
                <p className="text-xs text-muted">
                  {t('sellerProducts.stock')}: {p.quantity} {t(`product.units.${p.unit}`)}
                  {p.expiry_date && ` · ${t('product.expiry')}: ${formatDate(p.expiry_date)}`}
                </p>
                {actions(p)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
