import { Plus, MessageSquare, Menu, Settings, User } from 'lucide-react'

export function AssistantSidebar() {
  return (
    <div className="w-[260px] h-full bg-zinc-950 border-r border-zinc-800 flex flex-col flex-shrink-0">
      <div className="p-3 flex items-center justify-between">
        <div className="flex items-center space-x-2 text-zinc-200 font-semibold px-2">
          <div className="w-6 h-6 rounded-md bg-zinc-700 flex items-center justify-center">
            <span className="text-xs">R</span>
          </div>
          <span>RAIN</span>
        </div>
        <button className="p-2 text-zinc-400 hover:text-zinc-200 transition">
          <Menu size={18} />
        </button>
      </div>

      <div className="px-3 pb-3">
        <button className="w-full flex items-center space-x-2 py-2 px-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg font-medium transition cursor-pointer">
          <Plus size={16} />
          <span>New chat</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 space-y-6 mt-4 no-scrollbar">
        
        <div>
          <h3 className="text-xs text-zinc-500 font-semibold uppercase px-3 mb-2 tracking-wider">Today</h3>
          <div className="space-y-1">
            <button className="w-full text-left flex items-center space-x-2 px-3 py-2 bg-zinc-800 text-zinc-200 rounded-lg">
              <MessageSquare size={16} className="text-zinc-400 flex-shrink-0" />
              <span className="truncate text-sm font-medium">Chat Configuration Update</span>
            </button>
          </div>
        </div>

        <div>
          <h3 className="text-xs text-zinc-500 font-semibold uppercase px-3 mb-2 tracking-wider">Previous 7 Days</h3>
          <div className="space-y-1">
            <button className="w-full text-left flex items-center space-x-2 px-3 py-2 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-200 rounded-lg transition">
              <MessageSquare size={16} className="text-zinc-400 flex-shrink-0" />
              <span className="truncate text-sm">Refactoring Components</span>
            </button>
            <button className="w-full text-left flex items-center space-x-2 px-3 py-2 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-200 rounded-lg transition">
              <MessageSquare size={16} className="text-zinc-400 flex-shrink-0" />
              <span className="truncate text-sm">Design Adjustments</span>
            </button>
            <button className="w-full text-left flex items-center space-x-2 px-3 py-2 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-200 rounded-lg transition">
              <MessageSquare size={16} className="text-zinc-400 flex-shrink-0" />
              <span className="truncate text-sm">Feature Request Analysis</span>
            </button>
          </div>
        </div>
        
      </div>

      <div className="p-3 border-t border-zinc-800 space-y-1">
        <button className="w-full flex items-center space-x-3 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 px-3 py-2.5 rounded-lg transition">
          <Settings size={18} />
          <span className="text-sm font-medium">Settings</span>
        </button>
        <button className="w-full flex items-center space-x-3 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 px-3 py-2.5 rounded-lg transition">
          <User size={18} />
          <span className="text-sm font-medium">Account</span>
        </button>
      </div>
    </div>
  )
}
