import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { MARKET_COORDS } from '../../constants/marketCoords.js'

// A real map (Leaflet + OpenStreetMap tiles — free, no API key) — this app has no Maps
// API key/billing set up, so exact street-level geocoding per business isn't available.
// Markers are placed at each profile's real market center, then jittered deterministically
// so multiple results in the same city don't stack exactly on top of each other.
const DEFAULT_CENTER = [39.8283, -98.5795] // continental US center, used only if no results resolve

function jitter(id, salt) {
  const n = (id * 2654435761 + salt * 40503) % 1000
  return (Math.abs(n) % 1000) / 1000 - 0.5 // -0.5..0.5
}

function pinIcon(isPro) {
  return L.divIcon({
    className: '',
    html: `<div style="
      width: 22px; height: 22px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg);
      background: ${isPro ? '#6d28d9' : '#111827'}; border: 2px solid #fff;
      box-shadow: 0 1px 3px rgba(0,0,0,0.35);
    "></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 22],
    popupAnchor: [0, -22],
  })
}

function MapPlaceholder({ results }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef([])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    mapRef.current = L.map(containerRef.current, { scrollWheelZoom: false }).setView(DEFAULT_CENTER, 4)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(mapRef.current)

    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []

    const points = []
    for (const r of results) {
      const center = MARKET_COORDS[r.location]
      if (!center) continue // unknown market — skip rather than guess a location
      const lat = center[0] + jitter(r.id, 1) * 0.12
      const lng = center[1] + jitter(r.id, 2) * 0.12
      const marker = L.marker([lat, lng], { icon: pinIcon(r.is_pro) })
        .addTo(map)
        .bindPopup(`<strong>${r.name}</strong><br/>${r.business_name || ''}<br/>${r.location}`)
      markersRef.current.push(marker)
      points.push([lat, lng])
    }

    if (points.length > 0) {
      map.fitBounds(points, { padding: [30, 30], maxZoom: 12 })
    } else {
      map.setView(DEFAULT_CENTER, 4)
    }
  }, [results])

  return (
    <div
      ref={containerRef}
      style={{
        position: 'sticky',
        top: 16,
        width: 320,
        height: 480,
        borderRadius: 'var(--radius)',
        border: '1px solid var(--border)',
        overflow: 'hidden',
        flexShrink: 0,
      }}
    />
  )
}

export default MapPlaceholder
