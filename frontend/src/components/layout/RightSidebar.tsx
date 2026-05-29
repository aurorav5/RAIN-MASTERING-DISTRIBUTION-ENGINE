import { BarChart2, Radio, CheckCircle2 } from 'lucide-react'

export function RightSidebar() {
  return (
    <aside className="w-[280px] flex flex-col h-full bg-black/40 backdrop-blur-[40px] border-l border-white/5 shrink-0 overflow-hidden z-30 pt-6 px-4 space-y-6">
      
      {/* Metering Panel */}
      <div className="crystal-bubble p-4 space-y-4 shadow-xl">
        <h3 className="text-[10px] font-mono font-black tracking-widest text-white/50 uppercase flex items-center gap-2">
          <BarChart2 size={12} />
          Metering
        </h3>
        
        <div className="space-y-3">
          <div className="space-y-1">
            <div className="flex justify-between items-center px-1">
              <span className="text-[9px] font-mono tracking-widest text-cyan-400">LUFS INT</span>
              <span className="text-[10px] font-mono font-bold text-white">-13.8</span>
            </div>
            <div className="h-6 w-full rounded-md bg-black/50 border border-white/10 overflow-hidden relative">
              <div className="absolute inset-y-0 left-0 bg-gradient-to-r from-green-500 via-yellow-400 to-red-500 w-[75%] opacity-80" />
              <div className="absolute inset-y-0 left-0 bg-[linear-gradient(90deg,transparent_2px,rgba(0,0,0,0.5)_2px,rgba(0,0,0,0.5)_3px)] bg-[length:3px_100%] w-full" />
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between items-center px-1">
              <span className="text-[9px] font-mono tracking-widest text-red-400">TRUE PEAK</span>
              <span className="text-[10px] font-mono font-bold text-white">-0.3</span>
            </div>
            <div className="h-6 w-full rounded-md bg-black/50 border border-white/10 overflow-hidden relative">
              <div className="absolute inset-y-0 left-0 bg-gradient-to-r from-green-500 via-yellow-400 to-red-500 w-[95%] opacity-80" />
              <div className="absolute inset-y-0 left-0 bg-[linear-gradient(90deg,transparent_2px,rgba(0,0,0,0.5)_2px,rgba(0,0,0,0.5)_3px)] bg-[length:3px_100%] w-full" />
            </div>
          </div>
        </div>
      </div>

      {/* Platform Consistent Panel */}
      <div className="crystal-bubble p-4 space-y-3 shadow-xl flex-1">
        <h3 className="text-[10px] font-mono font-black tracking-widest text-white/50 uppercase flex items-center gap-2 mb-2">
          <Radio size={12} />
          Platform Consistent
        </h3>
        
        <div className="space-y-2">
          {['Spotify', 'Apple Music', 'Tidal HiFi', 'YouTube', 'Vinyl Pre-Master'].map((platform, i) => (
            <div key={platform} className="crystal-bubble p-2 px-3 flex items-center justify-between hover:bg-white/5 cursor-pointer">
              <span className="text-xs font-semibold text-white/90">{platform}</span>
              <CheckCircle2 size={14} className={i < 3 ? "text-green-400" : "text-white/20"} />
            </div>
          ))}
        </div>
      </div>

      {/* Platform Features Details */}
      <div className="crystal-bubble p-4 mb-6">
        <h3 className="text-[10px] font-mono font-black tracking-widest text-white/50 uppercase mb-2">
          Technical Properties
        </h3>
        <div className="grid grid-cols-2 gap-2 gap-y-3">
          <div>
            <div className="text-[8px] text-white/40 uppercase tracking-widest">Format</div>
            <div className="text-[11px] font-mono font-bold text-white mt-0.5">24-bit PCM</div>
          </div>
          <div>
            <div className="text-[8px] text-white/40 uppercase tracking-widest">Sample Rate</div>
            <div className="text-[11px] font-mono font-bold text-white mt-0.5">48 kHz</div>
          </div>
          <div>
            <div className="text-[8px] text-white/40 uppercase tracking-widest">Codec</div>
            <div className="text-[11px] font-mono font-bold text-white mt-0.5">Lossless WAV</div>
          </div>
          <div>
            <div className="text-[8px] text-white/40 uppercase tracking-widest">Dither</div>
            <div className="text-[11px] font-mono font-bold text-white mt-0.5">Triangular</div>
          </div>
        </div>
      </div>

    </aside>
  )
}
