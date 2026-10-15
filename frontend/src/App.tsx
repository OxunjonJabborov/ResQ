import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'

import { RequireAuth } from './auth/guards'
import { Layout } from './components/Layout'
import { PageSpinner } from './components/States'
import CartPage from './pages/CartPage'
import CatalogPage from './pages/CatalogPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import ProductPage from './pages/ProductPage'
import StorePage from './pages/StorePage'

const CheckoutPage = lazy(() => import('./pages/CheckoutPage'))
const OrdersPage = lazy(() => import('./pages/OrdersPage'))
const OrderDetailPage = lazy(() => import('./pages/OrderDetailPage'))
const FavoritesPage = lazy(() => import('./pages/FavoritesPage'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const SellerLayout = lazy(() => import('./pages/seller/SellerLayout'))
const SellerOrdersPage = lazy(() => import('./pages/seller/SellerOrdersPage'))
const SellerProductsPage = lazy(() => import('./pages/seller/SellerProductsPage'))
const SellerProductFormPage = lazy(() => import('./pages/seller/SellerProductFormPage'))
const SellerStatsPage = lazy(() => import('./pages/seller/SellerStatsPage'))
const SellerStorePage = lazy(() => import('./pages/seller/SellerStorePage'))

const auth = (el: React.ReactNode) => <RequireAuth>{el}</RequireAuth>

export default function App() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="catalog" element={<CatalogPage />} />
          <Route path="products/:id" element={<ProductPage />} />
          <Route path="stores/:id" element={<StorePage />} />
          <Route path="cart" element={<CartPage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="checkout" element={auth(<CheckoutPage />)} />
          <Route path="orders" element={auth(<OrdersPage />)} />
          <Route path="orders/:id" element={auth(<OrderDetailPage />)} />
          <Route path="favorites" element={auth(<FavoritesPage />)} />
          <Route path="notifications" element={auth(<NotificationsPage />)} />
          <Route path="profile" element={auth(<ProfilePage />)} />
          <Route path="seller" element={auth(<SellerLayout />)}>
            <Route index element={<SellerOrdersPage />} />
            <Route path="orders" element={<SellerOrdersPage />} />
            <Route path="orders/:id" element={<SellerOrdersPage />} />
            <Route path="products" element={<SellerProductsPage />} />
            <Route path="products/new" element={<SellerProductFormPage />} />
            <Route path="products/:id" element={<SellerProductFormPage />} />
            <Route path="stats" element={<SellerStatsPage />} />
            <Route path="store" element={<SellerStorePage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
