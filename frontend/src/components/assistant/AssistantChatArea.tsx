import { ChevronDown } from 'lucide-react'
import { AssistantInputBox } from './AssistantInputBox'

export function AssistantChatArea() {
  return (
    <div className="flex-1 flex flex-col h-full bg-zinc-900 overflow-hidden relative">
      {/* Header */}
      <header className="h-14 flex items-center px-4 border-b border-zinc-800 flex-shrink-0 z-10 transition-colors bg-zinc-900/90 backdrop-blur">
        <button className="flex items-center space-x-2 text-zinc-300 hover:text-white transition group px-3 py-1.5 rounded-lg hover:bg-zinc-800">
          <span className="font-semibold text-sm">Model:</span>
          <span className="text-sm">Auto</span>
          <ChevronDown size={16} className="text-zinc-500 group-hover:text-zinc-400 transition" />
        </button>
      </header>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto no-scrollbar scroll-smooth">
        <div className="max-w-3xl mx-auto py-8 px-4 flex flex-col space-y-8 pb-32">
          
          {/* AI Message */}
          <div className="flex items-start space-x-4">
            <div className="w-8 h-8 rounded-full bg-rain-teal/20 text-rain-teal border border-rain-teal/30 flex-shrink-0 flex items-center justify-center font-bold">
              R
            </div>
            <div className="flex flex-col space-y-1">
              <span className="font-semibold text-zinc-200 text-sm">RAIN</span>
              <p className="text-zinc-300 text-base leading-relaxed">
                Hello! I'm RAIN, your AI coding assistant. What can I help you with today?
              </p>
            </div>
          </div>
          
        </div>
      </div>

      {/* Input section */}
      <AssistantInputBox />
    </div>
  )
}
