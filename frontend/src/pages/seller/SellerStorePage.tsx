import { useMutation, useQueryClient } from '@tanstack/react-query'
import { LocateFixed } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api/client'
import { sellerApi } from '../../api/endpoints'
import type { SellerProfile, WorkingHours } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { InlineError, PageSpinner, Spinner } from '../../components/States'
import { toast } from '../../components/Toast'
import { useCities, useSellerProfile } from '../../hooks/queries'

const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const
const DEFAULT_HOURS: WorkingHours = Object.fromEntries(DAYS.map((d) => [d, { open: '09:00', close: '21:00' }]))

interface FormState {
  store_name: string
  description: string
  phone: string
  city: string
  address: string
  latitude: string
  longitude: string
  working_hours: WorkingHours
}

function initialForm(existing?: SellerProfile): FormState {
  if (!existing) {
    return { store_name: '', description: '', phone: '+998', city: '', address: '', latitude: '', longitude: '', working_hours: DEFAULT_HOURS }
  }
  return {
    store_name: existing.store_name,
    description: existing.description,
    phone: existing.phone,
    city: String(existing.city),
    address: existing.address,
    latitude: existing.latitude,
    longitude: existing.longitude,
    working_hours: Object.keys(existing.working_hours).length ? existing.working_hours : DEFAULT_HOURS,
  }
}

export default function SellerStorePage() {
  const profile = useSellerProfile()
  // The layout already handles loading and errors; a 404 means "no store yet".
  if (profile.isPending) return <PageSpinner />
  return <StoreForm key={profile.data?.id ?? 'new'} existing={profile.data} />
}

function StoreForm({ existing }: { existing?: SellerProfile }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { refetchUser } = useAuth()
  const cities = useCities()
  const [logo, setLogo] = useState<File | null>(null)
  const [form, setForm] = useState<FormState>(() => initialForm(existing))

  const save = useMutation({
    mutationFn: () => {
      const body = new FormData()
      for (const [key, value] of Object.entries(form)) {
        if (key !== 'working_hours') body.append(key, String(value))
      }
      if (logo) body.append('logo', logo)
      // Multipart cannot carry nested JSON, so hours go in a JSON request afterwards.
      return (existing ? sellerApi.updateProfile(body) : sellerApi.createProfile(body)).then(() =>
        sellerApi.updateProfile({ working_hours: form.working_hours }),
      )
    },
    onSuccess: (data) => {
      qc.setQueryData(['seller-profile'], data)
      void refetchUser()
      toast(t('common.saved'))
      if (!existing) navigate('/seller/products/new')
    },
  })

  const fieldErrors = save.error instanceof ApiError ? save.error.fieldErrors : {}
  const set = (key: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  const locate = () =>
    navigator.geolocation?.getCurrentPosition((pos) =>
      setForm((f) => ({ ...f, latitude: pos.coords.latitude.toFixed(6), longitude: pos.coords.longitude.toFixed(6) })),
    )

  const onCity = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const city = cities.data?.find((c) => String(c.id) === e.target.value)
    setForm((f) => ({
      ...f,
      city: e.target.value,
      // Pre-fill with the city centre if no coordinates were entered yet.
      latitude: f.latitude || city?.latitude || '',
      longitude: f.longitude || city?.longitude || '',
    }))
  }

  const setDay = (day: (typeof DAYS)[number], value: { open: string; close: string } | null) =>
    setForm((f) => ({ ...f, working_hours: { ...f.working_hours, [day]: value } }))

  const err = (key: string) => fieldErrors[key] && <span className="mt-1 block text-xs text-red-600">{fieldErrors[key]}</span>

  return (
    <form
      className="mx-auto max-w-2xl space-y-5"
      onSubmit={(e: FormEvent) => {
        e.preventDefault()
        save.mutate()
      }}
    >
      {!existing && <p className="text-sm text-muted">{t('seller.createStoreHint')}</p>}
      {existing?.verification_status === 'verified' && <p className="text-xs text-muted">{t('seller.reviewNotice')}</p>}
      <section className="card space-y-4 p-5">
        <label className="block">
          <span className="label">{t('seller.storeName')}</span>
          <input className="input" required maxLength={120} value={form.store_name} onChange={set('store_name')} />
          {err('store_name')}
        </label>
        <label className="block">
          <span className="label">{t('seller.description')}</span>
          <textarea className="input min-h-20" value={form.description} onChange={set('description')} />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label">{t('seller.phone')}</span>
            <input className="input" required inputMode="tel" value={form.phone} onChange={set('phone')} />
            {err('phone')}
          </label>
          <label className="block">
            <span className="label">{t('seller.logo')}</span>
            <input className="input !py-2" type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setLogo(e.target.files?.[0] ?? null)} />
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label">{t('seller.city')}</span>
            <select className="input" required value={form.city} onChange={onCity}>
              <option value="">{t('profile.chooseCity')}</option>
              {(cities.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            {err('city')}
          </label>
          <label className="block">
            <span className="label">{t('seller.address')}</span>
            <input className="input" required maxLength={255} value={form.address} onChange={set('address')} />
            {err('address')}
          </label>
        </div>
        <div>
          <span className="label">{t('seller.location')}</span>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input className="input" required inputMode="decimal" placeholder={t('seller.latitude')} aria-label={t('seller.latitude')} value={form.latitude} onChange={set('latitude')} />
            <input className="input" required inputMode="decimal" placeholder={t('seller.longitude')} aria-label={t('seller.longitude')} value={form.longitude} onChange={set('longitude')} />
            <button type="button" className="btn-secondary shrink-0" onClick={locate}>
              <LocateFixed className="h-4 w-4" aria-hidden /> {t('seller.useMyLocation')}
            </button>
          </div>
          {err('latitude')}
          {err('longitude')}
        </div>
      </section>

      <section className="card p-5">
        <h2 className="mb-3 font-semibold">{t('seller.workingHours')}</h2>
        <div className="space-y-2">
          {DAYS.map((day) => {
            const slot = form.working_hours[day]
            return (
              <div key={day} className="flex flex-wrap items-center gap-2">
                <span className="w-28 text-sm">{t(`store.weekdays.${day}`)}</span>
                <label className="flex items-center gap-1.5 text-sm text-muted">
                  <input type="checkbox" className="accent-brand-700" checked={!slot} onChange={(e) => setDay(day, e.target.checked ? null : { open: '09:00', close: '21:00' })} />
                  {t('seller.dayOff')}
                </label>
                {slot && (
                  <>
                    <input type="time" className="input !w-28" value={slot.open} onChange={(e) => setDay(day, { ...slot, open: e.target.value })} aria-label={`${day} open`} />
                    <span>–</span>
                    <input type="time" className="input !w-28" value={slot.close} onChange={(e) => setDay(day, { ...slot, close: e.target.value })} aria-label={`${day} close`} />
                  </>
                )}
              </div>
            )
          })}
        </div>
        {err('working_hours')}
      </section>

      <InlineError error={save.error && !Object.keys(fieldErrors).length ? save.error : null} />
      <button type="submit" className="btn-primary w-full !py-3" disabled={save.isPending}>
        {save.isPending && <Spinner className="h-4 w-4 !text-white" />}
        {existing ? t('common.save') : t('seller.submit')}
      </button>
    </form>
  )
}
