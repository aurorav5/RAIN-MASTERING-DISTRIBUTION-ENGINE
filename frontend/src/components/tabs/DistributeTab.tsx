import { useState, useCallback } from 'react'
import { useAuthStore } from '@/stores/auth'
import { Send, FileText, Globe, DollarSign } from 'lucide-react'

const PLATFORMS = [
  // Tier 1 - Major
  { id: 'spotify', name: 'Spotify', lufs: -14, codec: '3d', color: '#1DB954', tier: 1 },
  { id: 'apple_music', name: 'Apple Music', lufs: -16, codec: '5d', color: '#FA2D48', tier: 1 },
  { id: 'youtube_music', name: 'YouTube Music', lufs: -14, codec: '3d', color: '#FF0000', tier: 1 },
  { id: 'tidal', name: 'Tidal HiFi', lufs: -14, codec: '5d', color: '#00D4FF', tier: 1 },
  { id: 'amazon', name: 'Amazon Music HD', lufs: -14, codec: '5d', color: '#FF9900', tier: 1 },
  // Tier 2 - Secondary
  { id: 'deezer', name: 'Deezer', lufs: -15, codec: '5d', color: '#A238FF', tier: 2 },
  { id: 'tiktok', name: 'TikTok / CapCut', lufs: -14, codec: '7d', color: '#FF0050', tier: 2 },
  { id: 'instagram', name: 'Instagram / Facebook', lufs: -14, codec: '7d', color: '#E1306C', tier: 2 },
  { id: 'pandora', name: 'Pandora', lufs: -14, codec: '9d', color: '#005483', tier: 2 },
  { id: 'soundcloud', name: 'SoundCloud', lufs: -14, codec: '5d', color: '#FF5500', tier: 2 },
  // Tier 3 - Regional / Specialty
  { id: 'qobuz', name: 'Qobuz', lufs: -14, codec: '5d', color: '#4A9EFF', tier: 3 },
  { id: 'shazam', name: 'Shazam / Apple', lufs: -16, codec: '5d', color: '#0088FF', tier: 3 },
  { id: 'tencent', name: 'Tencent Music', lufs: -14, codec: '54d', color: '#12B7F5', tier: 3 },
  { id: 'netease', name: 'NetEase Music', lufs: -14, codec: '44d', color: '#C20C0C', tier: 3 },
  { id: 'anghami', name: 'Anghami', lufs: -14, codec: '7d', color: '#8B5CF6', tier: 3 },
  { id: 'jiosaavn', name: 'JioSaavn', lufs: -14, codec: '7d', color: '#2BC5B4', tier: 3 },
  { id: 'boomplay', name: 'Boomplay', lufs: -14, codec: '5d', color: '#4AFF8A', tier: 3 },
  { id: 'audiomack', name: 'Audiomack', lufs: -14, codec: '7d', color: '#FFA500', tier: 3 },
  { id: 'napster', name: 'Napster', lufs: -14, codec: '5d', color: '#000000', tier: 3 },
  { id: 'kkbox', name: 'KKBOX', lufs: -14, codec: '7d', color: '#09CEF6', tier: 3 },
] as const

const SUBTABS = ['Distribute', 'Platforms', 'Metadata'] as const

