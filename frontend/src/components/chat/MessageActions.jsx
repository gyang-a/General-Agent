import { Copy, RefreshCcw, ThumbsDown, ThumbsUp } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { useChatStore } from '@/stores/chatStore'

function formatTokenCount(value) {
  const count = Number(value)
  if (!Number.isFinite(count) || count <= 0) return '0'
  return new Intl.NumberFormat('zh-CN').format(Math.floor(count))
}

function TokenUsage({ usage }) {
  if (!usage) return null

  const items = [
    ['缓存命中:', usage.cacheHitTokens],
    ['输入:', usage.inputTokens],
    ['输出:', usage.outputTokens],
    ['总计:', usage.totalTokens],
  ]

  return (
    <div className='mr-auto flex min-w-0 flex-wrap text-gray-500 hover:text-red-500 font-bold  items-center gap-x-2 gap-y-1 text-[11px] leading-5 text-muted-foreground'>
      Token使用情况:{items.map(([label, value]) => (
        <span key={label} className='whitespace-nowrap'>
          {label} {formatTokenCount(value)}
        </span>
      ))}
    </div>
  )
}

export function MessageActions({ message, onRegenerate }) {
  const setMessageFeedback = useChatStore((s) => s.setMessageFeedback)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content || '')
    toast.success('已复制到剪贴板')
  }

  return (
    <div className='mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border/60 pt-2'>
      <TokenUsage usage={message.usage} />
      <div className='flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100'>
        <Button size='sm' variant='ghost' className='h-7 px-2 text-xs' onClick={handleCopy}>
          <Copy className='mr-1 h-3.5 w-3.5' />复制
        </Button>
        <Button size='sm' variant='ghost' className='h-7 px-2 text-xs' onClick={onRegenerate}>
          <RefreshCcw className='mr-1 h-3.5 w-3.5' />重试
        </Button>
        <Button
          size='icon'
          variant='ghost'
          className={message.feedback === 'up' ? 'h-7 w-7 text-primary' : 'h-7 w-7'}
          onClick={() => setMessageFeedback(message.id, 'up')}
        >
          <ThumbsUp className='h-3.5 w-3.5' />
        </Button>
        <Button
          size='icon'
          variant='ghost'
          className={message.feedback === 'down' ? 'h-7 w-7 text-red-500' : 'h-7 w-7'}
          onClick={() => setMessageFeedback(message.id, 'down')}
        >
          <ThumbsDown className='h-3.5 w-3.5' />
        </Button>
      </div>
    </div>
  )
}
