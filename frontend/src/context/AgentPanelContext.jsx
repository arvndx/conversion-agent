import { createContext, useContext, useState } from 'react'

// Lifted out of AgentWidget so the rest of the app can react to the panel's open state —
// specifically, so routed page content can shrink to make room for it instead of the panel
// just floating on top and covering whatever happens to be underneath.
export const AGENT_PANEL_WIDTH_CSS = 'clamp(340px, 25%, 460px)'

const AgentPanelContext = createContext(null)

export function AgentPanelProvider({ children }) {
  const [open, setOpen] = useState(false)
  return <AgentPanelContext.Provider value={{ open, setOpen }}>{children}</AgentPanelContext.Provider>
}

export function useAgentPanel() {
  return useContext(AgentPanelContext)
}
