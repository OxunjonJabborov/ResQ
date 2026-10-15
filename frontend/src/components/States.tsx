import { AlertTriangle, Loader2, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { useErrorMessage } from '../hooks/useErrorMessage'

export function Spinner({ className = 'h-5 w-5' }: { className?: string }) {
  return <Loader2 className={`animate-spin text-brand-700 ${className}`} aria-hidden />
}

export function PageSpinner() {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-[40vh] items-center justify-center" role="status" aria-live="polite">
      <Spinner className="h-8 w-8" />
      <span className="sr-only">{t('common.loading')}</span>
    </div>
  )
}

export function EmptyState({
  icon: Icon,
  title,
  hint,
  action,
}: {
  icon: LucideIcon
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-4 rounded-full bg-brand-50 p-4 text-brand-700">
        <Icon className="h-8 w-8" aria-hidden />
      </div>
      <h2 className="text-lg font-semibold">{title}</h2>
      {hint && <p className="mt-1 max-w-sm text-sm text-muted">{hint}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation()
  const message = useErrorMessage()(error)
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center" role="alert">
      <div className="mb-4 rounded-full bg-red-50 p-4 text-red-600">
        <AlertTriangle className="h-8 w-8" aria-hidden />
      </div>
      <h2 className="text-lg font-semibold">{t('common.errorTitle')}</h2>
      <p className="mt-1 max-w-sm text-sm text-muted">{message}</p>
      {onRetry && (
        <button type="button" className="btn-secondary mt-5" onClick={onRetry}>
          {t('common.retry')}
        </button>
      )}
    </div>
  )
}

export function InlineError({ error }: { error: unknown }) {
  const message = useErrorMessage()(error)
  if (!error) return null
  return (
    <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
      {message}
    </p>
  )
}

export function SkeletonGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card animate-pulse overflow-hidden">
          <div className="aspect-[4/3] bg-line/60" />
          <div className="space-y-2 p-3">
            <div className="h-3 w-3/4 rounded bg-line/70" />
            <div className="h-4 w-1/2 rounded bg-line/70" />
          </div>
        </div>
      ))}
    </div>
  )
}
