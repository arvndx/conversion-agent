import { useState } from 'react'

function EditableField({ label, value, onSave, multiline, target }) {
  const [draft, setDraft] = useState(value || '')
  const [saving, setSaving] = useState(false)
  const dirty = draft !== (value || '')

  async function save() {
    setSaving(true)
    try {
      await onSave(draft)
    } finally {
      setSaving(false)
    }
  }

  const Field = multiline ? 'textarea' : 'input'

  return (
    <div style={{ marginBottom: 16 }} data-agent-target={target}>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{label}</label>
      <div style={{ display: 'flex', gap: 8, alignItems: multiline ? 'flex-start' : 'center' }}>
        <Field
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={multiline ? 3 : undefined}
          style={{
            flex: 1,
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '8px 10px',
            fontSize: 14,
            fontFamily: 'inherit',
          }}
        />
        <button
          onClick={save}
          disabled={!dirty || saving}
          style={{
            border: 'none',
            borderRadius: 6,
            padding: '8px 14px',
            fontSize: 13,
            fontWeight: 600,
            cursor: dirty && !saving ? 'pointer' : 'default',
            background: dirty ? 'var(--brand)' : 'var(--border)',
            color: dirty ? '#fff' : 'var(--ink-soft)',
          }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}

export default EditableField
