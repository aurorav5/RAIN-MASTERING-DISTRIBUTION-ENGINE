/**
 * AI Disclosure types — must mirror backend/app/services/ddex.py AIDisclosure dataclass.
 * Sept 2025 DDEX AI Disclosure standard (adopted by 15+ distributors, coordinated with Spotify).
 * Required for EU AI Act Article 50 compliance (deadline 2026-08-02).
 */

export const AIArea = {
  VOCALS: 'vocals',
  INSTRUMENTATION: 'instrumentation',
  COMPOSITION: 'composition',
  POST_PRODUCTION: 'post_production',
  MIXING_MASTERING: 'mixing_mastering',
} as const
export type AIArea = typeof AIArea[keyof typeof AIArea]

export const AI_AREA_DISPLAY: Record<AIArea, string> = {
  [AIArea.VOCALS]: 'Vocals',
  [AIArea.INSTRUMENTATION]: 'Instrumentation',
  [AIArea.COMPOSITION]: 'Composition',
  [AIArea.POST_PRODUCTION]: 'Post-production',
  [AIArea.MIXING_MASTERING]: 'Mixing & mastering',
}

export const AIInvolvement = {
  NONE: 'none',
  PARTIAL: 'partial',
  SUBSTANTIAL: 'substantial',
  FULL: 'full',
} as const
export type AIInvolvement = typeof AIInvolvement[keyof typeof AIInvolvement]

export interface AIDisclosure {
  vocals_ai: boolean
  vocals_tool: string | null
  instrumentation_ai: boolean
  instrumentation_tool: string | null
  composition_ai: boolean
  composition_tool: string | null
  post_production_ai: boolean
  post_production_tool: string | null
  mixing_mastering_ai: boolean
  mixing_mastering_tool: string | null
  overall_ai_involvement: AIInvolvement
}

export function emptyAIDisclosure(): AIDisclosure {
  return {
    vocals_ai: false, vocals_tool: null,
    instrumentation_ai: false, instrumentation_tool: null,
    composition_ai: false, composition_tool: null,
    post_production_ai: false, post_production_tool: null,
    mixing_mastering_ai: false, mixing_mastering_tool: null,
    overall_ai_involvement: AIInvolvement.NONE,
  }
}

/** Recompute overall_ai_involvement from the individual area flags. Mirrors backend logic. */
export function recomputeOverall(d: AIDisclosure): AIInvolvement {
  const count = [
    d.vocals_ai, d.instrumentation_ai, d.composition_ai,
    d.post_production_ai, d.mixing_mastering_ai,
  ].filter(Boolean).length
  if (count === 0) return AIInvolvement.NONE
  if (count <= 2) return AIInvolvement.PARTIAL
  if (count === 3) return AIInvolvement.SUBSTANTIAL
  return AIInvolvement.FULL
}

/** Flag+tool pair access for iterating areas in UI. */
export const AI_AREA_FIELDS: Record<AIArea, { flag: keyof AIDisclosure; tool: keyof AIDisclosure }> = {
  [AIArea.VOCALS]:           { flag: 'vocals_ai',           tool: 'vocals_tool' },
  [AIArea.INSTRUMENTATION]:  { flag: 'instrumentation_ai',  tool: 'instrumentation_tool' },
  [AIArea.COMPOSITION]:      { flag: 'composition_ai',      tool: 'composition_tool' },
  [AIArea.POST_PRODUCTION]:  { flag: 'post_production_ai',  tool: 'post_production_tool' },
  [AIArea.MIXING_MASTERING]: { flag: 'mixing_mastering_ai', tool: 'mixing_mastering_tool' },
}
