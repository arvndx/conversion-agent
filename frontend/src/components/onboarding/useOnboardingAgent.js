import { useCallback, useEffect, useRef, useState } from 'react'
import { getAgentConversation, greetAgent, sendAgentMessage } from '../../api/agent.js'

const textBlocks = (blocks) => (blocks || []).filter((b) => b.type === 'text' && b.text)

// What the assistant said: all of its text blocks.
const textOf = (blocks) => textBlocks(blocks).map((b) => b.text).join('\n\n').trim()

// What the owner typed: every stored user message is [context block, typed text], and only the typed
// text (the last block) belongs in the chat.
const typedOf = (blocks) => (textBlocks(blocks).at(-1)?.text || '').trim()

// Rebuild the chat (and the drafts the agent proposed) from the stored conversation, so a refresh
// keeps what was said instead of greeting again.
function fromHistory(history) {
  const messages = []
  let drafts = {}
  for (const entry of history || []) {
    if (entry.role === 'user' && entry.kind === 'turn') {
      const text = typedOf(entry.content)
      if (text) messages.push({ role: 'user', text })
    } else if (entry.role === 'assistant') {
      const text = textOf(entry.content)
      if (text) messages.push({ role: 'assistant', text })
      for (const block of entry.content || []) {
        if (block.type === 'tool_use' && block.name === 'propose_field_updates') drafts = { ...drafts, ...(block.input?.fields || {}) }
      }
    }
  }
  return { messages, drafts }
}

// The onboarding conversation. Cards and buttons record decisions over REST; `send` then tells the
// agent what the owner just did so it carries on. `onTurn` runs after every agent turn (refresh the state).
// `enabled` holds the greeting back until the page knows onboarding is actually under way.
export function useOnboardingAgent(profileId, onTurn, enabled = true) {
  const [messages, setMessages] = useState([])
  const [drafts, setDrafts] = useState({}) // field -> text the agent drafted, waiting for the owner
  const [sending, setSending] = useState(false)
  const [celebrate, setCelebrate] = useState(0)
  const startedFor = useRef(null)
  const turnRef = useRef(onTurn)
  useEffect(() => {
    turnRef.current = onTurn
  })
  const route = `/onboarding/${profileId}`

  const take = useCallback((result) => {
    if (result?.reply_text) setMessages((prev) => [...prev, { role: 'assistant', text: result.reply_text }])
    for (const action of result?.ui_actions || []) {
      if (action.type === 'propose_field_updates') setDrafts((prev) => ({ ...prev, ...(action.result?.fields || action.input?.fields || {}) }))
      if (action.type === 'celebrate') setCelebrate((n) => n + 1)
    }
  }, [])

  const failure = () =>
    setMessages((prev) => [...prev, { role: 'system', text: "I couldn't reach the assistant just now. Your answers are saved — try again in a moment." }])

  useEffect(() => {
    if (!enabled || startedFor.current === profileId) return
    startedFor.current = profileId
    ;(async () => {
      const saved = await getAgentConversation(profileId).catch(() => null)
      const restored = fromHistory(saved?.messages)
      setMessages(restored.messages)
      setDrafts(restored.drafts)
      if (restored.messages.some((m) => m.role === 'assistant')) return // already talking: do not greet again
      setSending(true)
      try {
        take(await greetAgent(profileId, { route }))
      } catch {
        failure()
      } finally {
        setSending(false)
        await turnRef.current?.()
      }
    })()
  }, [profileId, enabled]) // eslint-disable-line react-hooks/exhaustive-deps

  const send = useCallback(
    async (text) => {
      setMessages((prev) => [...prev, { role: 'user', text }])
      setSending(true)
      try {
        take(await sendAgentMessage(profileId, text, { route }))
      } catch {
        failure()
      } finally {
        setSending(false)
        await turnRef.current?.()
      }
    },
    [profileId, route, take],
  )

  const dropDraft = useCallback((key) => setDrafts((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => k !== key))), [])

  return { messages, sending, send, drafts, dropDraft, celebrate }
}
