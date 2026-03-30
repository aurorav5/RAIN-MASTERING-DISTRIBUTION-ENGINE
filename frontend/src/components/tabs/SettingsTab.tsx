import { useState } from 'react'
import { useAuthStore } from '@/stores/auth'
import { TierBadge } from '@/components/common/Badge'

export default function SettingsTab() {
  const { tier, userId, tierGte } = useAuthStore()
  const [previewQuality, setPreviewQuality] = useState<'low' | 'medium' | 'high'>('high')
  const [autoAnalyze, setAutoAnalyze] = useState(true)
  const [darkWaveform, setDarkWaveform] = useState(true)
  const [showTooltips, setShowTooltips] = useState(true)
  const [apiKeyVisible, setApiKeyVisible] = useState(false)
  const [bufferSize, setBufferSize] = useState('512')

  return (
    <div className="p-2 space-y-3 w-full">
      {/* Account info */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            ACCOUNT
          </span>
        </div>
        <div className="panel-card-body space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[9px] font-mono text-rain-dim">USER ID</span>
            <span className="text-[10px] font-mono text-rain-text">{userId ?? 'Not signed in'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[9px] font-mono text-rain-dim">TIER</span>
            <TierBadge tier={tier} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[9px] font-mono text-rain-dim">RENDERS USED</span>
            <span className="text-[10px] font-mono text-rain-text tabular-nums">3 / 10</span>
          </div>
          <button className="w-full h-8 rounded text-[10px] font-mono tracking-widest font-bold bg-gradient-to-r from-rain-purple to-rain-magenta text-white hover:opacity-90 transition-opacity">
            UPGRADE PLAN
          </button>
        </div>
      </div>

      {/* API Keys */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            API KEYS
          </span>
        </div>
        <div className="panel-card-body space-y-3">
          <div className="space-y-1">
            <span className="text-[9px] font-mono text-rain-dim">RAIN API KEY</span>
            <div className="flex items-center gap-2">
              <input
                type={apiKeyVisible ? 'text' : 'password'}
                value="rain_sk_••••••••••••••••"
                readOnly
                className="flex-1 bg-rain-bg border border-rain-border rounded px-2 py-1.5 text-rain-text text-[10px] font-mono"
              />
              <button
                onClick={() => setApiKeyVisible(!apiKeyVisible)}
                className="px-2 py-1.5 bg-rain-bg border border-rain-border rounded text-[9px] font-mono text-rain-dim hover:text-rain-text transition-colors"
              >
                {apiKeyVisible ? 'HIDE' : 'SHOW'}
              </button>
            </div>
          </div>
          {tierGte('artist') && (
            <div className="space-y-1">
              <span className="text-[9px] font-mono text-rain-dim">ANTHROPIC API KEY</span>
              <div className="flex items-center gap-2">
                <input
                  type="password"
                  value="sk-ant-••••••••"
                  readOnly
                  className="flex-1 bg-rain-bg border border-rain-border rounded px-2 py-1.5 text-rain-text text-[10px] font-mono"
                />
                <button className="px-2 py-1.5 bg-rain-bg border border-rain-border rounded text-[9px] font-mono text-rain-dim hover:text-rain-text transition-colors">
                  SHOW
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Audio preferences */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            AUDIO PREFERENCES
          </span>
        </div>
        <div className="panel-card-body space-y-3">
          <div className="space-y-1">
            <span className="text-[9px] font-mono text-rain-dim">PREVIEW QUALITY</span>
            <div className="flex gap-2">
              {(['low', 'medium', 'high'] as const).map(q => (
                <button
                  key={q}
                  onClick={() => setPreviewQuality(q)}
                  className={`flex-1 h-7 rounded text-[9px] font-mono tracking-wider border transition-colors ${
                    previewQuality === q
                      ? 'bg-rain-purple/20 border-rain-purple/40 text-rain-purple'
                      : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                  }`}
                >
                  {q.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <span className="text-[9px] font-mono text-rain-dim">BUFFER SIZE</span>
            <select
              value={bufferSize}
              onChange={(e) => setBufferSize(e.target.value)}
              className="w-full bg-rain-bg border border-rain-border rounded px-2 py-1.5 text-rain-text text-[10px] font-mono"
            >
              <option value="128">128 samples (2.7ms)</option>
              <option value="256">256 samples (5.3ms)</option>
              <option value="512">512 samples (10.7ms)</option>
              <option value="1024">1024 samples (21.3ms)</option>
              <option value="2048">2048 samples (42.7ms)</option>
            </select>
          </div>
        </div>
      </div>

      {/* UI preferences */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            INTERFACE
          </span>
        </div>
        <div className="panel-card-body space-y-3">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-[10px] font-mono text-rain-text">Auto-analyze on upload</span>
            <button
              onClick={() => setAutoAnalyze(!autoAnalyze)}
              className={`w-8 h-4 rounded-full transition-colors relative ${
                autoAnalyze ? 'bg-rain-purple' : 'bg-rain-border'
              }`}
            >
              <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                autoAnalyze ? 'left-4' : 'left-0.5'
              }`} />
            </button>
          </label>
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-[10px] font-mono text-rain-text">Dark waveform background</span>
            <button
              onClick={() => setDarkWaveform(!darkWaveform)}
              className={`w-8 h-4 rounded-full transition-colors relative ${
                darkWaveform ? 'bg-rain-purple' : 'bg-rain-border'
              }`}
            >
              <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                darkWaveform ? 'left-4' : 'left-0.5'
              }`} />
            </button>
          </label>
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-[10px] font-mono text-rain-text">Show tooltips</span>
            <button
              onClick={() => setShowTooltips(!showTooltips)}
              className={`w-8 h-4 rounded-full transition-colors relative ${
                showTooltips ? 'bg-rain-purple' : 'bg-rain-border'
              }`}
            >
              <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                showTooltips ? 'left-4' : 'left-0.5'
              }`} />
            </button>
          </label>
        </div>
      </div>
    </div>
  )
}
