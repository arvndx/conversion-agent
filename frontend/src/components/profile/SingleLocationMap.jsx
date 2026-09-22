import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { MARKET_COORDS } from '../../constants/marketCoords.js'

function pinIcon() {
  return L.divIcon({
    className: '',
    html: `<div style="
      width: 26px; height: 26px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg);
      background: #6d28d9; border: 2px solid #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.35);
    "></div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 26],
  })
}

// Single-business version of the search page's real map — same real market-center
// coordinates (no Maps API key/billing in this app, so no exact street geocoding).
function SingleLocationMap({ location, height = 140 }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)

  useEffect(() => {
    const center = MARKET_COORDS[location]
    if (!containerRef.current || !center) return

    mapRef.current = L.map(containerRef.current, {
      scrollWheelZoom: false,
      dragging: false,
      zoomControl: false,
      attributionControl: true,
    }).setView(center, 12)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(mapRef.current)
    L.marker(center, { icon: pinIcon() }).addTo(mapRef.current)

    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [location])

  const center = MARKET_COORDS[location]
  if (!center) {
    // Unknown market — no real coordinates to show rather than guessing a location.
    return (
      <div
        style={{
          height,
          borderRadius: 8,
          background: 'var(--surface-muted)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--ink-soft)',
          fontSize: 12,
        }}
      >
        Map unavailable for this location
      </div>
    )
  }

  return <div ref={containerRef} style={{ height, borderRadius: 8, overflow: 'hidden' }} />
}

export default SingleLocationMap