export default function DistributeTab() {
  const { tierGte } = useAuthStore()
  const [activeSubTab, setActiveSubTab] = useState<typeof SUBTABS[number]>('Platforms')
  const [selectedPlatforms, setSelectedPlatforms] = useState<Set<string>>(new Set(['spotify', 'apple_music', 'youtube_music', 'tidal', 'amazon']))
  const [tierFilter, setTierFilter] = useState<number | 'all' | 'none'>('all')

  const canDistribute = tierGte('studio_pro')

  const togglePlatform = useCallback((id: string) => {
    setSelectedPlatforms(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const selectTier = useCallback((tier: number | 'all' | 'none') => {
    setTierFilter(tier)
    if (tier === 'all') {
      setSelectedPlatforms(new Set(PLATFORMS.map(p => p.id)))
    } else if (tier === 'none') {
      setSelectedPlatforms(new Set())
    } else {
      setSelectedPlatforms(new Set(PLATFORMS.filter(p => p.tier <= tier).map(p => p.id)))
    }
  }, [])

  const filteredPlatforms = PLATFORMS.filter(p =>
    tierFilter === 'all' || tierFilter === 'none' ? true : p.tier <= tierFilter
  )

  const estRoyalty = selectedPlatforms.size * 60 // $60 per platform per 50k streams rough estimate

  return (
    <div className="p-2 space-y-3 w-full page-enter">
      {/* Distribute header */}
      <div className="flex items-center gap-2">
        <Send size={14} className="text-rain-teal" />
        <span className="text-xs font-semibold text-rain-teal uppercase tracking-widest">Distribute</span>
      </div>

      {/* Sub-tabs */}
      <div className="flex items-center gap-1 mb-4">
        {SUBTABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveSubTab(tab)}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
              activeSubTab === tab
                ? 'bg-rain-teal/10 border border-rain-teal/20 text-rain-teal shadow-glow-teal'
                : 'text-rain-dim hover:text-rain-text border border-transparent'
            }`}
          >
            {tab === 'Distribute' && <Send size={12} />}
            {tab === 'Platforms' && <Globe size={12} />}
            {tab === 'Metadata' && <FileText size={12} />}
            {tab}
          </button>
        ))}

        {/* RAIN badge */}
        <div className="ml-auto flex items-center gap-2">
          <div className="h-6 w-20 rounded overflow-hidden flex">
            <div className="h-full bg-rain-red flex-1" />
            <div className="h-full bg-rain-orange flex-1" />
          </div>
          <span className="text-xs font-mono text-rain-dim">23K</span>
        </div>
      </div>

      {/* Platforms Panel */}
      {activeSubTab === 'Platforms' && (
        <div className="panel-card">
          <div className="panel-card-header justify-between">
            <span>Target Platforms</span>
            <div className="flex items-center gap-2">
              {[1, 2, 3].map(t => (
                <button
                  key={t}
                  onClick={() => selectTier(t)}
                  className={`px-3 py-1 rounded text-[9px] font-mono font-bold tracking-wider transition-all ${
                    tierFilter === t
                      ? 'bg-rain-teal/10 text-rain-teal border border-rain-teal/20'
                      : 'text-rain-dim hover:text-rain-text border border-transparent'
                  }`}
                >
                  TIER {t}
                </button>
              ))}
              <button
                onClick={() => selectTier('all')}
                className={`px-3 py-1 rounded text-[9px] font-mono font-bold tracking-wider transition-all ${
                  tierFilter === 'all' ? 'bg-rain-teal/10 text-rain-teal border border-rain-teal/20' : 'text-rain-dim hover:text-rain-text border border-transparent'
                }`}
              >
                ALL
              </button>
              <button
                onClick={() => selectTier('none')}
                className={`px-3 py-1 rounded text-[9px] font-mono font-bold tracking-wider transition-all ${
                  tierFilter === 'none' ? 'bg-rain-teal/10 text-rain-teal border border-rain-teal/20' : 'text-rain-dim hover:text-rain-text border border-transparent'
                }`}
              >
                NONE
              </button>
            </div>
          </div>

          <div className="panel-card-body">
            {/* Platform grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
              {filteredPlatforms.map((platform) => (
                <button
                  key={platform.id}
                  onClick={() => togglePlatform(platform.id)}
                  disabled={!canDistribute}
                  className={`platform-card ${selectedPlatforms.has(platform.id) ? 'selected' : ''}`}
                >
                  <span
                    className="platform-dot"
                    style={{ backgroundColor: platform.color }}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-rain-text truncate">{platform.name}</div>
                    <div className="text-[9px] font-mono text-rain-dim">
                      {platform.lufs} LUFS &middot; {platform.codec}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Estimated royalties */}
            <div className="mt-6 flex items-center justify-between p-5 rounded-lg glass-panel">
              <div>
                <div className="text-[10px] font-mono text-rain-dim uppercase tracking-wider mb-1">
                  Est. Royalties / 50K Streams
                </div>
                <div className="text-3xl font-black text-rain-teal">
                  <DollarSign size={20} className="inline" />
                  {estRoyalty.toFixed(2)} USD
                </div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-black text-rain-teal">{selectedPlatforms.size}</div>
                <div className="text-[9px] font-mono text-rain-dim uppercase tracking-wider">Platforms</div>
                {/* Mini gauge */}
                <svg width="60" height="30" viewBox="0 0 60 30" className="mt-1">
                  <path
                    d="M 5 25 A 25 25 0 0 1 55 25"
                    fill="none"
                    stroke="rgba(0,212,170,0.15)"
                    strokeWidth="4"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 5 25 A 25 25 0 0 1 55 25"
                    fill="none"
                    stroke="#00D4AA"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeDasharray={`${(selectedPlatforms.size / 20) * 78.5} 78.5`}
                    style={{ filter: 'drop-shadow(0 0 4px rgba(0,212,170,0.4))' }}
                  />
                </svg>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Distribute sub-tab */}
      {activeSubTab === 'Distribute' && (
        <div className="panel-card">
          <div className="panel-card-header">DDEX Delivery</div>
          <div className="panel-card-body space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-semibold text-rain-silver block mb-2 uppercase tracking-wider">ISRC</label>
                <input type="text" placeholder="XX-XXX-XX-XXXXX" disabled={!canDistribute} className="input-field font-mono text-sm" />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-rain-silver block mb-2 uppercase tracking-wider">UPC / EAN</label>
                <input type="text" placeholder="0000000000000" disabled={!canDistribute} className="input-field font-mono text-sm" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-semibold text-rain-silver block mb-2 uppercase tracking-wider">Release Title</label>
                <input type="text" placeholder="Track title" disabled={!canDistribute} className="input-field" />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-rain-silver block mb-2 uppercase tracking-wider">Artist Name</label>
                <input type="text" placeholder="Primary artist" disabled={!canDistribute} className="input-field" />
              </div>
            </div>
            <button disabled={!canDistribute} className="btn-primary w-full">
              Submit to LabelGrid
            </button>
          </div>
        </div>
      )}

      {/* Metadata sub-tab */}
      {activeSubTab === 'Metadata' && (
        <div className="panel-card">
          <div className="panel-card-header">Metadata</div>
          <div className="panel-card-body space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-semibold text-rain-silver block mb-2 uppercase tracking-wider">Genre</label>
                <select disabled={!canDistribute} className="input-field">
                  <option>Electronic</option><option>Hip-Hop</option><option>Pop</option><option>Rock</option>
                  <option>R&B</option><option>Classical</option><option>Jazz</option><option>Country</option><option>Latin</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] font-semibold text-rain-silver block mb-2 uppercase tracking-wider">Release Date</label>
                <input type="date" disabled={!canDistribute} className="input-field" />
              </div>
            </div>
            <div>
              <label className="text-[10px] font-semibold text-rain-silver block mb-2 uppercase tracking-wider">Copyright</label>
              <input type="text" placeholder="&copy; 2026 Artist Name" disabled={!canDistribute} className="input-field" />
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs text-rain-silver">
                <input type="checkbox" disabled={!canDistribute} className="accent-rain-teal" />
                Explicit content
              </label>
              <label className="flex items-center gap-2 text-xs text-rain-silver">
                <input type="checkbox" disabled={!canDistribute} className="accent-rain-teal" />
                AI-generated content
              </label>
            </div>
          </div>
        </div>
      )}

      {!canDistribute && (
        <div className="glass-panel rounded-lg px-4 py-3 text-center">
          <span className="text-xs text-rain-dim">
            Distribution requires <span className="text-rain-teal font-semibold">Studio Pro</span> tier or above.
          </span>
        </div>
      )}
    </div>
  )
}
