import { useEffect, useRef } from 'react'
import { Outlet } from 'react-router-dom'
import { TopBar } from '@/components/layout/TopBar'
import { TabBar } from '@/components/layout/TabBar'
import { TransportBar } from '@/components/transport/TransportBar'

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
    <div className="min-h-screen h-screen bg-[#08070F] text-rain-text flex flex-col overflow-hidden relative">
      {/* Ambient background */}
      <div ref={bgRef} className="ambient-bg" />

      {/* App chrome */}
      <div className="relative z-10 flex flex-col h-full">
        <TopBar />
        <TabBar />
        <TransportBar />
        <main className="flex-1 overflow-auto page-enter">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
