import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'
import { api } from '@/utils/api'
import { Save, FolderOpen, HelpCircle, Search, Bell } from 'lucide-react'

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
    <header className="h-11 bg-rain-dark/80 backdrop-blur-md border-b border-rain-border/40 flex items-center justify-between px-4 shrink-0 z-20">
      {/* Left: session status badges */}
      <div className="flex items-center gap-2">
        <span className="badge badge-outline">OFFLINE</span>
        {isMastered && <span className="badge badge-green">MASTERED</span>}
      </div>

      {/* Center: technical badges */}
      <div className="flex items-center gap-2">
        <span className="badge badge-purple">CLAUDE OPUS 4.6</span>
        <span className="badge badge-cyan">BS-ROFORMER SW</span>
        <span className="badge badge-green">48KHZ &middot; STEREO</span>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-1.5">
        <span className="badge badge-teal text-[9px]">API/WEBHOOK</span>

        {/* Search — Cmd+K hint */}
        <button
          className="flex items-center gap-1.5 h-7 px-2 rounded border border-rain-border/30 bg-rain-surface/40 text-rain-dim hover:text-rain-text hover:border-rain-teal/20 transition-colors text-[10px] font-mono focus-visible:outline focus-visible:outline-2 focus-visible:outline-rain-teal/50"
          title="Search (⌘K)"
          aria-label="Open search"
        >
          <Search size={11} />
          <span className="hidden sm:inline text-rain-muted">⌘K</span>
        </button>

        {/* Notification bell */}
        <button
          className="w-7 h-7 rounded flex items-center justify-center text-rain-dim hover:text-rain-text transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-rain-teal/50"
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell size={13} />
        </button>

        <button
          className="w-7 h-7 rounded flex items-center justify-center text-rain-dim hover:text-rain-text transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-rain-teal/50"
          title="Help"
          aria-label="Help"
        >
          <HelpCircle size={13} />
        </button>

        <div className="w-7 h-7 rounded-full bg-rain-teal/15 border border-rain-teal/25 flex items-center justify-center" aria-label="User avatar">
          <span className="text-[10px] font-bold text-rain-teal">
            {userId ? userId.charAt(0).toUpperCase() : 'U'}
          </span>
        </div>

        <div className={`tier-badge ${tier} text-[9px]`}>{tier.toUpperCase()}</div>

        <button
          className="badge badge-outline hover:border-rain-teal/30 transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-rain-teal/50"
          title="Load session"
          aria-label="Load session"
        >
          <FolderOpen size={10} /> LOAD
        </button>
        <button
          className="badge badge-outline hover:border-rain-teal/30 transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-rain-teal/50"
          title="Save session"
          aria-label="Save session"
        >
          <Save size={10} /> SAVE
        </button>

        <button
          onClick={() => { void handleLogout() }}
          className="w-7 h-7 rounded flex items-center justify-center text-rain-dim hover:text-rain-text transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-rain-teal/50"
          title="Sign out"
          aria-label="Sign out"
        >
          <svg
            width="13" height="13" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
          </svg>
        </button>
      </div>
    </header>
  )
}
