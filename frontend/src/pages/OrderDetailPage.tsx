import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Clock, MapPin, Phone } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ordersApi } from '../api/endpoints'
import type { BuyerOrder } from '../api/types'
import { Modal } from '../components/Modal'
import { ErrorState, InlineError, PageSpinner, Spinner } from '../components/States'
import { StarInput, Stars } from '../components/Stars'
import { OrderStatusBadge } from '../components/StatusBadge'
import { toast } from '../components/Toast'
import { formatDateTime, formatMoney, formatPhone, mapsUrl } from '../lib/format'

function ReviewForm({ order }: { order: BuyerOrder }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const mutation = useMutation({
    mutationFn: () => ordersApi.review(order.id, rating, comment),
    onSuccess: () => {
      toast(t('orders.reviewThanks'))
      void qc.invalidateQueries({ queryKey: ['order', String(order.id)] })
    },
  })
  return (
    <form
      className="card space-y-3 p-4"
      onSubmit={(e: FormEvent) => {
        e.preventDefault()
        mutation.mutate()
      }}
    >
      <h2 className="font-semibold">{t('orders.reviewTitle')}</h2>
      <StarInput value={rating} onChange={setRating} />
      <textarea className="input min-h-20" maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} placeholder={t('orders.reviewPlaceholder')} />
      <InlineError error={mutation.error} />
      <button type="submit" className="btn-primary" disabled={mutation.isPending}>
        {t('orders.reviewSend')}
      </button>
    </form>
  )
}

function DisputeDialog({ order, open, onClose }: { order: BuyerOrder; open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [description, setDescription] = useState('')
  const mutation = useMutation({
    mutationFn: () => ordersApi.dispute(order.id, reason, description),
    onSuccess: () => {
      toast(t('orders.disputeSent'))
      onClose()
    },
  })
  return (
    <Modal open={open} onClose={onClose} title={t('orders.dispute')}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          mutation.mutate()
        }}
      >
        <label className="block">
          <span className="label">{t('orders.disputeReason')}</span>
          <input className="input" required maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <label className="block">
          <span className="label">{t('orders.disputeDescription')}</span>
          <textarea className="input min-h-28" required maxLength={3000} value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <InlineError error={mutation.error} />
        <button type="submit" className="btn-primary w-full" disabled={mutation.isPending}>
          {t('orders.reviewSend')}
        </button>
      </form>
    </Modal>
  )
}

export default function OrderDetailPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [disputeOpen, setDisputeOpen] = useState(false)
  const query = useQuery({
    queryKey: ['order', id],
    queryFn: () => ordersApi.get(id),
    refetchInterval: (q) => (q.state.data && ['pending', 'confirmed', 'ready_for_pickup'].includes(q.state.data.status) ? 30_000 : false),
  })
  const cancel = useMutation({
    mutationFn: () => ordersApi.cancel(Number(id)),
    onSuccess: (order) => {
      qc.setQueryData(['order', id], order)
      void qc.invalidateQueries({ queryKey: ['orders'] })
    },
  })

  if (query.isPending) return <PageSpinner />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const o = query.data

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Link to="/orders" className="text-sm text-muted">← {t('orders.title')}</Link>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">{t('orders.orderNumber', { number: o.number })}</h1>
        <OrderStatusBadge status={o.status} />
      </div>
      <p className="text-sm text-muted">{t('orders.placed', { time: formatDateTime(o.created_at) })}</p>

      {o.pickup_code && (
        <section className="card flex flex-col items-center gap-3 p-5 text-center">
          <p className="text-sm font-medium text-muted">{t('orders.pickupCode')}</p>
          <p className="font-mono text-4xl font-extrabold tracking-[0.3em] text-brand-800">{o.pickup_code}</p>
          {o.pickup_qr && <img src={o.pickup_qr} alt="QR" className="h-44 w-44" />}
          <p className="text-sm text-muted">{t('orders.qrHint')}</p>
          {o.status === 'ready_for_pickup' && o.pickup_deadline && (
            <p className="flex items-center gap-1 text-sm font-semibold text-deal-700">
              <Clock className="h-4 w-4" aria-hidden />
              {t('orders.pickupBefore', { time: formatDateTime(o.pickup_deadline) })}
            </p>
          )}
          {o.status === 'pending' && <p className="text-sm text-muted">{t('orders.confirmBy', { time: formatDateTime(o.confirm_deadline) })}</p>}
        </section>
      )}

      {o.status === 'cancelled' && o.cancel_reason && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">
          {t(`orders.cancelReason.${o.cancel_reason}`)}
          {o.cancel_comment ? ` — ${o.cancel_comment}` : ''}
        </p>
      )}

      <section className="card p-4">
        <h2 className="font-semibold">{o.seller.store_name}</h2>
        <p className="mt-1 flex items-start gap-2 text-sm text-muted">
          <MapPin className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {o.seller.city.name}, {o.seller.address}
        </p>
        <div className="mt-3 flex gap-2">
          <a className="btn-secondary flex-1" href={mapsUrl(o.seller.latitude, o.seller.longitude)} target="_blank" rel="noreferrer">
            <MapPin className="h-4 w-4" aria-hidden /> {t('orders.directions')}
          </a>
          <a className="btn-secondary flex-1" href={`tel:${o.seller.phone}`}>
            <Phone className="h-4 w-4" aria-hidden /> {formatPhone(o.seller.phone)}
          </a>
        </div>
      </section>

      <section className="card divide-y divide-line">
        <h2 className="p-4 font-semibold">{t('orders.items')}</h2>
        {o.items.map((item) => (
          <div key={item.id} className="flex justify-between gap-3 p-4 text-sm">
            <Link to={`/products/${item.product}`} className="min-w-0">
              {item.title} <span className="text-muted">× {item.quantity} {t(`product.units.${item.unit}`)}</span>
            </Link>
            <span className="shrink-0 font-medium">{formatMoney(item.line_total)}</span>
          </div>
        ))}
        <div className="space-y-1 p-4 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">{t('orders.savings')}</span>
            <span className="font-semibold text-brand-700">{formatMoney(o.savings)}</span>
          </div>
          <div className="flex justify-between text-base font-bold">
            <span>{t('orders.total')}</span>
            <span>{formatMoney(o.subtotal)}</span>
          </div>
          <p className="text-muted">{t(`orders.payment.${o.payment_method}`, { defaultValue: o.payment_method })}</p>
        </div>
      </section>

      {o.can_review && <ReviewForm order={o} />}
      {o.review && (
        <section className="card p-4">
          <h2 className="mb-1 font-semibold">{t('orders.yourReview')}</h2>
          <Stars value={o.review.rating} />
          {o.review.comment && <p className="mt-1 text-sm">{o.review.comment}</p>}
        </section>
      )}

      <InlineError error={cancel.error} />
      <div className="flex flex-col gap-2 sm:flex-row">
        {o.can_cancel && (
          <button
            type="button"
            className="btn-secondary !text-red-600"
            disabled={cancel.isPending}
            onClick={() => window.confirm(t('orders.cancelConfirm')) && cancel.mutate()}
          >
            {cancel.isPending && <Spinner className="h-4 w-4" />}
            {t('orders.cancel')}
          </button>
        )}
        {(o.status === 'completed' || o.status === 'cancelled') && (
          <button type="button" className="btn-ghost" onClick={() => setDisputeOpen(true)}>
            <AlertTriangle className="h-4 w-4" aria-hidden /> {t('orders.dispute')}
          </button>
        )}
      </div>
      <DisputeDialog order={o} open={disputeOpen} onClose={() => setDisputeOpen(false)} />
    </div>
  )
}
