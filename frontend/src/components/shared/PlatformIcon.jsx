// A small coloured tile for a social network or directory, so rows are recognisable at a glance.
const BRANDS = [
  [/google/, '#ea4335', 'G'],
  [/facebook/, '#1877f2', 'f'],
  [/linkedin/, '#0a66c2', 'in'],
  [/twitter|^x$/, '#111827', '𝕏'],
  [/instagram/, 'linear-gradient(135deg, #f58529, #dd2a7b 55%, #8134af)', '◎'],
  [/zillow/, '#006aff', 'Z'],
  [/realtor/, '#d92228', 'R'],
  [/homes/, '#00a4e4', 'H'],
  [/yelp/, '#d32323', 'y'],
  [/lendingtree/, '#0e9f6e', 'L'],
  [/trusted/, '#0b4f9c', 'T'],
  [/healthgrades/, '#f26b21', 'h'],
]

function PlatformIcon({ name }) {
  const key = String(name || '').toLowerCase()
  const hit = BRANDS.find(([re]) => re.test(key))
  const [, background, glyph] = hit || [null, '#8b93a7', key.charAt(0).toUpperCase() || '•']
  return <span className="platform-icon" style={{ background }} aria-hidden="true">{glyph}</span>
}

export default PlatformIcon
