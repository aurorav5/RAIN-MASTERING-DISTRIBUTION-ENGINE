import { TierGate } from '../common/TierGate'

export function AIETab() {
  return (
    <TierGate requiredTier="creator" feature="Artist Identity Engine">
      <div className="p-2 space-y-3 w-full">
        <div>
          <p className="text-rain-dim text-xs font-mono mb-2">SESSIONS TOWARD AIE ACTIVATION</p>
          <div className="h-2 bg-rain-panel rounded overflow-hidden">
            <div className="h-full bg-rain-blue rounded" style={{ width: '0%' }} />
          </div>
          <p className="text-rain-dim text-[10px] font-mono mt-1">0 / 5 sessions</p>
        </div>
        <p className="text-rain-dim text-xs font-mono">
          Complete 5 mastering sessions to activate your Artist Identity profile.
        </p>
      </div>
    </TierGate>
  )
}
