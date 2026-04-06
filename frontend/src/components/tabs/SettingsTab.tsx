import { useState, useCallback, useEffect } from 'react'
import { useAuthStore } from '@/stores/auth'
import { TierBadge } from '@/components/common/Badge'
import { Check, Eye, EyeOff, Shield } from 'lucide-react'

// ---------------------------------------------------------------------------
// Secrets storage — localStorage with obfuscation (not encryption, but
// prevents casual shoulder-surfing in devtools)
// ---------------------------------------------------------------------------

const SECRETS_KEY = 'rain_secrets_v1'

interface StoredSecrets {
  anthropic_api_key: string
  stripe_key: string
  labelgrid_key: string
}

function loadSecrets(): StoredSecrets {
  try {
    const raw = localStorage.getItem(SECRETS_KEY)
    if (raw) return JSON.parse(atob(raw)) as StoredSecrets
  } catch { /* corrupted */ }
  return { anthropic_api_key: '', stripe_key: '', labelgrid_key: '' }
}

function saveSecrets(secrets: StoredSecrets): void {
  localStorage.setItem(SECRETS_KEY, btoa(JSON.stringify(secrets)))
}

export function getStoredApiKey(key: keyof StoredSecrets): string {
  return loadSecrets()[key]
}

export default function SettingsTab() {
  const { tier, userId, tierGte } = useAuthStore()
  const [previewQuality, setPreviewQuality] = useState<'low' | 'medium' | 'high'>('high')
  const [autoAnalyze, setAutoAnalyze] = useState(true)
  const [darkWaveform, setDarkWaveform] = useState(true)
  const [showTooltips, setShowTooltips] = useState(true)
  const [bufferSize, setBufferSize] = useState('512')

  // Secrets state
  const [secrets, setSecrets] = useState<StoredSecrets>(loadSecrets)
  const [visibleFields, setVisibleFields] = useState<Record<string, boolean>>({})
  const [savedIndicator, setSavedIndicator] = useState<string | null>(null)

  const toggleVisible = useCallback((field: string) => {
    setVisibleFields(prev => ({ ...prev, [field]: !prev[field] }))
  }, [])

  const updateSecret = useCallback((field: keyof StoredSecrets, value: string) => {
    setSecrets(prev => {
      const updated = { ...prev, [field]: value }
      saveSecrets(updated)
      return updated
    })
    setSavedIndicator(field)
    setTimeout(() => setSavedIndicator(null), 2000)
  }, [])

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

      {/* API Keys & Secrets */}
      <div className="panel-card">
        <div className="panel-card-header">
          <Shield size={12} className="text-rain-teal" />
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            API KEYS & SECRETS
          </span>
          <span className="text-[8px] font-mono text-rain-dim ml-auto">stored locally, never sent to RAIN servers</span>
        </div>
        <div className="panel-card-body space-y-4">
          {/* Anthropic API Key */}
          <SecretField
            label="ANTHROPIC API KEY"
            hint="Enables Claude AI Co-Master Engineer"
            placeholder="sk-ant-..."
            value={secrets.anthropic_api_key}
            visible={visibleFields['anthropic'] ?? false}
            saved={savedIndicator === 'anthropic_api_key'}
            onToggleVisible={() => toggleVisible('anthropic')}
            onChange={(v) => updateSecret('anthropic_api_key', v)}
          />

          {/* Stripe Key */}
          <SecretField
            label="STRIPE SECRET KEY"
            hint="Billing integration (test or live)"
            placeholder="sk_test_..."
            value={secrets.stripe_key}
            visible={visibleFields['stripe'] ?? false}
            saved={savedIndicator === 'stripe_key'}
            onToggleVisible={() => toggleVisible('stripe')}
            onChange={(v) => updateSecret('stripe_key', v)}
          />

          {/* LabelGrid Key */}
          <SecretField
            label="LABELGRID API KEY"
            hint="Music distribution to 180+ DSPs"
            placeholder="lg_..."
            value={secrets.labelgrid_key}
            visible={visibleFields['labelgrid'] ?? false}
            saved={savedIndicator === 'labelgrid_key'}
            onToggleVisible={() => toggleVisible('labelgrid')}
            onChange={(v) => updateSecret('labelgrid_key', v)}
          />

          <p className="text-[8px] font-mono text-rain-dim/50 leading-relaxed">
            Keys are stored in your browser's localStorage with base64 encoding.
            They never leave your device. Clear browser data to remove them.
          </p>
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

// ---------------------------------------------------------------------------
// SecretField — reusable API key input with show/hide + saved indicator
// ---------------------------------------------------------------------------

function SecretField({
  label,
  hint,
  placeholder,
  value,
  visible,
  saved,
  onToggleVisible,
  onChange,
}: {
  label: string
  hint: string
  placeholder: string
  value: string
  visible: boolean
  saved: boolean
  onToggleVisible: () => void
  onChange: (v: string) => void
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-mono font-bold text-rain-dim uppercase tracking-wider">{label}</span>
        {saved && (
          <span className="text-[8px] font-mono text-green-400 flex items-center gap-1 animate-pulse">
            <Check size={8} /> Saved
          </span>
        )}
      </div>
      <p className="text-[8px] text-rain-dim/60">{hint}</p>
      <div className="flex items-center gap-1.5">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
          autoComplete="off"
          className="flex-1 bg-rain-bg border border-rain-border rounded px-2 py-1.5 text-rain-text text-[10px] font-mono focus:border-rain-teal/40 focus:outline-none transition-colors placeholder:text-rain-dim/30"
        />
        <button
          onClick={onToggleVisible}
          className="p-1.5 bg-rain-bg border border-rain-border rounded text-rain-dim hover:text-rain-text transition-colors"
          title={visible ? 'Hide' : 'Show'}
        >
          {visible ? <EyeOff size={12} /> : <Eye size={12} />}
        </button>
      </div>
    </div>
  )
}
