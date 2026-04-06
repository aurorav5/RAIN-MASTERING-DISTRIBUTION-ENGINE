import { useState, useCallback } from 'react'
import { Disc, Plus, Music2, GripVertical, Trash2, Download, Clock } from 'lucide-react'
// Album state is managed locally until backend persistence is implemented

interface AlbumTrack {
  sessionId: string
  title: string
  artist: string
  duration: number
  lufs: number
  rainScore: number
}

interface Album {
  name: string
  artist: string
  tracks: AlbumTrack[]
  gapMs: number
  targetLufs: number
}

export default function AlbumTab() {
  const [album, setAlbum] = useState<Album | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newArtist, setNewArtist] = useState('')

  const handleCreate = useCallback(() => {
    if (!newName.trim()) return
    setAlbum({
      name: newName.trim(),
      artist: newArtist.trim() || 'Unknown Artist',
      tracks: [],
      gapMs: 2000,
      targetLufs: -14.0,
    })
    setShowCreate(false)
    setNewName('')
    setNewArtist('')
  }, [newName, newArtist])

  const removeTrack = useCallback((idx: number) => {
    if (!album) return
    setAlbum({
      ...album,
      tracks: album.tracks.filter((_, i) => i !== idx),
    })
  }, [album])

  const moveTrack = useCallback((from: number, to: number) => {
    if (!album || to < 0 || to >= album.tracks.length) return
    const tracks = [...album.tracks]
    const removed = tracks.splice(from, 1)
    if (removed.length === 0) return
    tracks.splice(to, 0, removed[0]!)
    setAlbum({ ...album, tracks })
  }, [album])

  const totalDuration = album?.tracks.reduce((sum, t) => sum + t.duration, 0) ?? 0
  const avgLufs = album?.tracks.length
    ? album.tracks.reduce((sum, t) => sum + t.lufs, 0) / album.tracks.length
    : 0
  const lufsRange = album?.tracks.length
    ? Math.max(...album.tracks.map(t => t.lufs)) - Math.min(...album.tracks.map(t => t.lufs))
    : 0

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="p-2 space-y-3 w-full page-enter">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Disc size={14} className="text-rain-teal" />
          <span className="text-xs font-semibold text-rain-teal uppercase tracking-widest">Album Assembly</span>
        </div>
        <button
          className="btn-ghost text-xs flex items-center gap-2 py-2 px-4"
          onClick={() => setShowCreate(true)}
        >
          <Plus size={12} /> New Album
        </button>
      </div>

      {showCreate && (
        <div className="panel-card p-4 space-y-3">
          <input
            type="text"
            placeholder="Album name"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            className="w-full bg-rain-bg border border-rain-border rounded px-3 py-2 text-sm text-rain-white placeholder-rain-muted focus:border-rain-teal outline-none"
          />
          <input
            type="text"
            placeholder="Artist name"
            value={newArtist}
            onChange={e => setNewArtist(e.target.value)}
            className="w-full bg-rain-bg border border-rain-border rounded px-3 py-2 text-sm text-rain-white placeholder-rain-muted focus:border-rain-teal outline-none"
          />
          <div className="flex gap-2">
            <button className="btn-ghost text-xs py-2 px-4" onClick={handleCreate}>Create</button>
            <button className="btn-ghost text-xs py-2 px-4 text-rain-dim" onClick={() => setShowCreate(false)}>Cancel</button>
          </div>
        </div>
      )}

      {album ? (
        <>
          <div className="panel-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-bold text-rain-white">{album.name}</h3>
                <p className="text-[10px] text-rain-dim">{album.artist}</p>
              </div>
              <div className="flex items-center gap-4 text-[10px] text-rain-muted font-mono">
                <span>{album.tracks.length} tracks</span>
                <span>{formatTime(totalDuration)}</span>
              </div>
            </div>

            {/* Album-level QC stats */}
            {album.tracks.length > 0 && (
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="text-center">
                  <div className="text-lg font-black text-rain-teal">{formatTime(totalDuration)}</div>
                  <div className="text-[9px] text-rain-muted">Total Duration</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-black text-rain-white">{avgLufs.toFixed(1)}</div>
                  <div className="text-[9px] text-rain-muted">Avg LUFS</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-black text-rain-white">{lufsRange.toFixed(1)} LU</div>
                  <div className="text-[9px] text-rain-muted">LUFS Range</div>
                </div>
              </div>
            )}

            {/* Gap control */}
            <div className="flex items-center gap-3 mb-3">
              <label className="text-[10px] text-rain-dim">Track gap:</label>
              <input
                type="range"
                min={0}
                max={5000}
                step={100}
                value={album.gapMs}
                onChange={e => setAlbum({ ...album, gapMs: Number(e.target.value) })}
                className="rain-slider flex-1"
              />
              <span className="text-[10px] font-mono text-rain-muted w-10 text-right">
                {(album.gapMs / 1000).toFixed(1)}s
              </span>
            </div>
          </div>

          {/* Track list */}
          <div className="panel-card">
            <div className="panel-card-header">Track List</div>
            <div className="panel-card-body">
              {album.tracks.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center">
                  <Music2 size={24} className="text-rain-dim mb-3" />
                  <p className="text-[10px] text-rain-dim">
                    No tracks added. Complete mastering sessions to add tracks to this album.
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  {album.tracks.map((track, idx) => (
                    <div
                      key={track.sessionId}
                      className="flex items-center gap-3 px-3 py-2 rounded hover:bg-rain-bg/50 group"
                    >
                      <span className="text-[10px] font-mono text-rain-muted w-4">{idx + 1}</span>
                      <button
                        className="opacity-0 group-hover:opacity-50 hover:opacity-100 cursor-grab"
                        onMouseDown={() => {}}
                      >
                        <GripVertical size={12} className="text-rain-dim" />
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-rain-white truncate">{track.title}</div>
                        <div className="text-[9px] text-rain-muted">{track.artist}</div>
                      </div>
                      <span className="text-[10px] font-mono text-rain-dim">{formatTime(track.duration)}</span>
                      <span className="text-[10px] font-mono text-rain-dim">{track.lufs.toFixed(1)} LUFS</span>
                      <button
                        className="opacity-0 group-hover:opacity-50 hover:opacity-100"
                        onClick={() => removeTrack(idx)}
                      >
                        <Trash2 size={12} className="text-red-400" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Export options */}
          {album.tracks.length > 0 && (
            <div className="panel-card p-4">
              <div className="panel-card-header">Export</div>
              <div className="flex gap-2 mt-3">
                <button className="btn-ghost text-xs py-2 px-4 flex items-center gap-2">
                  <Download size={12} /> DDP Image
                </button>
                <button className="btn-ghost text-xs py-2 px-4 flex items-center gap-2">
                  <Download size={12} /> DDEX Release
                </button>
                <button className="btn-ghost text-xs py-2 px-4 flex items-center gap-2">
                  <Download size={12} /> Individual Tracks
                </button>
              </div>
            </div>
          )}
        </>
      ) : !showCreate && (
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
      )}
    </div>
  )
}
