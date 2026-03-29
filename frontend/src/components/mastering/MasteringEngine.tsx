import { useSessionStore } from '@/stores/session'
import { Zap, RotateCcw } from 'lucide-react'

interface MasteringEngineProps {
  onMasterNow: () => void
  onReset: () => void
  disabled: boolean
}

export function MasteringEngine({ onMasterNow, onReset, disabled }: MasteringEngineProps) {
  const { status } = useSessionStore()

  const statusColor: Record<string, string> = {
    idle: '#3A4A3A',
    uploading: '#FFB347',
    analyzing: '#00D4AA',
    processing: '#00E5C8',
    complete: '#4AFF8A',
    failed: '#FF4444',
  }

  const color = statusColor[status] ?? '#4A4565'
  const isProcessing = status === 'uploading' || status === 'analyzing' || status === 'processing'

  return (
    <div className="panel-card">
      <div className="panel-card-body flex items-center gap-4 py-3">
        {/* Status indicator */}
        <div className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ background: color, boxShadow: `0 0 8px ${color}60` }}
          />
          <span className="text-sm font-mono font-bold text-rain-text uppercase tracking-wider">
            Mastering Engine
          </span>
          {isProcessing && (
            <span className="text-[9px] font-mono text-rain-dim animate-pulse">
              {status.toUpperCase()}...
            </span>
          )}
        </div>

        {/* Instruction text */}
        <span className="text-[9px] font-mono text-rain-muted flex-1 text-center">
          {status === 'idle' && 'Load an audio file in the transport bar above, then click MASTER NOW to begin processing'}
          {status === 'complete' && 'Processing complete. Check metering panel for RAIN Score.'}
          {status === 'failed' && 'Processing failed. Check console for error details.'}
          {isProcessing && 'Processing in progress...'}
        </span>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={onMasterNow}
            disabled={disabled || isProcessing}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-md font-mono text-[11px] font-bold transition-all ${
              disabled || isProcessing
                ? 'bg-rain-muted text-rain-dim cursor-not-allowed'
                : 'bg-gradient-to-r from-rain-teal to-rain-cyan text-rain-black shadow-glow-teal hover:shadow-glow-cyan cursor-pointer'
            }`}
          >
            {isProcessing ? (
              <div className="w-3.5 h-3.5 border-2 border-rain-dim border-t-transparent rounded-full animate-spin" />
            ) : (
              <Zap size={14} />
            )}
            MASTER NOW
          </button>
          <button
            onClick={onReset}
            className="flex items-center gap-1 px-3 py-2 rounded-md bg-rain-surface border border-rain-border text-rain-dim font-mono text-[10px] hover:text-rain-text hover:border-rain-muted transition-colors"
          >
            <RotateCcw size={12} />
            RESET
          </button>
        </div>
      </div>
    </div>
  )
}
