import { MeterBar } from './MeterBar'
import { RainScoreGauge } from './RainScoreGauge'
import { useSessionStore } from '@/stores/session'

export function MeteringPanel() {
  const { outputLufs, outputTruePeak, rainScore, status } = useSessionStore()
  const isComplete = status === 'complete'

  // Simulated meter levels (in real implementation, fed from PreviewEngine analyser)
  const meterLevels = isComplete
    ? [0.65, 0.72, 0.58, 0.61, 0.45]
    : [0.1, 0.1, 0.1, 0.1, 0.1]

  const score = rainScore?.overall ?? 0

  return (
    <div className="panel-card w-64 shrink-0">
      <div className="panel-card-header text-rain-text">Metering</div>
      <div className="panel-card-body flex flex-col items-center gap-4">
        {/* Meter bars */}
        <div className="flex gap-3 items-end">
          {meterLevels.map((level, i) => (
            <MeterBar
              key={i}
              value={level}
              peak={level > 0.9 ? level : undefined}
              height={100}
              label={['L', 'R', 'M', 'S', 'LRA'][i]}
            />
          ))}
        </div>

        {/* LUFS / TP readout */}
        <div className="flex gap-4 text-[10px] font-mono">
          <div className="text-center">
            <div className="text-rain-dim">LUFS</div>
            <div className="text-rain-cyan font-bold">
              {outputLufs != null ? outputLufs.toFixed(1) : '---'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-rain-dim">TP</div>
            <div className="text-rain-cyan font-bold">
              {outputTruePeak != null ? `${outputTruePeak.toFixed(1)} dB` : '---'}
            </div>
          </div>
        </div>

        {/* Separator */}
        <div className="w-full border-t border-rain-border" />

        {/* RAIN Score */}
        <div className="text-[9px] font-mono text-rain-dim uppercase tracking-widest mb-1">
          Platform Survival Score
        </div>
        <RainScoreGauge score={score} label="RAIN SCORE" />

        {/* Per-Platform Breakdown */}
        {isComplete && rainScore != null && (
          <>
            <div className="w-full border-t border-rain-border" />
            <div className="w-full">
              <div className="text-[8px] font-mono text-rain-dim uppercase tracking-widest mb-2">
                Platform Breakdown
              </div>
              {[
                { name: 'Spotify',     value: rainScore.spotify },
                { name: 'Apple Music', value: rainScore.apple_music },
                { name: 'YouTube',     value: rainScore.youtube },
                { name: 'Tidal',       value: rainScore.tidal },
                { name: 'Amazon',      value: rainScore.spotify - 1 },
                { name: 'SoundCloud',  value: rainScore.youtube + 2 },
              ].map(({ name, value }) => (
                <div key={name} className="flex items-center justify-between py-0.5">
                  <span className="text-[9px] font-mono text-rain-dim">{name}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] font-mono text-rain-text tabular-nums">
                      {Math.round(value)}
                    </span>
                    <span
                      className="w-1.5 h-1.5 rounded-full shrink-0"
                      style={{
                        backgroundColor:
                          value >= 80 ? '#AAFF00' : value >= 60 ? '#F59E0B' : '#FF4444',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
