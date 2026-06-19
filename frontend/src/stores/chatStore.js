import { create } from 'zustand'
import { createId } from '@/lib/utils'

const EMPTY_MESSAGES = []

const quickCards = [
  '帮我总结今天的技术新闻',
  '给我写一份产品需求文档模板',
  '解释一下 SSE 和 WebSocket 的区别',
  '帮我润色一段中文邮件',
]

function normalizeTextContent(value) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map((item) => normalizeTextContent(item)).join('')

  if (typeof value === 'object') {
    if (typeof value.text === 'string') return value.text
    if (typeof value.content === 'string') return value.content
    if (Array.isArray(value.content)) return value.content.map((item) => normalizeTextContent(item)).join('')
  }

  return ''
}

function normalizeTokenUsage(value) {
  if (!value || typeof value !== 'object') return null
  const toCount = (item) => {
    const count = Number(item)
    return Number.isFinite(count) && count > 0 ? Math.floor(count) : 0
  }
  return {
    inputTokens: toCount(value.inputTokens ?? value.input_tokens ?? value.prompt_tokens),
    outputTokens: toCount(value.outputTokens ?? value.output_tokens ?? value.completion_tokens),
    totalTokens: toCount(value.totalTokens ?? value.total_tokens),
    cacheHitTokens: toCount(value.cacheHitTokens ?? value.cache_hit_tokens ?? value.cached_tokens),
  }
}

function normalizePersistedMessages(messagesByConversation = {}) {
  const next = {}
  for (const [conversationId, list] of Object.entries(messagesByConversation)) {
    next[conversationId] = Array.isArray(list)
      ? list.map((message) => ({
          ...message,
          content: normalizeTextContent(message?.content),
          usage: normalizeTokenUsage(message?.usage),
        }))
      : []
  }
  return next
}

function buildNewConversation() {
  const id = createId('conv')
  const now = Date.now()
  return {
    id,
    conversationId: id,
    title: '新对话',
    pinned: false,
    updatedAt: now,
    createdAt: now,
    lastPreview: '',
    contextDocs: [],
    refs: [],
  }
}

function buildEmptyChatSnapshot() {
  const conversation = buildNewConversation()
  return {
    conversations: [conversation],
    currentConversationId: conversation.id,
    messagesByConversation: {},
    streamError: '',
    generating: false,
  }
}

function normalizeConversation(item) {
  const id = String(item?.id || item?.conversationId || '').trim()
  if (!id) return null
  return {
    ...item,
    id,
    conversationId: id,
    title: String(item?.title || '').trim() || '新对话',
    pinned: Boolean(item?.pinned),
    updatedAt: Number(item?.updatedAt) || Number(item?.createdAt) || Date.now(),
    createdAt: Number(item?.createdAt) || Number(item?.updatedAt) || Date.now(),
    lastPreview: normalizeTextContent(item?.lastPreview),
    refs: Array.isArray(item?.refs) ? item.refs : [],
    contextDocs: Array.isArray(item?.contextDocs) ? item.contextDocs : [],
  }
}

function normalizeChatSnapshot(snapshot) {
  const conversations = Array.isArray(snapshot?.conversations)
    ? snapshot.conversations.map(normalizeConversation).filter(Boolean)
    : []
  const safeConversations = conversations.length > 0 ? conversations : buildEmptyChatSnapshot().conversations
  const currentConversationId =
    snapshot?.currentConversationId &&
    safeConversations.some((item) => item.id === snapshot.currentConversationId)
      ? snapshot.currentConversationId
      : safeConversations[0].id

  return {
    conversations: safeConversations,
    currentConversationId,
    messagesByConversation: normalizePersistedMessages(snapshot?.messagesByConversation || {}),
    streamError: '',
    generating: false,
  }
}

