import { useCallback, useRef, useState } from 'react'
import { Upload, AlertCircle, CheckCircle, Music2 } from 'lucide-react'
import { clsx } from 'clsx'

const ACCEPTED_FORMATS = ['.wav', '.flac', '.aiff', '.aif', '.mp3', '.m4a']
const MAX_SIZE_MB = 500

interface Props {
  onFileSelected: (file: File) => void
  accept?: string[]
  maxSizeMb?: number
  disabled?: boolean
}

interface FileInfo {
  name: string
  sizeMb: number
  format: string
}

export function UploadZone({
  onFileSelected, accept = ACCEPTED_FORMATS, maxSizeMb = MAX_SIZE_MB, disabled = false,
}: Props) {
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null)
  const zoneRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback((file: File) => {
    const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase()
    if (!accept.includes(ext)) {
      setError(`Format ${ext} not supported. Use: ${accept.join(', ')}`)
      return
    }
    const sizeMb = file.size / (1024 * 1024)
    if (sizeMb > maxSizeMb) {
      setError(`File too large (${sizeMb.toFixed(1)} MB). Max: ${maxSizeMb} MB`)
      return
    }
    setError(null)
    setFileInfo({ name: file.name, sizeMb, format: ext.slice(1).toUpperCase() })
    onFileSelected(file)
  }, [accept, maxSizeMb, onFileSelected])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!zoneRef.current) return
    const rect = zoneRef.current.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 100
    const y = ((e.clientY - rect.top) / rect.height) * 100
    zoneRef.current.style.setProperty('--drop-x', `${x}%`)
    zoneRef.current.style.setProperty('--drop-y', `${y}%`)
  }, [])

  return (
    <div
      ref={zoneRef}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      onMouseMove={onMouseMove}
      className={clsx(
        'upload-zone min-h-[200px] flex flex-col items-center justify-center gap-4',
        dragging && 'dragging',
        disabled && 'opacity-40 cursor-not-allowed',
        error && '!border-rain-red/40',
        fileInfo && 'has-file',
      )}
    >
      <input
        ref={inputRef} type="file" className="hidden"
        accept={accept.join(',')} disabled={disabled}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
      />

      {fileInfo ? (
        <div className="text-center space-y-3">
          <div className="w-16 h-16 rounded-2xl glass flex items-center justify-center mx-auto">
            <CheckCircle size={28} className="text-rain-green" />
          </div>
          <div>
            <p className="text-rain-text font-semibold text-base">{fileInfo.name}</p>
            <p className="text-rain-dim text-sm mt-1">
              {fileInfo.format} &middot; {fileInfo.sizeMb.toFixed(1)} MB
            </p>
          </div>
        </div>
      ) : error ? (
        <div className="text-center space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-rain-red/10 border border-rain-red/20 flex items-center justify-center mx-auto">
            <AlertCircle size={28} className="text-rain-red" />
          </div>
          <p className="text-rain-red text-sm max-w-sm">{error}</p>
        </div>
      ) : (
        <div className="text-center space-y-4">
          <div className="w-20 h-20 rounded-2xl glass flex items-center justify-center mx-auto group-hover:shadow-[0_0_30px_rgba(139,92,246,0.15)] transition-shadow">
            <Music2 size={32} className="text-rain-purple" />
          </div>
          <div>
            <p className="text-rain-text font-semibold text-base">Drop your audio here</p>
            <p className="text-rain-dim text-sm mt-2">
              WAV &middot; FLAC &middot; AIFF &middot; MP3 &middot; M4A &middot; up to {maxSizeMb} MB
            </p>
          </div>
          <div className="flex items-center justify-center gap-2 text-xs text-rain-muted">
            <Upload size={12} />
            <span>or click to browse</span>
          </div>
        </div>
      )}
    </div>
  )
}
