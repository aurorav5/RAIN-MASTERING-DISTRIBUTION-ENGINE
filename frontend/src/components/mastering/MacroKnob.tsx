import { useState, useCallback, useRef } from 'react'

interface MacroKnobProps {
  label: string
  value: number
  min?: number
  max?: number
  onChange: (value: number) => void
  color?: string
  subParams?: string[]
  /** Knob diameter in px. Defaults to 88. */
  size?: number
  /** Whether to render the label and sub-params below the knob. Defaults to true. */
  showLabel?: boolean
}

export function MacroKnob({
  label,
  value,
  min = 0,
  max = 10,
  onChange,
  color = '#D946EF',
  subParams = [],
  size = 88,
  showLabel = true,
}: MacroKnobProps) {
  const [isDragging, setIsDragging] = useState(false)
  const knobRef = useRef<HTMLDivElement>(null)
  const startY = useRef(0)
  const startValue = useRef(0)

  const half = size / 2
  const radius = half - 2 // leave 2px padding for stroke
  const normalized = (value - min) / (max - min)
  const angle = -135 + normalized * 270 // -135 to +135 degrees
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference - normalized * circumference * 0.75 // 270 deg arc

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true)
    startY.current = e.clientY
    startValue.current = value

    const handleMouseMove = (e: MouseEvent) => {
      const delta = (startY.current - e.clientY) / 150
      const newVal = Math.round((startValue.current + delta * (max - min)) * 10) / 10
      onChange(Math.min(max, Math.max(min, newVal)))
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [value, min, max, onChange])

  return (
    <div className="flex flex-col items-center gap-2">
      {/* Knob */}
      <div
        ref={knobRef}
        className="relative cursor-pointer select-none"
        onMouseDown={handleMouseDown}
        style={{ width: size, height: size }}
      >
        {/* SVG Ring Track + Value Arc */}
        <svg viewBox={`0 0 ${size} ${size}`} className="absolute inset-0">
          {/* Track */}
          <circle
            cx={half} cy={half} r={radius}
            fill="none"
            stroke="#2A2545"
            strokeWidth="3"
            strokeDasharray={`${circumference * 0.75} ${circumference * 0.25}`}
            strokeDashoffset={circumference * 0.125}
            strokeLinecap="round"
            transform={`rotate(135 ${half} ${half})`}
          />
          {/* Value arc */}
          <circle
            cx={half} cy={half} r={radius}
            fill="none"
            stroke={`url(#knob-grad-${label})`}
            strokeWidth="3"
            strokeDasharray={`${normalized * circumference * 0.75} ${circumference}`}
            strokeDashoffset={0}
            strokeLinecap="round"
            transform={`rotate(135 ${half} ${half})`}
            style={{ filter: `drop-shadow(0 0 4px ${color}60)` }}
          />
          <defs>
            <linearGradient id={`knob-grad-${label}`} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#8B5CF6" />
              <stop offset="50%" stopColor="#D946EF" />
              <stop offset="100%" stopColor="#F97316" />
            </linearGradient>
          </defs>
        </svg>

        {/* 3D Knob Body */}
        <div
          className="absolute inset-[8px] rounded-full"
          style={{
            background: 'radial-gradient(circle at 38% 35%, #2A2545, #141225 55%, #0D0B1A)',
            boxShadow: isDragging
              ? `0 4px 20px ${color}40, inset 0 1px 2px rgba(255,255,255,0.1), inset 0 -2px 4px rgba(0,0,0,0.3)`
              : '0 4px 12px rgba(0,0,0,0.5), inset 0 1px 2px rgba(255,255,255,0.08), inset 0 -2px 4px rgba(0,0,0,0.3)',
            transition: 'box-shadow 0.2s',
          }}
        >
          {/* Inner circle */}
          <div
            className="absolute inset-[4px] rounded-full flex items-center justify-center"
            style={{
              background: 'radial-gradient(circle at 40% 35%, #1C1835, #0D0B1A)',
              boxShadow: 'inset 0 2px 6px rgba(0,0,0,0.4)',
            }}
          >
            {/* Value */}
            <span className="text-lg font-bold font-mono" style={{ color }}>{value.toFixed(1)}</span>
          </div>

          {/* Indicator notch */}
          <div
            className="absolute top-[6px] left-1/2 w-[3px] h-[10px] rounded-full"
            style={{
              transform: `translateX(-50%) rotate(${angle}deg)`,
              transformOrigin: `50% ${(size - 16) / 2 - 6}px`,
              background: `linear-gradient(to bottom, ${color}, ${color}88)`,
              boxShadow: `0 0 6px ${color}80`,
            }}
          />
        </div>
      </div>

      {/* Label */}
      {showLabel && (
        <span className="text-[10px] font-mono font-bold tracking-widest text-rain-text uppercase">
          {label}
        </span>
      )}

      {/* Sub-parameters */}
      {showLabel && subParams.length > 0 && (
        <div className="text-[8px] font-mono text-rain-dim space-y-0.5 text-center">
          {subParams.map((p) => (
            <div key={p}>- {p}</div>
          ))}
        </div>
      )}
    </div>
  )
}
