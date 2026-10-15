import { useMutation } from '@tanstack/react-query'
import { Leaf } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { authApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { InlineError, Spinner } from '../components/States'
import { toast } from '../components/Toast'
import { formatPhone } from '../lib/format'

/** Keep only the 9 national digits after +998. */
function nationalDigits(value: string) {
  let d = value.replace(/\D/g, '')
  if (d.startsWith('998') && d.length > 9) d = d.slice(3)
  return d.slice(0, 9)
}

function maskNational(d: string) {
  return [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(' ')
}

/** Only allow same-site relative redirects after login. */
function safeNext(next: string | null) {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/'
}

export default function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const { login, isAuthenticated } = useAuth()
  const [digits, setDigits] = useState('')
  const [code, setCode] = useState('')
  const [step, setStep] = useState<'phone' | 'code'>('phone')
  const [resendAt, setResendAt] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const [debugCode, setDebugCode] = useState<string | null>(null)
  const codeRef = useRef<HTMLInputElement>(null)
  const phone = `+998${digits}`

  useEffect(() => {
    if (step !== 'code') return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [step])

  const request = useMutation({
    mutationFn: () => authApi.requestOtp(phone),
    onSuccess: (res) => {
      setStep('code')
      setResendAt(Date.now() + res.resend_in * 1000)
      setDebugCode(res.debug_code ?? null)
      setTimeout(() => codeRef.current?.focus(), 50)
    },
    onError: (err) => {
      // A code was already sent recently: go to the code step anyway.
      if (err instanceof ApiError && err.code === 'otp_cooldown') {
        setStep('code')
        setResendAt(Date.now() + Number(err.data.retry_after ?? 60) * 1000)
      }
    },
  })
  const verify = useMutation({
    mutationFn: () => authApi.verifyOtp(phone, code),
    onSuccess: (res) => {
      login(res)
      toast(t('auth.welcome'))
      navigate(res.is_new && !res.user.first_name ? `/profile?welcome=1&next=${encodeURIComponent(next)}` : next, { replace: true })
    },
  })

  if (isAuthenticated && !verify.isSuccess) return <Navigate to={next} replace />
  const secondsLeft = Math.max(0, Math.ceil((resendAt - now) / 1000))

  const onPhone = (e: FormEvent) => {
    e.preventDefault()
    if (digits.length === 9) request.mutate()
  }
  const onCode = (e: FormEvent) => {
    e.preventDefault()
    if (code.length === 6) verify.mutate()
  }

  return (
    <div className="mx-auto max-w-sm py-6">
      <div className="mb-6 text-center">
        <span className="inline-flex rounded-2xl bg-brand-700 p-3 text-white">
          <Leaf className="h-7 w-7" aria-hidden />
        </span>
        <h1 className="mt-3 text-2xl font-bold">{t('auth.title')}</h1>
        <p className="mt-1 text-sm text-muted">{step === 'phone' ? t('auth.subtitle') : t('auth.codeSentTo', { phone: formatPhone(phone) })}</p>
      </div>

      {step === 'phone' ? (
        <form onSubmit={onPhone} className="card space-y-4 p-5">
          <label className="block">
            <span className="label">{t('auth.phone')}</span>
            <div className="flex items-center rounded-xl border border-line focus-within:border-brand-600 focus-within:ring-2 focus-within:ring-brand-600/20">
              <span className="pl-3 text-base font-medium text-muted">+998</span>
              <input
                className="w-full bg-transparent px-2 py-2.5 text-base outline-none"
                inputMode="tel"
                autoComplete="tel-national"
                placeholder="90 123 45 67"
                value={maskNational(digits)}
                onChange={(e) => setDigits(nationalDigits(e.target.value))}
                autoFocus
              />
            </div>
          </label>
          <InlineError error={request.error} />
          <button type="submit" className="btn-primary w-full !py-3" disabled={digits.length !== 9 || request.isPending}>
            {request.isPending && <Spinner className="h-4 w-4 !text-white" />}
            {t('auth.sendCode')}
          </button>
        </form>
      ) : (
        <form onSubmit={onCode} className="card space-y-4 p-5">
          <label className="block">
            <span className="label">{t('auth.code')}</span>
            <input
              ref={codeRef}
              className="input text-center text-2xl font-bold tracking-[0.5em]"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            />
          </label>
          {debugCode && <p className="rounded-xl bg-amber-50 px-3 py-2 text-center text-sm text-amber-900">{t('auth.devCode', { code: debugCode })}</p>}
          <InlineError error={verify.error ?? request.error} />
          <button type="submit" className="btn-primary w-full !py-3" disabled={code.length !== 6 || verify.isPending}>
            {verify.isPending && <Spinner className="h-4 w-4 !text-white" />}
            {t('auth.verify')}
          </button>
          <div className="flex items-center justify-between text-sm">
            <button type="button" className="text-muted hover:text-ink" onClick={() => { setStep('phone'); setCode(''); verify.reset() }}>
              {t('auth.changePhone')}
            </button>
            <button type="button" className="font-medium text-brand-700 disabled:text-muted" disabled={secondsLeft > 0 || request.isPending} onClick={() => request.mutate()}>
              {secondsLeft > 0 ? t('auth.resendIn', { seconds: secondsLeft }) : t('auth.resend')}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
