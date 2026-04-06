import { useSessionStore } from '@/stores/session'

const STAGES = [
  { name: 'UPLOAD', sub: 'PCM / WAV' },
  { name: 'ANALYSIS', sub: 'BS.1770 scan' },
  { name: 'GENRE', sub: 'Classifier' },
  { name: 'INFERENCE', sub: 'RainNet v2' },
  { name: 'VALIDATE', sub: 'Schema gate' },
  { name: 'M/S PROC', sub: 'Mid/Side' },
  { name: 'MB COMP', sub: '3-band dyn' },
  { name: 'EQ', sub: '8-band LPF' },
  { name: 'ANALOG', sub: 'THD engine' },
  { name: 'SAIL', sub: 'Limiter' },
  { name: 'VERIFY', sub: 'LUFS check' },
  { name: 'COMPLETE', sub: 'RAIN-CERT' },
]

const STATUS_TO_STAGE: Record<string, number> = {
  idle: -1,
  uploading: 0,
  analyzing: 1,
  processing: 6,
  complete: 11,
  failed: -1,
}

export function SignalChain() {
  const { status } = useSessionStore()
  const activeIdx = STATUS_TO_STAGE[status] ?? -1

  return (
    <div className="panel-card">
      <div className="panel-card-header justify-between">
        <span>Signal Chain</span>
        <span className="text-[9px] font-mono text-rain-dim">RAIN-DSP v6.0 &middot; {STAGES.length} stages</span>
      </div>
      <div className="panel-card-body">
        <div className="flex gap-1 items-stretch">
          {STAGES.map((stage, i) => {
            let cls = 'chain-stage flex-1 text-center'
            if (i < activeIdx) cls += ' completed'
            else if (i === activeIdx) cls += ' active'
            return (
              <div key={stage.name} className={cls}>
                <div className="text-[10px] font-bold">{stage.name}</div>
                <div className="text-[7px] opacity-60 mt-0.5">{stage.sub}</div>
              </div>
            )
          })}
        </div>
        <div className="flex justify-between mt-1 px-1">
          <span className="text-[8px] font-mono text-rain-dim">INPUT</span>
          <span className="text-[8px] font-mono text-rain-dim">IDLE</span>
          <span className="text-[8px] font-mono text-rain-dim">OUTPUT</span>
        </div>
      </div>
    </div>
  )
}
