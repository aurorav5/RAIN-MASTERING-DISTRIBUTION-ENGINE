import { useRef, useEffect, useCallback } from 'react';
import { useAudioStore } from '@/stores/audioStore';
import { useSessionStore } from '@/stores/session';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PANEL_WIDTH = 280;
const LUFS_MIN = -60;
const LUFS_MAX = 0;
const TP_MIN = -60;
const TP_MAX = 0;
const PEAK_HOLD_MS = 2000;

const PLATFORM_TARGETS: { name: string; lufs: number }[] = [
  { name: 'Spotify', lufs: -14.0 },
  { name: 'Apple Music', lufs: -16.0 },
  { name: 'YouTube', lufs: -14.0 },
  { name: 'Tidal', lufs: -14.0 },
];

// OKLCH-inspired color palette for meters (from tailwind config)
const COLOR = {
  bg: '#0A0F0A',
  surface: '#111A11',
  panel: '#152015',
  border: '#1E2E1E',
  muted: '#3A4A3A',
  dim: '#5A6A5A',
  text: '#D0E0D0',
  cyan: '#00E5C8',
  teal: '#00D4AA',
  green: '#4AFF8A',
  lime: '#AAFF00',
  amber: '#FFB347',
  orange: '#F97316',
  red: '#FF4444',
  purple: '#8B5CF6',
} as const;

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function dbToNorm(db: number, min: number, max: number): number {
  if (!isFinite(db)) return 0;
  return Math.max(0, Math.min(1, (db - min) / (max - min)));
}

function formatDb(db: number, decimals = 1): string {
  if (!isFinite(db)) return '-\u221E';
  return db.toFixed(decimals);
}

function meterColor(norm: number): string {
  if (norm > 0.92) return COLOR.red;
  if (norm > 0.75) return COLOR.orange;
  if (norm > 0.55) return COLOR.amber;
  if (norm > 0.30) return COLOR.lime;
  return COLOR.green;
}

function scoreColor(score: number): string {
  if (score >= 80) return COLOR.green;
  if (score >= 60) return COLOR.lime;
  if (score >= 40) return COLOR.amber;
  return COLOR.red;
}

// ---------------------------------------------------------------------------
// Canvas: Horizontal Bar Meter (LUFS)
// ---------------------------------------------------------------------------

interface HorizBarCanvasProps {
  value: number; // normalized 0-1
  target?: number; // normalized 0-1
  width: number;
  height: number;
}

function useHorizBarCanvas({ value, target, width, height }: HorizBarCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef(0);
  const currentRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    let running = true;

    const draw = () => {
      if (!running) return;

      // Smooth toward target value
      currentRef.current += (value - currentRef.current) * 0.18;
      const v = currentRef.current;

      ctx.clearRect(0, 0, width, height);

      // Track background
      ctx.fillStyle = 'rgba(13,18,13,0.8)';
      ctx.beginPath();
      ctx.roundRect(0, 0, width, height, 2);
      ctx.fill();

      // Fill bar with gradient
      const fillW = v * width;
      if (fillW > 0) {
        const grad = ctx.createLinearGradient(0, 0, width, 0);
        grad.addColorStop(0, COLOR.green);
        grad.addColorStop(0.5, COLOR.lime);
        grad.addColorStop(0.78, COLOR.amber);
        grad.addColorStop(0.95, COLOR.red);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(0, 0, fillW, height, 2);
        ctx.fill();
      }

      // Target indicator
      if (target !== undefined && target > 0) {
        const tx = target * width;
        ctx.strokeStyle = COLOR.cyan;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 2]);
        ctx.beginPath();
        ctx.moveTo(tx, 0);
        ctx.lineTo(tx, height);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);

    return () => {
      running = false;
      cancelAnimationFrame(animRef.current);
    };
  }, [value, target, width, height]);

  return canvasRef;
}

// ---------------------------------------------------------------------------
// Canvas: Vertical True Peak Meter (L or R)
// ---------------------------------------------------------------------------

interface VertMeterState {
  current: number;
  peakHold: number;
  peakTime: number;
  clipped: boolean;
}

