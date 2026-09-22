import { createContext, useCallback, useContext, useRef } from 'react'

// Lets the one globally-mounted AgentWidget reach into whichever page is
// currently active (e.g. filling a form field) without prop-drilling the
// widget through every route. Pages register a handler on mount; the widget
// calls it by key when a matching UI action comes back from the agent.
const AgentUIBridgeContext = createContext(null)

export function AgentUIBridgeProvider({ children }) {
  const handlers = useRef({})

  const register = useCallback((key, fn) => {
    handlers.current[key] = fn
    return () => {
      if (handlers.current[key] === fn) delete handlers.current[key]
    }
  }, [])

  const call = useCallback((key, payload) => {
    const fn = handlers.current[key]
    if (fn) fn(payload)
  }, [])

  return <AgentUIBridgeContext.Provider value={{ register, call }}>{children}</AgentUIBridgeContext.Provider>
}

export function useAgentUIBridge() {
  return useContext(AgentUIBridgeContext)
}
