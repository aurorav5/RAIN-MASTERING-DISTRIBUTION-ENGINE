import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react'

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type Direction = 'horizontal' | 'vertical'

interface PanelConfig {
  id: string
  defaultSize: number  // percentage of group
  minSize: number      // percentage minimum
  maxSize: number      // percentage maximum
}

interface PanelGroupContextValue {
  direction: Direction
  groupId: string
  registerPanel: (config: PanelConfig) => void
  unregisterPanel: (id: string) => void
  getPanelSize: (id: string) => number
  startResize: (handleIndex: number, event: ReactMouseEvent) => void
  resetToDefaults: () => void
}

const PanelGroupContext = createContext<PanelGroupContextValue | null>(null)

function usePanelGroup(): PanelGroupContextValue {
  const ctx = useContext(PanelGroupContext)
  if (!ctx) {
    throw new Error('ResizablePanel must be used within a ResizablePanelGroup')
  }
  return ctx
}

// ─────────────────────────────────────────────
// localStorage helpers
// ─────────────────────────────────────────────

const STORAGE_PREFIX = 'rain-panel-sizes-'

function loadSizes(groupId: string): Record<string, number> | null {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + groupId)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, number>
    }
    return null
  } catch {
    return null
  }
}

function saveSizes(groupId: string, sizes: Record<string, number>): void {
  try {
    localStorage.setItem(STORAGE_PREFIX + groupId, JSON.stringify(sizes))
  } catch {
    // storage unavailable — silent fail
  }
}

// ─────────────────────────────────────────────
// ResizablePanelGroup
// ─────────────────────────────────────────────

interface ResizablePanelGroupProps {
  direction: Direction
  groupId: string
  children: ReactNode
  className?: string
  style?: CSSProperties
}

