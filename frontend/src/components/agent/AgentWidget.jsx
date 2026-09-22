import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import AgentPanel from './AgentPanel.jsx'
import CelebrationOverlay from './CelebrationOverlay.jsx'
import TourSpotlight from './TourSpotlight.jsx'
import useCurrentProfileId from './useCurrentProfileId.js'
import { greetAgent, resumeAfterHandoff, sendAgentMessage, startTourBatch } from '../../api/agent.js'
import { useAgentUIBridge } from '../../context/AgentUIBridgeContext.jsx'
import { useAgentPanel, AGENT_PANEL_WIDTH_CSS } from '../../context/AgentPanelContext.jsx'

const HIDDEN_ROUTES = ['/', '/search', '/inbox']
const POPUP_DURATION_MS = 10000

// Module scope, not component state: resets naturally on a hard page refresh
// (the whole module re-executes), but survives client-side route changes within
// the same load — so a route only gets greeted once per visit, not once ever.
const greetedThisLoad = new Set()

function AgentWidget() {
  const location = useLocation()
  const navigate = useNavigate()
  const profileId = useCurrentProfileId()
  const bridge = useAgentUIBridge()

  const { open, setOpen } = useAgentPanel()
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [celebrateTrigger, setCelebrateTrigger] = useState(0)
  const [hasUnread, setHasUnread] = useState(false)
  const [popup, setPopup] = useState(null) // { kind: 'text', text } | { kind: 'tour_offer' }
  const popupTimerRef = useRef(null)
  const [spotlight, setSpotlight] = useState(null) // { target, reason }
  const [tourProgress, setTourProgress] = useState(null) // { stepNumber, totalSteps, title }
  const [tourSteps, setTourSteps] = useState(null) // full pre-generated array, or null when no tour is loaded
  const [tourIndex, setTourIndex] = useState(0)
  const [doubtOpen, setDoubtOpen] = useState(false)
  const [preparingTour, setPreparingTour] = useState(false)
  const handoffTimerRef = useRef(null)
  const tourActiveRef = useRef(false)

  useEffect(() => {
    tourActiveRef.current = Boolean(tourProgress)
  }, [tourProgress])

  const route = location.pathname
  // /claim/:id/details now embeds its own dedicated agent UI (search, candidate picker,
  // paginated form with inline suggestions) — the floating widget would just duplicate it.
  const hidden = HIDDEN_ROUTES.includes(route) || route.startsWith('/claim/') || !profileId
  const latestRequestRef = useRef(null)

  useEffect(() => {
    // Page content reserves space for the panel based on `open` alone (see App.jsx) — if a
    // route where this widget renders nothing left `open` true from an earlier route, that
    // margin would be reserved for a panel that isn't actually there. Closing here keeps the
    // two in sync without RoutedContent needing to duplicate this component's own hidden logic.
    if (hidden) setOpen(false)
  }, [hidden])

  // This widget is mounted once at the app level and never unmounts on a client-side route
  // change (e.g. switching profiles via the "Viewing as" dropdown, no page reload) — without
  // this, every profile's conversation would just keep piling into the same message list.
  // Declared before the greeting effect below so, on the same profile switch, state is
  // cleared first and the fresh greeting lands in an empty list, not appended to the old one.
  // Guarded by a ref (not just the dependency array) for the same reason greetedThisLoad is
  // module state: React's dev-mode StrictMode double-invokes effects once on mount, and
  // without this guard the second invocation would wipe out the tour-offer/greeting the
  // first invocation had just added, since state itself isn't torn down between the two.
  const resetForProfileIdRef = useRef(null)
  useEffect(() => {
    if (resetForProfileIdRef.current === profileId) return
    resetForProfileIdRef.current = profileId
    setMessages([])
    setTourProgress(null)
    setTourSteps(null)
    setTourIndex(0)
    setSpotlight(null)
    setDoubtOpen(false)
    setPopup(null)
    setHasUnread(false)
    setPreparingTour(false)
  }, [profileId])

  function showTextPopup(text) {
    clearTimeout(popupTimerRef.current)
    setPopup({ kind: 'text', text })
    popupTimerRef.current = setTimeout(() => setPopup(null), POPUP_DURATION_MS)
  }

  function showTourOfferPopup() {
    clearTimeout(popupTimerRef.current)
    setPopup({ kind: 'tour_offer' })
    popupTimerRef.current = setTimeout(() => setPopup(null), POPUP_DURATION_MS)
  }

  // The plain contextual greeting (unreplied review, trial status, etc.) — used as the
  // first thing shown everywhere EXCEPT the dashboard-family routes, and as the fallback
  // there too once the tour offer is declined.
  function fetchAndShowGreeting() {
    const requestKey = `${profileId}:${route}`
    latestRequestRef.current = requestKey
    greetAgent(profileId, { route })
      .then((result) => {
        if (latestRequestRef.current !== requestKey || !result?.reply_text) return
        setMessages((prev) => [...prev, { role: 'assistant', text: result.reply_text }])
        applyUiActions(result.ui_actions)
        if (!open) {
          setHasUnread(true)
          showTextPopup(result.reply_text)
        }
      })
      .catch(() => {
        greetedThisLoad.delete(route) // let a later visit to this route retry
      })
  }

  useEffect(() => {
    if (hidden || greetedThisLoad.has(route)) return
    if (tourActiveRef.current) {
      // The tour just navigated here itself — its own explanation covers this page,
      // so a separate proactive greeting would just talk over it.
      greetedThisLoad.add(route)
      return
    }
    // Claimed synchronously — no network call needed for the tour offer itself, so there's
    // no StrictMode double-invoke race to guard against on this branch.
    greetedThisLoad.add(route)

    const justClaimed = new URLSearchParams(location.search).get('justClaimed') === '1'
    if (/^\/dashboard\/[^/]+\/manage$/.test(route) && justClaimed) {
      // Only auto-start (no offer) the moment right after claiming — Manage is where every
      // score-affecting lever lives, and someone who just finished the whole claim form
      // shouldn't also have to click "Sure" on an offer. Any other visit to Manage falls
      // through to the same offer-popup treatment as Dashboard/Profile below.
      startTour()
      return
    }

    if (route.startsWith('/dashboard/') || route.startsWith('/profile/')) {
      setMessages((prev) => [...prev, { role: 'assistant', kind: 'tour_offer', resolved: false }])
      if (!open) {
        setHasUnread(true)
        showTourOfferPopup()
      }
      return
    }

    // The claim flow keeps the plain greeting — the profile isn't claimed yet, so there's
    // no dashboard to tour.
    fetchAndShowGreeting()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId, route, hidden])

  useEffect(() => () => {
    clearTimeout(popupTimerRef.current)
    clearTimeout(handoffTimerRef.current)
  }, [])

  function openWidget() {
    clearTimeout(popupTimerRef.current)
    setPopup(null)
    setOpen(true)
    setHasUnread(false)
  }

  function resolveTourOffer() {
    setMessages((prev) => prev.map((m) => (m.kind === 'tour_offer' ? { ...m, resolved: true } : m)))
  }

  function applyTourStep(steps, index) {
    const step = steps[index]
    if (!step) return
    // Narration now renders in an anchored callout right next to the highlighted element
    // (see TourSpotlight), not as a chat message — it's a visual tour, not a conversation.
    setTourProgress({ stepNumber: step.step_number, totalSteps: step.total_steps, title: step.title, text: step.text, id: step.id })
    // The step names its own real page and element — structural, not something the model
    // has to remember to call — so the tour reliably lands on the right spot every time.
    if (step.route && step.route !== route) {
      greetedThisLoad.add(step.route) // don't let landing here trigger a separate greeting/offer
      navigate(step.route)
    }
    if (step.ui_target) {
      setSpotlight({ target: step.ui_target })
    }
  }

  async function startTour() {
    resolveTourOffer()
    openWidget()
    setDoubtOpen(false)
    setSending(true)
    setPreparingTour(true)
    try {
      const result = await startTourBatch(profileId, { route })
      if (result.error === 'not_claimed') {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', text: "This profile hasn't been claimed yet, so there's no dashboard to tour — want help claiming it instead?" },
        ])
        return
      }
      setTourSteps(result.steps)
      setTourIndex(0)
      applyTourStep(result.steps, 0)
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: "Sorry, I couldn't put the tour together just now. Try again in a moment." },
      ])
    } finally {
      setSending(false)
      setPreparingTour(false)
    }
  }

  function advanceLocalTour() {
    if (doubtOpen || !tourSteps) return
    const next = tourIndex + 1
    if (next >= tourSteps.length) {
      setTourSteps(null)
      setTourProgress(null)
      setTourIndex(0)
      setSpotlight(null) // finishing the tour should clear the highlight immediately, same as ending it early
      return
    }
    setTourIndex(next)
    applyTourStep(tourSteps, next)
  }

  // Lets the user bail out of an auto-started (or any in-progress) tour without
  // finishing every step — the tour still stops on the page/step it was on.
  function endTour() {
    setTourSteps(null)
    setTourProgress(null)
    setTourIndex(0)
    setDoubtOpen(false)
    setSpotlight(null)
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', text: "No problem, ending the tour here — ask me anytime if you'd like to pick it back up." },
    ])
  }

  function handleTourOfferSure() {
    startTour()
  }

  function handleTourOfferNotNow() {
    resolveTourOffer()
    setPopup(null)
    fetchAndShowGreeting()
  }

  // Returns true if this turn asked (via free text) to start the tour — callers await
  // their own in-flight request's sending-state before kicking that off, so the two
  // loading spinners never overlap/race each other.
  function applyUiActions(uiActions) {
    let shouldStartTour = false
    for (const action of uiActions || []) {
      if (action.type === 'highlight_ui') {
        // The tool itself resolves which page this target actually lives on — navigate there
        // first if that's not where we already are, so the highlight can never silently miss.
        if (action.result?.route && action.result.route !== route) {
          greetedThisLoad.add(action.result.route)
          navigate(action.result.route)
        }
        setSpotlight({ target: action.input?.target, reason: action.input?.reason })
      } else if (action.type === 'navigate_to' && action.result?.path) {
        // The agent is navigating mid-conversation for a reason it already gave — treat the
        // destination as already greeted, or the proactive greeting/tour-offer would fire a
        // second, unrelated popup the moment we land there.
        greetedThisLoad.add(action.result.path)
        navigate(action.result.path)
      } else if (action.type === 'celebrate') {
        setCelebrateTrigger((n) => n + 1)
      } else if (action.type === 'start_tour') {
        shouldStartTour = true
      } else if (action.type === 'record_doubt_attempt') {
        setDoubtOpen(!action.result?.resolved)
      } else if (action.type === 'escalate_unresolved_doubt') {
        handleSimulatedHandoff(action.result)
      } else if (action.type === 'confirm_website_url' || action.type === 'present_candidate_matches' || action.type === 'propose_field_updates') {
        // Claim-assist-only UI actions — handled entirely by the dedicated /claim/:id/details
        // page itself now, which this widget never mounts on. Nothing to do here.
      } else if (action.type === 'propose_review_reply' && action.input?.review_id) {
        // The bridge is a single handler slot per key — with multiple unreplied reviews on
        // screen, every ReviewRow would register under the same literal 'propose_review_reply'
        // key and silently overwrite each other, so only the last-mounted row ever received
        // updates. Routing by a per-review key fixes that structurally.
        bridge?.call(`propose_review_reply:${action.input.review_id}`, action)
      } else {
        bridge?.call(action.type, action)
      }
    }
    return shouldStartTour
  }

  function handleSimulatedHandoff(result) {
    const waitSeconds = result?.simulated_wait_seconds ?? 6
    setMessages((prev) => [
      ...prev,
      { role: 'system', text: `Simulated: connecting you with a specialist about "${result?.topic}"…` },
    ])
    clearTimeout(handoffTimerRef.current)
    handoffTimerRef.current = setTimeout(async () => {
      try {
        const resumeResult = await resumeAfterHandoff(profileId, { route })
        setDoubtOpen(false)
        if (resumeResult?.reply_text) {
          setMessages((prev) => [...prev, { role: 'assistant', text: resumeResult.reply_text }])
          applyUiActions(resumeResult.ui_actions)
        }
      } catch {
        setMessages((prev) => [
          ...prev,
          { role: 'system', text: 'Simulated specialist follow-up failed to load — try asking again.' },
        ])
      }
    }, waitSeconds * 1000)
  }

  async function onSend(text) {
    setMessages((prev) => [...prev, { role: 'user', text }])
    setSending(true)
    let shouldStartTour = false
    try {
      const result = await sendAgentMessage(profileId, text, { route })
      setMessages((prev) => [...prev, { role: 'assistant', text: result.reply_text }])
      shouldStartTour = applyUiActions(result.ui_actions)
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: "Sorry, I couldn't reach the assistant just now. Try again in a moment." },
      ])
    } finally {
      setSending(false)
    }
    // Started only after this turn's own loading state has fully settled, so the two
    // "sending" cycles (this reply, then the tour batch) never visually overlap.
    if (shouldStartTour) {
      await startTour()
    }
  }

  useEffect(() => {
    if (!bridge) return
    return bridge.register('open_and_send', ({ message }) => {
      setOpen(true)
      onSend(message)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bridge, profileId, route])

  if (hidden) return null

  return (
    <>
      <CelebrationOverlay trigger={celebrateTrigger} />

      {open && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            right: 0,
            bottom: 0,
            width: AGENT_PANEL_WIDTH_CSS,
            background: '#fafafa',
            borderLeft: '1px solid var(--border)',
            boxShadow: '-8px 0 32px rgba(16,24,40,0.08)',
            zIndex: 1000,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            animation: 'agent-panel-slide-in 0.2s ease',
          }}
        >
          <div
            style={{
              background: tourProgress ? 'linear-gradient(135deg, #6d28d9, var(--brand))' : '#fff',
              borderBottom: tourProgress ? 'none' : '1px solid var(--border)',
              color: tourProgress ? '#fff' : 'var(--ink)',
              padding: '14px 18px',
              fontWeight: 700,
              fontSize: 14,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexShrink: 0,
              transition: 'background 0.3s ease',
            }}
          >
            {tourProgress ? (
              // Step title is intentionally left out here — the anchored callout right next
              // to the highlighted element already shows it, so repeating it in the header
              // was both redundant and the exact thing that used to overflow/clip this bar.
              <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                🧭 Guided Tour
                <span style={{ fontWeight: 500, fontSize: 11.5, opacity: 0.85, marginLeft: 6 }}>
                  · Step {tourProgress.stepNumber}/{tourProgress.totalSteps}
                </span>
              </span>
            ) : (
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <span
                  style={{
                    width: 24,
                    height: 24,
                    flexShrink: 0,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #6d28d9, var(--brand))',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 12,
                  }}
                >
                  ✨
                </span>
                Profile Pilot
              </span>
            )}
            <button
              onClick={() => setOpen(false)}
              aria-label="Close assistant"
              style={{
                background: 'none',
                border: 'none',
                color: tourProgress ? '#fff' : 'var(--ink-soft)',
                cursor: 'pointer',
                fontSize: 15,
                flexShrink: 0,
                marginLeft: 8,
              }}
            >
              ✕
            </button>
          </div>
          <div style={{ flex: 1, minHeight: 0 }}>
            <AgentPanel
              messages={messages}
              sending={sending}
              onSend={onSend}
              route={route}
              tourProgress={tourProgress}
              onTourOfferSure={handleTourOfferSure}
              onTourOfferNotNow={handleTourOfferNotNow}
              onStartTour={startTour}
              preparingTour={preparingTour}
            />
          </div>
        </div>
      )}

      {spotlight && (
        <TourSpotlight
          target={spotlight.target}
          reason={spotlight.reason}
          tourStep={tourProgress}
          doubtOpen={doubtOpen}
          onNext={advanceLocalTour}
          onEnd={endTour}
          onDone={() => setSpotlight(null)}
        />
      )}

      {!open && popup?.kind === 'tour_offer' && (
        <div
          style={{
            position: 'fixed',
            bottom: 90,
            right: 24,
            maxWidth: 270,
            background: 'linear-gradient(135deg, #f5f3ff, #eef2ff)',
            borderRadius: 14,
            boxShadow: '0 12px 32px rgba(109, 40, 217, 0.22)',
            border: '1px solid #ddd6fe',
            padding: '14px',
            fontSize: 13,
            lineHeight: 1.4,
            zIndex: 1000,
            animation: 'agent-popup-in 0.25s ease',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 20 }}>🧭</span>
            <div style={{ fontWeight: 700, color: 'var(--ink)' }}>Take a quick tour?</div>
          </div>
          <div style={{ marginBottom: 10, color: 'var(--ink-soft)' }}>
            See exactly what's boosting — or blocking — your visibility, step by step.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={handleTourOfferSure}
              style={{
                flex: 1,
                background: 'var(--brand)',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                padding: '7px 0',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Sure →
            </button>
            <button
              onClick={handleTourOfferNotNow}
              style={{
                flex: 1,
                background: '#fff',
                color: 'var(--ink)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '7px 0',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Not now
            </button>
          </div>
        </div>
      )}

      {!open && popup?.kind === 'text' && (
        <div
          onClick={openWidget}
          style={{
            position: 'fixed',
            bottom: 90,
            right: 24,
            maxWidth: 260,
            background: '#fff',
            borderRadius: 12,
            boxShadow: '0 12px 32px rgba(0,0,0,0.18)',
            border: '1px solid var(--border)',
            padding: '10px 12px',
            fontSize: 13,
            lineHeight: 1.4,
            cursor: 'pointer',
            zIndex: 1000,
          }}
        >
          {popup.text}
        </div>
      )}

      {/* Hidden while the panel is open — it already has its own ✕ close button in the
          header, so this floating launcher would just sit redundantly on top of it now
          that the panel is a full-height dock rather than a small corner box. */}
      {!open && (
        <button
          onClick={openWidget}
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            width: 56,
            height: 56,
            borderRadius: '50%',
            background: 'var(--brand)',
            color: '#fff',
            border: 'none',
            fontSize: 22,
            cursor: 'pointer',
            boxShadow: '0 6px 16px rgba(0,0,0,0.25)',
            zIndex: 1000,
          }}
          aria-label="Open assistant"
        >
          💬
          {hasUnread && (
            <span
              style={{
                position: 'absolute',
                top: 2,
                right: 2,
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: '#ef4444',
                border: '2px solid #fff',
              }}
            />
          )}
        </button>
      )}
    </>
  )
}

export default AgentWidget
