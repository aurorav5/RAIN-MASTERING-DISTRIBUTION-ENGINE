import { NavLink } from 'react-router-dom'
import {
  Disc3, Layers, Move3D, ShieldCheck, Download, Send,
  Settings, BarChart3, Rocket
} from 'lucide-react'

const TABS = [
  { to: '', label: 'Master', icon: Disc3, end: true },
  { to: 'stems', label: 'Stems', icon: Layers },
  { to: 'spatial', label: 'Spatial', icon: Move3D },
  { to: 'qc', label: 'QC', icon: ShieldCheck },
  { to: 'export', label: 'Export', icon: Download },
  { to: 'distribute', label: 'Distribute', icon: Send },
  { to: 'analytics', label: 'Analytics', icon: BarChart3 },
  { to: 'roadmap', label: 'Roadmap', icon: Rocket },
  { to: 'settings', label: 'Settings', icon: Settings },
] as const

export function TabBar() {
  return (
    <nav className="h-12 bg-[#08070F]/60 border-b border-rain-border/20 flex items-center gap-1.5 px-4 overflow-x-auto shrink-0 z-10">
      {TABS.map((tab) => {
        const { to, label, icon: Icon } = tab
        const end = 'end' in tab ? (tab as { end: boolean }).end : undefined
        return (
          <NavLink
            key={label}
            to={to}
            end={end}
            className={({ isActive }) => `tab-3d flex items-center gap-2 ${isActive ? 'active' : ''}`}
          >
            <Icon size={13} />
            <span>{label}</span>
          </NavLink>
        )
      })}
    </nav>
  )
}
