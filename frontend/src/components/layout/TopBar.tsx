import { useAuthStore } from '@/stores/auth'
import { TierBadge } from '@/components/common/Badge'
import { Settings, LogOut, Bell } from 'lucide-react'

export function TopBar() {
  const { tier, clearAuth, userId } = useAuthStore()

  return (
    <header className="h-14 glass-subtle flex items-center justify-between px-6 shrink-0 z-20">
      {/* Left: Logo + version */}
      <div className="flex items-center gap-4">
        <span className="text-2xl font-black tracking-tight">
          <span className="rain-logo-r">R</span>
          <span className="rain-logo-inf">&infin;</span>
          <span className="rain-logo-n">N</span>
        </span>
        <div className="hidden sm:flex items-center gap-2">
          <span className="text-[10px] text-rain-dim tracking-widest uppercase font-semibold">
            AI Mastering Engine
          </span>
          <span className="px-1.5 py-0.5 rounded text-[8px] font-bold tracking-wider text-rain-purple bg-rain-purple/10 border border-rain-purple/20">
            v6.0
          </span>
        </div>
      </div>

      {/* Center: Status indicators */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg glass-subtle">
          <span className="w-1.5 h-1.5 rounded-full bg-rain-green animate-pulse" />
          <span className="text-[10px] font-semibold text-rain-dim tracking-wider uppercase">Local</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg glass-subtle border-rain-purple/10 border">
          <span className="text-[10px] font-semibold text-rain-purple tracking-wider uppercase">Claude Opus 4.6</span>
        </div>
      </div>

      {/* Right: User controls */}
      <div className="flex items-center gap-4">
        <TierBadge tier={tier} />

        <button className="w-8 h-8 rounded-lg glass-subtle flex items-center justify-center text-rain-dim hover:text-rain-text transition-colors">
          <Bell size={14} />
        </button>

        <div className="flex items-center gap-3 pl-3 border-l border-rain-border/30">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-rain-purple/30 to-rain-magenta/20 border border-rain-purple/20 flex items-center justify-center">
            <span className="text-xs font-bold text-rain-purple">
              {userId ? userId.charAt(0).toUpperCase() : 'U'}
            </span>
          </div>
          <button
            onClick={clearAuth}
            className="text-rain-dim hover:text-rain-text transition-colors"
            title="Sign Out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </header>
  )
}
