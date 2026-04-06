/**
 * RAIN Analytics — PostHog wrapper
 *
 * Events tracked:
 * - page_view: { page: string }
 * - audio_upload: { format: string, duration_s: number, size_mb: number }
 * - mastering_started: { genre: string, platform: string }
 * - mastering_complete: { output_lufs: number, qc_pass: boolean, duration_ms: number }
 * - download: { format: 'wav' | 'mp3', has_cert: boolean }
 * - waitlist_join: { has_referral: boolean }
 * - checkout_started: { tier: string, price_id: string }
 * - signup: { source: 'landing' | 'waitlist' | 'direct' }
 * - stem_separation_requested: { tier: string }
 * - distribution_submitted: { platform_count: number, has_ddex: boolean }
 */

const POSTHOG_KEY = import.meta.env['VITE_POSTHOG_KEY'] as string | undefined
const POSTHOG_HOST = (import.meta.env['VITE_POSTHOG_HOST'] as string | undefined) ?? 'https://app.posthog.com'

interface PostHogInstance {
  capture: (event: string, props?: Record<string, unknown>) => void
  identify: (id: string, props?: Record<string, unknown>) => void
}

let _posthog: PostHogInstance | null = null
let _initPromise: Promise<PostHogInstance | null> | null = null

async function getPostHog(): Promise<PostHogInstance | null> {
  if (!POSTHOG_KEY) return null
  if (_posthog) return _posthog
  if (_initPromise) return _initPromise

  // posthog-js is an optional runtime dependency — not in package.json.
  // It is loaded dynamically only when VITE_POSTHOG_KEY is configured.
  // eslint-disable-next-line @typescript-eslint/ban-ts-comment
  // @ts-ignore: posthog-js optional dep, not installed by default
  _initPromise = import('posthog-js').then((mod: { default: { init: (key: string, opts: Record<string, unknown>) => void } & PostHogInstance }) => {
    const ph = mod.default
    ph.init(POSTHOG_KEY, { api_host: POSTHOG_HOST, autocapture: false, capture_pageview: false })
    _posthog = ph
    return _posthog
  }).catch(() => null)

  return _initPromise
}

export const analytics = {
  track(event: string, properties?: Record<string, unknown>): void {
    if (!POSTHOG_KEY) return
    void getPostHog().then((ph) => {
      ph?.capture(event, properties)
    })
  },

  identify(userId: string, traits?: Record<string, unknown>): void {
    if (!POSTHOG_KEY) return
    void getPostHog().then((ph) => {
      ph?.identify(userId, traits)
    })
  },

  page(pageName: string): void {
    if (!POSTHOG_KEY) return
    void getPostHog().then((ph) => {
      ph?.capture('page_view', { page: pageName })
    })
  },
}
