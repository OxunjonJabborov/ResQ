import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'

/** Map API errors to a user-facing, translated message. */
export function useErrorMessage() {
  const { t, i18n } = useTranslation()
  return useCallback(
    (error: unknown): string => {
      if (!error) return ''
      if (error instanceof ApiError) {
        if (error.status === 429 && !error.code) return t('errors.throttled')
        if (error.code && i18n.exists(`errors.${error.code}`)) {
          return t(`errors.${error.code}`, { seconds: error.data.retry_after ?? '' })
        }
        return error.message || t('errors.generic')
      }
      if (error instanceof TypeError) return t('errors.network')
      return t('errors.generic')
    },
    [t, i18n],
  )
}