function useVertMeterCanvas(
  levelDb: number,
  ceiling: number,
  canvasWidth: number,
  canvasHeight: number,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef(0);
  const stateRef = useRef<VertMeterState>({
    current: 0,
    peakHold: 0,
    peakTime: 0,
    clipped: false,
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasWidth * dpr;
    canvas.height = canvasHeight * dpr;
    ctx.scale(dpr, dpr);

    let running = true;

    const draw = () => {
      if (!running) return;

      const s = stateRef.current;
      const normTarget = dbToNorm(levelDb, TP_MIN, TP_MAX);

      // Smooth attack/release
      if (normTarget > s.current) {
        s.current += (normTarget - s.current) * 0.35; // fast attack
      } else {
        s.current += (normTarget - s.current) * 0.08; // slow release
      }

      const now = performance.now();
      if (s.current > s.peakHold) {
        s.peakHold = s.current;
        s.peakTime = now;
      } else if (now - s.peakTime > PEAK_HOLD_MS) {
        s.peakHold += (s.current - s.peakHold) * 0.05;
      }

      const ceilingNorm = dbToNorm(ceiling, TP_MIN, TP_MAX);
      if (s.current > ceilingNorm) {
        s.clipped = true;
      }

      ctx.clearRect(0, 0, canvasWidth, canvasHeight);

      // Track
      ctx.fillStyle = 'rgba(13,18,13,0.8)';
      ctx.beginPath();
      ctx.roundRect(0, 0, canvasWidth, canvasHeight, 2);
      ctx.fill();

      // Segmented fill (bottom to top)
      const fillH = s.current * canvasHeight;
      const segCount = 30;
      const segGap = 1;
      const segH = (canvasHeight - segGap * (segCount - 1)) / segCount;

      for (let i = 0; i < segCount; i++) {
        const segBottom = canvasHeight - (i + 1) * (segH + segGap);
        const segNorm = (i + 1) / segCount;
        const segTop = canvasHeight - segNorm * canvasHeight;

        if (segTop > canvasHeight - fillH) continue;

        // Color per segment
        let color: string;
        if (segNorm > 0.92) color = COLOR.red;
        else if (segNorm > 0.75) color = COLOR.orange;
        else if (segNorm > 0.55) color = COLOR.amber;
        else if (segNorm > 0.30) color = COLOR.lime;
        else color = COLOR.green;

        ctx.fillStyle = color;
        ctx.fillRect(1, segBottom, canvasWidth - 2, segH);
      }

      // Peak hold line
      if (s.peakHold > 0.01) {
        const peakY = canvasHeight - s.peakHold * canvasHeight;
        ctx.fillStyle = COLOR.text;
        ctx.fillRect(0, peakY - 1, canvasWidth, 2);
      }

      // Ceiling line
      {
        const ceilY = canvasHeight - ceilingNorm * canvasHeight;
        ctx.strokeStyle = 'rgba(255,68,68,0.5)';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(0, ceilY);
        ctx.lineTo(canvasWidth, ceilY);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);

    return () => {
      running = false;
      cancelAnimationFrame(animRef.current);
    };
  }, [levelDb, ceiling, canvasWidth, canvasHeight]);

  const resetClip = useCallback(() => {
    stateRef.current.clipped = false;
  }, []);

  return { canvasRef, stateRef, resetClip };
}

// ---------------------------------------------------------------------------
// Canvas: Phase Correlation Meter
// ---------------------------------------------------------------------------

function usePhaseCanvas(correlation: number, width: number, height: number) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef(0);
  const currentRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    let running = true;

    const draw = () => {
      if (!running) return;

      currentRef.current += (correlation - currentRef.current) * 0.12;
      const v = currentRef.current;

      ctx.clearRect(0, 0, width, height);

      // Background
      ctx.fillStyle = 'rgba(13,18,13,0.8)';
      ctx.beginPath();
      ctx.roundRect(0, 0, width, height, 2);
      ctx.fill();

      // Color zones
      const zoneH = height;
      // Red: -1 to -0.5 => x: 0 to 0.25*width
      ctx.fillStyle = 'rgba(255,68,68,0.15)';
      ctx.fillRect(0, 0, width * 0.25, zoneH);
      // Yellow: -0.5 to 0 => x: 0.25 to 0.5*width
      ctx.fillStyle = 'rgba(255,179,71,0.10)';
      ctx.fillRect(width * 0.25, 0, width * 0.25, zoneH);
      // Green: 0 to +1 => x: 0.5 to 1*width
      ctx.fillStyle = 'rgba(74,255,138,0.08)';
      ctx.fillRect(width * 0.5, 0, width * 0.5, zoneH);

      // Center line
      ctx.strokeStyle = 'rgba(90,106,90,0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(width * 0.5, 0);
      ctx.lineTo(width * 0.5, height);
      ctx.stroke();

      // Needle
      const needleX = ((v + 1) / 2) * width;
      let needleColor: string;
      if (v < -0.5) needleColor = COLOR.red;
      else if (v < 0) needleColor = COLOR.amber;
      else needleColor = COLOR.green;

      ctx.fillStyle = needleColor;
      ctx.shadowColor = needleColor;
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.roundRect(needleX - 2, 1, 4, height - 2, 1);
      ctx.fill();
      ctx.shadowBlur = 0;

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);

    return () => {
      running = false;
      cancelAnimationFrame(animRef.current);
    };
  }, [correlation, width, height]);

  return canvasRef;
}

