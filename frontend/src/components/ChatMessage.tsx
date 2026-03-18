import type { Message } from '@/types/api'
import { handbookPageUrl } from '@/services/api'

interface ChatMessageProps {
  message: Message
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-4`}>
      <span className={`text-xs font-medium mb-1 ${isUser ? 'text-blueberry' : 'text-blurple'}`}>
        {isUser ? 'You' : 'Ollie'}
      </span>
      <div
        data-role={message.role}
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-blurple text-white rounded-br-sm'
            : 'bg-white text-blackout border border-barnacle rounded-bl-sm shadow-sm'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {message.citations.length > 0 && (
          <div className="mt-2 pt-2 border-t border-butterfly/30 flex flex-wrap gap-2">
            {message.citations.map((c) => (
              <a
                key={c.page}
                href={handbookPageUrl(c.page)}
                target="_blank"
                rel="noopener noreferrer"
                className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                  isUser
                    ? 'bg-white/20 text-white hover:bg-white/30'
                    : 'bg-barnacle text-blurple hover:bg-butterfly'
                } transition-colors`}
              >
                📄 {c.section} (p. {c.page})
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
