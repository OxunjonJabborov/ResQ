import { Bell, Heart, Home, LayoutGrid, Leaf, Package, ShoppingBag, Store, User } from 'lucide-react'
import { NavLink, Outlet, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../auth/AuthContext'
import { useCart, useUnreadCount } from '../hooks/queries'
import { LanguageSwitcher } from './LanguageSwitcher'
import { ToastHost } from './Toast'

function Badge({ count }: { count?: number }) {
  if (!count) return null
  return (
    <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-deal-600 px-1 text-[10px] font-bold text-white">
      {count > 99 ? '99+' : count}
    </span>
  )
}

export function Layout() {
  const { t } = useTranslation()
  const { user, isAuthenticated } = useAuth()
  const cart = useCart()
  const unread = useUnreadCount()
  const cartCount = cart.data?.item_count
  const navClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition ${
      isActive ? 'bg-brand-50 text-brand-800' : 'text-muted hover:text-ink'
    }`

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-card/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4">
          <Link to="/" className="flex items-center gap-1.5 text-lg font-extrabold tracking-tight text-brand-800">
            <span className="rounded-lg bg-brand-700 p-1 text-white">
              <Leaf className="h-4 w-4" aria-hidden />
            </span>
            ResQ
          </Link>
          <nav className="ml-4 hidden items-center gap-1 md:flex" aria-label="Main">
            <NavLink to="/catalog" className={navClass}>
              {t('nav.catalog')}
            </NavLink>
            {isAuthenticated && (
              <>
                <NavLink to="/orders" className={navClass}>
                  {t('nav.orders')}
                </NavLink>
                <NavLink to="/favorites" className={navClass}>
                  {t('nav.favorites')}
                </NavLink>
              </>
            )}
            {user?.is_seller && (
              <NavLink to="/seller" className={navClass}>
                <Store className="h-4 w-4" aria-hidden />
                {t('nav.seller')}
              </NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <LanguageSwitcher />
            {isAuthenticated ? (
              <>
                <Link to="/notifications" className="btn-ghost relative !px-2.5" aria-label={t('nav.notifications')}>
                  <Bell className="h-5 w-5" />
                  <Badge count={unread.data?.count} />
                </Link>
                <Link to="/cart" className="btn-ghost relative hidden !px-2.5 md:inline-flex" aria-label={t('nav.cart')}>
                  <ShoppingBag className="h-5 w-5" />
                  <Badge count={cartCount} />
                </Link>
                <Link to="/profile" className="btn-ghost hidden !px-2.5 md:inline-flex" aria-label={t('nav.profile')}>
                  <User className="h-5 w-5" />
                </Link>
              </>
            ) : (
              <Link to="/login" className="btn-primary !py-2">
                {t('nav.login')}
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-24 pt-4 md:pb-10">
        <Outlet />
      </main>

      {/* Mobile bottom navigation */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
        aria-label="Mobile"
      >
        <div className="grid grid-cols-5">
          {[
            { to: '/', icon: Home, label: t('nav.home'), end: true },
            { to: '/catalog', icon: LayoutGrid, label: t('nav.catalog') },
            { to: '/cart', icon: ShoppingBag, label: t('nav.cart'), badge: cartCount },
            user?.is_seller
              ? { to: '/seller', icon: Store, label: t('nav.seller') }
              : isAuthenticated
                ? { to: '/favorites', icon: Heart, label: t('nav.favorites') }
                : { to: '/orders', icon: Package, label: t('nav.orders') },
            { to: isAuthenticated ? '/profile' : '/login', icon: User, label: t('nav.profile') },
          ].map(({ to, icon: Icon, label, end, badge }) => (
            <NavLink
              key={to + label}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium ${isActive ? 'text-brand-700' : 'text-muted'}`
              }
            >
              <span className="relative">
                <Icon className="h-5 w-5" aria-hidden />
                <Badge count={badge} />
              </span>
              <span className="max-w-full truncate px-1">{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
      <ToastHost />
    </div>
  )
}
