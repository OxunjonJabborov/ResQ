import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LogOut, Send, Store } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { authApi, notificationsApi } from '../api/endpoints'
import type { Lang, NotificationPreferences } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { InlineError, PageSpinner, Spinner } from '../components/States'
import { toast } from '../components/Toast'
import { useCategories, useCities } from '../hooks/queries'
import { formatDateTime, formatPhone } from '../lib/format'
import i18n from '../i18n'

function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 py-3">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        {hint && <span className="block text-xs text-muted">{hint}</span>}
      </span>
      <input type="checkbox" className="mt-1 h-5 w-5 accent-brand-700" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </label>
  )
}

function NotificationSettings() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const categories = useCategories()
  const prefs = useQuery({ queryKey: ['prefs'], queryFn: notificationsApi.preferences })
  const update = useMutation({
    mutationFn: (data: Partial<NotificationPreferences>) => notificationsApi.updatePreferences(data),
    onSuccess: (data) => qc.setQueryData(['prefs'], data),
  })
  const link = useMutation({
    mutationFn: notificationsApi.telegramLink,
    onSuccess: (res) => {
      if (res.url) window.open(res.url, '_blank', 'noopener')
      else toast(t('profile.telegramNotConfigured'), 'error')
    },
  })
  const unlink = useMutation({
    mutationFn: notificationsApi.telegramUnlink,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['prefs'] }),
  })
  if (prefs.isPending) return <Spinner />
  if (!prefs.data) return null
  const p = prefs.data
  const fav = new Set(p.favorite_categories)

  return (
    <section className="card p-5">
      <h2 className="font-semibold">{t('profile.notifications')}</h2>
      <div className="divide-y divide-line">
        <div className="flex flex-wrap items-center justify-between gap-3 py-3">
          <span className="text-sm font-medium">{p.telegram_connected ? t('profile.telegramConnected') : t('profile.telegram')}</span>
          {p.telegram_connected ? (
            <button type="button" className="btn-ghost" onClick={() => unlink.mutate()}>
              {t('profile.telegramDisconnect')}
            </button>
          ) : (
            <button type="button" className="btn-secondary" onClick={() => link.mutate()} disabled={link.isPending}>
              <Send className="h-4 w-4" aria-hidden /> {t('profile.telegramConnect')}
            </button>
          )}
        </div>
        {p.telegram_connected && (
          <Toggle checked={p.telegram_enabled} onChange={(v) => update.mutate({ telegram_enabled: v })} label={t('profile.telegram')} />
        )}
        <Toggle checked={p.email_enabled} onChange={(v) => update.mutate({ email_enabled: v })} label={t('profile.emailNotifications')} />
        <Toggle checked={p.deals_enabled} onChange={(v) => update.mutate({ deals_enabled: v })} label={t('profile.deals')} hint={t('profile.dealsHint')} />
        <div className="py-3">
          <p className="mb-2 text-sm font-medium">{t('profile.favoriteCategories')}</p>
          <div className="flex flex-wrap gap-2">
            {(categories.data ?? []).map((c) => (
              <button
                key={c.id}
                type="button"
                className={fav.has(c.id) ? 'chip-active' : 'chip'}
                aria-pressed={fav.has(c.id)}
                onClick={() => {
                  const next = new Set(fav)
                  if (next.has(c.id)) next.delete(c.id)
                  else next.add(c.id)
                  update.mutate({ favorite_categories: [...next] })
                }}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>
      </div>
      <InlineError error={update.error ?? link.error} />
    </section>
  )
}

export default function ProfilePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const qc = useQueryClient()
  const { user, logout } = useAuth()
  const cities = useCities()
  // Seeded once from the loaded user; the form owns its edits afterwards.
  const [form, setForm] = useState(() => ({
    first_name: user?.first_name ?? '',
    last_name: user?.last_name ?? '',
    email: user?.email ?? '',
    city: user?.city ? String(user.city) : '',
    language: (user?.language ?? 'uz') as Lang,
  }))

  const save = useMutation({
    mutationFn: () => authApi.updateMe({ ...form, city: form.city ? Number(form.city) : null }),
    onSuccess: (data) => {
      qc.setQueryData(['me'], data)
      void i18n.changeLanguage(data.language)
      toast(t('common.saved'))
      const next = params.get('next')
      if (params.get('welcome') && next?.startsWith('/') && !next.startsWith('//')) navigate(next)
    },
  })

  if (!user) return <PageSpinner />
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const field = (key: 'first_name' | 'last_name' | 'email') => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [key]: e.target.value })),
  })

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <h1 className="text-xl font-bold">{t('profile.title')}</h1>
      {params.get('welcome') && <p className="rounded-xl bg-brand-50 p-3 text-sm text-brand-800">{t('auth.completeProfile')}</p>}
      {user.order_blocked_until && new Date(user.order_blocked_until) > new Date() && (
        <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{t('profile.blocked', { time: formatDateTime(user.order_blocked_until) })}</p>
      )}

      <form onSubmit={onSubmit} className="card space-y-4 p-5">
        <p className="text-sm">
          <span className="text-muted">{t('profile.phone')}: </span>
          <span className="font-medium">{formatPhone(user.phone)}</span>
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label">{t('profile.firstName')}</span>
            <input className="input" maxLength={80} autoComplete="given-name" {...field('first_name')} />
          </label>
          <label className="block">
            <span className="label">{t('profile.lastName')}</span>
            <input className="input" maxLength={80} autoComplete="family-name" {...field('last_name')} />
          </label>
        </div>
        <label className="block">
          <span className="label">
            {t('profile.email')} <span className="font-normal text-muted">({t('common.optional')})</span>
          </span>
          <input className="input" type="email" autoComplete="email" {...field('email')} />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label">{t('profile.city')}</span>
            <select className="input" value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}>
              <option value="">{t('profile.chooseCity')}</option>
              {(cities.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">{t('profile.language')}</span>
            <select className="input" value={form.language} onChange={(e) => setForm((f) => ({ ...f, language: e.target.value as Lang }))}>
              <option value="uz">O'zbekcha</option>
              <option value="ru">Русский</option>
            </select>
          </label>
        </div>
        <InlineError error={save.error} />
        <button type="submit" className="btn-primary" disabled={save.isPending}>
          {save.isPending && <Spinner className="h-4 w-4 !text-white" />}
          {t('common.save')}
        </button>
      </form>

      <NotificationSettings />

      <Link to={user.is_seller ? '/seller' : '/seller/store'} className="card flex items-center gap-3 p-5 transition hover:border-brand-600">
        <span className="rounded-xl bg-deal-100 p-2.5 text-deal-700">
          <Store className="h-6 w-6" aria-hidden />
        </span>
        <span>
          <span className="block font-semibold">{user.is_seller ? t('profile.myStore') : t('profile.becomeSeller')}</span>
          {!user.is_seller && <span className="block text-sm text-muted">{t('profile.becomeSellerHint')}</span>}
        </span>
      </Link>

      <button
        type="button"
        className="btn-secondary w-full !text-red-600"
        onClick={async () => {
          await logout()
          navigate('/')
        }}
      >
        <LogOut className="h-4 w-4" aria-hidden /> {t('nav.logout')}
      </button>
    </div>
  )
}
