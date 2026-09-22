import SingleLocationMap from './SingleLocationMap.jsx'

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

function BusinessHoursCard({ address, hours, location }) {
  const hasHours = hours && Object.keys(hours).length > 0

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 16, flex: 1 }}>
      <h3 style={{ fontSize: 15, marginTop: 0 }}>Location &amp; Business Hours</h3>
      <div style={{ marginBottom: 12 }}>
        <SingleLocationMap location={location} height={100} />
      </div>
      {hasHours ? (
        <table style={{ width: '100%', fontSize: 13 }}>
          <tbody>
            {DAYS.map((day) => (
              <tr key={day}>
                <td style={{ padding: '2px 0', color: 'var(--ink-soft)' }}>{day}</td>
                <td style={{ padding: '2px 0', textAlign: 'right' }}>{hours[day] || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No business hours listed yet.</div>
      )}
    </div>
  )
}

export default BusinessHoursCard
