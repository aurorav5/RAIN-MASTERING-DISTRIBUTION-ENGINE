export default function AnalyzeTab() {
  const pre = [
    ['Integrated LUFS', '-16.8 LUFS', ''],
    ['True Peak', '-0.2 dBTP', 'warn'],
    ['Dynamic Range', 'DR11', 'good'],
    ['RMS Level', '-14.4 dBFS', ''],
    ['Stereo Width', '0.68', ''],
    ['Crest Factor', '11.2 dB', ''],
  ]
  const post = [
    ['Integrated LUFS', '-14.0 LUFS', 'good'],
    ['True Peak', '-1.0 dBTP', 'good'],
    ['Dynamic Range', 'DR8', 'warn'],
    ['RMS Level', '-12.2 dBFS', 'good'],
    ['Stereo Width', '0.72', 'good'],
    ['Crest Factor', '9.1 dB', ''],
  ]

  const colorMap: Record<string, string> = {
    good: 'text-rain-green',
    warn: 'text-rain-amber',
    bad: 'text-rain-red',
  }

  const StatCard = ({ title, rows }: { title: string; rows: string[][] }) => (
    <div className="panel-card">
      <div className="panel-card-header">{title}</div>
      <div className="panel-card-body space-y-0">
        {rows.map(([k, v, cls]) => (
          <div key={k} className="flex justify-between items-center py-1.5 border-b border-rain-border/50 last:border-b-0">
            <span className="text-[10px] font-mono text-rain-muted">{k}</span>
            <span className={`text-[10px] font-mono ${colorMap[cls ?? ''] ?? 'text-rain-text'}`}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  )

  return (
    <div className="p-4 space-y-3">
      <div className="panel-card">
        <div className="panel-card-header">PRE / POST ANALYSIS</div>
        <div className="panel-card-body">
          <div className="grid grid-cols-2 gap-3">
            <StatCard title="PRE-MASTER" rows={pre} />
            <StatCard title="POST-MASTER" rows={post} />
          </div>
        </div>
      </div>
    </div>
  )
}
