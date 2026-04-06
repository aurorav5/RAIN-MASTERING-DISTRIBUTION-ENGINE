import { useSessionStore } from '@/stores/session'
import { CheckCircle, Disc3, Wifi, FileText, Shield } from 'lucide-react'

export function StatusFooter() {
  const { inputBuffer, status, outputBuffer, outputLufs } = useSessionStore()

  return (
    <div className="shrink-0">
      {/* Status badges bar */}
      <div className="status-footer">
        <div className="flex items-center gap-2 flex-1">
          <span className={`status-pill ${inputBuffer ? 'badge-green' : 'badge-outline'}`}>
            <Disc3 size={8} />
            AUDIO {inputBuffer ? 'LOADED' : 'EMPTY'}
          </span>

          {status === 'complete' && (
            <span className="status-pill badge-green">
              <CheckCircle size={8} />
              MASTERED
            </span>
          )}

          <span className="status-pill badge-green">
            <CheckCircle size={8} />
            OFFLINE-CAPABLE
          </span>

          <span className="status-pill badge-cyan">
            <FileText size={8} />
            DDEX ERN 4.3
          </span>

          <span className="status-pill badge-purple">
            <Shield size={8} />
            RDN V6.01
          </span>
        </div>

        <div className="flex items-center gap-4 text-[9px] text-rain-dim font-mono">
          <span>{status === 'processing' ? 'ENGINE: PROCESSING' : status === 'complete' ? 'ENGINE: IDLE' : 'ENGINE: READY'}</span>
          <span>48kHz / 24-bit</span>
          {outputLufs != null && <span>LUFS: {outputLufs.toFixed(1)}</span>}
          <span className="text-rain-green">CONNECTED</span>
        </div>
      </div>

      {/* Attribution footer */}
      <div className="flex items-center justify-between px-4 py-2 bg-rain-black/80 border-t border-rain-border/10">
        <span className="text-[9px] text-rain-muted font-mono">
          R&infin;N AI Mastering Engine v6.0 &middot; TheDray Productions / ARCOVEL Technologies International
        </span>
        <span className="text-[9px] text-rain-muted font-mono">
          International, Centurion, South Africa &middot; Architect: Phil Weyers B&ouml;lke &middot; Built with Claude Sonnet 4.6
        </span>
      </div>
    </div>
  )
}
