import { useState, useCallback, type ReactNode } from 'react'
import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from './ResizablePanel'

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

interface PanelLayoutProps {
  /** Fixed top transport bar (TransportBar) */
  transportBar: ReactNode
  /** Left sidebar (already exists, fixed width managed by Sidebar itself) */
  sidebar: ReactNode
  /** Waveform / timeline / spectrum visualization area */
  waveformArea: ReactNode
  /** Controls region: macros, signal chain, metadata tabs */
  controlsArea: ReactNode
  /** Metering panel on the right */
  meteringPanel: ReactNode
  /** Status footer */
  statusFooter: ReactNode
}

const METERING_STORAGE_KEY = 'rain-metering-collapsed'

function loadMeteringCollapsed(): boolean {
  try {
    return localStorage.getItem(METERING_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function saveMeteringCollapsed(collapsed: boolean): void {
  try {
    localStorage.setItem(METERING_STORAGE_KEY, String(collapsed))
  } catch {
    // silent
  }
}

// ─────────────────────────────────────────────
// PanelLayout
// ─────────────────────────────────────────────

export function PanelLayout({
  transportBar,
  sidebar,
  waveformArea,
  controlsArea,
  meteringPanel,
  statusFooter,
}: PanelLayoutProps) {
  const [meteringCollapsed, setMeteringCollapsed] = useState(loadMeteringCollapsed)

  const toggleMetering = useCallback(() => {
    setMeteringCollapsed((prev) => {
      const next = !prev
      saveMeteringCollapsed(next)
      return next
    })
  }, [])

  return (
    <div className="flex flex-col h-screen bg-rain-black overflow-hidden">
      {/* ── Transport Bar (fixed height ~56px) ── */}
      <div className="shrink-0">{transportBar}</div>

      {/* ── Main workspace area ── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* ── Left: Sidebar (fixed, managed by Sidebar component) ── */}
        <div className="shrink-0 h-full">{sidebar}</div>

        {/* ── Center + Right: Resizable horizontal split ── */}
        <div className="flex-1 flex min-w-0 h-full">
          {meteringCollapsed ? (
            // When metering is collapsed, center takes full width
            <div className="flex-1 flex flex-col min-w-0 h-full">
              <CenterContent
                waveformArea={waveformArea}
                controlsArea={controlsArea}
              />
            </div>
          ) : (
            // Horizontal split: center | handle | metering
            <ResizablePanelGroup
              direction="horizontal"
              groupId="rain-main-horizontal"
              className="flex-1 h-full"
            >
              {/* Center panel: vertical split of waveform + controls */}
              <ResizablePanel
                id="center"
                defaultSize={78}
                minSize={40}
                maxSize={92}
                className="h-full"
              >
                <CenterContent
                  waveformArea={waveformArea}
                  controlsArea={controlsArea}
                />
              </ResizablePanel>

              <ResizableHandle index={0} />

              {/* Right: Metering panel (~280px default via 22%) */}
              <ResizablePanel
                id="metering"
                defaultSize={22}
                minSize={8}
                maxSize={40}
                className="h-full"
              >
                <div className="h-full overflow-y-auto bg-rain-dark/60 border-l border-rain-border/20">
                  {meteringPanel}
                </div>
              </ResizablePanel>
            </ResizablePanelGroup>
          )}

          {/* Metering collapse/expand toggle */}
          <button
            onClick={toggleMetering}
            className="shrink-0 w-6 h-full flex items-center justify-center bg-rain-dark/40 border-l border-rain-border/20 text-rain-dim hover:text-rain-teal hover:bg-rain-surface/40 transition-colors"
            title={meteringCollapsed ? 'Show metering panel' : 'Hide metering panel'}
            aria-label={meteringCollapsed ? 'Show metering panel' : 'Hide metering panel'}
          >
            {meteringCollapsed ? (
              <PanelRightOpen size={12} />
            ) : (
              <PanelRightClose size={12} />
            )}
          </button>
        </div>
      </div>

      {/* ── Status Footer (fixed height) ── */}
      <div className="shrink-0">{statusFooter}</div>
    </div>
  )
}

// ─────────────────────────────────────────────
// CenterContent — vertical split
// ─────────────────────────────────────────────

interface CenterContentProps {
  waveformArea: ReactNode
  controlsArea: ReactNode
}

function CenterContent({ waveformArea, controlsArea }: CenterContentProps) {
  return (
    <ResizablePanelGroup
      direction="vertical"
      groupId="rain-center-vertical"
      className="h-full w-full"
    >
      {/* Top: Waveform / Spectrum (resizable height) */}
      <ResizablePanel
        id="waveform"
        defaultSize={45}
        minSize={20}
        maxSize={80}
        className="w-full"
      >
        <div className="h-full overflow-hidden bg-rain-bg/40">
          {waveformArea}
        </div>
      </ResizablePanel>

      <ResizableHandle index={0} />

      {/* Bottom: Controls (macros, signal chain, metadata) */}
      <ResizablePanel
        id="controls"
        defaultSize={55}
        minSize={20}
        maxSize={80}
        className="w-full"
      >
        <div className="h-full overflow-auto">
          {controlsArea}
        </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  )
}
