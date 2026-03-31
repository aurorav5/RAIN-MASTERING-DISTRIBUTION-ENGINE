import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Disc3, Layers, Move3D, ShieldCheck, Download, Send,
  Settings, BarChart3, Rocket, Users, Disc, Database,
  TestTube2, TrendingUp, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useAuthStore } from '@/stores/auth'

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────
interface NavItem {
  to: string
  label: string
  icon: React.ElementType
  end?: boolean
}

interface NavSection {
  title: string
  items: NavItem[]
}

// ─────────────────────────────────────────────
// Nav structure
// ─────────────────────────────────────────────
const NAV_SECTIONS: NavSection[] = [
  {
    title: 'Workspace',
    items: [
      { to: '/app', label: 'Master', icon: Disc3, end: true },
      { to: '/app/stems', label: 'Stems', icon: Layers },
      { to: '/app/spatial', label: 'Spatial', icon: Move3D },
    ],
  },
  {
    title: 'Tools',
    items: [
      { to: '/app/qc', label: 'QC', icon: ShieldCheck },
      { to: '/app/collab', label: 'Collab', icon: Users },
      { to: '/app/export', label: 'Export', icon: Download },
      { to: '/app/distribute', label: 'Distribute', icon: Send },
    ],
  },
  {
    title: 'Library',
    items: [
      { to: '/app/album', label: 'Album', icon: Disc },
      { to: '/app/dataset', label: 'Dataset', icon: Database },
    ],
  },
  {
    title: 'Platform',
    items: [
      { to: '/app/market', label: 'Market', icon: TrendingUp },
      { to: '/app/analytics', label: 'Analytics', icon: BarChart3 },
    ],
  },
  {
    title: 'System',
    items: [
      { to: '/app/test', label: 'Test', icon: TestTube2 },
      { to: '/app/roadmap', label: 'Roadmap', icon: Rocket },
      { to: '/app/settings', label: 'Settings', icon: Settings },
    ],
  },
]

const STORAGE_KEY = 'rain-sidebar-collapsed'

// ─────────────────────────────────────────────
// Tier badge colour map
// ─────────────────────────────────────────────
const TIER_COLOURS: Record<string, string> = {
  free: 'text-rain-dim border-rain-muted/30',
  spark: 'text-rain-amber border-rain-amber/30',
  creator: 'text-rain-blue border-rain-blue/30',
  artist: 'text-rain-teal border-rain-teal/30',
  studio_pro: 'text-rain-cyan border-rain-cyan/30',
  enterprise: 'text-rain-gold border-rain-gold/30',
}

// ─────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────
export function Sidebar() {
  const { tier, userId } = useAuthStore()

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(collapsed))
    } catch {
      // storage unavailable — silent fail
    }
  }, [collapsed])

  const tierColour = TIER_COLOURS[tier] ?? TIER_COLOURS['free']
  const avatarInitial = userId ? userId.charAt(0).toUpperCase() : 'U'
  const displayName = userId ?? 'user'

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 52 : 220 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="relative flex flex-col h-full bg-rain-dark/80 backdrop-blur-md border-r border-rain-border/30 shrink-0 overflow-hidden z-30"
      aria-label="Primary navigation"
    >
      {/* ── Toggle button ── */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="absolute top-3 right-[-12px] z-40 w-6 h-6 rounded-full bg-rain-panel border border-rain-border/40 flex items-center justify-center text-rain-dim hover:text-rain-teal hover:border-rain-teal/30 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-rain-teal/50"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed
          ? <ChevronRight size={11} />
          : <ChevronLeft size={11} />
        }
      </button>

      {/* ── Logo ── */}
      <div className="flex items-center gap-2.5 px-3 pt-4 pb-3 shrink-0 overflow-hidden">
        {/* Icon mark — always visible */}
        <div className="w-7 h-7 rounded-md bg-rain-teal/10 border border-rain-teal/20 flex items-center justify-center shrink-0">
          <span className="text-rain-teal text-xs font-black">R</span>
        </div>

        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.div
              key="logo-text"
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 'auto' }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.18 }}
              className="overflow-hidden whitespace-nowrap"
            >
              <div className="text-sm font-black tracking-tight text-rain-white leading-none">
                <span className="rain-logo-r">R</span>
                <span className="rain-logo-inf">&infin;</span>
                <span className="rain-logo-n">N</span>
              </div>
              <div className="text-[8px] text-rain-dim tracking-widest font-semibold uppercase mt-0.5">
                AI Mastering Engine
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Divider ── */}
      <div className="mx-3 h-px bg-rain-border/20 shrink-0" />

      {/* ── Nav sections ── */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-2" aria-label="Sidebar navigation">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title} className="mb-1">
            {/* Section header — only when expanded */}
            <AnimatePresence initial={false}>
              {!collapsed && (
                <motion.div
                  key={`header-${section.title}`}
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.15 }}
                  className="overflow-hidden"
                >
                  <div className="px-3 pt-3 pb-1">
                    <span className="text-[9px] font-mono font-bold tracking-widest uppercase text-rain-muted">
                      {section.title}
                    </span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Nav items */}
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  [
                    'flex items-center gap-2.5 mx-1.5 my-0.5 px-2 py-2 rounded-md text-[11px] font-semibold uppercase tracking-[0.06em] transition-all duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-rain-teal/50 group relative',
                    isActive
                      ? 'bg-rain-teal/8 text-rain-teal border-l-2 border-rain-teal pl-[6px]'
                      : 'text-rain-dim hover:text-rain-text hover:bg-rain-teal/4 border-l-2 border-transparent pl-[6px]',
                  ].join(' ')
                }
                title={collapsed ? item.label : undefined}
              >
                {({ isActive }) => (
                  <>
                    <item.icon
                      size={14}
                      className={[
                        'shrink-0 transition-colors duration-150',
                        isActive ? 'text-rain-teal drop-shadow-[0_0_6px_rgba(0,212,170,0.5)]' : 'text-rain-dim group-hover:text-rain-text',
                      ].join(' ')}
                    />
                    <AnimatePresence initial={false}>
                      {!collapsed && (
                        <motion.span
                          key={`label-${item.to}`}
                          initial={{ opacity: 0, width: 0 }}
                          animate={{ opacity: 1, width: 'auto' }}
                          exit={{ opacity: 0, width: 0 }}
                          transition={{ duration: 0.15 }}
                          className="overflow-hidden whitespace-nowrap"
                        >
                          {item.label}
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* ── Divider ── */}
      <div className="mx-3 h-px bg-rain-border/20 shrink-0" />

      {/* ── User / plan badge ── */}
      <div className="px-2 py-3 shrink-0">
        <div className="flex items-center gap-2 overflow-hidden">
          {/* Avatar — always visible */}
          <div className="w-7 h-7 rounded-full bg-rain-teal/15 border border-rain-teal/25 flex items-center justify-center shrink-0">
            <span className="text-[10px] font-bold text-rain-teal">{avatarInitial}</span>
          </div>

          <AnimatePresence initial={false}>
            {!collapsed && (
              <motion.div
                key="user-info"
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                className="overflow-hidden whitespace-nowrap flex items-center gap-2"
              >
                <span className="text-[11px] text-rain-silver truncate max-w-[90px]">
                  {displayName}
                </span>
                <span
                  className={[
                    'text-[8px] font-mono font-bold tracking-widest uppercase px-1.5 py-0.5 rounded border',
                    tierColour,
                  ].join(' ')}
                >
                  {tier.replace('_', ' ')}
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.aside>
  )
}
