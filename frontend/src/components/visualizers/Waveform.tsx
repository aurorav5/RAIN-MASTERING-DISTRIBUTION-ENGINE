import { useEffect, useRef, useCallback, useState } from 'react';
import { useAudioStore } from '@/stores/audioStore';
import { audioEngine } from '@/audio/AudioEngine';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Props {
  /** Minimum height in pixels. The component is vertically flexible. */
  height?: number;
  /** Optional AudioBuffer override. If not provided, reads from audioEngine. */
  audioBuffer?: AudioBuffer | null;
}

/** Display mode for dual-channel rendering. */
type ChannelDisplayMode = 'stacked' | 'mirrored';

interface SelectionRange {
  /** Start time in seconds. */
  start: number;
  /** End time in seconds. */
  end: number;
}

/** Pre-computed per-channel waveform data for efficient rendering. */
interface ChannelPeaks {
  /** Per-bucket peak max (positive). */
  peakMax: Float32Array;
  /** Per-bucket peak min (negative). */
  peakMin: Float32Array;
  /** Per-bucket RMS value. */
  rms: Float32Array;
}

interface WaveformData {
  left: ChannelPeaks;
  right: ChannelPeaks | null;
  duration: number;
  sampleRate: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BG_COLOR = '#080C08';
const GRID_COLOR = '#1A1A1A';
const CENTER_LINE_COLOR = '#2A2A2A';
const CURSOR_COLOR = '#00FF88';
const SELECTION_COLOR = 'rgba(0, 255, 136, 0.12)';
const SELECTION_BORDER_COLOR = 'rgba(0, 255, 136, 0.4)';
const LABEL_COLOR = '#606060';
const RULER_BG = '#0A0E0A';
const RULER_TEXT_COLOR = '#707070';
const RULER_TICK_COLOR = '#2A2A2A';

const FONT_MONO = '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace';
const LABEL_FONT = `9px ${FONT_MONO}`;
const RULER_FONT = `9px ${FONT_MONO}`;

/** Left margin for dB scale labels. */
const DB_SCALE_WIDTH = 36;
/** Top margin for time ruler. */
const RULER_HEIGHT = 20;
/** Minimum pixels per second before zoom stops. */
const MIN_PX_PER_SEC = 2;
/** Maximum pixels per second (extreme zoom). */
const MAX_PX_PER_SEC = 5000;
/** Number of waveform buckets to pre-compute at the highest resolution. */
const MAX_BUCKETS = 8192;
/** Zoom sensitivity per wheel tick. */
const ZOOM_FACTOR = 1.15;

/** dB scale tick marks to render. */
const DB_TICKS = [0, -3, -6, -12, -18, -24, -36, -48];

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

/** Returns waveform color based on amplitude in dBFS. */
function amplitudeColor(dbfs: number, alpha: number): string {
  if (dbfs > -3) return `rgba(255, 50, 50, ${alpha})`;       // Red: clipping
  if (dbfs > -6) return `rgba(255, 160, 40, ${alpha})`;      // Orange
  if (dbfs > -12) return `rgba(255, 220, 50, ${alpha})`;     // Yellow
  return `rgba(60, 200, 80, ${alpha})`;                       // Green: safe
}

/** Convert linear amplitude to dBFS. */
function linearToDbfs(linear: number): number {
  if (linear <= 0) return -Infinity;
  return 20 * Math.log10(linear);
}

// ---------------------------------------------------------------------------
// Waveform data computation
// ---------------------------------------------------------------------------

function computeChannelPeaks(
  channelData: Float32Array,
  numBuckets: number,
): ChannelPeaks {
  const length = channelData.length;
  const peakMax = new Float32Array(numBuckets);
  const peakMin = new Float32Array(numBuckets);
  const rms = new Float32Array(numBuckets);
  const samplesPerBucket = length / numBuckets;

  for (let i = 0; i < numBuckets; i++) {
    const start = Math.floor(i * samplesPerBucket);
    const end = Math.min(Math.floor((i + 1) * samplesPerBucket), length);
    const count = end - start;

    let max = -1;
    let min = 1;
    let sumSq = 0;

    for (let s = start; s < end; s++) {
      const sample = channelData[s] ?? 0;
      if (sample > max) max = sample;
      if (sample < min) min = sample;
      sumSq += sample * sample;
    }

    peakMax[i] = max;
    peakMin[i] = min;
    rms[i] = count > 0 ? Math.sqrt(sumSq / count) : 0;
  }

  return { peakMax, peakMin, rms };
}

function computeWaveformData(buffer: AudioBuffer): WaveformData {
  const numBuckets = Math.min(MAX_BUCKETS, buffer.length);
  const left = computeChannelPeaks(buffer.getChannelData(0), numBuckets);
  const right = buffer.numberOfChannels >= 2
    ? computeChannelPeaks(buffer.getChannelData(1), numBuckets)
    : null;

  return {
    left,
    right,
    duration: buffer.duration,
    sampleRate: buffer.sampleRate,
  };
}

// ---------------------------------------------------------------------------
// Time formatting
// ---------------------------------------------------------------------------

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds - mins * 60;
  const wholeSeconds = Math.floor(secs);
  return `${String(mins).padStart(2, '0')}:${String(wholeSeconds).padStart(2, '0')}`;
}

