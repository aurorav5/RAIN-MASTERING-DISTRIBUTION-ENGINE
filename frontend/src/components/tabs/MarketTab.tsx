import { TrendingUp, DollarSign, Globe, BarChart3 } from 'lucide-react'

export default function MarketTab() {
  return (
    <div className="p-4 space-y-4 max-w-[1200px] mx-auto page-enter">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp size={14} className="text-rain-teal" />
        <span className="text-xs font-semibold text-rain-teal uppercase tracking-widest">Market Intelligence</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { icon: DollarSign, label: 'Est. Revenue', value: '$0.00', sub: 'This period' },
          { icon: Globe, label: 'Active DSPs', value: '20', sub: 'Platforms connected' },
          { icon: BarChart3, label: 'RAIN Score Avg', value: '0', sub: 'Across releases' },
          { icon: TrendingUp, label: 'Growth', value: '--', sub: 'vs last period' },
        ].map(({ icon: Icon, label, value, sub }) => (
          <div key={label} className="panel-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Icon size={14} className="text-rain-teal" />
              <span className="text-[10px] font-semibold text-rain-dim uppercase tracking-wider">{label}</span>
            </div>
            <div className="text-2xl font-black text-rain-white">{value}</div>
            <div className="text-[9px] font-mono text-rain-muted mt-1">{sub}</div>
          </div>
        ))}
      </div>

      <div className="panel-card">
        <div className="panel-card-header">Distribution Analytics</div>
        <div className="panel-card-body flex items-center justify-center py-16">
          <div className="text-center">
            <BarChart3 size={32} className="text-rain-dim mx-auto mb-4" />
            <p className="text-sm text-rain-dim">No releases distributed yet</p>
            <p className="text-[10px] text-rain-muted mt-1">Complete a mastering session and distribute to see analytics</p>
          </div>
        </div>
      </div>
    </div>
  )
}
