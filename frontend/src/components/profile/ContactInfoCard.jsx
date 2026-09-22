function ContactInfoCard({ profile }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: '#fff', padding: 16, flex: 1 }}>
      <h3 style={{ fontSize: 15, marginTop: 0 }}>Contact Info</h3>
      {profile.phone_number && <div style={{ fontSize: 14, marginBottom: 6 }}>📞 {profile.phone_number}</div>}
      {profile.address && <div style={{ fontSize: 14 }}>📍 {profile.address}</div>}
      {!profile.phone_number && !profile.address && (
        <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No contact info listed yet.</div>
      )}
    </div>
  )
}

export default ContactInfoCard
