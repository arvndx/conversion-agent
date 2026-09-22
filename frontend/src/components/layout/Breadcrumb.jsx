import { Link } from 'react-router-dom'

function Breadcrumb({ items }) {
  return (
    <div style={{ fontSize: 13, color: 'var(--ink-soft)', padding: '12px 24px' }}>
      {items.map((item, i) => (
        <span key={item.label}>
          {i > 0 && ' / '}
          {item.to ? <Link to={item.to}>{item.label}</Link> : item.label}
        </span>
      ))}
    </div>
  )
}

export default Breadcrumb
