import { useState, useRef, useEffect } from 'react'
import { Send, Layers } from 'lucide-react'

interface ChatMsg { role: 'user' | 'ai'; text: string }
interface Stem { name: string; pct: number; dbfs: number }

const STEMS: Stem[] = [
  { name: 'Lead Vocals',    pct: 78, dbfs: -6  },
  { name: 'Backing Vocals', pct: 42, dbfs: -14 },
  { name: 'Bass',           pct: 85, dbfs: -4  },
  { name: 'Kick',           pct: 90, dbfs: -3  },
  { name: 'Snare',          pct: 70, dbfs: -8  },
  { name: 'Hi-hats',        pct: 55, dbfs: -12 },
  { name: 'Cymbals',        pct: 48, dbfs: -14 },
  { name: 'Guitar',         pct: 60, dbfs: -10 },
  { name: 'Piano',          pct: 35, dbfs: -18 },
  { name: 'Synths / Pads',  pct: 50, dbfs: -14 },
  { name: 'FX / Atmosphere',pct: 28, dbfs: -22 },
  { name: 'Room / Ambience',pct: 20, dbfs: -28 },
]

const AI_REPLIES: Record<string, string> = {
  warm: 'Understood. Increasing WARMTH macro to 7.2, enabling Manley Massive Passive low-shelf +2dB at 80Hz, and activating Studer A800 tape saturation. THD harmonics set to 2nd-order dominant.',
  loud: 'Targeting -10 LUFS streaming. Increasing GLUE to 8.0, enabling SSL G-Bus with 4:1 ratio, PUNCH macro 7.5. True peak ceiling remains -1.0 dBTP.',
  wide: 'Expanding stereo field. WIDTH macro set to 6.5. Side channel +3dB above 2kHz. LR crossover lowered to 80Hz for tight mono bass.',
  bright: 'Boosting BRIGHTEN macro to 7.0. Adding high shelf at 10kHz +2.5dB, air band presence at 14kHz. Transient enhancement on hi-hats and cymbals.',
  punch: 'Increasing PUNCH macro to 7.5. Kick transient boost +4dB, drum lookahead engaged, low-end tightening via multiband compression on sub-120Hz.',
  clean: 'Setting all macros to neutral (5.0). Disabling analog saturation. Linear-phase EQ only. SAIL limiter in transparent mode.',
}

export default function ColabTab() {
  const [msgs, setMsgs] = useState<ChatMsg[]>([
    { role: 'ai', text: 'Hello. I am Rain AI. Describe what you want the master to sound like and I will translate your words into processing parameters.' }
  ])
  const [input, setInput] = useState('')
  const [separating, setSeparating] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const send = () => {
    if (!input.trim()) return
    const userMsg: ChatMsg = { role: 'user', text: input }
    setMsgs(m => [...m, userMsg])
    setInput('')
    setTimeout(() => {
      const key = Object.keys(AI_REPLIES).find(k => userMsg.text.toLowerCase().includes(k))
      const reply = key
        ? AI_REPLIES[key]!
        : `Analyzing request: "${userMsg.text}". Processing signal chain parameters and updating macro system...`
      setMsgs(m => [...m, { role: 'ai', text: reply }])
    }, 900)
  }

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs])

  return (
    <div className="p-4 grid grid-cols-[1fr_280px] gap-3" style={{ height: 'calc(100vh - 200px)' }}>
      {/* Chat Area */}
      <div className="panel-card flex flex-col min-h-0">
        <div className="panel-card-header">RAIN AI ASSISTANT</div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {msgs.map((m, i) => (
            <div key={i} className={`max-w-[82%] p-2 px-3 rounded text-xs leading-relaxed ${
              m.role === 'user'
                ? 'ml-auto bg-rain-panel border border-rain-border text-rain-text'
                : 'bg-rain-green/5 border border-rain-green/20 text-rain-dim'
            }`}>
              {m.role === 'ai' && (
                <div className="text-[8px] font-mono text-rain-green tracking-wider mb-1">RAIN AI</div>
              )}
              {m.text}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <div className="flex border-t border-rain-border shrink-0">
          <input
            className="flex-1 bg-rain-panel border-none px-3 py-2.5 text-rain-text text-xs outline-none placeholder:text-rain-muted font-mono"
            placeholder="Describe how you want the master to sound..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send()}
          />
          <button
            onClick={send}
            className="px-4 bg-gradient-to-r from-rain-purple to-rain-magenta text-white text-[10px] font-mono font-bold tracking-wider flex items-center gap-1.5 hover:opacity-90 transition-opacity"
          >
            <Send size={10} /> SEND
          </button>
        </div>
      </div>

      {/* Stems Panel */}
      <div className="panel-card flex flex-col min-h-0 overflow-hidden">
        <div className="panel-card-header justify-between">
          <span className="flex items-center gap-2">
            <Layers size={11} />
            12 STEMS
          </span>
          <button
            onClick={() => { setSeparating(true); setTimeout(() => setSeparating(false), 3000) }}
            className="text-[8px] font-mono px-2 py-0.5 border border-rain-purple/30 bg-rain-purple/10 text-rain-purple rounded hover:bg-rain-purple/20 transition-colors"
          >
            {separating ? 'SEPARATING...' : 'SEPARATE'}
          </button>
        </div>
        <div className="panel-card-body overflow-y-auto space-y-0">
          {STEMS.map(s => (
            <div key={s.name} className="flex items-center gap-2 py-1.5 border-b border-rain-border/50 last:border-b-0">
              <div className="flex-1 text-[10px] font-mono text-rain-dim">{s.name}</div>
              <div className="w-14 h-0.5 bg-rain-bg rounded overflow-hidden">
                <div className="h-full bg-rain-cyan rounded" style={{ width: `${s.pct}%` }} />
              </div>
              <div className="text-[8px] font-mono text-rain-muted w-8 text-right">{s.dbfs}dB</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
