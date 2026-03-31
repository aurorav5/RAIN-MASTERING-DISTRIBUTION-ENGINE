import { FlaskConical } from 'lucide-react'

export default function TestLabTab() {
  return (
    <div className="p-4 flex items-center justify-center h-64">
      <div className="text-center space-y-3">
        <FlaskConical size={32} className="mx-auto text-rain-purple/40" />
        <div className="text-[9px] font-mono text-rain-muted tracking-[3px]">MODULE</div>
        <div className="text-lg font-bold tracking-[4px] text-rain-dim">TEST LAB</div>
        <div className="text-[9px] font-mono text-rain-muted tracking-wider">
          A/B comparison, blind testing, codec preview, and DSP parameter experimentation.
        </div>
        <span className="inline-block text-[8px] font-mono px-2 py-0.5 border border-rain-purple/30 bg-rain-purple/10 text-rain-purple rounded">
          COMING SOON
        </span>
      </div>
    </div>
  )
}
