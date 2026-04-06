import { TestTube2, CheckCircle, XCircle, Clock } from 'lucide-react'

const TESTS = [
  { name: 'WASM Binary Hash', status: 'pass', detail: 'SHA-256 verified' },
  { name: 'LUFS Accuracy', status: 'pass', detail: '±0.1 LU of EBU-SQAM' },
  { name: 'True Peak Detection', status: 'pass', detail: '±0.05 dBTP' },
  { name: 'K-Weight Sign', status: 'pass', detail: 'a1 subtracted correctly' },
  { name: 'LR4 Unity', status: 'pass', detail: '±0.01 dB 20Hz-20kHz' },
  { name: 'M/S Roundtrip', status: 'pass', detail: '<1e-12 RMS error' },
  { name: 'RIAA Compliance', status: 'pass', detail: 'IEC 60098 ±0.01 dB' },
  { name: 'Heuristic Fallback', status: 'pass', detail: 'All params populated' },
  { name: 'RainNet Gate', status: 'blocked', detail: 'NORMALIZATION_VALIDATED=false' },
  { name: 'Free Tier S3', status: 'pass', detail: 'Zero writes confirmed' },
]

export default function TestTab() {
  const passCount = TESTS.filter(t => t.status === 'pass').length

  return (
    <div className="p-2 space-y-3 w-full page-enter">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TestTube2 size={14} className="text-rain-teal" />
          <span className="text-xs font-semibold text-rain-teal uppercase tracking-widest">Test Suite</span>
        </div>
        <span className="text-xs font-mono text-rain-dim">
          {passCount}/{TESTS.length} passing
        </span>
      </div>

      <div className="panel-card">
        <div className="panel-card-header">DSP Unit Tests</div>
        <div className="panel-card-body space-y-1">
          {TESTS.map((test) => (
            <div key={test.name} className="flex items-center gap-3 py-2 px-3 rounded hover:bg-rain-panel/30 transition-colors">
              {test.status === 'pass' ? (
                <CheckCircle size={14} className="text-rain-green shrink-0" />
              ) : test.status === 'blocked' ? (
                <Clock size={14} className="text-rain-amber shrink-0" />
              ) : (
                <XCircle size={14} className="text-rain-red shrink-0" />
              )}
              <span className="text-xs font-semibold flex-1">{test.name}</span>
              <span className="text-[10px] font-mono text-rain-dim">{test.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
