import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { AuthLayout } from './AuthLayout'
import { useAuthStore, type Tier } from '@/stores/auth'
import { api, APIError } from '@/utils/api'

export default function LoginView() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { setTokens } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await api.auth.login(email, password)
      setTokens(res.access_token, res.refresh_token, res.tier as Tier, res.user_id)
      void navigate('/app')
    } catch (err) {
      console.error('Login error:', err)
      setError(err instanceof APIError ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout>
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-xl font-bold">Welcome back</h2>
          <p className="text-sm text-rain-dim mt-1">Sign in to your mastering studio</p>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-5">
          <div>
            <label className="text-xs font-semibold text-rain-silver block mb-2 tracking-wide uppercase">Email</label>
            <input
              type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              placeholder="you@studio.com"
              className="input-field"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-rain-silver block mb-2 tracking-wide uppercase">Password</label>
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;"
              className="input-field"
            />
          </div>

          {error && (
            <div className="bg-rain-red/10 border border-rain-red/20 rounded-lg px-4 py-3">
              <p className="text-rain-red text-xs">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <p className="text-rain-dim text-sm text-center">
          No account?{' '}
          <Link to="/register" className="text-rain-teal hover:text-rain-cyan transition-colors font-semibold">
            Start free
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}
