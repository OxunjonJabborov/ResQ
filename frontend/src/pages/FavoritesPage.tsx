import { useQuery } from '@tanstack/react-query'
import { Heart } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { favoritesApi } from '../api/endpoints'
import { ProductGrid } from '../components/ProductCard'
import { EmptyState, ErrorState, SkeletonGrid } from '../components/States'

export default function FavoritesPage() {
  const { t } = useTranslation()
  const query = useQuery({ queryKey: ['favorites'], queryFn: () => favoritesApi.list() })
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{t('favorites.title')}</h1>
      {query.isPending ? (
        <SkeletonGrid />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.results.length === 0 ? (
        <EmptyState
          icon={Heart}
          title={t('favorites.empty')}
          hint={t('favorites.emptyHint')}
          action={<Link to="/catalog" className="btn-primary">{t('cart.browse')}</Link>}
        />
      ) : (
        <ProductGrid products={query.data.results} />
      )}
    </div>
  )
}
