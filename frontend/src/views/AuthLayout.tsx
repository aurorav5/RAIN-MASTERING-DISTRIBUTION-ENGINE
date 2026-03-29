import { useEffect, useRef } from 'react'

interface Props { children: React.ReactNode }

export function AuthLayout({ children }: Props) {
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
    <div className="min-h-screen bg-rain-black flex items-center justify-center relative overflow-hidden">
      {/* Ambient background */}
      <div ref={bgRef} className="ambient-bg" />

      {/* Glow orbs */}
      <div className="hero-glow bg-teal-500" style={{ top: '15%', left: '25%', opacity: 0.1 }} />
      <div className="hero-glow bg-emerald-500" style={{ bottom: '20%', right: '20%', animationDelay: '-10s', opacity: 0.06 }} />

      <div className="relative z-10 w-full max-w-md px-6">
        {/* Logo */}
        <div className="text-center mb-10">
          <h1 className="rain-logo-xl mb-4">
            <span className="rain-logo-r">R</span>
            <span className="rain-logo-inf">&infin;</span>
            <span className="rain-logo-n">N</span>
          </h1>
          <p className="text-sm text-rain-dim">AI Mastering Engine</p>
        </div>

        {/* Auth card */}
        <div className="glass-panel rounded-2xl p-8">
          {children}
        </div>

        {/* Footer */}
        <p className="text-center text-[10px] text-rain-muted mt-8">
          ARCOVEL Technologies International &middot; Rain doesn't live in the cloud.
        </p>
      </div>
    </div>
  )
}
