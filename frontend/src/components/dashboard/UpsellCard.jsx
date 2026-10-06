function UpsellCard({ card, onUnlock }) {
  const [headline, subtext] = card.copy.split(' — ')

  return (
    <div className="upsell" data-agent-target={`upsell-${card.key}`}>
      <h4>{headline}</h4>
      {subtext && <p>{subtext}</p>}
      <button onClick={onUnlock} className="btn btn--pro btn--sm">👑 UNLOCK MORE POINTS</button>
    </div>
  )
}

export default UpsellCard
