import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '../auth/AuthContext'
import { cartApi, catalogApi, favoritesApi, notificationsApi, sellerApi } from '../api/endpoints'

export const qk = {
  categories: ['categories'] as const,
  cities: ['cities'] as const,
  cart: ['cart'] as const,
  unread: ['notifications', 'unread'] as const,
}

export function useCategories() {
  return useQuery({ queryKey: qk.categories, queryFn: catalogApi.categories, staleTime: 60 * 60 * 1000 })
}

export function useCities() {
  return useQuery({ queryKey: qk.cities, queryFn: catalogApi.cities, staleTime: 60 * 60 * 1000 })
}

export function useCart() {
  const { isAuthenticated } = useAuth()
  return useQuery({ queryKey: qk.cart, queryFn: cartApi.get, enabled: isAuthenticated })
}

export function useUnreadCount() {
  const { isAuthenticated } = useAuth()
  return useQuery({
    queryKey: qk.unread,
    queryFn: notificationsApi.unreadCount,
    enabled: isAuthenticated,
    refetchInterval: 60_000,
  })
}

export function useAddToCart() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ product, quantity }: { product: number; quantity: number }) => cartApi.add(product, quantity),
    onSuccess: (cart) => qc.setQueryData(qk.cart, cart),
  })
}

export function useToggleFavorite(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (isFavorite: boolean) => (isFavorite ? favoritesApi.remove(productId) : favoritesApi.add(productId)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['product', String(productId)] })
      void qc.invalidateQueries({ queryKey: ['favorites'] })
    },
  })
}

/** Flatten the category tree into [category, depth] pairs for selects. */
export function flattenCategories<T extends { children?: T[] }>(nodes: T[] = [], depth = 0): [T, number][] {
  return nodes.flatMap((node) => [[node, depth] as [T, number], ...flattenCategories(node.children ?? [], depth + 1)])
}

export function useSellerProfile() {
  return useQuery({ queryKey: ['seller-profile'], queryFn: sellerApi.profile, retry: false })
}
