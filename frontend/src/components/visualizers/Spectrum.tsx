/**
 * Spectrum.tsx — DAW-grade logarithmic spectrum analyzer for RAIN.
 *
 * Features:
 *   - Logarithmic frequency scale (20 Hz – 20 kHz)
 *   - dB scale on Y axis (-90 dB to 0 dB, grid every 6 dB)
 *   - Fill + line rendering with Bezier curve smoothing
 *   - Peak hold with slow decay
 *   - Frequency band highlighting (Sub/Low/Mid/Hi-Mid/Presence/Air)
 *   - Configurable smoothing (fast/medium/slow)
 *   - FFT size selector (2048/4096/8192)
 *   - Mouse hover tooltip (frequency + dB)
 *   - Optional pink noise reference overlay (-3 dB/octave)
 *
 * Uses Canvas 2D + requestAnimationFrame for performance.
 * Reads Float32Array dB data from AudioEngine.getFrequencyData().
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { audioEngine } from '../../audio/AudioEngine';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MIN_FREQ = 20;
const MAX_FREQ = 20_000;
const DB_MIN = -90;
const DB_MAX = 0;
const DB_RANGE = DB_MAX - DB_MIN; // 90

const FREQ_LABELS: ReadonlyArray<{ freq: number; label: string }> = [
  { freq: 20, label: '20' },
  { freq: 50, label: '50' },
  { freq: 100, label: '100' },
  { freq: 200, label: '200' },
  { freq: 500, label: '500' },
  { freq: 1000, label: '1k' },
  { freq: 2000, label: '2k' },
  { freq: 5000, label: '5k' },
  { freq: 10000, label: '10k' },
  { freq: 20000, label: '20k' },
];

/** Frequency band definitions for background shading. */
const BANDS: ReadonlyArray<{
  name: string;
  low: number;
  high: number;
  color: string;
}> = [
  { name: 'Sub', low: 20, high: 60, color: 'rgba(100, 50, 180, 0.06)' },
  { name: 'Low', low: 60, high: 250, color: 'rgba(50, 80, 200, 0.06)' },
  { name: 'Mid', low: 250, high: 2000, color: 'rgba(40, 180, 170, 0.06)' },
  { name: 'Hi-Mid', low: 2000, high: 6000, color: 'rgba(50, 180, 80, 0.06)' },
  { name: 'Presence', low: 6000, high: 12000, color: 'rgba(200, 180, 50, 0.06)' },
  { name: 'Air', low: 12000, high: 20000, color: 'rgba(220, 210, 190, 0.06)' },
];

const SMOOTHING_VALUES: Record<SmoothingMode, number> = {
  fast: 0.65,
  medium: 0.82,
  slow: 0.92,
};

const PEAK_DECAY_RATE = 0.15; // dB per frame (at 60fps ~ 9 dB/s)
const PEAK_HOLD_FRAMES = 45; // ~750ms at 60fps

const BG_COLOR = '#080C08';
const GRID_COLOR = 'rgba(60, 80, 60, 0.25)';
const GRID_LABEL_COLOR = 'rgba(140, 160, 140, 0.6)';
const SPECTRUM_LINE_COLOR = 'rgba(0, 220, 180, 0.9)';
const SPECTRUM_FILL_TOP = 'rgba(0, 220, 180, 0.25)';
const SPECTRUM_FILL_BOTTOM = 'rgba(0, 220, 180, 0.02)';
const PEAK_DOT_COLOR = 'rgba(255, 200, 80, 0.7)';
const REFERENCE_LINE_COLOR = 'rgba(255, 120, 160, 0.35)';
const TOOLTIP_BG = 'rgba(10, 16, 10, 0.88)';
const TOOLTIP_BORDER = 'rgba(0, 220, 180, 0.4)';
const TOOLTIP_TEXT = 'rgba(200, 230, 210, 0.9)';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SmoothingMode = 'fast' | 'medium' | 'slow';
type FFTSize = 2048 | 4096 | 8192;

