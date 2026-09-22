function SortDropdown({ value, onChange }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{ border: '1px solid var(--border)', borderRadius: 6, padding: '6px 10px' }}
    >
      <option value="score">Search Rank Score</option>
      <option value="rating">Rating</option>
    </select>
  )
}

export default SortDropdown
