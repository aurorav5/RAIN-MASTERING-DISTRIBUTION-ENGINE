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
const CollabTab = lazy(() => import('@/components/tabs/CollabTab'))
const ExportTab = lazy(() => import('@/components/tabs/ExportTab'))
const DistributeTab = lazy(() => import('@/components/tabs/DistributeTab'))
const AlbumTab = lazy(() => import('@/components/tabs/AlbumTab'))
const DatasetTab = lazy(() => import('@/components/tabs/DatasetTab'))
const TestTab = lazy(() => import('@/components/tabs/TestTab'))
const MarketTab = lazy(() => import('@/components/tabs/MarketTab'))
const AnalyticsTab = lazy(() => import('@/components/tabs/AnalyticsTab'))
const RoadmapTab = lazy(() => import('@/components/tabs/RoadmapTab'))
const SettingsTab = lazy(() => import('@/components/tabs/SettingsTab'))
const AIETab = lazy(() =>
  import('@/components/tabs/AIETab').then((m) => ({ default: m.AIETab }))
)
const DocsTab = lazy(() => import('@/components/tabs/DocsTab'))
const ReferenceTab = lazy(() => import('@/components/tabs/ReferenceTab'))
const RepairTab = lazy(() => import('@/components/tabs/RepairTab'))
const TestLabTab = lazy(() => import('@/components/tabs/TestLabTab'))

const DEV_MODE = import.meta.env.DEV

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  if (DEV_MODE) return <>{children}</>
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  if (DEV_MODE) return <Navigate to="/app" replace />
  return isAuthenticated ? <Navigate to="/app" replace /> : <>{children}</>
}

function TabFallback() {
  return (
    <div className="flex items-center justify-center h-64 page-enter">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 border-2 border-rain-teal border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-rain-dim">Loading module...</span>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PublicRoute><Suspense fallback={<TabFallback />}><LandingPage /></Suspense></PublicRoute>} />
        <Route path="/login" element={<LoginView />} />
        <Route path="/register" element={<RegisterView />} />

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
          <Route path="collab" element={<Suspense fallback={<TabFallback />}><CollabTab /></Suspense>} />
          <Route path="export" element={<Suspense fallback={<TabFallback />}><ExportTab /></Suspense>} />
          <Route path="distribute" element={<Suspense fallback={<TabFallback />}><DistributeTab /></Suspense>} />
          <Route path="album" element={<Suspense fallback={<TabFallback />}><AlbumTab /></Suspense>} />
          <Route path="dataset" element={<Suspense fallback={<TabFallback />}><DatasetTab /></Suspense>} />
          <Route path="test" element={<Suspense fallback={<TabFallback />}><TestTab /></Suspense>} />
          <Route path="market" element={<Suspense fallback={<TabFallback />}><MarketTab /></Suspense>} />
          <Route path="analytics" element={<Suspense fallback={<TabFallback />}><AnalyticsTab /></Suspense>} />
          <Route path="roadmap" element={<Suspense fallback={<TabFallback />}><RoadmapTab /></Suspense>} />
          <Route path="settings" element={<Suspense fallback={<TabFallback />}><SettingsTab /></Suspense>} />
          <Route path="aie" element={<Suspense fallback={<TabFallback />}><AIETab /></Suspense>} />
          <Route path="docs" element={<Suspense fallback={<TabFallback />}><DocsTab /></Suspense>} />
          <Route path="reference" element={<Suspense fallback={<TabFallback />}><ReferenceTab /></Suspense>} />
          <Route path="repair" element={<Suspense fallback={<TabFallback />}><RepairTab /></Suspense>} />
          <Route path="testlab" element={<Suspense fallback={<TabFallback />}><TestLabTab /></Suspense>} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
