import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CreditCard, Wallet } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { ordersApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { ErrorState, InlineError, PageSpinner, Spinner } from '../components/States'
import { toast } from '../components/Toast'
import { qk, useCart } from '../hooks/queries'
import { formatDateTime, formatMoney } from '../lib/format'

export default function CheckoutPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { user } = useAuth()
  const cart = useCart()
  const methods = useQuery({ queryKey: ['payment-methods'], queryFn: ordersApi.paymentMethods, staleTime: Infinity })
  const [method, setMethod] = useState('cash')
  const [note, setNote] = useState('')
  const place = useMutation({
    mutationFn: () => ordersApi.checkout(method, note),
    onSuccess: (orders) => {
      void qc.invalidateQueries({ queryKey: qk.cart })
      void qc.invalidateQueries({ queryKey: ['orders'] })
      toast(t('checkout.success'))
      navigate(orders.length === 1 ? `/orders/${orders[0].id}` : '/orders')
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'cart_unavailable') void qc.invalidateQueries({ queryKey: qk.cart })
    },
  })

  if (cart.isPending || methods.isPending) return <PageSpinner />
  if (cart.isError) return <ErrorState error={cart.error} onRetry={() => void cart.refetch()} />
  if (cart.data.item_count === 0 && !place.isPending) return <Navigate to="/cart" replace />
  const blockedUntil = user?.order_blocked_until

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <h1 className="text-xl font-bold">{t('checkout.title')}</h1>
      {blockedUntil && new Date(blockedUntil) > new Date() && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{t('profile.blocked', { time: formatDateTime(blockedUntil) })}</p>
      )}
      <section className="card divide-y divide-line">
        {cart.data.groups.map((g) => (
          <div key={g.seller.id} className="flex justify-between gap-4 p-4 text-sm">
            <div>
              <p className="font-semibold">{g.seller.store_name}</p>
              <p className="text-muted">{g.seller.address}</p>
              <p className="text-muted">{g.lines.map((l) => `${l.product.title} × ${l.quantity}`).join(', ')}</p>
            </div>
            <span className="shrink-0 font-semibold">{formatMoney(g.subtotal)}</span>
          </div>
        ))}
      </section>

      <fieldset className="card space-y-2 p-4">
        <legend className="px-1 text-sm font-semibold">{t('checkout.paymentMethod')}</legend>
        {(methods.data ?? []).map((m) => (
          <label key={m.code} className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3 ${method === m.code ? 'border-brand-700 bg-brand-50' : 'border-line'}`}>
            <input type="radio" name="payment" value={m.code} checked={method === m.code} onChange={() => setMethod(m.code)} className="accent-brand-700" />
            {m.code === 'card' ? <CreditCard className="h-5 w-5 text-muted" aria-hidden /> : <Wallet className="h-5 w-5 text-muted" aria-hidden />}
            <span className="text-sm font-medium">{t(`orders.payment.${m.code}`, { defaultValue: m.name })}</span>
          </label>
        ))}
      </fieldset>

      <label className="block">
        <span className="label">
          {t('checkout.note')} <span className="font-normal text-muted">({t('common.optional')})</span>
        </span>
        <textarea className="input min-h-20" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('checkout.notePlaceholder')} />
      </label>

      <p className="text-sm text-muted">{t('checkout.pickupInfo')}</p>
      {cart.data.groups.length > 1 && <p className="text-sm text-muted">{t('cart.splitNote', { count: cart.data.groups.length })}</p>}
      <InlineError error={place.error} />
      <button type="button" className="btn-primary w-full !py-3.5 text-base" disabled={place.isPending} onClick={() => place.mutate()}>
        {place.isPending && <Spinner className="h-4 w-4 !text-white" />}
        {t('checkout.placeOrder')} · {formatMoney(cart.data.total)}
      </button>
    </div>
  )
}
