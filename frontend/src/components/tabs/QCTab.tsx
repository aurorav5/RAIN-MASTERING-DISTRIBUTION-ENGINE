import { useState, useEffect } from 'react'
import { useSessionStore } from '@/stores/session'
import { api } from '@/utils/api'
import type { QCReportData, QCCheckData } from '@/utils/api'
import { CheckCircle, XCircle, AlertTriangle, Wrench, Shield } from 'lucide-react'

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'advisory'] as const

export default function QCTab() {
  const { rainScore, outputLufs, outputTruePeak, status, sessionId } = useSessionStore()
  const [qcReport, setQcReport] = useState<QCReportData | null>(null)
  const [loading, setLoading] = useState(false)

  // Auto-fetch QC when mastering is complete
  useEffect(() => {
    if (status !== 'complete' || !sessionId) return
    setLoading(true)
    api.master.qcReport(sessionId)
      .then(setQcReport)
      .catch(() => setQcReport(null))
      .finally(() => setLoading(false))
  }, [status, sessionId])

  const overallScore = rainScore?.overall ?? null

  return (
    <div className="p-2 space-y-3 w-full">
      {/* RAIN Score overview */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">RAIN SCORE</span>
        </div>
        <div className="panel-card-body">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 rounded-full border-2 border-rain-purple flex items-center justify-center shrink-0 relative">
              <span className="text-2xl font-mono font-black text-rain-text">
                {overallScore !== null ? overallScore.toFixed(0) : '--'}
              </span>
              <span className="absolute -bottom-3 text-[8px] font-mono text-rain-dim">/ 100</span>
            </div>
            <div className="flex-1 grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <span className="text-[9px] font-mono text-rain-dim">OUTPUT LUFS</span>
                <span className="block text-sm font-mono text-rain-text tabular-nums">
                  {outputLufs !== null ? `${outputLufs.toFixed(1)} LU` : '-- LU'}
                </span>
              </div>
              <div className="space-y-1">
                <span className="text-[9px] font-mono text-rain-dim">TRUE PEAK</span>
                <span className="block text-sm font-mono text-rain-text tabular-nums">
                  {outputTruePeak !== null ? `${outputTruePeak.toFixed(1)} dBTP` : '-- dBTP'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 18 QC Checks — live from backend */}
      <div className="panel-card">
        <div className="panel-card-header justify-between">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            18 AUTOMATED QC CHECKS
          </span>
          {qcReport && (
            <span className={`text-[9px] font-mono font-bold ${qcReport.passed ? 'text-rain-green' : 'text-rain-red'}`}>
              {qcReport.passed ? 'ALL PASSED' : `${qcReport.critical_failures} CRITICAL FAILURE${qcReport.critical_failures > 1 ? 'S' : ''}`}
            </span>
          )}
        </div>
        <div className="panel-card-body">
          {loading && (
            <div className="flex items-center justify-center py-4 gap-2">
              <div className="w-4 h-4 border-2 border-rain-teal border-t-transparent rounded-full animate-spin" />
              <span className="text-[10px] font-mono text-rain-dim">Running QC checks...</span>
            </div>
          )}

          {!qcReport && !loading && (
            <div className="text-center py-6">
              <Shield size={24} className="mx-auto text-rain-muted mb-2" />
              <p className="text-[10px] font-mono text-rain-dim">Master a track to run QC checks</p>
            </div>
          )}

          {qcReport && (
            <div className="space-y-0.5">
              {/* Summary bar */}
              <div className="flex items-center gap-2 mb-3">
                <div className="flex-1 h-1.5 bg-rain-panel rounded overflow-hidden flex">
                  {qcReport.checks.map((c, i) => (
                    <div
                      key={i}
                      className="h-full"
                      style={{
                        width: `${100 / 18}%`,
                        backgroundColor: c.passed
                          ? c.auto_remediated ? '#FFB347' : '#4AFF8A'
                          : '#FF4444',
                      }}
                    />
                  ))}
                </div>
                <span className="text-[9px] font-mono text-rain-dim shrink-0">
                  {qcReport.checks.filter(c => c.passed).length}/18
                </span>
              </div>

              {/* Individual checks */}
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr className="text-rain-dim border-b border-rain-border">
                    <th className="text-left py-1 font-normal w-5">#</th>
                    <th className="text-left py-1 font-normal">CHECK</th>
                    <th className="text-center py-1 font-normal w-16">SEVERITY</th>
                    <th className="text-right py-1 font-normal w-16">VALUE</th>
                    <th className="text-center py-1 font-normal w-12">STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {qcReport.checks.map((check) => (
                    <tr key={check.id} className="border-b border-rain-border/30">
                      <td className="py-1 text-rain-muted">{check.id}</td>
                      <td className="py-1 text-rain-text">
                        {check.name}
                        {check.detail && (
                          <span className="block text-[8px] text-rain-dim mt-0.5">{check.detail}</span>
                        )}
                      </td>
                      <td className="text-center py-1">
                        <span className={`px-1 py-0.5 rounded text-[8px] uppercase tracking-wider ${
                          check.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                          check.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                          check.severity === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                          check.severity === 'advisory' ? 'bg-blue-500/20 text-blue-400' :
                          'bg-rain-muted/20 text-rain-dim'
                        }`}>
                          {check.severity}
                        </span>
                      </td>
                      <td className="text-right py-1 tabular-nums text-rain-dim">
                        {check.value !== null ? check.value : '—'}
                      </td>
                      <td className="text-center py-1">
                        {check.auto_remediated ? (
                          <Wrench size={12} className="inline text-amber-400" />
                        ) : check.passed ? (
                          <CheckCircle size={12} className="inline text-rain-green" />
                        ) : (
                          <XCircle size={12} className="inline text-rain-red" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Remediation summary */}
              {qcReport.remediated_count > 0 && (
                <div className="mt-2 px-2 py-1.5 rounded border border-amber-500/30 bg-amber-500/10 text-[9px] font-mono text-amber-400 flex items-center gap-1.5">
                  <Wrench size={10} />
                  {qcReport.remediated_count} check{qcReport.remediated_count > 1 ? 's' : ''} auto-remediated
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