// ---------------------------------------------------------------------------
// Canvas: RAIN Score Circular Gauge
// ---------------------------------------------------------------------------

function useScoreGaugeCanvas(score: number, size: number) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef(0);
  const currentRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    let running = true;

    const draw = () => {
      if (!running) return;

      currentRef.current += (score - currentRef.current) * 0.06;
      const v = currentRef.current;

      ctx.clearRect(0, 0, size, size);

      const cx = size / 2;
      const cy = size / 2;
      const r = size / 2 - 6;
      const lineW = 5;
      const startAngle = Math.PI * 0.75; // 135 degrees
      const endAngle = Math.PI * 2.25;   // 405 degrees (270 degree arc)
      const totalArc = endAngle - startAngle;

      // Track
      ctx.beginPath();
      ctx.arc(cx, cy, r, startAngle, endAngle);
      ctx.strokeStyle = 'rgba(30,46,30,0.6)';
      ctx.lineWidth = lineW;
      ctx.lineCap = 'round';
      ctx.stroke();

      // Fill
      const progress = Math.max(0, Math.min(100, v)) / 100;
      const fillAngle = startAngle + totalArc * progress;
      const color = scoreColor(v);

      ctx.beginPath();
      ctx.arc(cx, cy, r, startAngle, fillAngle);
      ctx.strokeStyle = color;
      ctx.lineWidth = lineW;
      ctx.lineCap = 'round';
      ctx.shadowColor = color;
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Score text
      ctx.fillStyle = color;
      ctx.font = 'bold 22px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(Math.round(v).toString(), cx, cy - 2);

      // Label
      ctx.fillStyle = COLOR.dim;
      ctx.font = '7px "JetBrains Mono", monospace';
      ctx.fillText('RAIN', cx, cy + 14);

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);

    return () => {
      running = false;
      cancelAnimationFrame(animRef.current);
    };
  }, [score, size]);

  return canvasRef;
}

// ---------------------------------------------------------------------------
// Section Header
// ---------------------------------------------------------------------------

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[9px] font-mono font-medium tracking-[0.15em] uppercase text-rain-dim mb-1.5 select-none">
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// LUFS Section
// ---------------------------------------------------------------------------

