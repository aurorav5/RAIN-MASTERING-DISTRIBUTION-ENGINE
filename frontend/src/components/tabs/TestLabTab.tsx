import { useState, useRef, useCallback, type ChangeEvent } from 'react'
import { FlaskConical, Play, Pause, Shuffle, Volume2, Headphones, Upload } from 'lucide-react'

type ComparisonMode = 'ab' | 'codec'

export default function TestLabTab() {
  const [mode, setMode] = useState<ComparisonMode>('ab')
  const [playing, setPlaying] = useState(false)
  const [activeSource, setActiveSource] = useState<'A' | 'B'>('A')
  const [blindMode, setBlindMode] = useState(true)
  const [rating, setRating] = useState<'A' | 'B' | null>(null)
  const [codecPreview, setCodecPreview] = useState<string>('spotify')

  const audioRefA = useRef<HTMLAudioElement>(null)
  const audioRefB = useRef<HTMLAudioElement>(null)
  const [fileNameA, setFileNameA] = useState<string | null>(null)
  const [fileNameB, setFileNameB] = useState<string | null>(null)

  const handleFileLoad = useCallback((target: 'A' | 'B') => (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const url = URL.createObjectURL(file)
    const ref = target === 'A' ? audioRefA.current : audioRefB.current
    if (ref) {
      // Revoke previous object URL to avoid memory leaks
      if (ref.src && ref.src.startsWith('blob:')) URL.revokeObjectURL(ref.src)
      ref.src = url
      ref.load()
    }
    if (target === 'A') setFileNameA(file.name)
    else setFileNameB(file.name)
  }, [])

  const togglePlay = useCallback(() => {
    const ref = activeSource === 'A' ? audioRefA.current : audioRefB.current
    const otherRef = activeSource === 'A' ? audioRefB.current : audioRefA.current
    if (!ref) return
    if (playing) {
      ref.pause()
      otherRef?.pause()
    } else {
      ref.play()
    }
    setPlaying(!playing)
  }, [playing, activeSource])

  const switchSource = useCallback(() => {
    const current = activeSource === 'A' ? audioRefA.current : audioRefB.current
    const next = activeSource === 'A' ? audioRefB.current : audioRefA.current
    const time = current?.currentTime ?? 0
    current?.pause()
    if (next) {
      next.currentTime = time
      if (playing) next.play()
    }
    setActiveSource(prev => prev === 'A' ? 'B' : 'A')
  }, [activeSource, playing])

  const codecOptions = [
    { id: 'spotify', label: 'Spotify', codec: 'OGG 256k' },
    { id: 'apple', label: 'Apple Music', codec: 'AAC 256k' },
    { id: 'youtube', label: 'YouTube', codec: 'AAC 128k' },
    { id: 'tidal', label: 'Tidal', codec: 'FLAC (lossless)' },
  ]

  return (
    <div className="p-2 space-y-3 w-full page-enter">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FlaskConical size={14} className="text-rain-purple" />
          <span className="text-xs font-semibold text-rain-purple uppercase tracking-widest">Test Lab</span>
        </div>
        <div className="flex gap-1">
          <button
            className={`text-[10px] px-3 py-1 rounded ${mode === 'ab' ? 'bg-rain-purple/20 text-rain-purple' : 'text-rain-dim'}`}
            onClick={() => setMode('ab')}
          >
            A/B Compare
          </button>
          <button
            className={`text-[10px] px-3 py-1 rounded ${mode === 'codec' ? 'bg-rain-purple/20 text-rain-purple' : 'text-rain-dim'}`}
            onClick={() => setMode('codec')}
          >
            Codec Preview
          </button>
        </div>
      </div>

      {mode === 'ab' ? (
        <>
          {/* File loaders */}
          <div className="grid grid-cols-2 gap-3 mb-3">
            <label className="panel-card p-3 flex items-center gap-2 cursor-pointer hover:border-rain-purple/50 transition-colors">
              <Upload size={14} className="text-rain-purple shrink-0" />
              <div className="min-w-0">
                <div className="text-[10px] font-bold text-rain-white">Track A (Original)</div>
                <div className="text-[9px] text-rain-muted truncate">{fileNameA ?? 'Click to load audio'}</div>
              </div>
              <input type="file" accept="audio/*" className="hidden" onChange={handleFileLoad('A')} />
            </label>
            <label className="panel-card p-3 flex items-center gap-2 cursor-pointer hover:border-rain-purple/50 transition-colors">
              <Upload size={14} className="text-rain-purple shrink-0" />
              <div className="min-w-0">
                <div className="text-[10px] font-bold text-rain-white">Track B (Mastered)</div>
                <div className="text-[9px] text-rain-muted truncate">{fileNameB ?? 'Click to load audio'}</div>
              </div>
              <input type="file" accept="audio/*" className="hidden" onChange={handleFileLoad('B')} />
            </label>
          </div>

          {/* A/B Comparison */}
          <div className="panel-card p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-bold text-rain-white">Blind A/B Comparison</h3>
              <label className="flex items-center gap-2 text-[10px] text-rain-dim">
                <input
                  type="checkbox"
                  checked={blindMode}
                  onChange={e => setBlindMode(e.target.checked)}
                  className="accent-rain-purple"
                />
                Blind mode
              </label>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div
                className={`panel-card p-4 text-center cursor-pointer transition-all ${
                  activeSource === 'A' ? 'border-rain-purple ring-1 ring-rain-purple/30' : ''
                }`}
                onClick={() => { if (activeSource !== 'A') switchSource() }}
              >
                <div className="text-lg font-black text-rain-white mb-1">
                  {blindMode ? 'Sample 1' : 'Original'}
                </div>
                <div className="text-[9px] text-rain-muted">
                  {activeSource === 'A' && playing ? 'Playing' : 'Click to listen'}
                </div>
              </div>
              <div
                className={`panel-card p-4 text-center cursor-pointer transition-all ${
                  activeSource === 'B' ? 'border-rain-purple ring-1 ring-rain-purple/30' : ''
                }`}
                onClick={() => { if (activeSource !== 'B') switchSource() }}
              >
                <div className="text-lg font-black text-rain-white mb-1">
                  {blindMode ? 'Sample 2' : 'Mastered'}
                </div>
                <div className="text-[9px] text-rain-muted">
                  {activeSource === 'B' && playing ? 'Playing' : 'Click to listen'}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-center gap-3">
              <button className="btn-ghost p-2 rounded-full" onClick={togglePlay}>
                {playing ? <Pause size={16} /> : <Play size={16} />}
              </button>
              <button className="btn-ghost p-2 rounded-full" onClick={switchSource}>
                <Shuffle size={16} />
              </button>
            </div>

            {/* Rating */}
            <div className="mt-4 pt-4 border-t border-rain-border">
              <p className="text-[10px] text-rain-dim text-center mb-3">Which sounds better?</p>
              <div className="flex justify-center gap-3">
                <button
                  className={`text-xs px-6 py-2 rounded ${
                    rating === 'A' ? 'bg-rain-purple text-white' : 'btn-ghost'
                  }`}
                  onClick={() => setRating('A')}
                >
                  {blindMode ? 'Sample 1' : 'Original'}
                </button>
                <button
                  className={`text-xs px-6 py-2 rounded ${
                    rating === 'B' ? 'bg-rain-purple text-white' : 'btn-ghost'
                  }`}
                  onClick={() => setRating('B')}
                >
                  {blindMode ? 'Sample 2' : 'Mastered'}
                </button>
              </div>
              {rating && !blindMode && (
                <p className="text-[10px] text-rain-teal text-center mt-2">
                  You preferred the {rating === 'A' ? 'original' : 'mastered'} version
                </p>
              )}
            </div>
          </div>

          {/* Hidden audio elements */}
          <audio ref={audioRefA} onEnded={() => setPlaying(false)} />
          <audio ref={audioRefB} onEnded={() => setPlaying(false)} />
        </>
      ) : (
        <>
          {/* Codec Preview */}
          <div className="panel-card p-4">
            <div className="flex items-center gap-2 mb-4">
              <Headphones size={14} className="text-rain-purple" />
              <h3 className="text-xs font-bold text-rain-white">Codec Preview</h3>
            </div>
            <p className="text-[10px] text-rain-dim mb-4">
              Preview how your master will sound on different streaming platforms after codec re-encoding.
            </p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {codecOptions.map(opt => (
                <button
                  key={opt.id}
                  className={`panel-card p-3 text-center transition-all ${
                    codecPreview === opt.id ? 'border-rain-purple ring-1 ring-rain-purple/30' : ''
                  }`}
                  onClick={() => setCodecPreview(opt.id)}
                >
                  <div className="text-xs font-bold text-rain-white">{opt.label}</div>
                  <div className="text-[9px] text-rain-muted mt-1">{opt.codec}</div>
                </button>
              ))}
            </div>

            <div className="mt-4 flex items-center justify-center gap-3">
              <button className="btn-ghost p-2 rounded-full" onClick={togglePlay}>
                {playing ? <Pause size={16} /> : <Play size={16} />}
              </button>
              <Volume2 size={14} className="text-rain-dim" />
              <span className="text-[10px] text-rain-dim">
                Previewing: {codecOptions.find(o => o.id === codecPreview)?.codec ?? ''}
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
