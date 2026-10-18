import i18n from '../i18n'

export function formatMoney(amount: number): string {
  // "12 500 so'm" / "12 500 сум"
  const n = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(amount).replace(/[\u00a0\u202f]/g, ' ')
  return `${n} ${i18n.t('common.currency')}`
}

// Browser ICU data often lacks Uzbek month names (renders "M10"), so Uzbek is formatted by hand.
const UZ_MONTHS = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek']

function pad(n: number) {
  return String(n).padStart(2, '0')
}

/** Parse "YYYY-MM-DD" as a local date (not UTC midnight) and anything else as ISO. */
function toDate(iso: string): Date {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(iso)
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = toDate(iso)
  if (i18n.language === 'ru') return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(d)
  return `${d.getDate()}-${UZ_MONTHS[d.getMonth()]}`
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = toDate(iso)
  return `${formatDate(iso)}, ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function formatKg(value: string | number): string {
  const n = Number(value)
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: n < 10 ? 1 : 0 }).format(n).replace(/[\u00a0\u202f]/g, ' ')
}

export function formatPhone(phone: string): string {
  const d = phone.replace(/\D/g, '')
  if (d.length !== 12) return phone
  return `+${d.slice(0, 3)} ${d.slice(3, 5)} ${d.slice(5, 8)} ${d.slice(8, 10)} ${d.slice(10)}`
}

/** "2 kun qoldi" / "today" style label for an expiry date. */
export function expiryLabel(days: number | null): string | null {
  if (days === null) return null
  if (days <= 0) return i18n.t('product.expiresToday')
  if (days === 1) return i18n.t('product.expiresTomorrow')
  return i18n.t('product.expiresInDays', { count: days })
}

export function minutesLeft(iso: string | null): number | null {
  if (!iso) return null
  return Math.round((new Date(iso).getTime() - Date.now()) / 60000)
}

export function mapsUrl(lat: string | number, lng: string | number): string {
  return `https://yandex.uz/maps/?pt=${lng},${lat}&z=16&l=map`
}
