import { useCallback, useEffect, useRef } from 'react'
import { streamChat } from '@/services/chatApi'
import { sanitizeUserInput } from '@/lib/sanitize'
import { useChatStore } from '@/stores/chatStore'
import { useUIStore } from '@/stores/uiStore'

function normalizeDeltaText(value) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map((item) => normalizeDeltaText(item)).join('')

  if (typeof value === 'object') {
    if (typeof value.text === 'string') return value.text
    if (typeof value.content === 'string') return value.content
    if (Array.isArray(value.content)) return value.content.map((item) => normalizeDeltaText(item)).join('')
  }

  return ''
}

const STREAM_FLUSH_MIN_INTERVAL = 40

export function useSSEChat() {
  const abortRef = useRef(null)
  const currentConversationId = useChatStore((s) => s.currentConversationId)
  const appendUserMessage = useChatStore((s) => s.appendUserMessage)
  const startAssistantMessage = useChatStore((s) => s.startAssistantMessage)
  const patchAssistantMessage = useChatStore((s) => s.patchAssistantMessage)
  const setGenerating = useChatStore((s) => s.setGenerating)
  const setStreamError = useChatStore((s) => s.setStreamError)
  const retrievalMode = useUIStore((s) => s.retrievalMode)
  const ragEnabled = useUIStore((s) => s.ragEnabled)
  const ragTopK = useUIStore((s) => s.ragTopK)

  const stopGenerating = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setGenerating(false)
  }, [setGenerating])

  const sendMessage = useCallback(
    async (payload) => {
      const rawText = typeof payload === 'string' ? payload : payload?.text || ''
      const attachments = Array.isArray(payload?.attachments) ? payload.attachments : []
      const model = typeof payload === 'object' ? String(payload?.model || '').trim() : ''
      const useWebSearch = typeof payload === 'object' ? Boolean(payload?.useWebSearch) : false
      const effectiveRetrievalMode = ragEnabled ? retrievalMode : 'direct'
      const safeRagTopK = Math.min(20, Math.max(1, Number(ragTopK) || 4))
      const text = sanitizeUserInput(rawText)
      const finalText = text || (attachments.length > 0 ? '请结合我上传的附件给出回答。' : '')

      if (!finalText || !currentConversationId) return

      setStreamError('')
      appendUserMessage(finalText, attachments, model)
      const assistant = startAssistantMessage()
      if (!assistant) return

      const controller = new AbortController()
      abortRef.current = controller

      let deltaBuffer = ''
      let flushIntervalId = null
      let rafId = null

      const flushDelta = () => {
        if (!assistant?.id || !deltaBuffer) return

        const chunkSize = Math.max(4, Math.min(4, deltaBuffer.length))
        const nextChunk = deltaBuffer.slice(0, chunkSize)
        deltaBuffer = deltaBuffer.slice(chunkSize)
        const nextContent = (assistant.content || '') + nextChunk

        rafId = requestAnimationFrame(() => {
          patchAssistantMessage(assistant.id, { content: nextContent }, { updateConversationMeta: false })
          assistant.content = nextContent
        })
      }

      const startScheduler = () => {
        if (flushIntervalId !== null) return
        flushIntervalId = setInterval(() => {
          if (deltaBuffer.length > 0) flushDelta()
        }, STREAM_FLUSH_MIN_INTERVAL)
      }

      const stopScheduler = (dropBuffer = false) => {
        if (flushIntervalId !== null) {
          clearInterval(flushIntervalId)
          flushIntervalId = null
        }
        if (rafId !== null) {
          cancelAnimationFrame(rafId)
          rafId = null
        }

        if (dropBuffer) {
          deltaBuffer = ''
          return
        }

        while (deltaBuffer.length > 0 && assistant?.id) {
          const nextContent = (assistant.content || '') + deltaBuffer
          deltaBuffer = ''
          patchAssistantMessage(assistant.id, { content: nextContent }, { updateConversationMeta: false })
          assistant.content = nextContent
        }
      }

      try {
        startScheduler()

        await streamChat({
          conversationId: currentConversationId,
          message: finalText,
          model,
          attachments,
          retrievalMode: effectiveRetrievalMode,
          ragTopK: safeRagTopK,
          useWebSearch,
          signal: controller.signal,
          onEvent: (event) => {
            if (!assistant?.id) return

            if (event.done) {
              stopScheduler()
              patchAssistantMessage(assistant.id, {}, { updateConversationMeta: true })
              setGenerating(false)
              return
            }

            if (event.error) {
              throw new Error(event.error)
            }

            const deltaText = normalizeDeltaText(event.delta)
            if (deltaText) {
              deltaBuffer += deltaText
            }

            if (
              (event.refs && event.refs.length > 0) ||
              (event.contextDocs && event.contextDocs.length > 0) ||
              event.retrievalModeUsed
            ) {
              patchAssistantMessage(assistant.id, {
                refs: event.refs || [],
                contextDocs: event.contextDocs || [],
                retrievalModeUsed: String(event.retrievalModeUsed || ''),
              }, { updateConversationMeta: false })
            }
          },
          onError: () => {
            stopScheduler()
            setStreamError('网络异常，已中断生成')
            setGenerating(false)
          },
        })
      } catch (error) {
        const isAbort = error.name === 'AbortError'
        stopScheduler(isAbort)

        if (!isAbort) {
          patchAssistantMessage(assistant.id, {
            content: assistant.content || '请求失败，请重试。',
          })
          setStreamError(error.message || '请求失败，请重试')
          setGenerating(false)
        }
      } finally {
        abortRef.current = null
      }
    },
    [
      appendUserMessage,
      currentConversationId,
      patchAssistantMessage,
      ragEnabled,
      ragTopK,
      retrievalMode,
      setGenerating,
      setStreamError,
      startAssistantMessage,
    ],
  )

  const regenerateLast = useCallback(async () => {
    const list = useChatStore.getState().getCurrentMessages()
    const latestUser = [...list].reverse().find((item) => item.role === 'user')
    if (latestUser) {
      await sendMessage({
        text: latestUser.content,
        attachments: latestUser.attachments || [],
        model: latestUser.model || '',
      })
    }
  }, [sendMessage])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  return {
    sendMessage,
    stopGenerating,
    regenerateLast,
  }
}