export const useChatStore = create((set, get) => ({
  ownerUsername: '',
  ...buildEmptyChatSnapshot(),
  quickCards,

  syncAuthOwner: (username) => {
    const safeUsername = String(username || '').trim()
    if (get().ownerUsername === safeUsername) return
    set({
      ownerUsername: safeUsername,
      ...buildEmptyChatSnapshot(),
    })
  },

  initCurrentConversation: () => {
    const { conversations, currentConversationId } = get()
    if (!currentConversationId && conversations.length > 0) {
      set({ currentConversationId: conversations[0].id })
    }
  },

  createConversation: () => {
    const conversation = buildNewConversation()
    set((state) => ({
      conversations: [conversation, ...state.conversations],
      currentConversationId: conversation.id,
    }))
  },

  setCurrentConversation: (id) => set({ currentConversationId: id }),

  renameConversation: (id, title) => {
    const nextTitle = String(title || '').trim() || '未命名对话'
    set((state) => ({
      conversations: state.conversations.map((item) =>
        item.id === id ? { ...item, title: nextTitle, updatedAt: Date.now() } : item,
      ),
    }))
  },

  togglePinConversation: (id) => {
    set((state) => ({
      conversations: [...state.conversations]
        .map((item) => (item.id === id ? { ...item, pinned: !item.pinned, updatedAt: Date.now() } : item))
        .sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.updatedAt - a.updatedAt),
    }))
  },

  deleteConversation: (id) => {
    set((state) => {
      const remain = state.conversations.filter((item) => item.id !== id)
      const nextConversations = remain.length > 0 ? remain : [buildNewConversation()]
      const nextCurrent =
        state.currentConversationId === id ? nextConversations[0].id : state.currentConversationId
      const { [id]: _, ...restMessages } = state.messagesByConversation

      return {
        conversations: nextConversations,
        currentConversationId: nextCurrent,
        messagesByConversation: restMessages,
      }
    })
  },

  clearAllHistories: () => {
    set(buildEmptyChatSnapshot())
  },

  clearCurrentUserHistoryBucket: () => {
    set(buildEmptyChatSnapshot())
  },

  applyRemoteHistorySnapshot: (snapshot) => {
    set(normalizeChatSnapshot(snapshot))
  },

  getCurrentConversation: () => {
    const { conversations, currentConversationId } = get()
    return conversations.find((item) => item.id === currentConversationId) || null
  },

  getCurrentMessages: () => {
    const { currentConversationId, messagesByConversation } = get()
    if (!currentConversationId) return EMPTY_MESSAGES
    return messagesByConversation[currentConversationId] || EMPTY_MESSAGES
  },

  appendUserMessage: (content, attachments = [], model = '') => {
    const conversationId = get().currentConversationId
    if (!conversationId) return null

    const text = normalizeTextContent(content)
    const message = {
      id: createId('msg_u'),
      role: 'user',
      content: text,
      attachments,
      model: String(model || ''),
      createdAt: Date.now(),
    }

    set((state) => {
      const list = state.messagesByConversation[conversationId] || []
      const nextList = [...list, message]
      return {
        messagesByConversation: {
          ...state.messagesByConversation,
          [conversationId]: nextList,
        },
        conversations: state.conversations
          .map((conv) =>
            conv.id === conversationId
              ? {
                  ...conv,
                  title: conv.title === '新对话' ? text.slice(0, 18) || '新对话' : conv.title,
                  updatedAt: Date.now(),
                  lastPreview: text,
                }
              : conv,
          )
          .sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.updatedAt - a.updatedAt),
      }
    })

    return message
  },

  startAssistantMessage: () => {
    const conversationId = get().currentConversationId
    if (!conversationId) return null

    const message = {
      id: createId('msg_ai'),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
      refs: [],
      contextDocs: [],
      usage: null,
      feedback: 'none',
    }

    set((state) => {
      const list = state.messagesByConversation[conversationId] || []
      return {
        generating: true,
        streamError: '',
        messagesByConversation: {
          ...state.messagesByConversation,
          [conversationId]: [...list, message],
        },
      }
    })

    return message
  },

  patchAssistantMessage: (messageId, patch, options = {}) => {
    const conversationId = get().currentConversationId
    if (!conversationId) return

    const updateConversationMeta = options?.updateConversationMeta !== false

    set((state) => {
      const list = state.messagesByConversation[conversationId] || []
      const safePatch = {
        ...patch,
        ...(Object.prototype.hasOwnProperty.call(patch || {}, 'content')
          ? { content: normalizeTextContent(patch.content) }
          : {}),
        ...(Object.prototype.hasOwnProperty.call(patch || {}, 'usage')
          ? { usage: normalizeTokenUsage(patch.usage) }
          : {}),
      }
      const nextList = list.map((msg) => (msg.id === messageId ? { ...msg, ...safePatch } : msg))

      if (!updateConversationMeta) {
        return {
          messagesByConversation: {
            ...state.messagesByConversation,
            [conversationId]: nextList,
          },
        }
      }

      const assistantLast = [...nextList].reverse().find((msg) => msg.role === 'assistant')
      return {
        messagesByConversation: {
          ...state.messagesByConversation,
          [conversationId]: nextList,
        },
        conversations: state.conversations.map((conv) =>
          conv.id === conversationId
            ? {
                ...conv,
                updatedAt: Date.now(),
                lastPreview: assistantLast?.content || conv.lastPreview,
                refs: assistantLast?.refs || conv.refs,
                contextDocs: assistantLast?.contextDocs || conv.contextDocs,
              }
            : conv,
        ),
      }
    })
  },

  setGenerating: (generating) => set({ generating }),
  setStreamError: (streamError) => set({ streamError }),

  clearCurrentConversationMessages: () => {
    const conversationId = get().currentConversationId
    if (!conversationId) return

    set((state) => ({
      messagesByConversation: {
        ...state.messagesByConversation,
        [conversationId]: [],
      },
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId ? { ...conv, lastPreview: '', refs: [], contextDocs: [] } : conv,
      ),
    }))
  },

  setMessageFeedback: (messageId, feedback) => {
    const conversationId = get().currentConversationId
    if (!conversationId) return

    set((state) => {
      const list = state.messagesByConversation[conversationId] || []
      return {
        messagesByConversation: {
          ...state.messagesByConversation,
          [conversationId]: list.map((msg) =>
            msg.id === messageId ? { ...msg, feedback: msg.feedback === feedback ? 'none' : feedback } : msg,
          ),
        },
      }
    })
  },
}))