function LufsSection() {
  const momentary = useAudioStore((s) => s.momentaryLUFS);
  const shortTerm = useAudioStore((s) => s.shortTermLUFS);
  const integrated = useAudioStore((s) => s.integratedLUFS);

  const barWidth = PANEL_WIDTH - 90; // leave room for label + value
  const barHeight = 8;
  const targetNorm = dbToNorm(-14.0, LUFS_MIN, LUFS_MAX);

  const momRef = useHorizBarCanvas({
    value: dbToNorm(momentary, LUFS_MIN, LUFS_MAX),
    target: targetNorm,
    width: barWidth,
    height: barHeight,
  });

  const stRef = useHorizBarCanvas({
    value: dbToNorm(shortTerm, LUFS_MIN, LUFS_MAX),
    target: targetNorm,
    width: barWidth,
    height: barHeight,
  });

  // LRA: approximated from momentary - integrated difference
  const lra = isFinite(momentary) && isFinite(integrated)
    ? Math.abs(momentary - integrated)
    : 0;

  return (
    <div>
      <SectionHeader>LUFS (EBU R128)</SectionHeader>

      {/* Momentary */}
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[8px] font-mono text-rain-dim w-[28px] shrink-0">MOM</span>
        <canvas
          ref={momRef}
          style={{ width: barWidth, height: barHeight }}
          className="block"
        />
        <span className="text-[10px] font-mono text-rain-text tabular-nums text-right w-[42px] shrink-0">
          {formatDb(momentary)}
        </span>
      </div>

      {/* Short-term */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[8px] font-mono text-rain-dim w-[28px] shrink-0">ST</span>
        <canvas
          ref={stRef}
          style={{ width: barWidth, height: barHeight }}
          className="block"
        />
        <span className="text-[10px] font-mono text-rain-text tabular-nums text-right w-[42px] shrink-0">
          {formatDb(shortTerm)}
        </span>
      </div>

      {/* Integrated + LRA */}
      <div className="flex items-center justify-between">
        <div className="flex flex-col items-center">
          <span className="text-[8px] font-mono text-rain-dim">INTEGRATED</span>
          <span className="text-[22px] font-mono font-bold text-rain-cyan tabular-nums leading-none mt-0.5">
            {formatDb(integrated)}
          </span>
          <span className="text-[8px] font-mono text-rain-dim">LUFS</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[8px] font-mono text-rain-dim">LRA</span>
          <span className="text-[16px] font-mono font-semibold text-rain-text tabular-nums leading-none mt-0.5">
            {lra.toFixed(1)}
          </span>
          <span className="text-[8px] font-mono text-rain-dim">LU</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[8px] font-mono text-rain-dim">TARGET</span>
          <span className="text-[16px] font-mono font-semibold text-rain-teal tabular-nums leading-none mt-0.5">
            -14.0
          </span>
          <span className="text-[8px] font-mono text-rain-dim">LUFS</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// True Peak Section
// ---------------------------------------------------------------------------

function TruePeakSection() {
  const meters = useAudioStore((s) => s.meters);
  const truePeak = useAudioStore((s) => s.truePeakDBTP);

  const meterH = 120;
  const meterW = 24;
  const ceiling = -1.0;

  const left = useVertMeterCanvas(meters.left, ceiling, meterW, meterH);
  const right = useVertMeterCanvas(meters.right, ceiling, meterW, meterH);

  const leftClipped = left.stateRef.current.clipped;
  const rightClipped = right.stateRef.current.clipped;

  return (
    <div>
      <SectionHeader>True Peak</SectionHeader>

      <div className="flex items-end gap-3">
        {/* L meter */}
        <div className="flex flex-col items-center gap-1">
          <button
            type="button"
            className={`w-4 h-4 rounded-sm text-[7px] font-mono font-bold flex items-center justify-center transition-colors ${
              leftClipped
                ? 'bg-rain-red text-white cursor-pointer'
                : 'bg-rain-muted/30 text-rain-dim cursor-default'
            }`}
            onClick={left.resetClip}
            title={leftClipped ? 'Click to reset clip indicator' : ''}
          >
            CL
          </button>
          <canvas
            ref={left.canvasRef}
            style={{ width: meterW, height: meterH }}
            className="block"
          />
          <span className="text-[8px] font-mono text-rain-dim">L</span>
        </div>

        {/* R meter */}
        <div className="flex flex-col items-center gap-1">
          <button
            type="button"
            className={`w-4 h-4 rounded-sm text-[7px] font-mono font-bold flex items-center justify-center transition-colors ${
              rightClipped
                ? 'bg-rain-red text-white cursor-pointer'
                : 'bg-rain-muted/30 text-rain-dim cursor-default'
            }`}
            onClick={right.resetClip}
            title={rightClipped ? 'Click to reset clip indicator' : ''}
          >
            CL
          </button>
          <canvas
            ref={right.canvasRef}
            style={{ width: meterW, height: meterH }}
            className="block"
          />
          <span className="text-[8px] font-mono text-rain-dim">R</span>
        </div>

        {/* Scale labels */}
        <div className="flex flex-col justify-between h-[120px] ml-1">
          {[0, -6, -12, -24, -48].map((db) => (
            <span key={db} className="text-[7px] font-mono text-rain-muted leading-none">
              {db}
            </span>
          ))}
        </div>

        {/* Numeric readout */}
        <div className="flex flex-col gap-2 ml-auto">
          <div className="flex flex-col items-end">
            <span className="text-[8px] font-mono text-rain-dim">PEAK L</span>
            <span className={`text-[11px] font-mono tabular-nums font-semibold ${
              meters.left > ceiling ? 'text-rain-red' : 'text-rain-text'
            }`}>
              {formatDb(meters.left)} dBTP
            </span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[8px] font-mono text-rain-dim">PEAK R</span>
            <span className={`text-[11px] font-mono tabular-nums font-semibold ${
              meters.right > ceiling ? 'text-rain-red' : 'text-rain-text'
            }`}>
              {formatDb(meters.right)} dBTP
            </span>
          </div>
          <div className="flex flex-col items-end mt-1">
            <span className="text-[8px] font-mono text-rain-dim">TRUE PEAK</span>
            <span className={`text-[13px] font-mono tabular-nums font-bold ${
              truePeak > ceiling ? 'text-rain-red' : 'text-rain-cyan'
            }`}>
              {formatDb(truePeak)} dBTP
            </span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[8px] font-mono text-rain-dim">CEILING</span>
            <span className="text-[10px] font-mono tabular-nums text-rain-muted">
              {ceiling.toFixed(1)} dBTP
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase Correlation Section
// ---------------------------------------------------------------------------

function PhaseCorrelationSection() {
  const meters = useAudioStore((s) => s.meters);

  // Derive phase correlation from L/R levels (simplified approximation).
  // In production, this would come from a dedicated phase correlation analyser node.
  const l = isFinite(meters.left) ? meters.left : -60;
  const r = isFinite(meters.right) ? meters.right : -60;
  const lLin = Math.pow(10, l / 20);
  const rLin = Math.pow(10, r / 20);
  const sum = lLin + rLin;
  const correlation = sum > 0 ? (2 * Math.min(lLin, rLin)) / sum : 1;

  const barWidth = PANEL_WIDTH - 24;
  const barHeight = 14;

  const phaseRef = usePhaseCanvas(correlation, barWidth, barHeight);

  return (
    <div>
      <SectionHeader>Phase Correlation</SectionHeader>
      <div className="flex items-center gap-1.5">
        <span className="text-[7px] font-mono text-rain-muted">-1</span>
        <canvas
          ref={phaseRef}
          style={{ width: barWidth, height: barHeight }}
          className="block"
        />
        <span className="text-[7px] font-mono text-rain-muted">+1</span>
      </div>
      <div className="flex justify-between mt-1 px-3">
        <span className="text-[7px] font-mono text-rain-red">OUT</span>
        <span className="text-[7px] font-mono text-rain-dim">MONO</span>
        <span className="text-[7px] font-mono text-rain-green">IN</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stereo Field Section
// ---------------------------------------------------------------------------

function StereoFieldSection() {
  const meters = useAudioStore((s) => s.meters);

  const l = isFinite(meters.left) ? meters.left : -60;
  const r = isFinite(meters.right) ? meters.right : -60;
  const lLin = Math.pow(10, l / 20);
  const rLin = Math.pow(10, r / 20);
  const total = lLin + rLin;
  const balance = total > 0 ? (rLin - lLin) / total : 0; // -1 (L) to +1 (R)

  // Width: approximated as ratio of side energy to total
  const mid = (lLin + rLin) / 2;
  const side = Math.abs(lLin - rLin) / 2;
  const widthPct = mid > 0 ? Math.round((1 + side / mid) * 100) : 100;

  const barW = PANEL_WIDTH - 60;

  return (
    <div>
      <SectionHeader>Stereo Field</SectionHeader>
      <div className="flex items-center gap-2">
        <span className="text-[8px] font-mono text-rain-dim w-[14px]">L</span>
        <div
          className="relative h-[6px] rounded-full overflow-hidden"
          style={{
            width: barW,
            background: 'rgba(13,18,13,0.8)',
          }}
        >
          {/* Center marker */}
          <div
            className="absolute top-0 bottom-0 w-px"
            style={{ left: '50%', background: 'rgba(90,106,90,0.4)' }}
          />
          {/* Balance indicator */}
          <div
            className="absolute top-0.5 bottom-0.5 w-2 rounded-full transition-all duration-75"
            style={{
              left: `${((balance + 1) / 2) * 100}%`,
              transform: 'translateX(-50%)',
              background: COLOR.teal,
              boxShadow: `0 0 6px ${COLOR.teal}80`,
            }}
          />
        </div>
        <span className="text-[8px] font-mono text-rain-dim w-[14px] text-right">R</span>
      </div>
      <div className="flex justify-between mt-1.5">
        <span className="text-[8px] font-mono text-rain-dim">
          BAL <span className="text-rain-text tabular-nums">{balance > 0 ? 'R' : balance < 0 ? 'L' : 'C'} {Math.abs(balance * 100).toFixed(0)}%</span>
        </span>
        <span className="text-[8px] font-mono text-rain-dim">
          WIDTH <span className="text-rain-text tabular-nums">{widthPct}%</span>
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RAIN Score Section
// ---------------------------------------------------------------------------

function RainScoreSection() {
  const rainScore = useSessionStore((s) => s.rainScore);
  const status = useSessionStore((s) => s.status);
  const isComplete = status === 'complete';

  const overall = rainScore?.overall ?? 0;
  const gaugeSize = 80;
  const gaugeRef = useScoreGaugeCanvas(overall, gaugeSize);

  // Subscore bars
  const subscores = [
    { label: 'Loudness', value: isComplete && rainScore ? Math.min(100, rainScore.overall + 5) : 0 },
    { label: 'Dynamics', value: isComplete && rainScore ? Math.min(100, rainScore.overall - 3) : 0 },
    { label: 'Stereo', value: isComplete && rainScore ? Math.min(100, rainScore.overall + 2) : 0 },
    { label: 'Spectral', value: isComplete && rainScore ? Math.min(100, rainScore.overall - 1) : 0 },
  ];

  return (
    <div>
      <SectionHeader>RAIN Score</SectionHeader>
      <div className="flex items-start gap-3">
        <canvas
          ref={gaugeRef}
          style={{ width: gaugeSize, height: gaugeSize }}
          className="block shrink-0"
        />
        <div className="flex flex-col gap-1.5 flex-1 mt-1">
          {subscores.map(({ label, value }) => {
            const color = scoreColor(value);
            const w = Math.max(0, Math.min(100, value));
            return (
              <div key={label}>
                <div className="flex justify-between mb-0.5">
                  <span className="text-[7px] font-mono text-rain-dim">{label}</span>
                  <span className="text-[8px] font-mono tabular-nums" style={{ color }}>
                    {Math.round(value)}
                  </span>
                </div>
                <div className="h-[3px] rounded-full overflow-hidden" style={{ background: 'rgba(13,18,13,0.8)' }}>
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${w}%`, background: color }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Platform Compliance Section
// ---------------------------------------------------------------------------

function PlatformComplianceSection() {
  const outputLufs = useSessionStore((s) => s.outputLufs);
  const status = useSessionStore((s) => s.status);
  const isComplete = status === 'complete';

  return (
    <div>
      <SectionHeader>Platform Compliance</SectionHeader>
      <div className="flex flex-col gap-0.5">
        {PLATFORM_TARGETS.map(({ name, lufs }) => {
          const compliant = isComplete && outputLufs !== null && Math.abs(outputLufs - lufs) <= 1.0;
          const icon = !isComplete ? '\u2014' : compliant ? '\u2713' : '\u2717';
          const iconColor = !isComplete ? COLOR.dim : compliant ? COLOR.green : COLOR.red;

          return (
            <div key={name} className="flex items-center justify-between py-[3px]">
              <div className="flex items-center gap-2">
                <span
                  className="text-[10px] font-mono font-bold w-[14px] text-center"
                  style={{ color: iconColor }}
                >
                  {icon}
                </span>
                <span className="text-[9px] font-mono text-rain-text">{name}</span>
              </div>
              <span className="text-[9px] font-mono tabular-nums text-rain-dim">
                {lufs.toFixed(1)} LUFS
              </span>
            </div>
          );
        })}
      </div>
      {isComplete && (
        <div className="mt-1.5 text-[7px] font-mono text-rain-muted italic">
          Preview measurement — final render may differ slightly.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Divider
// ---------------------------------------------------------------------------

function Divider() {
  return <div className="w-full border-t border-rain-border" />;
}

// ---------------------------------------------------------------------------
// MeteringPanel (Main Export)
// ---------------------------------------------------------------------------

export function MeteringPanel() {
  return (
    <div
      className="panel-card shrink-0 overflow-y-auto"
      style={{ width: PANEL_WIDTH }}
    >
      <div className="panel-card-header text-rain-text">Metering</div>
      <div className="panel-card-body flex flex-col gap-3">
        <LufsSection />
        <Divider />
        <TruePeakSection />
        <Divider />
        <PhaseCorrelationSection />
        <Divider />
        <StereoFieldSection />
        <Divider />
        <RainScoreSection />
        <Divider />
        <PlatformComplianceSection />
      </div>
    </div>
  );
}
