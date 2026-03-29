import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { AuthLayout } from './AuthLayout'
import { useAuthStore, type Tier } from '@/stores/auth'
import { api, APIError } from '@/utils/api'

export default function RegisterView() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { setTokens } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirm) { setError('Passwords do not match'); return }
    setError(null)
    setLoading(true)
    try {
      const res = await api.auth.register(email, password)
      setTokens(res.access_token, res.refresh_token, res.tier as Tier, res.user_id)
      void navigate('/app')
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout>
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-xl font-bold">Create your studio</h2>
          <p className="text-sm text-rain-dim mt-1">Free tier — no credit card required</p>
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
              placeholder="Min. 8 characters"
              className="input-field"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-rain-silver block mb-2 tracking-wide uppercase">Confirm Password</label>
            <input
              type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required
              placeholder="Confirm your password"
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
              'Create Account'
            )}
          </button>
        </form>

        <p className="text-rain-dim text-sm text-center">
          Already have an account?{' '}
          <Link to="/login" className="text-rain-purple hover:text-rain-magenta transition-colors font-semibold">
            Sign in
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}
