// A white card with an optional header: an icon tile, a title, a one-line subtitle and something on the right.
function Panel({ icon, tint, title, subtitle, aside, target, className = '', children }) {
  return (
    <section className={`panel ${className}`.trim()} data-agent-target={target}>
      {title && (
        <header className="panel__head">
          {icon && <span className="panel__icon" style={tint ? { '--tint': tint } : undefined} aria-hidden="true">{icon}</span>}
          <div className="panel__titles">
            <h3 className="panel__title">{title}</h3>
            {subtitle && <p className="panel__sub">{subtitle}</p>}
          </div>
          {aside}
        </header>
      )}
      {children}
    </section>
  )
}

export default Panel
