import { useAuthStore } from '@/stores/authStore'

const API_CHAT_URL = import.meta.env.VITE_CHAT_API_URL || '/api/chat/stream'

function parseSSEChunk(chunkText = '') {
  return chunkText
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.replace(/^data:\s?/, ''))
}

async function postChatStream({ token, body, signal }) {
  return fetch(API_CHAT_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  })
}

export async function streamChat({
  conversationId,
  message,
  model = '',
  attachments = [],
  retrievalMode = 'hybrid',
  ragTopK,
  useWebSearch = false,
  signal,
  onEvent,
  onError,
}) {
  const safeTopK = Math.min(20, Math.max(1, Number(ragTopK) || 4))
  const body = {
    conversationId,
    message,
    model,
    attachments,
    retrievalMode,
    ragTopK: safeTopK,
    useWebSearch,
  }

  let token = useAuthStore.getState().token
  let response = await postChatStream({ token, body, signal })

  if (response.status === 401) {
    token = await useAuthStore.getState().refreshToken?.()
    response = await postChatStream({ token, body, signal })
  }

  if (!response.ok || !response.body) {
    let messageText = '聊天服务暂不可用'
    if (response.status === 401) {
      useAuthStore.getState().logout().catch(() => null)
      messageText = '登录已失效，请重新登录'
    } else {
      try {
        const data = await response.json()
        messageText = data?.message || messageText
      } catch {
        messageText = messageText || '聊天服务暂不可用'
      }
    }
    throw new Error(messageText)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        const events = parseSSEChunk(part)
        for (const eventText of events) {
          if (eventText === '[DONE]') {
            onEvent?.({ done: true })
            continue
          }

          try {
            onEvent?.(JSON.parse(eventText))
          } catch {
            onEvent?.({ delta: eventText })
          }
        }
      }
    }
  } catch (error) {
    if (error.name !== 'AbortError') {
      onError?.(error)
    }
    throw error
  } finally {
    reader.releaseLock()
  }
}
