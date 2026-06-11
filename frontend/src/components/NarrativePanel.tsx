import ReactMarkdown from 'react-markdown'

interface Props {
  narrative: string
  streaming: boolean
}

export default function NarrativePanel({ narrative, streaming }: Props) {
  if (!narrative && !streaming) return null
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-700">Appraiser narrative</h2>
      <div className="prose prose-sm mt-2 max-w-none text-slate-700">
        <ReactMarkdown>{narrative}</ReactMarkdown>
        {streaming && <span className="animate-pulse text-slate-400">▍</span>}
      </div>
    </div>
  )
}
