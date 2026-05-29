import { Paperclip, Image as ImageIcon, Mic, Send } from 'lucide-react'

export function AssistantInputBox() {
  return (
    <div className="relative bottom-0 left-0 w-full px-4 pb-6 pt-2 bg-zinc-900 border-t border-zinc-800">
      <div className="max-w-3xl mx-auto relative flex items-end w-full">
        <textarea
          dir="auto"
          className="w-full bg-zinc-800 border-zinc-700 text-zinc-100 placeholder-zinc-400 rounded-xl px-4 py-4 pr-[8rem] resize-none focus:outline-none focus:ring-1 focus:ring-zinc-600 block min-h-[56px] max-h-48 overflow-y-auto"
          placeholder="Message RAIN..."
          rows={1}
        />
        
        <div className="absolute right-3 bottom-3 flex items-center space-x-2 text-zinc-400">
          <button className="p-1.5 hover:text-zinc-200 transition bg-zinc-800 hover:bg-zinc-700 rounded-lg">
            <Paperclip size={18} />
          </button>
          <button className="p-1.5 hover:text-zinc-200 transition bg-zinc-800 hover:bg-zinc-700 rounded-lg">
            <ImageIcon size={18} />
          </button>
          <button className="p-1.5 hover:text-zinc-200 transition bg-zinc-800 hover:bg-zinc-700 rounded-lg">
            <Mic size={18} />
          </button>
          <button className="p-1.5 text-zinc-300 bg-white/10 hover:bg-white/20 transition rounded-lg ml-1">
            <Send size={18} />
          </button>
        </div>
      </div>
      <div className="text-center text-xs text-zinc-500 mt-3 font-sans">
        RAIN can make mistakes. Verify important information.
      </div>
    </div>
  )
}
