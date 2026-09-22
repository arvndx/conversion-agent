function FiltersPanel({
  categories,
  locations,
  services,
  selectedCategory,
  selectedLocation,
  selectedService,
  minRating,
  minScore,
  onChange,
  onClear,
}) {
  return (
    <aside style={{ width: 240, flexShrink: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <strong>Filters</strong>
        <button
          onClick={onClear}
          style={{ background: 'none', border: 'none', color: 'var(--brand)', cursor: 'pointer', fontSize: 13 }}
        >
          Clear All
        </button>
      </div>

      <div style={{ marginBottom: 20 }}>
        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>Category</div>
        {categories.map((c) => (
          <label key={c} style={{ display: 'block', fontSize: 14, marginBottom: 6, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={selectedCategory === c}
              onChange={() => onChange({ category: selectedCategory === c ? '' : c })}
              style={{ marginRight: 8 }}
            />
            {c}
          </label>
        ))}
      </div>

      <div style={{ marginBottom: 20 }}>
        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>Location</div>
        {locations.map((l) => (
          <label key={l} style={{ display: 'block', fontSize: 14, marginBottom: 6, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={selectedLocation === l}
              onChange={() => onChange({ location: selectedLocation === l ? '' : l })}
              style={{ marginRight: 8 }}
            />
            {l}
          </label>
        ))}
      </div>

      <div style={{ marginBottom: 20 }}>
        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>Service</div>
        {services.map((s) => (
          <label key={s} style={{ display: 'block', fontSize: 14, marginBottom: 6, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={selectedService === s}
              onChange={() => onChange({ service: selectedService === s ? '' : s })}
              style={{ marginRight: 8 }}
            />
            {s}
          </label>
        ))}
      </div>

      <div style={{ marginBottom: 20 }}>
        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>Rating</div>
        <input
          type="range"
          min="0"
          max="5"
          step="0.5"
          value={minRating}
          onChange={(e) => onChange({ minRating: Number(e.target.value) })}
          style={{ width: '100%' }}
        />
        <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{minRating}+ stars</div>
      </div>

      <div>
        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>Search Rank Score</div>
        <input
          type="range"
          min="0"
          max="850"
          step="10"
          value={minScore}
          onChange={(e) => onChange({ minScore: Number(e.target.value) })}
          style={{ width: '100%' }}
        />
        <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{minScore}+ SRS</div>
      </div>
    </aside>
  )
}

export default FiltersPanel
