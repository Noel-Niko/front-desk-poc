import type { Citation } from '@/types/api'
import { handbookPageUrl } from '@/services/api'

interface ReferencePanelProps {
  citations: Citation[]
  childName: string | null
}

export function ReferencePanel({ citations, childName }: ReferencePanelProps) {
  // Deduplicate by page number
  const uniqueCitations = citations.reduce<Citation[]>((acc, c) => {
    if (!acc.some((existing) => existing.page === c.page)) {
      acc.push(c)
    }
    return acc
  }, [])

  return (
    <aside className="h-full flex flex-col bg-white border-l border-barnacle">
      <div className="px-4 py-3 border-b border-barnacle">
        <h2 className="text-sm font-bold text-blackout">References</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {childName && (
          <div className="bg-barnacle rounded-xl p-3">
            <p className="text-xs text-blueberry font-medium">Authenticated Child</p>
            <p className="text-sm font-bold text-blackout">{childName}</p>
          </div>
        )}

        {uniqueCitations.length > 0 ? (
          <div>
            <p className="text-xs font-medium text-blueberry mb-2">Handbook Citations</p>
            <div className="space-y-2">
              {uniqueCitations.map((c) => (
                <a
                  key={c.page}
                  href={handbookPageUrl(c.page)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block p-3 rounded-xl bg-barnacle hover:bg-butterfly/30 transition-colors"
                >
                  <p className="text-sm font-medium text-blackout">{c.section}</p>
                  <p className="text-xs text-blueberry mt-0.5">p. {c.page}</p>
                  <p className="text-xs text-blueberry/70 mt-1 line-clamp-2">{c.text}</p>
                </a>
              ))}
            </div>
          </div>
        ) : (
          !childName && (
            <p className="text-xs text-blueberry/60 text-center mt-8">
              No references yet. Start a conversation to see handbook citations and child data here.
            </p>
          )
        )}
      </div>
    </aside>
  )
}
