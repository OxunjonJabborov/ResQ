import { BadgeCheck, Clock, XCircle } from 'lucide-react'
import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api/client'
import { ErrorState, PageSpinner } from '../../components/States'
import { useSellerProfile } from '../../hooks/queries'

export default function SellerLayout() {
  const { t } = useTranslation()
  const location = useLocation()
  const profile = useSellerProfile()
  const noStore = profile.error instanceof ApiError && profile.error.status === 404

  if (profile.isPending) return <PageSpinner />
  if (profile.isError && !noStore) return <ErrorState error={profile.error} onRetry={() => void profile.refetch()} />
  // Without a store only the onboarding form is reachable.
  if (noStore && !location.pathname.startsWith('/seller/store')) return <Navigate to="/seller/store" replace />

  const p = profile.data
  const tabs = [
    { to: '/seller/orders', label: t('seller.tabs.orders'), match: (path: string) => path === '/seller' || path.startsWith('/seller/orders') },
    { to: '/seller/products', label: t('seller.tabs.products') },
    { to: '/seller/stats', label: t('seller.tabs.stats') },
    { to: '/seller/store', label: t('seller.tabs.store') },
  ]

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold">{p?.store_name ?? t('seller.createStore')}</h1>
        {p?.verification_status === 'verified' && (
          <span className="inline-flex items-center gap-1 rounded-full bg-brand-100 px-2.5 py-1 text-xs font-semibold text-brand-800">
            <BadgeCheck className="h-3.5 w-3.5" aria-hidden /> {t('seller.verified')}
          </span>
        )}
      </div>
      {p?.verification_status === 'pending' && (
        <p className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <Clock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {t('seller.verificationPending')}
        </p>
      )}
      {p?.verification_status === 'rejected' && (
        <p className="flex gap-2 rounded-xl bg-red-50 p-3 text-sm text-red-700">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {t('seller.verificationRejected', { note: p.verification_note || '—' })}
        </p>
      )}
      {p && (
        <nav className="-mx-4 flex gap-1 overflow-x-auto border-b border-line px-4" aria-label={t('seller.title')}>
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) => {
                const active = tab.match ? tab.match(location.pathname) : isActive
                return `whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium ${
                  active ? 'border-brand-700 text-brand-800' : 'border-transparent text-muted hover:text-ink'
                }`
              }}
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      )}
      <Outlet />
    </div>
  )
}
