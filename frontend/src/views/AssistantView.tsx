import { AssistantSidebar } from '../components/assistant/AssistantSidebar'
import { AssistantChatArea } from '../components/assistant/AssistantChatArea'

export default function AssistantView() {
  return (
    <div className="flex h-screen w-full bg-zinc-900 text-zinc-200 overflow-hidden font-sans">
      <AssistantSidebar />
      <AssistantChatArea />
    </div>
  )
}
