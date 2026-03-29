import { useEffect, useRef } from 'react'

interface Props {
  audioBuffer?: AudioBuffer | null
  liveData?: Uint8Array | null
  inputLufs?: number | null
  outputLufs?: number | null
  height?: number
}

export function Waveform({ audioBuffer, liveData, inputLufs, outputLufs, height = 100 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const W = canvas.width
    const H = canvas.height
    const centerY = H / 2

    // Background with subtle gradient
    ctx.clearRect(0, 0, W, H)
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H)
    bgGrad.addColorStop(0, '#0D0B1A')
    bgGrad.addColorStop(0.5, '#08070F')
    bgGrad.addColorStop(1, '#0D0B1A')
    ctx.fillStyle = bgGrad
    ctx.fillRect(0, 0, W, H)

    // Center line
    ctx.strokeStyle = 'rgba(42, 37, 69, 0.4)'
    ctx.lineWidth = 1
    ctx.setLineDash([2, 4])
    ctx.beginPath()
    ctx.moveTo(0, centerY)
    ctx.lineTo(W, centerY)
    ctx.stroke()
    ctx.setLineDash([])

    if (liveData && liveData.length > 0) {
      // Live waveform with gradient fill
      const gradient = ctx.createLinearGradient(0, 0, 0, H)
      gradient.addColorStop(0, 'rgba(0, 212, 255, 0.6)')
      gradient.addColorStop(0.5, 'rgba(139, 92, 246, 0.8)')
      gradient.addColorStop(1, 'rgba(0, 212, 255, 0.6)')

      ctx.beginPath()
      ctx.strokeStyle = '#00D4FF'
      ctx.lineWidth = 1.5
      ctx.shadowColor = 'rgba(0, 212, 255, 0.3)'
      ctx.shadowBlur = 8
      const sliceW = W / liveData.length
      for (let i = 0; i < liveData.length; i++) {
        const v = (liveData[i] ?? 128) / 128.0
        const y = (v * H) / 2
        i === 0 ? ctx.moveTo(i * sliceW, y) : ctx.lineTo(i * sliceW, y)
      }
      ctx.stroke()
      ctx.shadowBlur = 0

      // Mirror with lower opacity
      ctx.beginPath()
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.15)'
      ctx.lineWidth = 1
      for (let i = 0; i < liveData.length; i++) {
        const v = (liveData[i] ?? 128) / 128.0
        const y = H - (v * H) / 2
        i === 0 ? ctx.moveTo(i * sliceW, y) : ctx.lineTo(i * sliceW, y)
      }
      ctx.stroke()

    } else if (audioBuffer) {
      const data = audioBuffer.getChannelData(0)
      const step = Math.ceil(data.length / W)

      // Waveform bars with gradient
      for (let i = 0; i < W; i++) {
        let min = 1, max = -1
        for (let j = 0; j < step; j++) {
          const datum = data[i * step + j]
          if (datum !== undefined) {
            if (datum < min) min = datum
            if (datum > max) max = datum
          }
        }

        const y1 = (1 + min) * H / 2
        const y2 = (1 + max) * H / 2
        const barHeight = y2 - y1
        const intensity = Math.min(1, Math.abs(max - min) * 3)

        // Gradient based on amplitude
        const r = Math.round(139 + (0 - 139) * intensity)
        const g = Math.round(92 + (212 - 92) * intensity)
        const b = Math.round(246 + (255 - 246) * intensity)
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${0.4 + intensity * 0.5})`
        ctx.fillRect(i, y1, 1, Math.max(1, barHeight))
      }
    }

    // LUFS overlay with glass background
    ctx.shadowBlur = 0
    if (inputLufs !== null && inputLufs !== undefined) {
      ctx.fillStyle = 'rgba(8, 7, 15, 0.7)'
      ctx.fillRect(4, 4, 110, 20)
      ctx.fillStyle = '#7A7595'
      ctx.font = '600 10px "JetBrains Mono", monospace'
      ctx.fillText(`IN  ${inputLufs.toFixed(1)} LUFS`, 10, 17)
    }
    if (outputLufs !== null && outputLufs !== undefined) {
      ctx.fillStyle = 'rgba(8, 7, 15, 0.7)'
      ctx.fillRect(4, 28, 110, 20)
      ctx.fillStyle = '#00D4FF'
      ctx.font = '600 10px "JetBrains Mono", monospace'
      ctx.fillText(`OUT ${outputLufs.toFixed(1)} LUFS`, 10, 41)
    }
  }, [audioBuffer, liveData, inputLufs, outputLufs])

  return (
    <canvas
      ref={canvasRef}
      width={800}
      height={height}
      className="w-full rounded-lg border border-rain-border/20"
      style={{ height }}
    />
  )
}
