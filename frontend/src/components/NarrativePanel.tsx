import ReactMarkdown from 'react-markdown'

interface Props {
  narrative: string
  streaming: boolean
  bare?: boolean // render content only (for use inside a transcript bubble)
}

export default function NarrativePanel({ narrative, streaming, bare = false }: Props) {
  if (!narrative && !streaming) return null
  const body = (
    <div className="prose prose-sm mt-1 max-w-none text-slate-700">
      <ReactMarkdown>{narrative}</ReactMarkdown>
      {streaming && <span className="animate-pulse text-slate-400">▍</span>}
    </div>
  )
  if (bare) return body
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-700">Appraiser narrative</h2>
      {body}
    </div>
  )
}
