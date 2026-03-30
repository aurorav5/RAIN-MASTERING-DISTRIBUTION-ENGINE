import { Users, Video, MessageSquare, Share2 } from 'lucide-react'
import { useAuthStore } from '@/stores/auth'

export default function CollabTab() {
  const { tierGte } = useAuthStore()
  const canCollab = tierGte('studio_pro')

  return (
    <div className="p-2 space-y-3 w-full page-enter">
      <div className="flex items-center gap-2 mb-4">
        <Users size={14} className="text-rain-teal" />
        <span className="text-xs font-semibold text-rain-teal uppercase tracking-widest">Collaboration</span>
      </div>

      {!canCollab ? (
        <div className="glass-panel rounded-lg p-8 text-center">
          <Users size={32} className="text-rain-dim mx-auto mb-4" />
          <h3 className="text-base font-bold mb-2">Real-Time Collaboration</h3>
          <p className="text-sm text-rain-dim max-w-md mx-auto mb-4">
            Invite team members to review and co-master sessions in real time.
            Share A/B comparisons, leave timestamped comments, and approve masters together.
          </p>
          <span className="text-xs text-rain-muted">Requires Studio Pro or Enterprise tier</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="panel-card p-6 text-center">
            <Video size={24} className="text-rain-teal mx-auto mb-3" />
            <h3 className="text-sm font-bold mb-1">Live Session</h3>
            <p className="text-[10px] text-rain-dim">Share your mastering session with collaborators in real time</p>
          </div>
          <div className="panel-card p-6 text-center">
            <MessageSquare size={24} className="text-rain-teal mx-auto mb-3" />
            <h3 className="text-sm font-bold mb-1">Comments</h3>
            <p className="text-[10px] text-rain-dim">Leave timestamped feedback on any point in the audio</p>
          </div>
          <div className="panel-card p-6 text-center">
            <Share2 size={24} className="text-rain-teal mx-auto mb-3" />
            <h3 className="text-sm font-bold mb-1">A/B Share</h3>
            <p className="text-[10px] text-rain-dim">Share before/after comparisons with clients for approval</p>
          </div>
        </div>
      )}
    </div>
  )
}