interface Props {
  /** Override frequency data (Float32Array in dB). If omitted, reads from AudioEngine. */
  frequencyData?: Float32Array | null;
  /** Sample rate of the analyser source. Default: 48000 */
  sampleRate?: number;
  /** Minimum height in pixels. Default: 200 */
  height?: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map a frequency (Hz) to normalized X position [0, 1] on a log scale. */
function freqToX(freq: number): number {
  const logMin = Math.log10(MIN_FREQ);
  const logMax = Math.log10(MAX_FREQ);
  const clamped = Math.max(MIN_FREQ, Math.min(MAX_FREQ, freq));
  return (Math.log10(clamped) - logMin) / (logMax - logMin);
}

/** Map a normalized X position [0, 1] back to frequency (Hz). */
function xToFreq(x: number): number {
  const logMin = Math.log10(MIN_FREQ);
  const logMax = Math.log10(MAX_FREQ);
  return Math.pow(10, logMin + x * (logMax - logMin));
}

/** Map a dB value to normalized Y position [0, 1] (0 = top, 1 = bottom). */
function dbToY(db: number): number {
  const clamped = Math.max(DB_MIN, Math.min(DB_MAX, db));
  return 1.0 - (clamped - DB_MIN) / DB_RANGE;
}

/** Map a normalized Y position [0, 1] to dB. */
function yToDb(y: number): number {
  return DB_MIN + (1.0 - y) * DB_RANGE;
}

/**
 * Compute pink noise reference level at a given frequency.
 * Pink noise has -3 dB/octave slope. Reference: 0 dB at 1 kHz.
 */
function pinkNoiseDb(freq: number): number {
  return -3.0 * Math.log2(freq / 1000);
}

/** Format frequency for display. */
function formatFreq(hz: number): string {
  if (hz >= 1000) {
    const k = hz / 1000;
    return k % 1 === 0 ? `${k}k` : `${k.toFixed(1)}k`;
  }
  return `${Math.round(hz)}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Spectrum({
  frequencyData: externalData,
  sampleRate = 48_000,
  height = 200,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);

  // Persistent buffers stored in refs to avoid re-render on every frame.
  const smoothedRef = useRef<Float32Array | null>(null);
  const peakHoldRef = useRef<Float32Array | null>(null);
  const peakAgeRef = useRef<Uint16Array | null>(null);

  // UI state
  const [smoothing, setSmoothing] = useState<SmoothingMode>('medium');
  const [fftSize, setFftSize] = useState<FFTSize>(4096);
  const [showReference, setShowReference] = useState(false);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [canvasWidth, setCanvasWidth] = useState(960);

  // Layout margins
  const MARGIN_LEFT = 36;
  const MARGIN_RIGHT = 10;
  const MARGIN_TOP = 6;
  const MARGIN_BOTTOM = 22;

  // ---------------------------------------------------------------------------
  // Resize observer
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = Math.round(entry.contentRect.width * window.devicePixelRatio);
        if (w > 0) setCanvasWidth(w);
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // ---------------------------------------------------------------------------
  // Mouse tracking
  // ---------------------------------------------------------------------------
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      setMousePos({
        x: (e.clientX - rect.left) / rect.width,
        y: (e.clientY - rect.top) / rect.height,
      });
    },
    [],
  );

  const handleMouseLeave = useCallback(() => {
    setMousePos(null);
  }, []);

  // ---------------------------------------------------------------------------
  // Animation loop
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = window.devicePixelRatio;
    const cssW = canvasWidth / dpr;
    canvas.width = canvasWidth;
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const plotW = W - MARGIN_LEFT - MARGIN_RIGHT;
    const plotH = H - MARGIN_TOP - MARGIN_BOTTOM;

    const smoothAlpha = SMOOTHING_VALUES[smoothing];

    // -----------------------------------------------------------------------
    // Per-frame draw
    // -----------------------------------------------------------------------
    const draw = () => {
      // --- Acquire frequency data (Float32Array in dB) ---
      let rawData: Float32Array;
      if (externalData && externalData.length > 0) {
        rawData = externalData;
      } else {
        const { left, right } = audioEngine.getFrequencyData();
        if (left.length === 0) {
          // No data — draw static grid and schedule next frame
          drawBackground(ctx, W, H, plotW, plotH);
          rafRef.current = requestAnimationFrame(draw);
          return;
        }
        // Average L+R
        rawData = new Float32Array(left.length);
        for (let i = 0; i < left.length; i++) {
          rawData[i] = ((left[i] ?? 0) + (right[i] ?? 0)) * 0.5;
        }
      }

      const binCount = rawData.length;
      const nyquist = sampleRate / 2;

      // --- Allocate / reallocate persistent buffers ---
      if (smoothedRef.current === null || smoothedRef.current.length !== binCount) {
        smoothedRef.current = new Float32Array(binCount).fill(DB_MIN);
        peakHoldRef.current = new Float32Array(binCount).fill(DB_MIN);
        peakAgeRef.current = new Uint16Array(binCount);
      }
      const smoothed = smoothedRef.current;
      const peakHold = peakHoldRef.current as Float32Array;
      const peakAge = peakAgeRef.current as Uint16Array;

      // --- Smooth + peak hold ---
      for (let i = 0; i < binCount; i++) {
        const rawVal = rawData[i] ?? DB_MIN;
        const safeRaw = Number.isFinite(rawVal) ? rawVal : DB_MIN;
        const prevSmooth = smoothed[i] ?? DB_MIN;
        smoothed[i] = smoothAlpha * prevSmooth + (1 - smoothAlpha) * safeRaw;

        const curSmooth = smoothed[i] ?? DB_MIN;
        const curPeak = peakHold[i] ?? DB_MIN;

        if (curSmooth >= curPeak) {
          peakHold[i] = curSmooth;
          peakAge[i] = 0;
        } else {
          const age = (peakAge[i] ?? 0) + 1;
          peakAge[i] = age;
          if (age > PEAK_HOLD_FRAMES) {
            peakHold[i] = Math.max(DB_MIN, curPeak - PEAK_DECAY_RATE);
          }
        }
      }

      // --- Background + grid ---
      drawBackground(ctx, W, H, plotW, plotH);

      // --- Map bins to pixel X positions and collect points ---
      // We sample at ~1 point per 2 CSS pixels for smoothness.
      const step = Math.max(1, Math.floor(plotW / (2 * dpr)));
      const points: Array<{ px: number; py: number; peakPy: number }> = [];

      for (let px = 0; px <= plotW; px += step) {
        const normX = px / plotW;
        const freq = xToFreq(normX);
        const binFloat = (freq / nyquist) * binCount;

        // Interpolate between neighboring bins for smoother curve
        const binLo = Math.floor(binFloat);
        const binHi = Math.min(binCount - 1, binLo + 1);
        const frac = binFloat - binLo;
        const dbVal =
          binLo >= 0 && binLo < binCount
            ? (smoothed[binLo] ?? DB_MIN) * (1 - frac) + (smoothed[binHi] ?? DB_MIN) * frac
            : DB_MIN;

        const peakDb =
          binLo >= 0 && binLo < binCount
            ? (peakHold[binLo] ?? DB_MIN) * (1 - frac) + (peakHold[binHi] ?? DB_MIN) * frac
            : DB_MIN;

        const yNorm = dbToY(dbVal);
        const peakYNorm = dbToY(peakDb);

        points.push({
          px: MARGIN_LEFT + px,
          py: MARGIN_TOP + yNorm * plotH,
          peakPy: MARGIN_TOP + peakYNorm * plotH,
        });
      }

      if (points.length < 2) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      // --- Band highlighting ---
      ctx.save();
      for (const band of BANDS) {
        const x0 = MARGIN_LEFT + freqToX(band.low) * plotW;
        const x1 = MARGIN_LEFT + freqToX(band.high) * plotW;
        ctx.fillStyle = band.color;
        ctx.fillRect(x0, MARGIN_TOP, x1 - x0, plotH);
      }
      ctx.restore();

      // --- Pink noise reference ---
      if (showReference) {
        ctx.save();
        ctx.strokeStyle = REFERENCE_LINE_COLOR;
        ctx.lineWidth = 1 * dpr;
        ctx.setLineDash([4 * dpr, 4 * dpr]);
        ctx.beginPath();
        for (let px = 0; px <= plotW; px += 2) {
          const freq = xToFreq(px / plotW);
          const refDb = pinkNoiseDb(freq) - 20; // offset to sit around -20 dB area
          const yNorm = dbToY(refDb);
          const screenX = MARGIN_LEFT + px;
          const screenY = MARGIN_TOP + yNorm * plotH;
          if (px === 0) {
            ctx.moveTo(screenX, screenY);
          } else {
            ctx.lineTo(screenX, screenY);
          }
        }
        ctx.stroke();
        ctx.setLineDash([]);

        // Label
        ctx.fillStyle = REFERENCE_LINE_COLOR;
        ctx.font = `${9 * dpr}px "JetBrains Mono", ui-monospace, monospace`;
        ctx.fillText('PINK REF', MARGIN_LEFT + 4 * dpr, MARGIN_TOP + 14 * dpr);
        ctx.restore();
      }

      // --- Spectrum fill (gradient under curve) ---
      const fillGrad = ctx.createLinearGradient(0, MARGIN_TOP, 0, MARGIN_TOP + plotH);
      fillGrad.addColorStop(0, SPECTRUM_FILL_TOP);
      fillGrad.addColorStop(1, SPECTRUM_FILL_BOTTOM);

      const firstPt = points[0];
      const lastPt = points[points.length - 1];
      if (firstPt === undefined || lastPt === undefined) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(firstPt.px, firstPt.py);

      // Bezier curve through points
      for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1]!;
        const curr = points[i]!;
        const cpx = (prev.px + curr.px) / 2;
        ctx.bezierCurveTo(cpx, prev.py, cpx, curr.py, curr.px, curr.py);
      }

      // Close path along bottom
      ctx.lineTo(lastPt.px, MARGIN_TOP + plotH);
      ctx.lineTo(firstPt.px, MARGIN_TOP + plotH);
      ctx.closePath();
      ctx.fillStyle = fillGrad;
      ctx.fill();
      ctx.restore();

      // --- Spectrum line ---
      ctx.save();
      ctx.strokeStyle = SPECTRUM_LINE_COLOR;
      ctx.lineWidth = 1.5 * dpr;
      ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.moveTo(firstPt.px, firstPt.py);
      for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1]!;
        const curr = points[i]!;
        const cpx = (prev.px + curr.px) / 2;
        ctx.bezierCurveTo(cpx, prev.py, cpx, curr.py, curr.px, curr.py);
      }
      ctx.stroke();
      ctx.restore();

      // --- Peak hold dots ---
      ctx.save();
      ctx.fillStyle = PEAK_DOT_COLOR;
      const dotR = 1.2 * dpr;
      for (const pt of points) {
        if (pt.peakPy < MARGIN_TOP + plotH - 2) {
          ctx.beginPath();
          ctx.arc(pt.px, pt.peakPy, dotR, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.restore();

      // --- Mouse hover tooltip ---
      if (mousePos !== null) {
        const mxCanvas = mousePos.x * W;
        const myCanvas = mousePos.y * H;

        // Only show if within the plot area
        if (
          mxCanvas >= MARGIN_LEFT &&
          mxCanvas <= MARGIN_LEFT + plotW &&
          myCanvas >= MARGIN_TOP &&
          myCanvas <= MARGIN_TOP + plotH
        ) {
          const normX = (mxCanvas - MARGIN_LEFT) / plotW;
          const normY = (myCanvas - MARGIN_TOP) / plotH;
          const hoverFreq = xToFreq(normX);
          const hoverDb = yToDb(normY);

          // Crosshair
          ctx.save();
          ctx.strokeStyle = 'rgba(0, 220, 180, 0.2)';
          ctx.lineWidth = 1;
          ctx.setLineDash([2 * dpr, 3 * dpr]);
          ctx.beginPath();
          ctx.moveTo(mxCanvas, MARGIN_TOP);
          ctx.lineTo(mxCanvas, MARGIN_TOP + plotH);
          ctx.stroke();
          ctx.beginPath();
          ctx.moveTo(MARGIN_LEFT, myCanvas);
          ctx.lineTo(MARGIN_LEFT + plotW, myCanvas);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.restore();

          // Tooltip box
          const label = `${formatFreq(hoverFreq)} Hz  ${hoverDb.toFixed(1)} dB`;
          ctx.save();
          ctx.font = `${10 * dpr}px "JetBrains Mono", ui-monospace, monospace`;
          const textMetrics = ctx.measureText(label);
          const tw = textMetrics.width + 12 * dpr;
          const th = 18 * dpr;

          // Position tooltip: flip if too close to edges
          let tx = mxCanvas + 10 * dpr;
          let ty = myCanvas - th - 6 * dpr;
          if (tx + tw > W - MARGIN_RIGHT) tx = mxCanvas - tw - 10 * dpr;
          if (ty < MARGIN_TOP) ty = myCanvas + 10 * dpr;

          ctx.fillStyle = TOOLTIP_BG;
          ctx.strokeStyle = TOOLTIP_BORDER;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.roundRect(tx, ty, tw, th, 3 * dpr);
          ctx.fill();
          ctx.stroke();

          ctx.fillStyle = TOOLTIP_TEXT;
          ctx.fillText(label, tx + 6 * dpr, ty + 13 * dpr);
          ctx.restore();
        }
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    // -----------------------------------------------------------------------
    // Draw static background, grid, labels
    // -----------------------------------------------------------------------
    function drawBackground(
      c: CanvasRenderingContext2D,
      totalW: number,
      totalH: number,
      pW: number,
      pH: number,
    ) {
      // Clear
      c.fillStyle = BG_COLOR;
      c.fillRect(0, 0, totalW, totalH);

      c.save();
      c.strokeStyle = GRID_COLOR;
      c.lineWidth = 1;

      // --- Horizontal dB grid lines (every 6 dB) ---
      c.setLineDash([]);
      c.font = `${9 * dpr}px "JetBrains Mono", ui-monospace, monospace`;
      c.fillStyle = GRID_LABEL_COLOR;
      c.textAlign = 'right';
      c.textBaseline = 'middle';

      for (let db = DB_MAX; db >= DB_MIN; db -= 6) {
        const yNorm = dbToY(db);
        const screenY = MARGIN_TOP + yNorm * pH;

        c.beginPath();
        c.moveTo(MARGIN_LEFT, screenY);
        c.lineTo(MARGIN_LEFT + pW, screenY);
        c.stroke();

        // Label only at -90, -72, -54, -36, -18, 0
        if (db % 18 === 0) {
          c.fillText(`${db}`, MARGIN_LEFT - 4 * dpr, screenY);
        }
      }

      // --- Vertical frequency grid lines ---
      c.textAlign = 'center';
      c.textBaseline = 'top';

      for (const { freq, label } of FREQ_LABELS) {
        const xNorm = freqToX(freq);
        const screenX = MARGIN_LEFT + xNorm * pW;

        c.strokeStyle = GRID_COLOR;
        c.beginPath();
        c.moveTo(screenX, MARGIN_TOP);
        c.lineTo(screenX, MARGIN_TOP + pH);
        c.stroke();

        c.fillStyle = GRID_LABEL_COLOR;
        c.fillText(label, screenX, MARGIN_TOP + pH + 3 * dpr);
      }

      c.restore();
    }

    // Start animation
    rafRef.current = requestAnimationFrame(draw);

    return () => {
      if (rafRef.current !== 0) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = 0;
      }
    };
  }, [canvasWidth, height, sampleRate, smoothing, showReference, mousePos, externalData]);

  // ---------------------------------------------------------------------------
  // Toolbar button style helper
  // ---------------------------------------------------------------------------
  const btnClass = (active: boolean): string =>
    active
      ? 'px-1.5 py-0.5 text-[10px] font-mono rounded bg-teal-900/50 text-teal-300 border border-teal-700/40'
      : 'px-1.5 py-0.5 text-[10px] font-mono rounded text-neutral-500 hover:text-neutral-300 border border-transparent hover:border-neutral-700/40';

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="relative flex flex-col" ref={containerRef}>
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-2 py-1 bg-[#0a0e0a] border-b border-neutral-800/40 select-none">
        {/* Smoothing selector */}
        <span className="text-[9px] font-mono text-neutral-600 uppercase tracking-wider mr-0.5">
          Smooth
        </span>
        {(['fast', 'medium', 'slow'] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            className={btnClass(smoothing === mode)}
            onClick={() => setSmoothing(mode)}
          >
            {mode.toUpperCase()}
          </button>
        ))}

        <span className="w-px h-3 bg-neutral-800" />

        {/* FFT size selector */}
        <span className="text-[9px] font-mono text-neutral-600 uppercase tracking-wider mr-0.5">
          FFT
        </span>
        {([2048, 4096, 8192] as const).map((size) => (
          <button
            key={size}
            type="button"
            className={btnClass(fftSize === size)}
            onClick={() => setFftSize(size)}
          >
            {size}
          </button>
        ))}

        <span className="w-px h-3 bg-neutral-800" />

        {/* Pink noise reference toggle */}
        <button
          type="button"
          className={btnClass(showReference)}
          onClick={() => setShowReference((prev) => !prev)}
        >
          PINK REF
        </button>
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        className="w-full cursor-crosshair"
        style={{ height, minHeight: 200, background: BG_COLOR }}
      />
    </div>
  );
}
