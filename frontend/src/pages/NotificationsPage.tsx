import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { notificationsApi } from '../api/endpoints'
import type { AppNotification } from '../api/types'
import { EmptyState, ErrorState, PageSpinner } from '../components/States'
import { qk } from '../hooks/queries'
import { formatDateTime } from '../lib/format'

export default function NotificationsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const query = useInfiniteQuery({
    queryKey: ['notifications', 'list'],
    queryFn: ({ pageParam }) => notificationsApi.list(pageParam),
    initialPageParam: 1,
    getNextPageParam: (last, all) => (last.next ? all.length + 1 : undefined),
  })
  const markRead = useMutation({
    mutationFn: (ids?: number[]) => notificationsApi.markRead(ids),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications', 'list'] })
      void qc.invalidateQueries({ queryKey: qk.unread })
    },
  })

  if (query.isPending) return <PageSpinner />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const items = query.data.pages.flatMap((p) => p.results)

  const open = (n: AppNotification) => {
    if (!n.is_read) markRead.mutate([n.id])
    if (n.url) navigate(n.url)
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-bold">{t('notifications.title')}</h1>
        {items.some((n) => !n.is_read) && (
          <button type="button" className="btn-ghost" onClick={() => markRead.mutate(undefined)}>
            <CheckCheck className="h-4 w-4" aria-hidden /> {t('notifications.markAllRead')}
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <EmptyState icon={Bell} title={t('notifications.empty')} />
      ) : (
        <ul className="card divide-y divide-line">
          {items.map((n) => (
            <li key={n.id}>
              <button type="button" onClick={() => open(n)} className="flex w-full gap-3 p-4 text-left hover:bg-surface">
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.is_read ? 'bg-transparent' : 'bg-deal-500'}`} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className={`block text-sm ${n.is_read ? '' : 'font-semibold'}`}>{n.title}</span>
                  {n.body && <span className="block whitespace-pre-line text-sm text-muted">{n.body}</span>}
                  <span className="mt-1 block text-xs text-muted">{formatDateTime(n.created_at)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {query.hasNextPage && (
        <button type="button" className="btn-secondary w-full" onClick={() => void query.fetchNextPage()}>
          {t('catalog.loadMore')}
        </button>
      )}
    </div>
  )
}