function formatTimePrecise(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds - mins * 60;
  const wholeSeconds = Math.floor(secs);
  const ms = Math.floor((secs - wholeSeconds) * 100);
  return `${String(mins).padStart(2, '0')}:${String(wholeSeconds).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
}

// ---------------------------------------------------------------------------
// Choose ruler tick interval based on zoom level
// ---------------------------------------------------------------------------

function chooseTickInterval(pxPerSec: number): { major: number; minor: number } {
  // Snap to nice intervals in seconds.
  const candidates = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
  let major = 1;
  for (const c of candidates) {
    major = c;
    if (c * pxPerSec >= 60) break;
  }

  const minor = major / 4;
  return { major, minor };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Waveform({ height = 200, audioBuffer }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // State from store (subscriptions are granular via selectors).
  const playbackPosition = useAudioStore((s) => s.playbackPosition);
  const isPlaying = useAudioStore((s) => s.isPlaying);
  const storePeaks = useAudioStore((s) => s.waveformPeaks);

  // Local state
  const [channelMode, setChannelMode] = useState<ChannelDisplayMode>('stacked');
  const [selection, setSelection] = useState<SelectionRange | null>(null);

  // Refs for mutable state that shouldn't trigger re-renders.
  const waveformDataRef = useRef<WaveformData | null>(null);
  const zoomRef = useRef<number>(1); // pxPerSec, computed on first render
  const scrollOffsetRef = useRef<number>(0); // scroll offset in seconds
  const isDraggingRef = useRef<boolean>(false);
  const dragStartTimeRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);
  const canvasSizeRef = useRef<{ width: number; height: number }>({ width: 0, height: 0 });
  const isPlayingRef = useRef<boolean>(false);
  const playbackPosRef = useRef<number>(0);

  // Keep refs in sync with React state.
  isPlayingRef.current = isPlaying;
  playbackPosRef.current = playbackPosition;

  // Compute waveform data when buffer changes.
  const resolvedBuffer = audioBuffer ?? audioEngine.buffer;

  useEffect(() => {
    if (resolvedBuffer) {
      waveformDataRef.current = computeWaveformData(resolvedBuffer);
      // Initialize zoom to fit entire waveform.
      const canvas = canvasRef.current;
      if (canvas) {
        const drawWidth = canvas.width - DB_SCALE_WIDTH;
        const dur = resolvedBuffer.duration;
        if (dur > 0 && drawWidth > 0) {
          zoomRef.current = drawWidth / dur;
          scrollOffsetRef.current = 0;
        }
      }
    } else {
      waveformDataRef.current = null;
    }
  }, [resolvedBuffer]);

  // ------------------------------------------------------------------
  // Canvas rendering
  // ------------------------------------------------------------------

  const drawFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const data = waveformDataRef.current;
    const pxPerSec = zoomRef.current;
    const scrollSec = scrollOffsetRef.current;
    const position = playbackPosRef.current;
    const sel = selection;

    // -- Background --
    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, W, H);

    // Drawing area.
    const drawX = DB_SCALE_WIDTH;
    const drawW = W - DB_SCALE_WIDTH;
    const drawY = RULER_HEIGHT;
    const drawH = H - RULER_HEIGHT;

    if (drawW <= 0 || drawH <= 0) return;

    // -- Time ruler background --
    ctx.fillStyle = RULER_BG;
    ctx.fillRect(drawX, 0, drawW, RULER_HEIGHT);

    // -- dB scale background --
    ctx.fillStyle = RULER_BG;
    ctx.fillRect(0, 0, DB_SCALE_WIDTH, H);

    const duration = data?.duration ?? 0;

    // Helper: time -> canvas x
    const timeToX = (t: number): number => {
      return drawX + (t - scrollSec) * pxPerSec;
    };

    // Visible time range.
    const visStart = scrollSec;
    const visEnd = scrollSec + drawW / pxPerSec;

    // -- Time ruler ticks and labels --
    const { major, minor } = chooseTickInterval(pxPerSec);
    ctx.font = RULER_FONT;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';

    // Minor ticks
    const minorStart = Math.floor(visStart / minor) * minor;
    ctx.strokeStyle = RULER_TICK_COLOR;
    ctx.lineWidth = 1;
    for (let t = minorStart; t <= visEnd; t += minor) {
      if (t < 0) continue;
      const x = Math.round(timeToX(t)) + 0.5;
      if (x < drawX || x > W) continue;
      ctx.beginPath();
      ctx.moveTo(x, RULER_HEIGHT - 4);
      ctx.lineTo(x, RULER_HEIGHT);
      ctx.stroke();
    }

    // Major ticks + labels
    const majorStart = Math.floor(visStart / major) * major;
    for (let t = majorStart; t <= visEnd; t += major) {
      if (t < 0) continue;
      const x = Math.round(timeToX(t)) + 0.5;
      if (x < drawX || x > W) continue;

      ctx.strokeStyle = RULER_TICK_COLOR;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, RULER_HEIGHT - 8);
      ctx.lineTo(x, RULER_HEIGHT);
      ctx.stroke();

      // Vertical grid line in waveform area.
      ctx.strokeStyle = GRID_COLOR;
      ctx.beginPath();
      ctx.moveTo(x, drawY);
      ctx.lineTo(x, H);
      ctx.stroke();

      ctx.fillStyle = RULER_TEXT_COLOR;
      ctx.fillText(formatTime(t), x, RULER_HEIGHT - 9);
    }

    // -- dB scale and horizontal grid lines --
    const hasDualChannel = data !== null && data.right !== null;
    const isMirrored = channelMode === 'mirrored';

    ctx.font = LABEL_FONT;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

    /** Draw dB grid lines for a channel area. */
    function drawDbGrid(
      areaTop: number,
      areaHeight: number,
      drawContext: CanvasRenderingContext2D,
    ): void {
      const centerY = areaTop + areaHeight / 2;
      const halfH = areaHeight / 2;

      for (const db of DB_TICKS) {
        const linear = db === 0 ? 1.0 : Math.pow(10, db / 20);
        const yUp = centerY - linear * halfH;
        const yDown = centerY + linear * halfH;

        // Grid lines (both sides of center).
        drawContext.strokeStyle = GRID_COLOR;
        drawContext.lineWidth = 1;

        if (yUp >= areaTop && yUp <= areaTop + areaHeight) {
          drawContext.beginPath();
          drawContext.moveTo(drawX, Math.round(yUp) + 0.5);
          drawContext.lineTo(W, Math.round(yUp) + 0.5);
          drawContext.stroke();
        }
        if (db !== 0 && yDown >= areaTop && yDown <= areaTop + areaHeight) {
          drawContext.beginPath();
          drawContext.moveTo(drawX, Math.round(yDown) + 0.5);
          drawContext.lineTo(W, Math.round(yDown) + 0.5);
          drawContext.stroke();
        }

        // Label on left.
        if (yUp >= areaTop && yUp <= areaTop + areaHeight) {
          drawContext.fillStyle = LABEL_COLOR;
          const label = db === 0 ? ' 0' : `${db}`;
          drawContext.fillText(label, DB_SCALE_WIDTH - 4, yUp);
        }
      }

      // Center line.
      drawContext.strokeStyle = CENTER_LINE_COLOR;
      drawContext.lineWidth = 1;
      drawContext.beginPath();
      drawContext.moveTo(drawX, Math.round(centerY) + 0.5);
      drawContext.lineTo(W, Math.round(centerY) + 0.5);
      drawContext.stroke();
    }

    /** Draw waveform for a channel. */
    function drawChannel(
      peaks: ChannelPeaks,
      areaTop: number,
      areaHeight: number,
      drawContext: CanvasRenderingContext2D,
      totalBuckets: number,
      channelDuration: number,
      mirrored: boolean,
      isLower: boolean,
    ): void {
      const centerY = areaTop + areaHeight / 2;
      const halfH = areaHeight / 2;

      // Determine which buckets are visible.
      const bucketDuration = channelDuration / totalBuckets;
      const firstBucket = Math.max(0, Math.floor(visStart / bucketDuration));
      const lastBucket = Math.min(totalBuckets - 1, Math.ceil(visEnd / bucketDuration));

      // --- Peak waveform ---
      for (let i = firstBucket; i <= lastBucket; i++) {
        const bucketTime = i * bucketDuration;
        const x1 = timeToX(bucketTime);
        const x2 = timeToX(bucketTime + bucketDuration);
        const xPos = Math.round(x1);
        const barWidth = Math.max(1, Math.round(x2 - x1));

        if (xPos + barWidth < drawX || xPos > W) continue;

        const pMax = peaks.peakMax[i] ?? 0;
        const pMin = peaks.peakMin[i] ?? 0;

        // Color based on max absolute amplitude.
        const absMax = Math.max(Math.abs(pMax), Math.abs(pMin));
        const dbfs = linearToDbfs(absMax);
        const color = amplitudeColor(dbfs, 0.85);

        let y1: number;
        let y2: number;

        if (mirrored && isLower) {
          // Lower mirrored channel: flip so it mirrors the upper.
          y1 = centerY;
          y2 = centerY + absMax * halfH;
        } else {
          y1 = centerY - pMax * halfH;
          y2 = centerY - pMin * halfH;
        }

        drawContext.fillStyle = color;
        const top = Math.min(y1, y2);
        const barH = Math.max(1, Math.abs(y2 - y1));
        drawContext.fillRect(xPos, top, barWidth, barH);
      }

      // --- RMS overlay ---
      for (let i = firstBucket; i <= lastBucket; i++) {
        const bucketTime = i * bucketDuration;
        const x1 = timeToX(bucketTime);
        const x2 = timeToX(bucketTime + bucketDuration);
        const xPos = Math.round(x1);
        const barWidth = Math.max(1, Math.round(x2 - x1));

        if (xPos + barWidth < drawX || xPos > W) continue;

        const rmsVal = peaks.rms[i] ?? 0;
        if (rmsVal <= 0) continue;

        const dbfs = linearToDbfs(rmsVal);
        const rmsColor = amplitudeColor(dbfs, 0.45);

        let y1: number;
        let y2: number;

        if (mirrored && isLower) {
          y1 = centerY;
          y2 = centerY + rmsVal * halfH;
        } else {
          y1 = centerY - rmsVal * halfH;
          y2 = centerY + rmsVal * halfH;
        }

        drawContext.fillStyle = rmsColor;
        const top = Math.min(y1, y2);
        const barH = Math.max(1, Math.abs(y2 - y1));
        drawContext.fillRect(xPos, top, barWidth, barH);
      }
    }

    // --- Render channels ---
    if (data !== null) {
      const totalBuckets = data.left.peakMax.length;

      if (hasDualChannel && !isMirrored) {
        // Stacked: L top half, R bottom half.
        const chHeight = drawH / 2;
        const lTop = drawY;
        const rTop = drawY + chHeight;

        drawDbGrid(lTop, chHeight, ctx);
        drawDbGrid(rTop, chHeight, ctx);

        // Channel labels.
        ctx.font = LABEL_FONT;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillStyle = '#505050';
        ctx.fillText('L', drawX + 4, lTop + 2);
        ctx.fillText('R', drawX + 4, rTop + 2);

        // Separator line.
        ctx.strokeStyle = '#1E1E1E';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(drawX, Math.round(rTop) + 0.5);
        ctx.lineTo(W, Math.round(rTop) + 0.5);
        ctx.stroke();

        drawChannel(data.left, lTop, chHeight, ctx, totalBuckets, data.duration, false, false);
        if (data.right) {
          drawChannel(data.right, rTop, chHeight, ctx, totalBuckets, data.duration, false, false);
        }
      } else if (hasDualChannel && isMirrored) {
        // Mirrored: L above center, R below center.
        drawDbGrid(drawY, drawH, ctx);

        ctx.font = LABEL_FONT;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillStyle = '#505050';
        ctx.fillText('L', drawX + 4, drawY + 2);
        ctx.fillText('R', drawX + 4, drawY + drawH - 12);

        drawChannel(data.left, drawY, drawH, ctx, totalBuckets, data.duration, true, false);
        if (data.right) {
          drawChannel(data.right, drawY, drawH, ctx, totalBuckets, data.duration, true, true);
        }
      } else {
        // Mono or single-channel fallback.
        drawDbGrid(drawY, drawH, ctx);
        drawChannel(data.left, drawY, drawH, ctx, totalBuckets, data.duration, false, false);
      }
    } else if (storePeaks !== null && storePeaks.length > 0) {
      // Fallback: use mono peaks from store (absolute values only, no min/max).
      drawDbGrid(drawY, drawH, ctx);

      const totalBuckets = storePeaks.length;
      const bucketDuration = duration > 0 ? duration / totalBuckets : 1 / totalBuckets;
      const centerY = drawY + drawH / 2;
      const halfH = drawH / 2;

      const firstBucket = Math.max(0, Math.floor(visStart / bucketDuration));
      const lastBucket = Math.min(totalBuckets - 1, Math.ceil(visEnd / bucketDuration));

      for (let i = firstBucket; i <= lastBucket; i++) {
        const bucketTime = i * bucketDuration;
        const x1 = timeToX(bucketTime);
        const x2 = timeToX(bucketTime + bucketDuration);
        const xPos = Math.round(x1);
        const barWidth = Math.max(1, Math.round(x2 - x1));

        if (xPos + barWidth < drawX || xPos > W) continue;

        const absVal = storePeaks[i] ?? 0;
        const dbfs = linearToDbfs(absVal);
        const color = amplitudeColor(dbfs, 0.85);

        const yTop = centerY - absVal * halfH;
        const yBot = centerY + absVal * halfH;

        ctx.fillStyle = color;
        ctx.fillRect(xPos, yTop, barWidth, Math.max(1, yBot - yTop));
      }
    }

    // -- Selection region --
    if (sel !== null) {
      const selX1 = Math.max(drawX, timeToX(sel.start));
      const selX2 = Math.min(W, timeToX(sel.end));
      if (selX2 > selX1) {
        ctx.fillStyle = SELECTION_COLOR;
        ctx.fillRect(selX1, drawY, selX2 - selX1, drawH);

        ctx.strokeStyle = SELECTION_BORDER_COLOR;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(Math.round(selX1) + 0.5, drawY);
        ctx.lineTo(Math.round(selX1) + 0.5, H);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(Math.round(selX2) + 0.5, drawY);
        ctx.lineTo(Math.round(selX2) + 0.5, H);
        ctx.stroke();
      }
    }

    // -- Playback cursor --
    if (duration > 0 && position >= 0) {
      const cursorX = timeToX(position);
      if (cursorX >= drawX && cursorX <= W) {
        ctx.strokeStyle = CURSOR_COLOR;
        ctx.lineWidth = 1.5;
        ctx.shadowColor = 'rgba(0, 255, 136, 0.5)';
        ctx.shadowBlur = 6;
        ctx.beginPath();
        ctx.moveTo(Math.round(cursorX) + 0.5, 0);
        ctx.lineTo(Math.round(cursorX) + 0.5, H);
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Cursor time label.
        ctx.font = RULER_FONT;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillStyle = CURSOR_COLOR;
        ctx.fillText(formatTimePrecise(position), Math.round(cursorX), RULER_HEIGHT - 1);
      }
    }

    // -- Border for dB scale / ruler corner --
    ctx.strokeStyle = '#1E1E1E';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(DB_SCALE_WIDTH + 0.5, 0);
    ctx.lineTo(DB_SCALE_WIDTH + 0.5, H);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, RULER_HEIGHT + 0.5);
    ctx.lineTo(W, RULER_HEIGHT + 0.5);
    ctx.stroke();
  }, [selection, channelMode, storePeaks]);

  // ------------------------------------------------------------------
  // Animation loop
  // ------------------------------------------------------------------

  const animationLoop = useCallback(() => {
    drawFrame();
    rafIdRef.current = requestAnimationFrame(animationLoop);
  }, [drawFrame]);

  // Start/stop animation loop.
  useEffect(() => {
    rafIdRef.current = requestAnimationFrame(animationLoop);
    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, [animationLoop]);

  // ------------------------------------------------------------------
  // Canvas sizing (handles DPR and resize)
  // ------------------------------------------------------------------

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: cssW, height: cssH } = entry.contentRect;
        const dpr = window.devicePixelRatio || 1;
        const newW = Math.round(cssW * dpr);
        const newH = Math.round(cssH * dpr);

        if (canvas.width !== newW || canvas.height !== newH) {
          canvas.width = newW;
          canvas.height = newH;
          canvasSizeRef.current = { width: newW, height: newH };

          // Re-initialize zoom to fit if we haven't zoomed yet.
          const data = waveformDataRef.current;
          if (data && data.duration > 0) {
            const drawWidth = newW - DB_SCALE_WIDTH;
            const fitZoom = drawWidth / data.duration;
            // Only reset zoom if it was at the default fit level.
            if (zoomRef.current <= fitZoom * 1.01) {
              zoomRef.current = fitZoom;
              scrollOffsetRef.current = 0;
            }
          }
        }
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // ------------------------------------------------------------------
  // Mouse event handlers
  // ------------------------------------------------------------------

  const getTimeFromMouseEvent = useCallback((e: React.MouseEvent<HTMLCanvasElement>): number => {
    const canvas = canvasRef.current;
    if (!canvas) return 0;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const canvasX = (e.clientX - rect.left) * dpr;
    const pxPerSec = zoomRef.current;
    const scrollSec = scrollOffsetRef.current;
    return scrollSec + (canvasX - DB_SCALE_WIDTH) / pxPerSec;
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const mouseCanvasX = (e.clientX - rect.left) * dpr;
    const drawW = canvas.width - DB_SCALE_WIDTH;

    // Time at mouse position (before zoom).
    const mouseRelX = mouseCanvasX - DB_SCALE_WIDTH;
    const mouseTime = scrollOffsetRef.current + mouseRelX / zoomRef.current;

    // Apply zoom.
    const delta = e.deltaY;
    let newZoom: number;
    if (delta < 0) {
      newZoom = zoomRef.current * ZOOM_FACTOR;
    } else {
      newZoom = zoomRef.current / ZOOM_FACTOR;
    }

    // Clamp zoom.
    newZoom = Math.max(MIN_PX_PER_SEC, Math.min(MAX_PX_PER_SEC, newZoom));
    zoomRef.current = newZoom;

    // Adjust scroll so time at mouse position stays under the cursor.
    scrollOffsetRef.current = mouseTime - mouseRelX / newZoom;

    // Clamp scroll.
    const data = waveformDataRef.current;
    const dur = data?.duration ?? audioEngine.duration;
    const maxScroll = Math.max(0, dur - drawW / newZoom);
    scrollOffsetRef.current = Math.max(0, Math.min(scrollOffsetRef.current, maxScroll));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const canvasX = (e.clientX - rect.left) * dpr;

    // Ignore clicks in ruler or dB scale area.
    if (canvasX < DB_SCALE_WIDTH) return;

    const time = getTimeFromMouseEvent(e);
    const data = waveformDataRef.current;
    const dur = data?.duration ?? audioEngine.duration;
    const clampedTime = Math.max(0, Math.min(time, dur));

    if (e.shiftKey) {
      // Shift+click starts selection.
      isDraggingRef.current = true;
      dragStartTimeRef.current = clampedTime;
      setSelection({ start: clampedTime, end: clampedTime });
    } else {
      // Normal click: seek.
      isDraggingRef.current = false;
      setSelection(null);
      audioEngine.seekTo(clampedTime);
    }
  }, [getTimeFromMouseEvent]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return;

    const time = getTimeFromMouseEvent(e);
    const data = waveformDataRef.current;
    const dur = data?.duration ?? audioEngine.duration;
    const clampedTime = Math.max(0, Math.min(time, dur));
    const start = dragStartTimeRef.current;

    setSelection({
      start: Math.min(start, clampedTime),
      end: Math.max(start, clampedTime),
    });
  }, [getTimeFromMouseEvent]);

  const handleMouseUp = useCallback(() => {
    isDraggingRef.current = false;
  }, []);

  // ------------------------------------------------------------------
  // Channel mode toggle
  // ------------------------------------------------------------------

  const toggleChannelMode = useCallback(() => {
    setChannelMode((prev) => (prev === 'stacked' ? 'mirrored' : 'stacked'));
  }, []);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div
      ref={containerRef}
      className="relative w-full select-none"
      style={{ minHeight: height, height }}
    >
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full rounded-md"
        style={{ cursor: 'crosshair' }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />
      {/* Channel mode toggle button */}
      <button
        type="button"
        onClick={toggleChannelMode}
        className="absolute top-0.5 right-1 z-10 px-1.5 py-0.5 text-[9px] font-mono
                   text-[#606060] hover:text-[#909090] bg-[#0A0E0A]/80 rounded
                   border border-[#1E1E1E] hover:border-[#2A2A2A] transition-colors"
        title={channelMode === 'stacked' ? 'Switch to mirrored view' : 'Switch to stacked view'}
      >
        {channelMode === 'stacked' ? 'STACKED' : 'MIRROR'}
      </button>
    </div>
  );
}
