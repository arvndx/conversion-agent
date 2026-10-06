import { useState } from 'react'

function PromoBanner() {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  return (
    <div className="promo-banner">
      <strong>The Next Era of Search Has Arrived</strong>
      <span className="promo-banner__text">Customers are searching right now. Don&apos;t get left out of the AI answers.</span>
      <button className="promo-banner__cta">Learn about AI Visibility →</button>
      <span className="promo-banner__by">powered by VOCE</span>
      <button className="promo-banner__x" onClick={() => setDismissed(true)} aria-label="Dismiss">✕</button>
    </div>
  )
}

export default PromoBanner
