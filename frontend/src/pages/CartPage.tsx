import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, ShoppingBag, Store, Trash2 } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { cartApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { Price } from '../components/Price'
import { QtyStepper } from '../components/QtyStepper'
import { EmptyState, ErrorState, InlineError, PageSpinner } from '../components/States'
import { qk, useCart } from '../hooks/queries'
import { formatMoney } from '../lib/format'

export default function CartPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { isAuthenticated, isLoading } = useAuth()
  const qc = useQueryClient()
  const cart = useCart()
  const update = useMutation({
    mutationFn: ({ id, quantity }: { id: number; quantity: number }) => cartApi.update(id, quantity),
    onSuccess: (data) => qc.setQueryData(qk.cart, data),
  })
  const remove = useMutation({
    mutationFn: (id: number) => cartApi.remove(id),
    onSuccess: (data) => qc.setQueryData(qk.cart, data),
  })

  if (isLoading) return <PageSpinner />
  if (!isAuthenticated) {
    return (
      <EmptyState
        icon={ShoppingBag}
        title={t('cart.loginToCheckout')}
        action={<Link to="/login?next=/cart" className="btn-primary">{t('nav.login')}</Link>}
      />
    )
  }
  if (cart.isPending) return <PageSpinner />
  if (cart.isError) return <ErrorState error={cart.error} onRetry={() => void cart.refetch()} />
  const data = cart.data
  if (data.item_count === 0) {
    return (
      <EmptyState
        icon={ShoppingBag}
        title={t('cart.empty')}
        hint={t('cart.emptyHint')}
        action={<Link to="/catalog" className="btn-primary">{t('cart.browse')}</Link>}
      />
    )
  }
  const hasProblems = data.groups.some((g) => g.lines.some((l) => !l.available))

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-4">
        <h1 className="text-xl font-bold">{t('cart.title')}</h1>
        {data.groups.map((group) => (
          <section key={group.seller.id} className="card overflow-hidden">
            <header className="flex items-center gap-2 border-b border-line bg-surface/60 px-4 py-3">
              <Store className="h-4 w-4 text-brand-700" aria-hidden />
              <Link to={`/stores/${group.seller.id}`} className="font-semibold">
                {group.seller.store_name}
              </Link>
              <span className="truncate text-xs text-muted">· {group.seller.address}</span>
            </header>
            <ul className="divide-y divide-line">
              {group.lines.map((line) => (
                <li key={line.id} className={`flex gap-3 p-4 ${line.available ? '' : 'opacity-70'}`}>
                  <Link to={`/products/${line.product.id}`} className="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-surface">
                    {line.product.main_image && <img src={line.product.main_image} alt="" className="h-full w-full object-cover" />}
                  </Link>
                  <div className="min-w-0 flex-1 space-y-1">
                    <Link to={`/products/${line.product.id}`} className="line-clamp-2 text-sm font-medium">
                      {line.product.title}
                    </Link>
                    <Price current={line.product.current_price} original={line.product.original_price} size="sm" />
                    {!line.available && (
                      <p className="flex items-center gap-1 text-xs font-medium text-red-600">
                        <AlertCircle className="h-3.5 w-3.5" aria-hidden />
                        {line.problem === 'insufficient_stock'
                          ? t('cart.insufficientStock', { count: line.product.quantity })
                          : t('cart.unavailable')}
                      </p>
                    )}
                    <div className="flex items-center justify-between pt-1">
                      <QtyStepper
                        value={line.quantity}
                        max={Math.max(line.product.quantity, 1)}
                        disabled={update.isPending || line.problem === 'unavailable'}
                        onChange={(quantity) => update.mutate({ id: line.id, quantity })}
                      />
                      <button type="button" className="btn-ghost !p-2" onClick={() => remove.mutate(line.id)} aria-label={t('cart.remove')}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
        <InlineError error={update.error ?? remove.error} />
      </div>

      <aside className="card h-fit space-y-3 p-5 lg:sticky lg:top-20">
        <div className="flex justify-between text-sm">
          <span className="text-muted">{t('cart.savings')}</span>
          <span className="font-semibold text-brand-700">{formatMoney(data.original_total - data.total)}</span>
        </div>
        <div className="flex justify-between text-lg font-bold">
          <span>{t('cart.total')}</span>
          <span>{formatMoney(data.total)}</span>
        </div>
        {data.groups.length > 1 && <p className="text-xs text-muted">{t('cart.splitNote', { count: data.groups.length })}</p>}
        {hasProblems && <p className="text-xs text-red-600">{t('cart.fixProblems')}</p>}
        <button type="button" className="btn-primary w-full !py-3" disabled={hasProblems} onClick={() => navigate('/checkout')}>
          {t('cart.checkout')}
        </button>
      </aside>
    </div>
  )
}
