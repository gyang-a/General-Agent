import { useEffect, useState } from 'react'
import { Toaster } from 'sonner'
import { Sheet, SheetContent } from '@/components/ui/sheet'
import { Sidebar } from '@/components/sidebar/Sidebar'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { AuxPanel } from '@/components/panel/AuxPanel'
import { useAutoScroll } from '@/hooks/useAutoScroll'
import { useSSEChat } from '@/hooks/useSSEChat'
import { useHotkeys } from '@/hooks/useHotkeys'
import { fetchHistorySnapshot } from '@/services/historyApi'
import { fetchAvailableModels } from '@/services/modelApi'
import { useAuthStore } from '@/stores/authStore'
import { useChatStore } from '@/stores/chatStore'
import { useUIStore } from '@/stores/uiStore'

export function MainLayout() {
  const token = useAuthStore((s) => s.token)
  const ownerUsername = useChatStore((s) => s.ownerUsername)
  const currentConversationId = useChatStore((s) => s.currentConversationId)
  const applyRemoteHistorySnapshot = useChatStore((s) => s.applyRemoteHistorySnapshot)
  const initCurrentConversation = useChatStore((s) => s.initCurrentConversation)
  const createConversation = useChatStore((s) => s.createConversation)
  const mobileSidebarOpen = useUIStore((s) => s.mobileSidebarOpen)
  const setMobileSidebarOpen = useUIStore((s) => s.setMobileSidebarOpen)
  const rightPanelOpen = useUIStore((s) => s.rightPanelOpen)
  const setRightPanelOpen = useUIStore((s) => s.setRightPanelOpen)
  const [availableModels, setAvailableModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [isMobileRightPanelViewport, setIsMobileRightPanelViewport] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth < 1280
  })

  const { sendMessage, stopGenerating, regenerateLast } = useSSEChat()
  const { autoScrollEnabled, onAtBottomStateChange, forceEnableAutoScroll } = useAutoScroll()

  useEffect(() => {
    initCurrentConversation()
  }, [initCurrentConversation])

  useHotkeys({
    onNewConversation: createConversation,
    onSend: () => {},
  })

  useEffect(() => {
    forceEnableAutoScroll()
  }, [currentConversationId, forceEnableAutoScroll])

  useEffect(() => {
    if (!token || !ownerUsername) return

    let cancelled = false
    fetchHistorySnapshot()
      .then((snapshot) => {
        if (cancelled) return
        applyRemoteHistorySnapshot(snapshot)
      })
      .catch(() => null)

    return () => {
      cancelled = true
    }
  }, [applyRemoteHistorySnapshot, ownerUsername, token])

  useEffect(() => {
    if (!token || !ownerUsername) return

    let cancelled = false

    const refreshModels = () => {
      fetchAvailableModels()
        .then(({ models }) => {
          if (cancelled) return
          setAvailableModels(models)

          const storageKey = `Kria_model_${ownerUsername}`
          const cached = window.localStorage.getItem(storageKey) || ''
          setSelectedModel(cached && models.includes(cached) ? cached : '')
        })
        .catch(() => {
          if (cancelled) return
          setAvailableModels([])
          setSelectedModel('')
        })
    }

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refreshModels()
      }
    }

    const onModelsUpdated = () => {
      refreshModels()
    }

    refreshModels()
    window.addEventListener('focus', refreshModels)
    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('kria:models-updated', onModelsUpdated)

    return () => {
      cancelled = true
      window.removeEventListener('focus', refreshModels)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.removeEventListener('kria:models-updated', onModelsUpdated)
    }
  }, [ownerUsername, token])

  useEffect(() => {
    if (!ownerUsername || !selectedModel) return
    window.localStorage.setItem(`Kria_model_${ownerUsername}`, selectedModel)
  }, [ownerUsername, selectedModel])

  useEffect(() => {
    if (typeof window === 'undefined') return

    const media = window.matchMedia('(max-width: 1279px)')
    const sync = () => setIsMobileRightPanelViewport(media.matches)
    sync()

    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', sync)
      return () => media.removeEventListener('change', sync)
    }

    media.addListener(sync)
    return () => media.removeListener(sync)
  }, [])

  return (
    <div className='h-screen w-full bg-[radial-gradient(1400px_700px_at_-15%_-25%,rgba(91,123,255,0.18),transparent),radial-gradient(1100px_580px_at_115%_-10%,rgba(78,195,255,0.16),transparent),#f4f6fb] p-2 text-foreground md:p-3'>
      <div className='flex h-full w-full overflow-hidden rounded-[24px] border border-[#dce2f1] bg-card/85 shadow-[0_12px_45px_rgba(26,41,82,0.08)] backdrop-blur'>
        <div className='hidden md:block'>
          <Sidebar />
        </div>

        <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
          <SheetContent
            title='会话侧边栏'
            overlayClassName='md:hidden'
            className='w-[300px] border-r border-sidebar-border bg-sidebar p-0 md:hidden'
          >
            <Sidebar mobile />
          </SheetContent>
        </Sheet>

        {isMobileRightPanelViewport && (
          <Sheet open={rightPanelOpen} onOpenChange={setRightPanelOpen}>
            <SheetContent
              title='RAG 辅助面板'
              overlayClassName='xl:hidden'
              className='left-auto right-0 w-[94vw] max-w-[360px] border-r-0 border-l border-border bg-background p-0 text-foreground xl:hidden'
            >
              <AuxPanel mobile />
            </SheetContent>
          </Sheet>
        )}

        <div className='flex min-w-0 flex-1'>
          <ChatWindow
            autoScrollEnabled={autoScrollEnabled}
            onAtBottomStateChange={onAtBottomStateChange}
            onSend={sendMessage}
            onStop={stopGenerating}
            onRegenerate={regenerateLast}
            availableModels={availableModels}
            selectedModel={selectedModel}
            onSelectModel={setSelectedModel}
          />

          <AuxPanel />
        </div>
      </div>

      <Toaster richColors position='top-center' />
    </div>
  )
}
