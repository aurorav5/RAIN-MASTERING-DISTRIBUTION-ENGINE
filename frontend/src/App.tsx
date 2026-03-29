import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { lazy, Suspense } from 'react'
import AppLayout from './views/AppLayout'
import LoginView from './views/LoginView'
import RegisterView from './views/RegisterView'

const LandingPage = lazy(() => import('@/views/LandingPage'))

// Tab pages
const MasteringTab = lazy(() => import('@/components/tabs/MasteringTab'))
const StemsTab = lazy(() => import('@/components/tabs/StemsTab'))
const SpatialTab = lazy(() => import('@/components/tabs/SpatialTab'))
const QCTab = lazy(() => import('@/components/tabs/QCTab'))
const ExportTab = lazy(() => import('@/components/tabs/ExportTab'))
const DistributeTab = lazy(() => import('@/components/tabs/DistributeTab'))
const AnalyticsTab = lazy(() => import('@/components/tabs/AnalyticsTab'))
const RoadmapTab = lazy(() => import('@/components/tabs/RoadmapTab'))
const SettingsTab = lazy(() => import('@/components/tabs/SettingsTab'))

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <Navigate to="/app" replace /> : <>{children}</>
}

function TabFallback() {
  return (
    <div className="flex items-center justify-center h-64 page-enter">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 border-2 border-rain-purple border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-rain-dim">Loading module...</span>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<PublicRoute><Suspense fallback={<TabFallback />}><LandingPage /></Suspense></PublicRoute>} />
        <Route path="/login" element={<LoginView />} />
        <Route path="/register" element={<RegisterView />} />

        {/* App routes (authenticated) */}
        <Route
          path="/app/*"
          element={
            <PrivateRoute>
              <AppLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<Suspense fallback={<TabFallback />}><MasteringTab /></Suspense>} />
          <Route path="stems" element={<Suspense fallback={<TabFallback />}><StemsTab /></Suspense>} />
          <Route path="spatial" element={<Suspense fallback={<TabFallback />}><SpatialTab /></Suspense>} />
          <Route path="qc" element={<Suspense fallback={<TabFallback />}><QCTab /></Suspense>} />
          <Route path="export" element={<Suspense fallback={<TabFallback />}><ExportTab /></Suspense>} />
          <Route path="distribute" element={<Suspense fallback={<TabFallback />}><DistributeTab /></Suspense>} />
          <Route path="analytics" element={<Suspense fallback={<TabFallback />}><AnalyticsTab /></Suspense>} />
          <Route path="roadmap" element={<Suspense fallback={<TabFallback />}><RoadmapTab /></Suspense>} />
          <Route path="settings" element={<Suspense fallback={<TabFallback />}><SettingsTab /></Suspense>} />
        </Route>

        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
