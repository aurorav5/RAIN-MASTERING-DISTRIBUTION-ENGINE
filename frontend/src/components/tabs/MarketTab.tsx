import { useState, useEffect } from 'react'
import { TrendingUp, DollarSign, Globe, BarChart3, Loader2 } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useAuthStore } from '@/stores/auth'

interface MarketStats {
  releaseCount: number
  downloadCount: number
  avgRainScore: number
  activeDsps: number
  recentScores: { name: string; score: number }[]
}

export default function MarketTab() {
  const [stats, setStats] = useState<MarketStats | null>(null)
  const [loading, setLoading] = useState(true)

  const token = useAuthStore(s => s.accessToken)
  const baseUrl = (import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:8000/api/v1'

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch(`${baseUrl}/market/stats`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (!res.ok) throw new Error()
        const data = await res.json()
        if (!cancelled) setStats(data)
      } catch {
        // No releases yet — show empty state
        if (!cancelled) {
          setStats({
            releaseCount: 0,
            downloadCount: 0,
            avgRainScore: 0,
            activeDsps: 0,
            recentScores: [],
          })
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const cards = [
    { icon: DollarSign, label: 'Releases', value: stats?.releaseCount?.toString() ?? '--', sub: 'Total distributed' },
    { icon: Globe, label: 'Active DSPs', value: stats?.activeDsps?.toString() ?? '--', sub: 'Platforms connected' },
    { icon: BarChart3, label: 'RAIN Score Avg', value: stats?.avgRainScore?.toFixed(0) ?? '--', sub: 'Across releases' },
    { icon: TrendingUp, label: 'Downloads', value: stats?.downloadCount?.toString() ?? '--', sub: 'Total this period' },
  ]

  return (
    <div className="p-2 space-y-3 w-full page-enter">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp size={14} className="text-rain-teal" />
        <span className="text-xs font-semibold text-rain-teal uppercase tracking-widest">Market Intelligence</span>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={24} className="animate-spin text-rain-teal" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {cards.map(({ icon: Icon, label, value, sub }) => (
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
            <div className="panel-card-header">RAIN Scores — Recent Sessions</div>
            <div className="panel-card-body">
              {stats && stats.recentScores.length > 0 ? (
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stats.recentScores}>
                      <XAxis
                        dataKey="name"
                        tick={{ fontSize: 9, fill: '#6b7280' }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fontSize: 9, fill: '#6b7280' }}
                        axisLine={false}
                        tickLine={false}
                        width={30}
                      />
                      <Tooltip
                        contentStyle={{
                          background: '#1a1a2e',
                          border: '1px solid #2d2d4a',
                          borderRadius: 6,
                          fontSize: 11,
                        }}
                      />
                      <Bar dataKey="score" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="flex flex-col items-center py-12 text-center">
                  <BarChart3 size={32} className="text-rain-dim mb-4" />
                  <p className="text-sm text-rain-dim">No releases distributed yet</p>
                  <p className="text-[10px] text-rain-muted mt-1">
                    Master and distribute your first track to see analytics here
                  </p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
