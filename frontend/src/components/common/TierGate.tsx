import { Lock } from 'lucide-react'
import { useAuthStore } from '@/stores/auth'
import { Tier, TIER_DISPLAY_NAME } from '@/types/tiers'
import { Button } from './Button'

interface Props {
  requiredTier: Tier | string
  children: React.ReactNode
  feature?: string
}

export function TierGate({ requiredTier, children, feature }: Props) {
  const { tierGte } = useAuthStore()

  if (tierGte(requiredTier)) return <>{children}</>

  const label = TIER_DISPLAY_NAME[requiredTier as Tier] ?? String(requiredTier)

  return (
    <div className="relative">
      <div className="pointer-events-none select-none blur-sm opacity-40">{children}</div>
      <div className="absolute inset-0 flex flex-col items-center justify-center bg-rain-black/70 rounded">
        <Lock size={20} className="text-rain-dim mb-2" />
        <p className="text-rain-silver text-xs font-mono mb-3 text-center px-4">
          {feature ? `${feature} requires` : 'Requires'} {label}+
        </p>
        <Button size="sm" variant="ghost">Upgrade</Button>
      </div>
    </div>
  )
}
