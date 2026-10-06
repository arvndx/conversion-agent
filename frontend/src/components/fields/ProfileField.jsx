import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { FIELD_META } from './fieldMeta.js'

// Sizes a textarea to its text (the border is not part of scrollHeight).
function fitHeight(el) {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight + (el.offsetHeight - el.clientHeight)}px`
}

// One editable profile field as a tile: an icon, the label, a status chip, and the input.
//
//   autosave   a typed change is saved when the cursor leaves the field (onboarding)
//   otherwise  Save / Discard buttons appear once the text differs from what is saved (Manage)
//
// `value` is what is saved. When it changes from outside (a saved draft, the server tidying the text) the
// box starts again from it. `children` render under the input (the agent's suggested draft).
function ProfileField({ fieldKey, label, value, onSave, autosave = false, wide = false, disabled = false, missingLabel = 'Missing', inputId, target, children }) {
  const meta = FIELD_META[fieldKey] || {}
  const long = Boolean(meta.long)
  const saved = value || ''
  const [text, setText] = useState(saved)
  const [seen, setSeen] = useState(saved)
  const [phase, setPhase] = useState('idle') // idle | saving | saved
  const [error, setError] = useState(null)
  const inputRef = useRef(null)
  const timer = useRef(null)

  if (saved !== seen) { // the saved value changed: show it (adjusting state while rendering, not in an effect)
    setSeen(saved)
    setText(saved)
  }
  const dirty = text.trim() !== saved.trim()
  const empty = !saved && !text.trim()

  useEffect(() => () => clearTimeout(timer.current), [])
  useLayoutEffect(() => { // long text grows with what is typed instead of scrolling inside a small box
    if (long) fitHeight(inputRef.current)
  }, [text, long])
  useEffect(() => { // ...and again when the box changes width (a phone turned sideways, a resized window)
    const el = inputRef.current
    if (!long || !el || typeof ResizeObserver === 'undefined') return undefined
    let width = el.clientWidth
    const watcher = new ResizeObserver(() => {
      if (el.clientWidth !== width) {
        width = el.clientWidth
        fitHeight(el)
      }
    })
    watcher.observe(el)
    return () => watcher.disconnect()
  }, [long])

  async function save() {
    if (!dirty || phase === 'saving') return
    setPhase('saving')
    setError(null)
    try {
      await onSave(text)
      setPhase('saved')
      clearTimeout(timer.current)
      timer.current = setTimeout(() => setPhase('idle'), 2200)
    } catch (e) {
      setPhase('idle')
      setError(e?.message || 'That could not be saved. Try again.')
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Escape' && dirty) setText(saved)
    if (e.key === 'Enter' && !long) {
      e.preventDefault()
      if (autosave) e.currentTarget.blur()
      else save()
    }
  }

  let chip = null
  if (phase === 'saving') chip = <span className="pf-status pf-status--busy"><span className="ob-spinner" />Saving…</span>
  else if (phase === 'saved') chip = <span className="pf-status pf-status--saved">✓ Saved</span>
  else if (dirty && !autosave) chip = <span className="pf-status pf-status--dirty">Unsaved changes</span>
  else if (empty) chip = <span className="pf-status pf-status--missing">{missingLabel}</span>

  const Input = long ? 'textarea' : 'input'
  const cls = ['pf-field', wide && 'pf-field--wide', empty && 'pf-field--missing', dirty && 'pf-field--dirty'].filter(Boolean).join(' ')

  return (
    <div className={cls} data-agent-target={target}>
      <div className="pf-field__top">
        <span className="pf-field__icon" aria-hidden="true">{meta.icon || '•'}</span>
        <label className="pf-field__label" htmlFor={inputId}>{label}</label>
        {chip}
      </div>
      <Input
        id={inputId}
        ref={inputRef}
        className="pf-input"
        value={text}
        rows={long ? 1 : undefined}
        placeholder={meta.hint || ''}
        maxLength={meta.maxLength}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onBlur={autosave ? save : undefined}
        onKeyDown={onKeyDown}
      />
      {error && <div className="pf-error">{error}</div>}
      {children}
      {!autosave && dirty && (
        <div className="pf-field__foot">
          <button type="button" className="claim-btn-primary ob-btn" disabled={phase === 'saving'} onClick={save}>
            {phase === 'saving' ? 'Saving…' : 'Save'}
          </button>
          <button type="button" className="pf-discard" disabled={phase === 'saving'} onClick={() => setText(saved)}>Discard</button>
        </div>
      )}
    </div>
  )
}

export default ProfileField
