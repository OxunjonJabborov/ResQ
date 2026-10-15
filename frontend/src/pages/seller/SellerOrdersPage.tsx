import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Check, Clock, KeyRound, PackageCheck, Phone, X } from 'lucide-react'
import QrScanner from 'qr-scanner'
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { sellerApi } from '../../api/endpoints'
import type { OrderStatus, SellerOrder } from '../../api/types'
import { Modal } from '../../components/Modal'
import { EmptyState, ErrorState, InlineError, PageSpinner, Spinner } from '../../components/States'
import { OrderStatusBadge } from '../../components/StatusBadge'
import { toast } from '../../components/Toast'
import { formatDateTime, formatMoney, formatPhone, minutesLeft } from '../../lib/format'

type Tab = 'pending' | 'confirmed' | 'ready_for_pickup' | 'history'
const TABS: Tab[] = ['pending', 'confirmed', 'ready_for_pickup', 'history']

function QrReader({ onResult, onError }: { onResult: (text: string) => void; onError: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  useEffect(() => {
    if (!video.current) return
    const scanner = new QrScanner(video.current, (result) => onResult(result.data), {
      preferredCamera: 'environment',
      highlightScanRegion: true,
      returnDetailedScanResult: true,
    })
    scanner.start().catch(onError)
    return () => {
      scanner.stop()
      scanner.destroy()
    }
  }, [onResult, onError])
  return <video ref={video} className="aspect-square w-full rounded-2xl bg-black object-cover" muted playsInline />
}

/** Complete an order by typed 6-digit code or by scanning the buyer's QR. */
function PickupDialog({ open, onClose, order }: { open: boolean; onClose: () => void; order?: SellerOrder }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [code, setCode] = useState('')
  const [scanning, setScanning] = useState(false)
  const [cameraError, setCameraError] = useState(false)
  const complete = useMutation({
    mutationFn: (value: string) => (order ? sellerApi.complete(order.id, value) : sellerApi.completeByCode(value)),
    onSuccess: (o) => {
      void qc.invalidateQueries({ queryKey: ['seller-orders'] })
      toast(t('sellerOrders.completedToast', { number: o.number }))
      setCode('')
      setScanning(false)
      onClose()
    },
  })
  const { mutate } = complete
  const handleScan = useCallback(
    (text: string) => {
      setScanning(false)
      mutate(text)
    },
    [mutate],
  )
  const handleError = useCallback(() => {
    setCameraError(true)
    setScanning(false)
  }, [])

  return (
    <Modal open={open} onClose={onClose} title={order ? `${t('sellerOrders.codeTitle')} ${order.number}` : t('sellerOrders.codeTitle')}>
      <form
        className="space-y-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          if (code.length === 6) complete.mutate(code)
        }}
      >
        <p className="text-sm text-muted">{t('sellerOrders.codeHint')}</p>
        <input
          className="input text-center font-mono text-3xl font-bold tracking-[0.4em]"
          inputMode="numeric"
          autoFocus
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          aria-label={t('orders.pickupCode')}
        />
        {scanning && <QrReader onResult={handleScan} onError={handleError} />}
        {cameraError && <p className="text-sm text-red-600">{t('sellerOrders.cameraError')}</p>}
        <InlineError error={complete.error} />
        <div className="flex flex-col gap-2 sm:flex-row">
          <button type="submit" className="btn-primary flex-1 !py-3" disabled={code.length !== 6 || complete.isPending}>
            {complete.isPending ? <Spinner className="h-4 w-4 !text-white" /> : <PackageCheck className="h-5 w-5" aria-hidden />}
            {t('sellerOrders.complete')}
          </button>
          <button type="button" className="btn-secondary" onClick={() => { setCameraError(false); setScanning((s) => !s) }}>
            <Camera className="h-4 w-4" aria-hidden /> {scanning ? t('sellerOrders.stopScan') : t('sellerOrders.scanQr')}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function OrderCard({ order, highlight, onComplete }: { order: SellerOrder; highlight?: boolean; onComplete: (o: SellerOrder) => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const done = () => void qc.invalidateQueries({ queryKey: ['seller-orders'] })
  const confirm = useMutation({ mutationFn: () => sellerApi.confirm(order.id), onSuccess: done })
  const ready = useMutation({ mutationFn: () => sellerApi.ready(order.id), onSuccess: done })
  const cancel = useMutation({ mutationFn: () => sellerApi.cancel(order.id), onSuccess: done })
  const busy = confirm.isPending || ready.isPending || cancel.isPending
  const left = order.status === 'pending' ? minutesLeft(order.confirm_deadline) : null

  return (
    <li className={`card space-y-3 p-4 ${highlight ? 'ring-2 ring-brand-600' : ''}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{order.number}</span>
        <OrderStatusBadge status={order.status} />
        <span className="ml-auto text-xs text-muted">{formatDateTime(order.created_at)}</span>
      </div>
      <ul className="text-sm">
        {order.items.map((i) => (
          <li key={i.id} className="flex justify-between gap-3">
            <span>
              {i.title} <span className="text-muted">× {i.quantity} {t(`product.units.${i.unit}`)}</span>
            </span>
            <span>{formatMoney(i.line_total)}</span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-sm">
        <span className="flex items-center gap-1">
          <span className="text-muted">{t('sellerOrders.buyer')}:</span> {order.buyer.first_name || '—'}
          <a href={`tel:${order.buyer.phone}`} className="inline-flex items-center gap-1 text-brand-700">
            <Phone className="h-3.5 w-3.5" aria-hidden /> {formatPhone(order.buyer.phone)}
          </a>
        </span>
        <span className="font-bold">{formatMoney(order.subtotal)}</span>
      </div>
      {order.buyer_note && (
        <p className="rounded-lg bg-surface px-3 py-2 text-sm">
          <span className="text-muted">{t('sellerOrders.note')}:</span> {order.buyer_note}
        </p>
      )}
      {left !== null && left > 0 && (
        <p className="flex items-center gap-1 text-xs font-medium text-deal-700">
          <Clock className="h-3.5 w-3.5" aria-hidden /> {t('sellerOrders.autoCancelIn', { minutes: left })}
        </p>
      )}
      {order.status === 'ready_for_pickup' && order.pickup_deadline && (
        <p className="flex items-center gap-1 text-xs text-muted">
          <Clock className="h-3.5 w-3.5" aria-hidden /> {t('sellerOrders.pickupBy', { time: formatDateTime(order.pickup_deadline) })}
        </p>
      )}
      {order.status === 'cancelled' && order.cancel_reason && <p className="text-xs text-red-600">{t(`orders.cancelReason.${order.cancel_reason}`)}</p>}
      <InlineError error={confirm.error ?? ready.error ?? cancel.error} />
      {['pending', 'confirmed', 'ready_for_pickup'].includes(order.status) && (
        <div className="flex flex-wrap gap-2">
          {order.status === 'pending' && (
            <button type="button" className="btn-primary" disabled={busy} onClick={() => confirm.mutate()}>
              <Check className="h-4 w-4" aria-hidden /> {t('sellerOrders.confirm')}
            </button>
          )}
          {order.status === 'confirmed' && (
            <button type="button" className="btn-primary" disabled={busy} onClick={() => ready.mutate()}>
              <PackageCheck className="h-4 w-4" aria-hidden /> {t('sellerOrders.ready')}
            </button>
          )}
          {order.status === 'ready_for_pickup' && (
            <button type="button" className="btn-primary" onClick={() => onComplete(order)}>
              <KeyRound className="h-4 w-4" aria-hidden /> {t('sellerOrders.enterCode')}
            </button>
          )}
          <button
            type="button"
            className="btn-ghost text-red-600"
            disabled={busy}
            onClick={() => window.confirm(t('sellerOrders.cancelConfirm')) && cancel.mutate()}
          >
            <X className="h-4 w-4" aria-hidden /> {t('sellerOrders.cancel')}
          </button>
        </div>
      )}
    </li>
  )
}

export default function SellerOrdersPage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [chosenTab, setTab] = useState<Tab | null>(null)
  const [pickup, setPickup] = useState<{ open: boolean; order?: SellerOrder }>({ open: false })
  const counts = useQuery({
    queryKey: ['seller-orders', 'active'],
    queryFn: () => sellerApi.orders({ status: undefined, page_size: 100, ordering: '-created_at' }),
    refetchInterval: 30_000,
  })
  const focused = useQuery({ queryKey: ['seller-orders', 'one', id], queryFn: () => sellerApi.order(id!), enabled: !!id })

  // A linked order (e.g. from a notification) opens its tab until the user picks one.
  const focusedStatus = focused.data?.status
  const focusedTab: Tab | null = focusedStatus
    ? ['completed', 'cancelled'].includes(focusedStatus)
      ? 'history'
      : (focusedStatus as Tab)
    : null

  if (counts.isPending) return <PageSpinner />
  if (counts.isError) return <ErrorState error={counts.error} onRetry={() => void counts.refetch()} />
  const all = counts.data.results
  const byTab = (tb: Tab) => all.filter((o) => (tb === 'history' ? ['completed', 'cancelled'].includes(o.status) : o.status === (tb as OrderStatus)))
  // Open the first tab that needs attention unless the user or a link picked one.
  const firstBusy = (['pending', 'confirmed', 'ready_for_pickup'] as Tab[]).find((tb) => byTab(tb).length > 0)
  const tab: Tab = chosenTab ?? focusedTab ?? firstBusy ?? 'pending'
  const shown = byTab(tab)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4">
          {TABS.map((tb) => {
            const n = tb === 'history' ? 0 : byTab(tb).length
            return (
              <button key={tb} type="button" className={tab === tb ? 'chip-active' : 'chip'} onClick={() => setTab(tb)}>
                {t(`sellerOrders.tabs.${tb}`)}
                {n > 0 && <span className={`rounded-full px-1.5 text-xs ${tab === tb ? 'bg-white/25' : 'bg-deal-100 text-deal-700'}`}>{n}</span>}
              </button>
            )
          })}
        </div>
        <button type="button" className="btn-primary ml-auto" onClick={() => setPickup({ open: true })}>
          <KeyRound className="h-4 w-4" aria-hidden /> {t('sellerOrders.enterCode')}
        </button>
      </div>
      {shown.length === 0 ? (
        <EmptyState icon={PackageCheck} title={t('sellerOrders.empty')} />
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {shown.map((o) => (
            <OrderCard key={o.id} order={o} highlight={String(o.id) === id} onComplete={(order) => setPickup({ open: true, order })} />
          ))}
        </ul>
      )}
      <PickupDialog open={pickup.open} order={pickup.order} onClose={() => setPickup({ open: false })} />
    </div>
  )
}
