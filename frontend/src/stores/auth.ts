import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Tier = 'free' | 'spark' | 'creator' | 'artist' | 'studio_pro' | 'enterprise'

const TIER_RANK: Record<Tier, number> = {
  free: 0, spark: 1, creator: 2, artist: 3, studio_pro: 4, enterprise: 5,
}

// Prototype: always enterprise so all features are unlocked and testable.
// In production, the backend JWT sets the real tier.
const DEFAULT_TIER: Tier = 'enterprise'
const DEFAULT_AUTH = true

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  tier: Tier
  userId: string | null
  isAuthenticated: boolean
  setTokens: (access: string, refresh: string, tier: Tier, userId: string) => void
  clearAuth: () => void
  tierGte: (minimum: Tier) => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: 'dev-token',
      refreshToken: 'dev-refresh',
      tier: DEFAULT_TIER,
      userId: 'dev-user-phil',
      isAuthenticated: DEFAULT_AUTH,
      setTokens: (access, refresh, tier, userId) =>
        set({ accessToken: access, refreshToken: refresh, tier, userId, isAuthenticated: true }),
      clearAuth: () =>
        set({ accessToken: null, refreshToken: null, tier: 'free', userId: null, isAuthenticated: false }),
      tierGte: (minimum) => TIER_RANK[get().tier] >= TIER_RANK[minimum],
    }),
    {
      name: 'rain-auth',
      partialize: (s) => ({
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
        tier: s.tier,
        userId: s.userId,
        isAuthenticated: s.isAuthenticated,
      }),
      merge: (persisted, current) => ({
        ...current,
        ...(persisted as Partial<AuthState>),
        // Prototype: always force enterprise tier regardless of persisted state
        tier: 'enterprise' as Tier,
        isAuthenticated: true,
      }),
    }
  )
)
