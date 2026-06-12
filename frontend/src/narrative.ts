// Split the appraiser narrative on its three known section labels
// (Conclusion / How we got here / Caveats — see backend/agent/prompts/narrate.md).
// Tolerates headings, bold labels, or numbered-list forms, with inline content
// after a dash or colon. Returns null when the shape isn't there (degraded
// narrate output) — the caller falls back to the flat bubble; parsing must
// never break rendering.

export interface NarrativeSections {
  conclusion: string
  how: string
  caveats: string
}

const SECTION_RE =
  /^\s*(?:#{1,4}\s*|\d+\.\s*)?\*{0,2}(conclusion|how we got here|caveats)\*{0,2}\s*[—:–-]*\s*/i

const keyFor = (label: string): keyof NarrativeSections => {
  const l = label.toLowerCase()
  return l === 'conclusion' ? 'conclusion' : l === 'caveats' ? 'caveats' : 'how'
}

export function splitNarrative(text: string): NarrativeSections | null {
  const out: NarrativeSections = { conclusion: '', how: '', caveats: '' }
  let current: keyof NarrativeSections | null = null
  for (const line of text.split('\n')) {
    const m = line.match(SECTION_RE)
    if (m) {
      current = keyFor(m[1])
      const rest = line.slice(m[0].length).trim()
      if (rest) out[current] += rest + '\n'
    } else if (current) {
      out[current] += line + '\n'
    }
  }
  if (!out.conclusion.trim() || !(out.how.trim() || out.caveats.trim())) return null
  return {
    conclusion: out.conclusion.trim(),
    how: out.how.trim(),
    caveats: out.caveats.trim(),
  }
}

/** Count of markdown list items in the caveats text (badge on the collapsed row). */
export function caveatCount(caveats: string): number {
  return caveats.split('\n').filter(l => /^\s*(?:[-*•]|\d+\.)\s+/.test(l)).length
}
