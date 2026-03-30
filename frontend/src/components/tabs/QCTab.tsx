import { useSessionStore } from '@/stores/session'

const PLATFORMS = [
  { name: 'Spotify', target: -14.0, ceiling: -1.0 },
  { name: 'Apple Music', target: -16.0, ceiling: -1.0 },
  { name: 'YouTube', target: -14.0, ceiling: -1.0 },
  { name: 'Tidal', target: -14.0, ceiling: -1.0 },
  { name: 'Amazon Music', target: -14.0, ceiling: -1.0 },
  { name: 'Deezer', target: -15.0, ceiling: -1.0 },
] as const

const CODEC_CHECKS = [
  { codec: 'AAC 256k', penalty: 0.0, status: 'pass' },
  { codec: 'OGG 320k', penalty: 0.0, status: 'pass' },
  { codec: 'MP3 320k', penalty: -0.1, status: 'pass' },
  { codec: 'MP3 128k', penalty: -0.4, status: 'warn' },
  { codec: 'Opus 128k', penalty: -0.2, status: 'pass' },
] as const

export default function QCTab() {
  const { rainScore, outputLufs, outputTruePeak } = useSessionStore()

  const overallScore = rainScore?.overall ?? null

  return (
    <div className="p-2 space-y-3 w-full">
      {/* RAIN Score overview */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            RAIN SCORE
          </span>
        </div>
        <div className="panel-card-body">
          <div className="flex items-center gap-6">
            {/* Score circle */}
            <div className="w-20 h-20 rounded-full border-2 border-rain-purple flex items-center justify-center shrink-0 relative">
              <span className="text-2xl font-mono font-black text-rain-text">
                {overallScore !== null ? overallScore.toFixed(0) : '--'}
              </span>
              <span className="absolute -bottom-3 text-[8px] font-mono text-rain-dim">
                / 100
              </span>
            </div>

            {/* Measurements */}
            <div className="flex-1 grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <span className="text-[9px] font-mono text-rain-dim">OUTPUT LUFS</span>
                <span className="block text-sm font-mono text-rain-text tabular-nums">
                  {outputLufs !== null ? `${outputLufs.toFixed(1)} LU` : '-- LU'}
                </span>
              </div>
              <div className="space-y-1">
                <span className="text-[9px] font-mono text-rain-dim">TRUE PEAK</span>
                <span className="block text-sm font-mono text-rain-text tabular-nums">
                  {outputTruePeak !== null ? `${outputTruePeak.toFixed(1)} dBTP` : '-- dBTP'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Platform compliance table */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            PLATFORM COMPLIANCE
          </span>
        </div>
        <div className="panel-card-body">
          <table className="w-full text-[10px] font-mono">
            <thead>
              <tr className="text-rain-dim border-b border-rain-border">
                <th className="text-left py-1.5 font-normal tracking-wider">PLATFORM</th>
                <th className="text-right py-1.5 font-normal tracking-wider">TARGET</th>
                <th className="text-right py-1.5 font-normal tracking-wider">CEILING</th>
                <th className="text-right py-1.5 font-normal tracking-wider">SCORE</th>
                <th className="text-center py-1.5 font-normal tracking-wider">STATUS</th>
              </tr>
            </thead>
            <tbody>
              {PLATFORMS.map(({ name, target, ceiling }) => {
                const scores = rainScore as unknown as Record<string, number>
                const score = scores
                  ? scores[name.toLowerCase().replace(' ', '_')] ?? null
                  : null
                const passed = score !== null && score >= 80
                return (
                  <tr key={name} className="border-b border-rain-border/50 text-rain-text">
                    <td className="py-1.5">{name}</td>
                    <td className="text-right tabular-nums">{target.toFixed(1)} LU</td>
                    <td className="text-right tabular-nums">{ceiling.toFixed(1)} dBTP</td>
                    <td className="text-right tabular-nums">{score !== null ? score.toFixed(0) : '--'}</td>
                    <td className="text-center">
                      <span className={`inline-block w-2 h-2 rounded-full ${
                        score === null ? 'bg-rain-muted' : passed ? 'bg-rain-lime' : 'bg-red-500'
                      }`} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Codec penalty table */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            CODEC PENALTY CHECK
          </span>
        </div>
        <div className="panel-card-body">
          <table className="w-full text-[10px] font-mono">
            <thead>
              <tr className="text-rain-dim border-b border-rain-border">
                <th className="text-left py-1.5 font-normal tracking-wider">CODEC</th>
                <th className="text-right py-1.5 font-normal tracking-wider">PENALTY</th>
                <th className="text-center py-1.5 font-normal tracking-wider">STATUS</th>
              </tr>
            </thead>
            <tbody>
              {CODEC_CHECKS.map(({ codec, penalty, status }) => (
                <tr key={codec} className="border-b border-rain-border/50 text-rain-text">
                  <td className="py-1.5">{codec}</td>
                  <td className="text-right tabular-nums">{penalty.toFixed(1)} dB</td>
                  <td className="text-center">
                    <span className={`px-1.5 py-0.5 rounded text-[8px] tracking-wider ${
                      status === 'pass'
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-yellow-500/20 text-yellow-400'
                    }`}>
                      {status.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
