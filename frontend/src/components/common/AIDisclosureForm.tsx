import { useCallback } from 'react'
import {
  type AIDisclosure, AIArea, AI_AREA_DISPLAY, AI_AREA_FIELDS,
  AIInvolvement, recomputeOverall,
} from '@/types/ai_disclosure'

interface Props {
  value: AIDisclosure
  onChange: (next: AIDisclosure) => void
  /** Disable editing (review mode) */
  readOnly?: boolean
}

const INVOLVEMENT_COLOR: Record<AIInvolvement, string> = {
  [AIInvolvement.NONE]: 'text-rain-dim',
  [AIInvolvement.PARTIAL]: 'text-rain-teal',
  [AIInvolvement.SUBSTANTIAL]: 'text-rain-yellow',
  [AIInvolvement.FULL]: 'text-rain-red',
}

/**
 * DDEX Sept 2025 AI Disclosure form. Emits the exact shape expected by
 * backend/app/services/ddex.py AIDisclosure. Required for EU AI Act Art. 50.
 */
export function AIDisclosureForm({ value, onChange, readOnly = false }: Props) {
  const setAreaFlag = useCallback((area: AIArea, flag: boolean) => {
    const fields = AI_AREA_FIELDS[area]
    const next: AIDisclosure = {
      ...value,
      [fields.flag]: flag,
      // Clear the tool name when the flag goes off
      [fields.tool]: flag ? value[fields.tool] : null,
    } as AIDisclosure
    next.overall_ai_involvement = recomputeOverall(next)
    onChange(next)
  }, [value, onChange])

  const setAreaTool = useCallback((area: AIArea, tool: string) => {
    const fields = AI_AREA_FIELDS[area]
    onChange({ ...value, [fields.tool]: tool || null } as AIDisclosure)
  }, [value, onChange])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-rain-silver uppercase tracking-widest">
          AI Disclosure (DDEX Sept 2025)
        </h4>
        <span className={`text-[10px] font-mono uppercase ${INVOLVEMENT_COLOR[value.overall_ai_involvement]}`}>
          {value.overall_ai_involvement}
        </span>
      </div>
      <p className="text-[10px] text-rain-dim leading-relaxed">
        EU AI Act Article 50 (enforced 2026-08-02) requires disclosing where AI was used.
        Flag only the areas where AI meaningfully contributed — mastering with RAIN's RainNet counts as mixing/mastering.
      </p>

      <div className="space-y-2">
        {(Object.values(AIArea) as AIArea[]).map((area) => {
          const fields = AI_AREA_FIELDS[area]
          const flag = value[fields.flag] as boolean
          const tool = (value[fields.tool] as string | null) ?? ''
          return (
            <div key={area} className="flex items-center gap-2">
              <label className="flex items-center gap-2 min-w-[160px] text-xs text-rain-text">
                <input
                  type="checkbox"
                  checked={flag}
                  disabled={readOnly}
                  onChange={(e) => setAreaFlag(area, e.target.checked)}
                  className="accent-rain-teal"
                />
                {AI_AREA_DISPLAY[area]}
              </label>
              <input
                type="text"
                value={tool}
                disabled={readOnly || !flag}
                placeholder={flag ? 'Tool / model name (e.g. Suno, RAIN)' : 'Not applicable'}
                onChange={(e) => setAreaTool(area, e.target.value)}
                className="input-field text-xs flex-1 disabled:opacity-40"
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
