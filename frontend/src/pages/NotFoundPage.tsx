import { SearchX } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { EmptyState } from '../components/States'

export default function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <EmptyState
      icon={SearchX}
      title={t('errors.notFound')}
      action={
        <Link to="/" className="btn-primary">
          {t('nav.home')}
        </Link>
      }
    />
  )
}
