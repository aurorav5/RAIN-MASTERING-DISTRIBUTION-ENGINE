import { Database, Upload, BarChart3 } from 'lucide-react'
import { useAuthStore } from '@/stores/auth'

export default function DatasetTab() {
  const { tierGte } = useAuthStore()
  const isEnterprise = tierGte('enterprise')

  return (
    <div className="p-4 space-y-4 max-w-[1200px] mx-auto page-enter">
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
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="panel-card p-6">
            <Upload size={20} className="text-rain-teal mb-3" />
            <h3 className="text-sm font-bold mb-2">Upload Reference Masters</h3>
            <p className="text-[10px] text-rain-dim mb-4">Add high-quality reference tracks for LoRA fine-tuning</p>
            <button className="btn-ghost text-xs py-2 px-4 w-full">Upload Audio</button>
          </div>
          <div className="panel-card p-6">
            <BarChart3 size={20} className="text-rain-teal mb-3" />
            <h3 className="text-sm font-bold mb-2">Dataset Analytics</h3>
            <p className="text-[10px] text-rain-dim mb-4">View genre distribution, LUFS range, and training readiness</p>
            <div className="text-2xl font-black text-rain-teal">0 <span className="text-xs text-rain-dim font-normal">tracks</span></div>
          </div>
        </div>
      )}
    </div>
  )
}
