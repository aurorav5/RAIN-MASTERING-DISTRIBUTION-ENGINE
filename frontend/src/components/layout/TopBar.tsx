import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'
import { api } from '@/utils/api'
import { Save, FolderOpen, Settings, HelpCircle } from 'lucide-react'

export function TopBar() {
  const { tier, clearAuth, userId } = useAuthStore()
  const { status } = useSessionStore()

  const handleLogout = async () => {
    try {
      await api.auth.logout() // revokes refresh token family server-side
    } catch {
      // best-effort — still clear local state
    }
    clearAuth()
  }

  const isMastered = status === 'complete'

  return (
    <header className="h-12 bg-rain-dark/80 backdrop-blur-md border-b border-rain-border/40 flex items-center justify-between px-4 shrink-0 z-20">
      {/* Left: Logo + version */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-rain-teal/10 border border-rain-teal/20 flex items-center justify-center">
            <span className="text-rain-teal text-xs font-black">R</span>
          </div>
          <div>
            <span className="text-sm font-black tracking-tight text-rain-white">
              <span className="rain-logo-r">R</span>
              <span className="rain-logo-inf">&infin;</span>
              <span className="rain-logo-n">N</span>
            </span>
            <span className="text-[9px] text-rain-dim ml-2 tracking-widest font-semibold uppercase">AI Mastering Engine v6.0</span>
          </div>
        </div>
        <div className="flex items-center gap-2 ml-4">
          <span className="badge badge-outline">OFFLINE</span>
          {isMastered && <span className="badge badge-green">MASTERED</span>}
        </div>
      </div>

      {/* Center: Technical badges */}
      <div className="flex items-center gap-2">
        <span className="badge badge-purple">CLAUDE OPUS 4.6</span>
        <span className="badge badge-cyan">BS-ROFORMER SW</span>
        <span className="badge badge-green">48KHZ &middot; STEREO</span>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2">
        <span className="badge badge-teal text-[9px]">API/WEBHOOK</span>

        <button className="w-7 h-7 rounded flex items-center justify-center text-rain-dim hover:text-rain-text transition-colors" title="Help">
          <HelpCircle size={14} />
        </button>

        <div className="w-7 h-7 rounded-full bg-rain-teal/15 border border-rain-teal/25 flex items-center justify-center">
          <span className="text-[10px] font-bold text-rain-teal">
            {userId ? userId.charAt(0).toUpperCase() : 'U'}
          </span>
        </div>

        <div className="tier-badge enterprise text-[9px]">{tier.toUpperCase()}</div>

        <button className="badge badge-outline hover:border-rain-teal/30 transition-colors cursor-pointer" title="Load session">
          <FolderOpen size={10} /> LOAD
        </button>
        <button className="badge badge-outline hover:border-rain-teal/30 transition-colors cursor-pointer" title="Save session">
          <Save size={10} /> SAVE
        </button>

        <button onClick={() => { void handleLogout() }} className="w-7 h-7 rounded flex items-center justify-center text-rain-dim hover:text-rain-text transition-colors" title="Sign out">
          <Settings size={14} />
        </button>
      </div>
    </header>
  )
}
