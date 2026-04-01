import { useEffect, useRef } from 'react'
import { Outlet } from 'react-router-dom'
import { TopBar } from '@/components/layout/TopBar'
import { Sidebar } from '@/components/layout/Sidebar'
import { TransportBar } from '@/components/transport/TransportBar'
import { StatusFooter } from '@/components/layout/StatusFooter'
import { AIAssistantOverlay } from '@/components/common/AIAssistantOverlay'

export default function AppLayout() {
  const bgRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (bgRef.current) {
        bgRef.current.style.setProperty('--mouse-x', `${e.clientX}px`)
        bgRef.current.style.setProperty('--mouse-y', `${e.clientY}px`)
      }
    }
    window.addEventListener('mousemove', handler)
    return () => window.removeEventListener('mousemove', handler)
  }, [])

  return (
    <div className="flex h-screen bg-rain-black overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 relative z-10">
        <TopBar />
        <TransportBar />
        <main className="flex-1 overflow-auto page-enter">
          <Outlet />
        </main>
        <StatusFooter />
      </div>
      <div ref={bgRef} className="ambient-bg" />
      {/* Global AI Assistant — floating bubble visible on ALL tabs */}
      <AIAssistantOverlay />
    </div>
  )
}
