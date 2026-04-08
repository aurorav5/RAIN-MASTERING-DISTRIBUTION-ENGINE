import { useState } from 'react'

type RoadmapStatus = 'shipped' | 'in-progress' | 'planned' | 'exploring'

interface RoadmapItem {
  version: string
  title: string
  status: RoadmapStatus
  items: string[]
}

const ROADMAP: RoadmapItem[] = [
  {
    version: 'v6.0',
    title: 'Foundation',
    status: 'shipped',
    items: [
      'RainDSP WASM render engine',
      'Multiband dynamics + linear-phase EQ',
      'Heuristic fallback pipeline',
      'Platform loudness normalization',
      'RAIN-CERT watermark embedding',
      'Free tier local-only processing',
    ],
  },
  {
    version: 'v6.1',
    title: 'Intelligence',
    status: 'shipped',
    items: [
      'RainNet v2 ML inference (ONNX)',
      'Genre-aware parameter prediction',
      'Artist Identity Engine (AIE)',
      'Claude-powered mastering assistant',
      'Spectral repair via SpectralRepairNet',
    ],
  },
  {
    version: 'v6.2',
    title: 'Immersive',
    status: 'in-progress',
    items: [
      'Dolby Atmos spatial rendering',
      'Binaural monitoring preview',
      'Object-based audio panning',
      'Immersive stem separation',
      'Apple Spatial Audio metadata',
    ],
  },
  {
    version: 'v6.3',
    title: 'Distribution',
    status: 'in-progress',
    items: [
      'DDEX ERN 4.3 delivery',
      'LabelGrid integration',
      'DDP image export (CD)',
      'Vinyl pre-master chain',
      'Automated ISRC assignment',
    ],
  },
  {
    version: 'v7.0',
    title: 'Studio',
    status: 'exploring',
    items: [
      'Tauri desktop application',
      'JUCE DAW plugin (VST3/AU/AAX)',
      'Real-time collaborative sessions',
      'Custom RainNet training (Enterprise)',
      'White-label API access',
    ],
  },
]

const STATUS_STYLES: Record<RoadmapStatus, { bg: string; text: string; label: string }> = {
  shipped:       { bg: 'bg-green-500/20', text: 'text-green-400', label: 'SHIPPED' },
  'in-progress': { bg: 'bg-rain-purple/20', text: 'text-rain-purple', label: 'IN PROGRESS' },
  planned:       { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'PLANNED' },
  exploring:     { bg: 'bg-rain-cyan/20', text: 'text-[#00D4FF]', label: 'EXPLORING' },
}

export default function RoadmapTab() {
  const [expandedVersion, setExpandedVersion] = useState<string | null>('v6.1')

  return (
    <div className="p-2 space-y-3 w-full">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-mono text-rain-dim tracking-widest uppercase">
          Product Roadmap
        </span>
        <span className="text-[9px] font-mono text-rain-muted">
          RAIN AI Mastering Engine
        </span>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-[18px] top-4 bottom-4 w-px bg-rain-border" />

        <div className="space-y-3">
          {ROADMAP.map(({ version, title, status, items }) => {
            const style = STATUS_STYLES[status]
            const isExpanded = expandedVersion === version

            return (
              <div key={version} className="relative pl-10">
                {/* Dot on timeline */}
                <div className={`absolute left-2.5 top-3 w-3 h-3 rounded-full border-2 ${
                  status === 'shipped' ? 'bg-green-400 border-green-400' :
                  status === 'in-progress' ? 'bg-rain-purple border-rain-purple animate-pulse' :
                  'bg-rain-bg border-rain-border'
                }`} />

                <div className="panel-card">
                  <button
                    onClick={() => setExpandedVersion(isExpanded ? null : version)}
                    className="panel-card-header w-full flex items-center justify-between cursor-pointer hover:opacity-80 transition-opacity"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-[11px] font-mono font-bold text-rain-text">{version}</span>
                      <span className="text-[10px] font-mono text-rain-dim">{title}</span>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[8px] font-mono tracking-wider ${style.bg} ${style.text}`}>
                      {style.label}
                    </span>
                  </button>
                  {isExpanded && (
                    <div className="panel-card-body">
                      <ul className="space-y-1.5">
                        {items.map((item, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${
                              status === 'shipped' ? 'bg-green-400' :
                              status === 'in-progress' ? 'bg-rain-purple' :
                              'bg-rain-muted'
                            }`} />
                            <span className="text-[10px] font-mono text-rain-text">{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
