import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { Tier, TIER_RANK } from '@/types/tiers'

// Re-export for backward compat with existing imports (`import { type Tier } from '@/stores/auth'`)
export { Tier }
export type { Tier as TierType } from '@/types/tiers'

// Dev auto-auth bypass. Opt-in via VITE_DEV_AUTO_AUTH=true in .env.
// By default the real login flow runs in both dev and prod so credentials,
// tier gates, and refresh-cookie flow are tested against the real backend.
const DEV_AUTO_AUTH =
  import.meta.env.DEV && import.meta.env['VITE_DEV_AUTO_AUTH'] === 'true'
const DEFAULT_TIER: Tier = DEV_AUTO_AUTH ? Tier.ENTERPRISE : Tier.FREE
const DEFAULT_AUTH = DEV_AUTO_AUTH

interface AuthState {
  accessToken: string | null
  /** @deprecated refresh token now lives in httpOnly cookie — field kept for legacy clients */
  refreshToken: string | null
  tier: Tier
  userId: string | null
  isAuthenticated: boolean
  setTokens: (access: string, refresh: string, tier: Tier | string, userId: string) => void
  setAccessToken: (access: string, tier: Tier | string) => void
  clearAuth: () => void
  tierGte: (minimum: Tier | string) => boolean
}

function coerceTier(value: Tier | string): Tier {
  return (Object.values(Tier) as string[]).includes(value) ? (value as Tier) : Tier.FREE
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: DEV_AUTO_AUTH ? 'dev-token' : null,
      refreshToken: DEV_AUTO_AUTH ? 'dev-refresh' : null,
      tier: DEFAULT_TIER,
      userId: DEV_AUTO_AUTH ? 'dev-user-phil' : null,
      isAuthenticated: DEFAULT_AUTH,
      setTokens: (access, refresh, tier, userId) =>
        set({
          accessToken: access,
          refreshToken: refresh,
          tier: coerceTier(tier),
          userId,
          isAuthenticated: true,
        }),
      setAccessToken: (access, tier) =>
        set({ accessToken: access, tier: coerceTier(tier), isAuthenticated: true }),
      clearAuth: () =>
        set({ accessToken: null, refreshToken: null, tier: Tier.FREE, userId: null, isAuthenticated: false }),
      tierGte: (minimum) => {
        const t = TIER_RANK[get().tier]
        const m = TIER_RANK[coerceTier(minimum)]
        return t >= m
      },
    }),
    {
      // Bumped to v2 on 2026-04-05 to invalidate the dev-auto-auth shim stored
      // under the old `rain-auth` key. Old key: `rain-auth` → new: `rain-auth-v2`.
      name: 'rain-auth-v2',
      partialize: (s) => ({
        accessToken: s.accessToken,
        // refreshToken kept in store for legacy clients only; the real source is the httpOnly cookie
        refreshToken: s.refreshToken,
        tier: s.tier,
        userId: s.userId,
        isAuthenticated: s.isAuthenticated,
      }),
    }
  )
)
