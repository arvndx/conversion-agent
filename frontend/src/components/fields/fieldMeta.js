// What the profile forms (onboarding "Your details" and Manage "Profile Details") know about each field:
// an icon, a placeholder, whether it is long text, and which group it sits in. Fields a category adds
// that are not listed here still show, in "More details".

export const FIELD_META = {
  business_name: { icon: '🏢', hint: 'Your company or team name' },
  title: { icon: '💼', hint: 'e.g. Broker Associate' },
  license_number: { icon: '📜', hint: 'e.g. NMLS # 123456' },
  year_started: { icon: '📅', hint: 'e.g. 2012', maxLength: 4 },
  address: { icon: '📍', hint: '123 Main St, Austin, TX 78701', wide: true },
  website_url: { icon: '🌐', hint: 'https://yourbusiness.com' },
  phone_number: { icon: '📞', hint: '(555) 123-4567' },
  business_timing: { icon: '🕘', hint: 'e.g. Monday–Friday, 9 AM – 6 PM' },
  service_area: { icon: '🗺️', hint: 'e.g. Austin, TX and surrounding areas' },
  bio: { icon: '✍️', hint: 'A few sentences on who you help and how', long: true, wide: true },
  specialities: { icon: '🎯', hint: 'e.g. First-time buyers, Relocation, Luxury homes', long: true, wide: true },
  awards: { icon: '🏆', hint: 'Awards and recognition', long: true },
  achievements: { icon: '⭐', hint: 'Milestones you are proud of', long: true },
}

const GROUPS = [
  { id: 'business', label: 'Your business', icon: '🏢', keys: ['business_name', 'title', 'license_number', 'year_started'] },
  { id: 'where', label: 'Contact & location', icon: '📍', keys: ['address', 'website_url', 'phone_number', 'business_timing', 'service_area'] },
  { id: 'story', label: 'Your story', icon: '✍️', keys: ['bio', 'specialities', 'awards', 'achievements'] },
]
const OTHER = { id: 'other', label: 'More details', icon: '➕', keys: [] }

// Marks which tiles span the full row. Tiles that are wide by nature are, and a half-width tile left
// without a partner (an odd count, or a wide tile right after it) is widened so no row has a gap.
function layout(fields) {
  const out = fields.map((f) => ({ ...f, wide: Boolean(FIELD_META[f.key]?.wide) }))
  let open = null
  out.forEach((f, i) => {
    if (f.wide) {
      if (open !== null) out[open].wide = true
      open = null
    } else {
      open = open === null ? i : null
    }
  })
  if (open !== null) out[open].wide = true
  return out
}

// [{ id, label, icon, fields: [{ key, label, wide }] }] for the fields given, in display order.
export function groupFields(fields) {
  const byKey = new Map(fields.map((f) => [f.key, f]))
  const known = new Set(GROUPS.flatMap((g) => g.keys))
  const groups = GROUPS.map((g) => ({ ...g, fields: g.keys.filter((k) => byKey.has(k)).map((k) => byKey.get(k)) }))
  groups.push({ ...OTHER, fields: fields.filter((f) => !known.has(f.key)) })
  return groups.filter((g) => g.fields.length).map((g) => ({ ...g, fields: layout(g.fields) }))
}
