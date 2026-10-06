import { useEffect, useRef, useState } from 'react'
import { replyToReview } from '../../api/dashboard.js'
import { useAgentUIBridge } from '../../context/AgentUIBridgeContext.jsx'
import AvatarCircle from '../shared/AvatarCircle.jsx'

const ERASE_MS_PER_CHAR = 10
const TYPE_MS_PER_CHAR = 16

function ReviewHead({ review }) {
  const stars = Math.max(0, Math.min(5, review.rating || 0))
  return (
    <div className="review__head">
      <AvatarCircle name={review.reviewer_name} size={36} />
      <div className="review__who">{review.reviewer_name}</div>
      <span className="stars" aria-label={`${stars} out of 5 stars`}>{'★'.repeat(stars)}<i>{'★'.repeat(5 - stars)}</i></span>
    </div>
  )
}

function ReviewRow({ profileId, review, onReplied }) {
  const bridge = useAgentUIBridge()
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [aiFilled, setAiFilled] = useState(false)
  // Mirrors `draft` so the animation loop always reads the true current text without
  // needing `draft` in its dependencies (which would restart the effect on every keystroke).
  const draftRef = useRef('')
  // Bumped on every new incoming draft so an in-flight animation from a previous
  // (now-superseded) draft knows to stop, instead of two animations racing each other.
  const draftGenerationRef = useRef(0)

  function updateDraft(value) {
    draftRef.current = value
    setDraft(value)
  }

  useEffect(() => {
    if (!bridge) return
    // Keyed per review_id — the bridge only holds one handler per key, and with multiple
    // unreplied reviews on screen at once, a shared 'propose_review_reply' key would have
    // each row's registration silently overwrite the previous one's.
    return bridge.register(`propose_review_reply:${review.id}`, (action) => {
      const newText = action.input.draft_text || ''
      const generation = ++draftGenerationRef.current
      setAiFilled(true)

      function typeIn(text, i) {
        if (draftGenerationRef.current !== generation) return
        updateDraft(text.slice(0, i))
        if (i < text.length) setTimeout(() => typeIn(text, i + 1), TYPE_MS_PER_CHAR)
      }
      function eraseThenType(text, i) {
        if (draftGenerationRef.current !== generation) return
        updateDraft(text.slice(0, i))
        if (i > 0) setTimeout(() => eraseThenType(text, i - 1), ERASE_MS_PER_CHAR)
        else typeIn(newText, 0)
      }

      // First draft for this review (box currently empty): just type it straight in. A
      // redraft replacing existing text: visibly erase the old one first, then type the new
      // one — makes it obvious this is a fresh draft, not a silent instant swap.
      if (draftRef.current) eraseThenType(draftRef.current, draftRef.current.length)
      else typeIn(newText, 0)
    })
  }, [bridge, review.id])

  function onDraft() {
    bridge?.call('open_and_send', {
      message: `Please draft a reply to the review from ${review.reviewer_name} (review_id: "${review.id}") using propose_review_reply.`,
    })
  }

  async function onSend() {
    setSending(true)
    try {
      await replyToReview(profileId, review.id, draft)
      onReplied()
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="review review--pending" data-agent-target={`review-${review.id}`}>
      <ReviewHead review={review} />
      <p className="review__body">{review.body}</p>
      <textarea
        className={`reply-box${aiFilled ? ' reply-box--ai' : ''}`}
        value={draft}
        onChange={(e) => {
          draftGenerationRef.current++ // the user is typing — stop any in-flight redraft animation
          updateDraft(e.target.value)
          setAiFilled(false)
        }}
        placeholder="Write a reply…"
        rows={2}
      />
      {aiFilled && <div className="ai-note">✨ Drafted by assistant — review before sending</div>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button onClick={onDraft} className="btn btn--ghost btn--sm">✨ AI Draft Reply</button>
        <button onClick={onSend} disabled={!draft.trim() || sending} className="btn btn--primary btn--sm">
          {sending ? 'Sending…' : 'Send Reply'}
        </button>
      </div>
    </div>
  )
}

function ReviewReplyList({ profileId, reviews, onReplied }) {
  if (!reviews?.length) {
    return <div className="empty-note">No reviews yet.</div>
  }

  const unreplied = reviews.filter((r) => !r.reply)
  const replied = reviews.filter((r) => r.reply)

  return (
    <div>
      {unreplied.map((r) => (
        <ReviewRow key={r.id} profileId={profileId} review={r} onReplied={onReplied} />
      ))}
      {replied.map((r) => (
        <div key={r.id} className="review">
          <ReviewHead review={r} />
          <p className="review__body">{r.body}</p>
          <div className="review__reply"><small>Your reply</small>{r.reply}</div>
        </div>
      ))}
    </div>
  )
}

export default ReviewReplyList
