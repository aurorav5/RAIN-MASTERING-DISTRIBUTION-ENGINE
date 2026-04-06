/**
 * Canonical tier definitions — MUST mirror backend/app/core/tiers.py exactly.
 * Single source of truth. Per CLAUDE.md Pricing Model v4 (FINAL).
 * Do not add, rename, or reorder without Phil Bölke approval.
 *
 * Regenerate via: openapi-typescript http://localhost:8000/openapi.json
 */

export const Tier = {
  FREE: "free",
  SPARK: "spark",
  CREATOR: "creator",
  ARTIST: "artist",
  STUDIO_PRO: "studio_pro",
  ENTERPRISE: "enterprise",
} as const;

export type Tier = typeof Tier[keyof typeof Tier];

export const TIER_RANK: Record<Tier, number> = {
  [Tier.FREE]: 0,
  [Tier.SPARK]: 1,
  [Tier.CREATOR]: 2,
  [Tier.ARTIST]: 3,
  [Tier.STUDIO_PRO]: 4,
  [Tier.ENTERPRISE]: 5,
};

export const TIER_DISPLAY_NAME: Record<Tier, string> = {
  [Tier.FREE]: "Free",
  [Tier.SPARK]: "Spark",
  [Tier.CREATOR]: "Creator",
  [Tier.ARTIST]: "Artist",
  [Tier.STUDIO_PRO]: "Studio Pro",
  [Tier.ENTERPRISE]: "Enterprise",
};

export const TIER_PRICE_USD_MONTHLY: Record<Tier, number | null> = {
  [Tier.FREE]: 0,
  [Tier.SPARK]: 9,
  [Tier.CREATOR]: 29,
  [Tier.ARTIST]: 59,
  [Tier.STUDIO_PRO]: 149,
  [Tier.ENTERPRISE]: null, // custom, ~$499+
};

export const TIER_DOWNLOADS_PER_MONTH: Record<Tier, number | "unlimited"> = {
  [Tier.FREE]: 0,
  [Tier.SPARK]: 50,
  [Tier.CREATOR]: 10,
  [Tier.ARTIST]: 25,
  [Tier.STUDIO_PRO]: 75,
  [Tier.ENTERPRISE]: "unlimited",
};

/** Returns true if `tier` has at least the rank of `minimum`. */
export function tierGte(tier: Tier | string, minimum: Tier | string): boolean {
  const t = TIER_RANK[tier as Tier];
  const m = TIER_RANK[minimum as Tier];
  if (t === undefined || m === undefined) return false;
  return t >= m;
}

/** Tier feature gates (frontend convenience — backend enforces). */
export const TIER_FEATURES = {
  canDownload: (t: Tier) => tierGte(t, Tier.SPARK),
  canUseStems: (t: Tier) => tierGte(t, Tier.CREATOR),
  canUseClaude: (t: Tier) => tierGte(t, Tier.CREATOR),
  canUseDawPlugin: (t: Tier) => tierGte(t, Tier.ARTIST),
  canUseAIE: (t: Tier) => tierGte(t, Tier.ARTIST),
  canUseDistribution: (t: Tier) => tierGte(t, Tier.ARTIST),
  canUseAtmos: (t: Tier) => tierGte(t, Tier.STUDIO_PRO),
  canUseDDEX: (t: Tier) => tierGte(t, Tier.STUDIO_PRO),
  canUseDDP: (t: Tier) => tierGte(t, Tier.STUDIO_PRO),
  canUseVinyl: (t: Tier) => tierGte(t, Tier.STUDIO_PRO),
  canUseCollaboration: (t: Tier) => tierGte(t, Tier.STUDIO_PRO),
  canUseCustomRainNet: (t: Tier) => tierGte(t, Tier.ENTERPRISE),
  canUseWhiteLabel: (t: Tier) => tierGte(t, Tier.ENTERPRISE),
} as const;
