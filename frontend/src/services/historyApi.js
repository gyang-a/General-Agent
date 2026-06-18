import { useAuthStore } from '@/stores/authStore'

const API_HISTORY_URL = import.meta.env.VITE_HISTORY_API_URL || '/api/history'

function buildAuthHeaders() {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function handleUnauthorized(response) {
  if (response.status !== 401) return false
  useAuthStore.getState().clearAuth?.()
  return true
}

export async function fetchHistorySnapshot() {
  const response = await fetch(API_HISTORY_URL, {
    method: 'GET',
    headers: {
      ...buildAuthHeaders(),
    },
  })

  if (!response.ok) {
    if (handleUnauthorized(response)) {
      throw new Error('登录已失效，请重新登录')
    }
    throw new Error('读取历史记录失败')
  }

  const data = await response.json()
  return {
    conversations: Array.isArray(data?.conversations) ? data.conversations : [],
    currentConversationId: data?.currentConversationId || null,
    messagesByConversation:
      data?.messagesByConversation && typeof data.messagesByConversation === 'object'
        ? data.messagesByConversation
        : {},
  }
}

async function deleteHistoryResource(url) {
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      ...buildAuthHeaders(),
    },
  })

  if (!response.ok) {
    if (handleUnauthorized(response)) {
      throw new Error('登录已失效，请重新登录')
    }
    throw new Error('删除历史记录失败')
  }
}

export async function updateConversation(conversationId, patch) {
  const safeId = String(conversationId || '').trim()
  if (!safeId) return

  const response = await fetch(`${API_HISTORY_URL}/conversations/${encodeURIComponent(safeId)}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(patch || {}),
  })

  if (!response.ok) {
    if (handleUnauthorized(response)) {
      throw new Error('登录已失效，请重新登录')
    }
    throw new Error('更新会话失败')
  }
}

export async function deleteConversation(conversationId) {
  const safeId = String(conversationId || '').trim()
  if (!safeId) return
  await deleteHistoryResource(`${API_HISTORY_URL}/conversations/${encodeURIComponent(safeId)}`)
}

export async function clearConversationMessages(conversationId) {
  const safeId = String(conversationId || '').trim()
  if (!safeId) return
  await deleteHistoryResource(`${API_HISTORY_URL}/conversations/${encodeURIComponent(safeId)}/messages`)
}

export async function clearUserHistory() {
  await deleteHistoryResource(API_HISTORY_URL)
}
