import { useState, useEffect, useCallback } from 'react'
import { Database, Upload, BarChart3, Play, Loader2, CheckCircle, XCircle, Clock } from 'lucide-react'
import { useAuthStore } from '@/stores/auth'

interface DatasetStats {
  fileCount: number
  totalDuration: number
  genreDistribution: Record<string, number>
  lufsRange: [number, number]
}

type TrainingStatus = 'idle' | 'queued' | 'training' | 'completed' | 'failed'

export default function DatasetTab() {
  const { tierGte } = useAuthStore()
  const isEnterprise = tierGte('enterprise')

  const [stats, setStats] = useState<DatasetStats | null>(null)
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus>('idle')
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(true)
  const token = useAuthStore(s => s.accessToken)
  const baseUrl = (import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:8000/api/v1'
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}

  useEffect(() => {
    if (!isEnterprise) { setLoading(false); return }
    let cancelled = false
    async function load() {
      try {
        const res = await fetch(`${baseUrl}/datasets/stats`, { headers })
        if (!res.ok) throw new Error()
        const data = await res.json()
        if (!cancelled) setStats(data)
      } catch {
        if (!cancelled) setStats({ fileCount: 0, totalDuration: 0, genreDistribution: {}, lufsRange: [0, 0] })
      }
      try {
        const res = await fetch(`${baseUrl}/datasets/training-status`, { headers })
        if (!res.ok) throw new Error()
        const status = await res.json()
        if (!cancelled) setTrainingStatus(status.status ?? 'idle')
      } catch {
        // ignore
      }
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [isEnterprise])

  const handleUpload = useCallback(async () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'audio/*'
    input.multiple = true
    input.onchange = async () => {
      const files = input.files
      if (!files || files.length === 0) return
      setUploading(true)
      try {
        const formData = new FormData()
        for (const file of Array.from(files)) {
          formData.append('files', file)
        }
        formData.append('type', 'dataset')
        await fetch(`${baseUrl}/datasets/upload`, {
          method: 'POST',
          body: formData,
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        // Refresh stats
        const res2 = await fetch(`${baseUrl}/datasets/stats`, { headers })
        const data = await res2.json()
        setStats(data)
      } catch (e) {
        // Upload failed
      } finally {
        setUploading(false)
      }
    }
    input.click()
  }, [])

  const handleStartTraining = useCallback(async () => {
    try {
      setTrainingStatus('queued')
      await fetch(`${baseUrl}/datasets/train`, { method: 'POST', headers })
      setTrainingStatus('training')
    } catch {
      setTrainingStatus('failed')
    }
  }, [])

  const formatDuration = (sec: number) => {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    return h > 0 ? `${h}h ${m}m` : `${m}m`
  }

  const statusIcon = {
    idle: null,
    queued: <Clock size={14} className="text-yellow-400" />,
    training: <Loader2 size={14} className="animate-spin text-rain-teal" />,
    completed: <CheckCircle size={14} className="text-green-400" />,
    failed: <XCircle size={14} className="text-red-400" />,
  }

  const statusLabel = {
    idle: 'Ready',
    queued: 'Queued',
    training: 'Training...',
    completed: 'Complete',
    failed: 'Failed',
  }

  return (
    <div className="p-2 space-y-3 w-full page-enter">
      <div className="flex items-center gap-2 mb-4">
        <Database size={14} className="text-rain-teal" />
        <span className="text-xs font-semibold text-rain-teal uppercase tracking-widest">Dataset Manager</span>
        <span className="badge badge-gold ml-2">Enterprise</span>
      </div>

      {!isEnterprise ? (
        <div className="glass-panel rounded-lg p-8 text-center">
          <Database size={32} className="text-rain-dim mx-auto mb-4" />
          <h3 className="text-base font-bold mb-2">Custom Training Datasets</h3>
          <p className="text-sm text-rain-dim max-w-md mx-auto mb-4">
            Upload reference masters to train custom LoRA models on your sonic identity.
            Build datasets from your catalog for enterprise-grade custom mastering AI.
          </p>
          <span className="text-xs text-rain-muted">Requires Enterprise tier</span>
        </div>
      ) : loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={24} className="animate-spin text-rain-teal" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Upload card */}
            <div className="panel-card p-6">
              <Upload size={20} className="text-rain-teal mb-3" />
              <h3 className="text-sm font-bold mb-2">Upload Reference Masters</h3>
              <p className="text-[10px] text-rain-dim mb-4">Add high-quality reference tracks for LoRA fine-tuning</p>
              <button
                className="btn-ghost text-xs py-2 px-4 w-full flex items-center justify-center gap-2"
                onClick={handleUpload}
                disabled={uploading}
              >
                {uploading ? (
                  <><Loader2 size={12} className="animate-spin" /> Uploading...</>
                ) : (
                  <><Upload size={12} /> Upload Audio</>
                )}
              </button>
            </div>

            {/* Stats card */}
            <div className="panel-card p-6">
              <BarChart3 size={20} className="text-rain-teal mb-3" />
              <h3 className="text-sm font-bold mb-2">Dataset Analytics</h3>
              <div className="space-y-2 text-[10px]">
                <div className="flex justify-between text-rain-dim">
                  <span>Tracks</span>
                  <span className="font-mono text-rain-white">{stats?.fileCount ?? 0}</span>
                </div>
                <div className="flex justify-between text-rain-dim">
                  <span>Total Duration</span>
                  <span className="font-mono text-rain-white">{formatDuration(stats?.totalDuration ?? 0)}</span>
                </div>
                <div className="flex justify-between text-rain-dim">
                  <span>LUFS Range</span>
                  <span className="font-mono text-rain-white">
                    {stats && stats.lufsRange[0] !== 0
                      ? `${stats.lufsRange[0].toFixed(1)} to ${stats.lufsRange[1].toFixed(1)}`
                      : '--'}
                  </span>
                </div>
              </div>

              {/* Genre distribution */}
              {stats && Object.keys(stats.genreDistribution).length > 0 && (
                <div className="mt-3 pt-3 border-t border-rain-border">
                  <div className="text-[9px] text-rain-muted mb-2">Genre Distribution</div>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(stats.genreDistribution).map(([genre, count]) => (
                      <span key={genre} className="text-[9px] px-2 py-0.5 bg-rain-bg rounded text-rain-dim">
                        {genre}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Training control */}
          <div className="panel-card p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h3 className="text-xs font-bold text-rain-white">LoRA Training</h3>
                <div className="flex items-center gap-1.5">
                  {statusIcon[trainingStatus]}
                  <span className="text-[10px] text-rain-dim">{statusLabel[trainingStatus]}</span>
                </div>
              </div>
              <button
                className="btn-ghost text-xs py-2 px-4 flex items-center gap-2"
                onClick={handleStartTraining}
                disabled={trainingStatus === 'training' || trainingStatus === 'queued' || (stats?.fileCount ?? 0) === 0}
              >
                <Play size={12} /> Start Training
              </button>
            </div>
            {(stats?.fileCount ?? 0) === 0 && (
              <p className="text-[9px] text-rain-muted mt-2">Upload at least 1 reference track to enable training</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
