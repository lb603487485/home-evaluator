import type { AgentEvent, CommunityInfo, SubjectProperty } from './types'

export async function fetchCommunities(): Promise<CommunityInfo[]> {
  const res = await fetch('/api/communities')
  if (!res.ok) throw new Error(`communities: HTTP ${res.status}`)
  return res.json()
}

/** POST the subject and feed parsed SSE events to onEvent until the stream closes. */
export async function evaluate(
  subject: SubjectProperty,
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
  const res = await fetch('/api/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subject),
  })
  if (!res.ok || !res.body) throw new Error(`evaluate: HTTP ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventType = ''
  let dataLines: string[] = []

  const flush = () => {
    if (eventType && dataLines.length) {
      onEvent({ type: eventType, data: JSON.parse(dataLines.join('\n')) } as AgentEvent)
    }
    eventType = ''
    dataLines = []
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let nl
    while ((nl = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, nl).replace(/\r$/, '')
      buffer = buffer.slice(nl + 1)
      if (line === '') flush()
      else if (line.startsWith('event:')) eventType = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
  }
  flush()
}

export interface AskResponse {
  type: 'answer' | 'what_if'
  text: string
  modified_subject?: SubjectProperty
  changes?: { field: string; before: unknown; after: unknown }[]
}

export async function ask(body: {
  question: string
  history: { role: string; text: string }[]
  context: unknown
}): Promise<AskResponse> {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`ask: HTTP ${res.status}`)
  return res.json()
}

export const cad = new Intl.NumberFormat('en-CA', {
  style: 'currency',
  currency: 'CAD',
  maximumFractionDigits: 0,
})
