// The assistant's one action button, so every call to action keeps the same weight and shape.
function PilotAction({ children, onClick, disabled, variant = 'primary', type = 'button', style }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`pilot-action${variant === 'quiet' ? ' pilot-action--quiet' : ''}`}
      style={style}
    >
      {children}
    </button>
  )
}

export default PilotAction
