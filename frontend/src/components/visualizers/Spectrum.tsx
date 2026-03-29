import { useEffect, useRef } from 'react'

const BAND_LABELS = ['SUB', 'LOW', 'MID', 'HI-MID', 'AIR']
const BAND_FREQS  = [60, 250, 2000, 8000, 20000]

interface Props {
  frequencyData?: Uint8Array | null
  sampleRate?: number
  height?: number
}

export function Spectrum({ frequencyData, sampleRate = 48000, height = 140 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !frequencyData || frequencyData.length === 0) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const W = canvas.width
    const H = canvas.height

    // Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H)
    bgGrad.addColorStop(0, '#0D0B1A')
    bgGrad.addColorStop(1, '#08070F')
    ctx.fillStyle = bgGrad
    ctx.fillRect(0, 0, W, H)

    // dB grid lines
    ctx.strokeStyle = 'rgba(42, 37, 69, 0.3)'
    ctx.lineWidth = 0.5
    ctx.setLineDash([2, 4])
    for (let db = 0; db <= 4; db++) {
      const y = (db / 4) * H
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(W, y)
      ctx.stroke()
    }
    ctx.setLineDash([])

    // dB labels
    ctx.fillStyle = '#4A4565'
    ctx.font = '8px "JetBrains Mono", monospace'
    const dbLabels = ['0', '-12', '-24', '-36', '-48']
    dbLabels.forEach((label, i) => {
      ctx.fillText(label, W - 24, (i / 4) * H + 10)
    })

    const binCount = frequencyData.length
    const barW = Math.max(2, W / binCount)
    const gap = 1

    for (let i = 0; i < binCount; i++) {
      const v = (frequencyData[i] ?? 0) / 255
      const barH = v * H * 0.95

      // Gradient per bar based on frequency position and amplitude
      const freq_t = i / binCount
      const barGrad = ctx.createLinearGradient(0, H - barH, 0, H)

      if (freq_t < 0.15) {
        // Sub/Bass: purple → magenta
        barGrad.addColorStop(0, `rgba(139, 92, 246, ${0.3 + v * 0.7})`)
        barGrad.addColorStop(1, `rgba(139, 92, 246, ${0.1 + v * 0.3})`)
      } else if (freq_t < 0.4) {
        // Low-mid: blue → cyan
        barGrad.addColorStop(0, `rgba(74, 158, 255, ${0.3 + v * 0.7})`)
        barGrad.addColorStop(1, `rgba(0, 212, 255, ${0.1 + v * 0.3})`)
      } else if (freq_t < 0.7) {
        // Mid: cyan → green
        barGrad.addColorStop(0, `rgba(0, 212, 255, ${0.3 + v * 0.7})`)
        barGrad.addColorStop(1, `rgba(74, 255, 138, ${0.1 + v * 0.3})`)
      } else {
        // High/Air: lime → orange
        barGrad.addColorStop(0, `rgba(170, 255, 0, ${0.3 + v * 0.7})`)
        barGrad.addColorStop(1, `rgba(249, 115, 22, ${0.1 + v * 0.3})`)
      }

      ctx.fillStyle = barGrad
      const x = i * barW
      ctx.fillRect(x, H - barH, barW - gap, barH)

      // Glow at bar top for high amplitude
      if (v > 0.6) {
        ctx.shadowColor = freq_t < 0.4 ? 'rgba(139, 92, 246, 0.4)' : 'rgba(0, 212, 255, 0.4)'
        ctx.shadowBlur = 6
        ctx.fillRect(x, H - barH, barW - gap, 2)
        ctx.shadowBlur = 0
      }
    }

    // Platform compliance line at -1 dBTP
    ctx.setLineDash([6, 4])
    ctx.strokeStyle = 'rgba(255, 179, 71, 0.6)'
    ctx.lineWidth = 1
    ctx.beginPath()
    const complianceY = H * 0.08
    ctx.moveTo(0, complianceY)
    ctx.lineTo(W, complianceY)
    ctx.stroke()
    ctx.setLineDash([])

    // Compliance label
    ctx.fillStyle = 'rgba(255, 179, 71, 0.8)'
    ctx.font = '600 8px "JetBrains Mono", monospace'
    ctx.fillText('-1 dBTP ceiling', 6, complianceY - 4)

  }, [frequencyData, sampleRate, height])

  return (
    <div className="relative rounded-lg overflow-hidden border border-rain-border/20">
      <canvas
        ref={canvasRef}
        width={800}
        height={height}
        className="w-full"
        style={{ height }}
      />
      {/* Frequency band labels */}
      <div className="absolute bottom-2 left-0 right-0 flex justify-between px-3 pointer-events-none">
        {BAND_LABELS.map((label, i) => (
          <span key={label} className="text-[9px] font-mono text-rain-dim/60">
            {label}
            <br />
            <span className="text-[7px]">{BAND_FREQS[i]}Hz</span>
          </span>
        ))}
      </div>
    </div>
  )
}
