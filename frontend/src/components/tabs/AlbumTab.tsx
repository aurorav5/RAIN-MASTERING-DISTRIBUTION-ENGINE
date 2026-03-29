import { Disc, Plus, Music2 } from 'lucide-react'

export default function AlbumTab() {
  return (
    <div className="p-2 space-y-3 w-full page-enter">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Disc size={14} className="text-rain-teal" />
          <span className="text-xs font-semibold text-rain-teal uppercase tracking-widest">Album Assembly</span>
        </div>
        <button className="btn-ghost text-xs flex items-center gap-2 py-2 px-4">
          <Plus size={12} /> New Album
        </button>
      </div>

      <div className="panel-card">
        <div className="panel-card-header">Track List</div>
        <div className="panel-card-body">
          <div className="flex flex-col items-center py-12 text-center">
            <Music2 size={32} className="text-rain-dim mb-4" />
            <h3 className="text-sm font-bold mb-2">No album created yet</h3>
            <p className="text-[10px] text-rain-dim max-w-sm">
              Create an album to sequence tracks, apply consistent mastering across the project,
              and generate DDP or DDEX deliverables for the full release.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
