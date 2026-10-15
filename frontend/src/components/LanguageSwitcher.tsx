import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { authApi } from '../api/endpoints'
import type { Lang } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { LANGUAGES } from '../i18n'

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation()
  const { isAuthenticated } = useAuth()
  const qc = useQueryClient()

  const change = async (lang: Lang) => {
    await i18n.changeLanguage(lang)
    // Server-rendered names (categories, cities) depend on Accept-Language.
    void qc.invalidateQueries()
    if (isAuthenticated) {
      try {
        const user = await authApi.updateMe({ language: lang })
        qc.setQueryData(['me'], user)
      } catch {
        /* the UI language still switches locally */
      }
    }
  }

  return (
    <div className="flex rounded-xl border border-line p-0.5" role="group" aria-label={t('nav.language')}>
      {LANGUAGES.map((lang) => (
        <button
          key={lang.code}
          type="button"
          onClick={() => void change(lang.code)}
          aria-pressed={i18n.language === lang.code}
          title={lang.label}
          className={`rounded-lg px-2 py-1 text-xs font-bold transition ${
            i18n.language === lang.code ? 'bg-brand-700 text-white' : 'text-muted hover:text-ink'
          }`}
        >
          {lang.short}
        </button>
      ))}
    </div>
  )
}