export function ResizablePanelGroup({
  direction,
  groupId,
  children,
  className = '',
  style,
}: ResizablePanelGroupProps) {
  const panelsRef = useRef<Map<string, PanelConfig>>(new Map())
  const panelOrderRef = useRef<string[]>([])
  const [sizes, setSizes] = useState<Record<string, number>>({})
  const containerRef = useRef<HTMLDivElement>(null)
  const resizingRef = useRef<{
    handleIndex: number
    startPos: number
    startSizes: Record<string, number>
    panelIds: [string, string]
  } | null>(null)

  // Build ordered panel list from registration order
  const getOrderedPanelIds = useCallback((): string[] => {
    return panelOrderRef.current.filter((id) => panelsRef.current.has(id))
  }, [])

  const registerPanel = useCallback((config: PanelConfig) => {
    panelsRef.current.set(config.id, config)
    if (!panelOrderRef.current.includes(config.id)) {
      panelOrderRef.current.push(config.id)
    }

    // Initialize sizes from localStorage or defaults
    setSizes((prev) => {
      const stored = loadSizes(groupId)
      const storedSize = stored?.[config.id]
      const size = storedSize !== undefined ? storedSize : config.defaultSize
      return { ...prev, [config.id]: size }
    })
  }, [groupId])

  const unregisterPanel = useCallback((id: string) => {
    panelsRef.current.delete(id)
    panelOrderRef.current = panelOrderRef.current.filter((pid) => pid !== id)
    setSizes((prev) => {
      const next = { ...prev }
      delete next[id]
      return next
    })
  }, [])

  const getPanelSize = useCallback((id: string): number => {
    return sizes[id] ?? 50
  }, [sizes])

  const clampSize = useCallback((id: string, size: number): number => {
    const config = panelsRef.current.get(id)
    if (!config) return size
    return Math.min(config.maxSize, Math.max(config.minSize, size))
  }, [])

  // Reset all panels in this group to their registered default sizes
  const resetToDefaults = useCallback(() => {
    const defaults: Record<string, number> = {}
    for (const [id, config] of panelsRef.current.entries()) {
      defaults[id] = config.defaultSize
    }
    setSizes(defaults)
    try {
      localStorage.removeItem(STORAGE_PREFIX + groupId)
    } catch {
      // silent
    }
  }, [groupId])

  // Apply a delta (in percentage points) between two adjacent panels
  const applyDelta = useCallback(
    (
      idBefore: string,
      idAfter: string,
      baseBefore: number,
      baseAfter: number,
      deltaPct: number,
    ) => {
      let newBefore = baseBefore + deltaPct
      let newAfter = baseAfter - deltaPct

      // Clamp the "before" panel first, then adjust "after" to compensate
      const clampedBefore = clampSize(idBefore, newBefore)
      const adjustment = clampedBefore - newBefore
      newBefore = clampedBefore
      newAfter = newAfter - adjustment

      // Now clamp the "after" panel, and adjust "before" to compensate
      const clampedAfter = clampSize(idAfter, newAfter)
      const adjustment2 = clampedAfter - newAfter
      newAfter = clampedAfter
      newBefore = newBefore - adjustment2

      // Final validation: both must still be within bounds
      const finalBefore = clampSize(idBefore, newBefore)
      const finalAfter = clampSize(idAfter, newAfter)

      setSizes((prev) => ({
        ...prev,
        [idBefore]: finalBefore,
        [idAfter]: finalAfter,
      }))
    },
    [clampSize],
  )

  const startResize = useCallback((handleIndex: number, event: ReactMouseEvent) => {
    event.preventDefault()
    const ordered = getOrderedPanelIds()
    if (handleIndex < 0 || handleIndex >= ordered.length - 1) return

    const panelBefore = ordered[handleIndex]
    const panelAfter = ordered[handleIndex + 1]
    if (!panelBefore || !panelAfter) return

    const startPos = direction === 'horizontal' ? event.clientX : event.clientY

    resizingRef.current = {
      handleIndex,
      startPos,
      startSizes: { ...sizes },
      panelIds: [panelBefore, panelAfter],
    }

    // Set cursor on body during drag
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
  }, [direction, sizes, getOrderedPanelIds])

  // Global mouse move/up handlers for drag
  useEffect(() => {
    const onMouseMove = (e: globalThis.MouseEvent) => {
      const state = resizingRef.current
      if (!state) return
      const container = containerRef.current
      if (!container) return

      const rect = container.getBoundingClientRect()
      const totalSize = direction === 'horizontal' ? rect.width : rect.height
      if (totalSize === 0) return

      const currentPos = direction === 'horizontal' ? e.clientX : e.clientY
      const deltaPx = currentPos - state.startPos
      const deltaPct = (deltaPx / totalSize) * 100

      const [idBefore, idAfter] = state.panelIds
      const baseBefore = state.startSizes[idBefore] ?? 50
      const baseAfter = state.startSizes[idAfter] ?? 50

      applyDelta(idBefore, idAfter, baseBefore, baseAfter, deltaPct)
    }

    const onMouseUp = () => {
      if (resizingRef.current) {
        resizingRef.current = null
        document.body.style.cursor = ''
        document.body.style.userSelect = ''

        // Persist to localStorage
        setSizes((current) => {
          saveSizes(groupId, current)
          return current
        })
      }
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [direction, groupId, applyDelta])

  const contextValue: PanelGroupContextValue = {
    direction,
    groupId,
    registerPanel,
    unregisterPanel,
    getPanelSize,
    startResize,
    resetToDefaults,
  }

  return (
    <PanelGroupContext.Provider value={contextValue}>
      <div
        ref={containerRef}
        className={`flex ${direction === 'horizontal' ? 'flex-row' : 'flex-col'} ${className}`}
        style={{ ...style, overflow: 'hidden' }}
      >
        {children}
      </div>
    </PanelGroupContext.Provider>
  )
}

// ─────────────────────────────────────────────
// ResizablePanel
// ─────────────────────────────────────────────

interface ResizablePanelProps {
  id: string
  defaultSize: number    // percentage
  minSize?: number       // percentage minimum (default 5)
  maxSize?: number       // percentage maximum (default 95)
  children: ReactNode
  className?: string
  style?: CSSProperties
}

export function ResizablePanel({
  id,
  defaultSize,
  minSize = 5,
  maxSize = 95,
  children,
  className = '',
  style,
}: ResizablePanelProps) {
  const { direction, registerPanel, unregisterPanel, getPanelSize } = usePanelGroup()

  useEffect(() => {
    registerPanel({ id, defaultSize, minSize, maxSize })
    return () => unregisterPanel(id)
    // Only register/unregister on mount/unmount. Config is static.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const size = getPanelSize(id)

  const panelStyle: CSSProperties = {
    ...style,
    flexShrink: 0,
    flexGrow: 0,
    overflow: 'hidden',
    ...(direction === 'horizontal'
      ? { flexBasis: `${size}%`, width: `${size}%` }
      : { flexBasis: `${size}%`, height: `${size}%` }),
  }

  return (
    <div className={`min-w-0 min-h-0 ${className}`} style={panelStyle}>
      {children}
    </div>
  )
}

// ─────────────────────────────────────────────
// ResizableHandle
// ─────────────────────────────────────────────

interface ResizableHandleProps {
  /** Zero-based index: handle between panel[index] and panel[index+1] */
  index: number
  className?: string
}

/** Keyboard step size in percentage points per keypress */
const KEYBOARD_STEP = 2

export function ResizableHandle({ index, className = '' }: ResizableHandleProps) {
  const { direction, startResize, resetToDefaults } = usePanelGroup()
  const isHorizontal = direction === 'horizontal'

  const handleDoubleClick = useCallback(() => {
    resetToDefaults()
  }, [resetToDefaults])

  const onMouseDown = useCallback(
    (e: ReactMouseEvent) => {
      startResize(index, e)
    },
    [index, startResize],
  )

  // Keyboard resizing: arrow keys move the handle
  const onKeyDown = useCallback(
    (e: ReactKeyboardEvent<HTMLDivElement>) => {
      const positiveKeys = isHorizontal
        ? ['ArrowRight', 'ArrowDown']
        : ['ArrowDown', 'ArrowRight']
      const negativeKeys = isHorizontal
        ? ['ArrowLeft', 'ArrowUp']
        : ['ArrowUp', 'ArrowLeft']

      if (positiveKeys.includes(e.key) || negativeKeys.includes(e.key)) {
        e.preventDefault()
        // Synthesize a mouse event at center of handle, offset by step pixels
        const target = e.currentTarget
        const rect = target.getBoundingClientRect()
        const centerX = rect.left + rect.width / 2
        const centerY = rect.top + rect.height / 2

        // Calculate step in pixels (approximate: 2% of parent)
        const parent = target.parentElement
        if (!parent) return
        const parentRect = parent.getBoundingClientRect()
        const totalSize = isHorizontal ? parentRect.width : parentRect.height
        const stepPx = (KEYBOARD_STEP / 100) * totalSize
        const sign = positiveKeys.includes(e.key) ? 1 : -1

        // Create synthetic mousedown at center, then mouseup at offset
        const syntheticDown = new MouseEvent('mousedown', {
          clientX: centerX,
          clientY: centerY,
          bubbles: true,
        }) as unknown as ReactMouseEvent
        // We need to use the context's startResize directly with a fake event
        // Instead, directly dispatch mouse events to trigger the global handler
        startResize(index, {
          ...syntheticDown,
          clientX: centerX,
          clientY: centerY,
          preventDefault: () => {},
        } as unknown as ReactMouseEvent)

        // Immediately dispatch a mousemove and mouseup to complete the gesture
        const offsetX = isHorizontal ? centerX + stepPx * sign : centerX
        const offsetY = isHorizontal ? centerY : centerY + stepPx * sign

        requestAnimationFrame(() => {
          window.dispatchEvent(
            new MouseEvent('mousemove', {
              clientX: offsetX,
              clientY: offsetY,
              bubbles: true,
            }),
          )
          requestAnimationFrame(() => {
            window.dispatchEvent(
              new MouseEvent('mouseup', { bubbles: true }),
            )
          })
        })
      }

      // Home key resets to defaults
      if (e.key === 'Home') {
        e.preventDefault()
        resetToDefaults()
      }
    },
    [isHorizontal, index, startResize, resetToDefaults],
  )

  return (
    <div
      className={[
        'relative flex items-center justify-center shrink-0',
        isHorizontal ? 'w-[5px] cursor-col-resize' : 'h-[5px] cursor-row-resize',
        'group/handle',
        'focus-visible:outline-none',
        className,
      ].join(' ')}
      onMouseDown={onMouseDown}
      onDoubleClick={handleDoubleClick}
      onKeyDown={onKeyDown}
      role="separator"
      aria-orientation={isHorizontal ? 'vertical' : 'horizontal'}
      aria-label={`Resize handle. Drag to resize. Double-click or press Home to reset.`}
      tabIndex={0}
      title="Drag to resize. Double-click to reset."
    >
      {/* Visible track */}
      <div
        className={[
          'absolute transition-colors duration-150',
          'bg-rain-border/30',
          'group-hover/handle:bg-rain-teal/40',
          'group-active/handle:bg-rain-teal/60',
          'group-focus-visible/handle:bg-rain-teal/50',
          isHorizontal
            ? 'w-px h-full left-1/2 -translate-x-1/2'
            : 'h-px w-full top-1/2 -translate-y-1/2',
        ].join(' ')}
      />

      {/* Grip dots */}
      <div
        className={[
          'absolute z-10 flex gap-[2px]',
          'opacity-0 group-hover/handle:opacity-100 group-focus-visible/handle:opacity-100',
          'transition-opacity duration-150',
          isHorizontal ? 'flex-col' : 'flex-row',
        ].join(' ')}
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-[3px] h-[3px] rounded-full bg-rain-teal/50"
          />
        ))}
      </div>

      {/* Wider hit area (invisible) */}
      <div
        className={[
          'absolute',
          isHorizontal
            ? 'w-3 h-full left-1/2 -translate-x-1/2'
            : 'h-3 w-full top-1/2 -translate-y-1/2',
        ].join(' ')}
      />
    </div>
  )
}
