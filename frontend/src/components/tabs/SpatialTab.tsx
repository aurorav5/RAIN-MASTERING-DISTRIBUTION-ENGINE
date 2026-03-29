import { useState } from 'react'

export default function SpatialTab() {
  const [msEnabled, setMsEnabled] = useState(false)
  const [midGain, setMidGain] = useState(0)
  const [sideGain, setSideGain] = useState(0)
  const [stereoWidth, setStereoWidth] = useState(1.0)
  const [correlationMode, setCorrelationMode] = useState<'normal' | 'wide' | 'mono'>('normal')

  return (
    <div className="p-2 space-y-3 w-full">
      {/* M/S Processing */}
      <div className="panel-card">
        <div className="panel-card-header flex items-center justify-between">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            MID / SIDE PROCESSING
          </span>
          <button
            onClick={() => setMsEnabled(!msEnabled)}
            className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold transition-colors ${
              msEnabled
                ? 'bg-rain-purple/20 border border-rain-purple/40 text-rain-purple'
                : 'bg-rain-bg border border-rain-border text-rain-muted'
            }`}
          >
            {msEnabled ? 'ON' : 'OFF'}
          </button>
        </div>
        <div className="panel-card-body space-y-4">
          {/* Mid Gain */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-mono text-rain-dim">MID GAIN</span>
              <span className="text-[9px] font-mono text-rain-text tabular-nums">
                {midGain > 0 ? '+' : ''}{midGain.toFixed(1)} dB
              </span>
            </div>
            <input
              type="range"
              min="-6"
              max="6"
              step="0.1"
              value={midGain}
              onChange={(e) => setMidGain(Number(e.target.value))}
              disabled={!msEnabled}
              className="rain-slider w-full"
            />
          </div>

          {/* Side Gain */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-mono text-rain-dim">SIDE GAIN</span>
              <span className="text-[9px] font-mono text-rain-text tabular-nums">
                {sideGain > 0 ? '+' : ''}{sideGain.toFixed(1)} dB
              </span>
            </div>
            <input
              type="range"
              min="-6"
              max="6"
              step="0.1"
              value={sideGain}
              onChange={(e) => setSideGain(Number(e.target.value))}
              disabled={!msEnabled}
              className="rain-slider w-full"
            />
          </div>
        </div>
      </div>

      {/* Stereo Width */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            STEREO WIDTH
          </span>
        </div>
        <div className="panel-card-body space-y-4">
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-mono text-rain-dim">WIDTH</span>
              <span className="text-[9px] font-mono text-rain-text tabular-nums">
                {(stereoWidth * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="2"
              step="0.01"
              value={stereoWidth}
              onChange={(e) => setStereoWidth(Number(e.target.value))}
              className="rain-slider w-full"
            />
            <div className="flex justify-between text-[8px] font-mono text-rain-muted">
              <span>MONO</span>
              <span>STEREO</span>
              <span>WIDE</span>
            </div>
          </div>

          {/* Correlation Mode */}
          <div className="space-y-1">
            <span className="text-[9px] font-mono text-rain-dim">CORRELATION MODE</span>
            <div className="flex gap-2">
              {(['normal', 'wide', 'mono'] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => setCorrelationMode(mode)}
                  className={`flex-1 h-7 rounded text-[9px] font-mono tracking-wider border transition-colors ${
                    correlationMode === mode
                      ? 'bg-rain-cyan/20 border-rain-cyan/40 text-[#00D4FF]'
                      : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                  }`}
                >
                  {mode.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Phase Correlation Meter placeholder */}
          <div className="space-y-1">
            <span className="text-[9px] font-mono text-rain-dim">PHASE CORRELATION</span>
            <div className="h-4 bg-rain-bg border border-rain-border rounded overflow-hidden relative">
              <div className="absolute inset-y-0 left-1/2 w-px bg-rain-border" />
              <div
                className="absolute inset-y-0 bg-gradient-to-r from-red-500/60 via-yellow-500/60 to-green-500/60"
                style={{ left: '20%', right: '20%' }}
              />
              <div
                className="absolute top-0 bottom-0 w-1 bg-rain-lime rounded"
                style={{ left: '72%' }}
              />
            </div>
            <div className="flex justify-between text-[8px] font-mono text-rain-muted">
              <span>-1</span>
              <span>0</span>
              <span>+1</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
