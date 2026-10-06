import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import CelebrationOverlay from '../components/agent/CelebrationOverlay.jsx'
import PilotChatPanel from '../components/pilot/PilotChatPanel.jsx'
import AgentVoice from '../components/onboarding/AgentVoice.jsx'
import ConflictScene from '../components/onboarding/ConflictScene.jsx'
import DoneScene from '../components/onboarding/DoneScene.jsx'
import FieldsScene from '../components/onboarding/FieldsScene.jsx'
import IdentityScene from '../components/onboarding/IdentityScene.jsx'
import LinkScene from '../components/onboarding/LinkScene.jsx'
import OnboardingProgress from '../components/onboarding/OnboardingProgress.jsx'
import ReadingScene from '../components/onboarding/ReadingScene.jsx'
import UrlScene from '../components/onboarding/UrlScene.jsx'
import { useOnboarding } from '../components/onboarding/useOnboarding.js'
import { useOnboardingAgent } from '../components/onboarding/useOnboardingAgent.js'
import { useAuth } from '../context/AuthContext.jsx'
import '../styles/claim.css'

// What the owner's click tells the agent, so it carries on from the state the server already holds.
const SAY = {
  urls: "I've answered the cards for the pages I recognise.",
  noneMine: 'None of these are mine. Please search the web for my pages.',
  searchMore: 'Please search the web for more of my pages.',
  identity: "I've answered the questions about those pages.",
  conflicts: "I've chosen for each difference.",
  resume: 'Please continue.',
  draft: 'Please draft my description and specialities.',
  finish: 'That all looks right — please finish.',
  done: 'I am all set up. Please tell me my score and what to do next.',
  read: 'My pages have been read. Please continue.',
  more: 'I confirmed more pages. Please read them.',
}

const READ_STATUSES = ['scraping', 'done', 'blocked', 'failed', 'needs_identity']

// Which single thing the owner should be looking at. Anything waiting on them always comes before the reading board:
// a page to confirm, then (once reading has started) a link to a site we do not read, then a page whose owner is
// unclear, then a difference between pages. The board (progress and what each page gave) is shown only when nothing
// is waiting on them. A clean finish needs no details form.
const READ_DONE = ['done', 'blocked', 'failed', 'needs_identity']
const has = (data, ...statuses) => data.sources.some((s) => statuses.includes(s.status))
const pendingLinks = (data) => (data.link_only || []).filter((l) => l.url && !l.confirmed)
// Reading starts by itself once every page card is answered, so confirmed pages with nothing left to ask count as reading
// (unless starting it failed, when the owner is offered a retry).
const isReading = (data, readFailed) => has(data, 'scraping') || (has(data, 'confirmed') && !has(data, 'proposed') && !readFailed)
const isClean = (data) => !data.completed && data.stage === 'fields' && data.blockers.length === 0 && has(data, 'done')

function sceneFor(data, { finishing, readFailed }) {
  if (data.completed) return 'completed'
  const reading = isReading(data, readFailed)
  const started = reading || has(data, ...READ_STATUSES)
  if (has(data, 'proposed')) return 'urls'
  if (!started && ['no_urls', 'confirm_urls', 'ready_to_scrape'].includes(data.stage)) return 'urls'
  if (started && pendingLinks(data).length > 0) return 'links'
  if (has(data, 'needs_identity')) return 'identity'
  if (data.conflicts.some((c) => c.status === 'open')) return 'conflicts'
  if (reading) return 'board'
  if (has(data, 'confirmed')) return 'urls' // starting the reading failed: offer a retry
  if (data.stage === 'fields' && !has(data, ...READ_STATUSES)) return 'urls'
  if (data.stage === 'fields' && !finishing) return 'fields'
  return 'board'
}

function Header({ name }) {
  return (
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 24px', background: '#fff', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
      <Link to="/" style={{ fontWeight: 800, fontSize: 18, color: 'var(--brand)' }}>ClearRank</Link>
      <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{name ? `Setting up ${name}` : 'Setting up your profile'}</span>
    </header>
  )
}

function Notice({ title, children }) {
  return (
    <div className="claim-card" style={{ maxWidth: 520, margin: '60px auto', textAlign: 'center' }}>
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      <p style={{ color: 'var(--ink-soft)', lineHeight: 1.6 }}>{children}</p>
    </div>
  )
}

function OnboardingPage() {
  const { id } = useParams()
  const profileId = Number(id)
  const onboarding = useOnboarding(profileId)
  const { data, error, failed, refresh, clearError } = onboarding
  const agent = useOnboardingAgent(profileId, () => refresh().catch(() => {}), Boolean(data) && !data.completed)
  const { refresh: refreshAccount } = useAuth()
  const completed = Boolean(data?.completed)

  // Finishing onboarding changes the account (it is no longer "unfinished"): refresh it, or the dashboard would
  // send them straight back here.
  useEffect(() => {
    if (completed) refreshAccount()
  }, [completed, refreshAccount])

  const agentBusy = agent.sending
  const [searchFlag, setSearchFlag] = useState(false)
  const [readFailed, setReadFailed] = useState(false) // starting the reading was refused or failed
  const readBusy = useRef(false)
  const [finishState, setFinishState] = useState('idle') // idle | busy | failed
  const announced = useRef(null) // ids of finished pages the agent has been told about

  // A clean finish (something was read, nothing is waiting on the owner): the page saves it straight away (a plain
  // database write, well under a second) and then asks the agent to talk them through the score.
  const clean = Boolean(data) && isClean(data)
  const finishing = clean && finishState !== 'failed'
  const reading = Boolean(data) && isReading(data, readFailed)
  const scene = data ? sceneFor(data, { finishing, readFailed }) : null
  const searching = searchFlag || (agentBusy && data?.stage === 'no_urls')

  // The agent's latest words, if it spoke after the owner's last action: shown on the main screen, not only in the chat.
  const voice = (() => {
    for (let i = agent.messages.length - 1; i >= 0; i -= 1) {
      const m = agent.messages[i]
      if (m.role === 'user') return null
      if (m.role === 'assistant') return m.text
    }
    return null
  })()

  // As soon as the last page card is answered, start reading the confirmed pages: no button, no agent round trip.
  useEffect(() => {
    if (!data || data.completed || readFailed || readBusy.current) return
    if (!has(data, 'confirmed') || has(data, 'proposed')) return
    readBusy.current = true
    onboarding.read().then((result) => { if (!result) setReadFailed(true) }).finally(() => { readBusy.current = false })
  }, [data, readFailed]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reading happens in the background, so poll while it runs (not only while the agent is mid-turn).
  useEffect(() => {
    if (!reading) return undefined
    const timer = setInterval(() => refresh().catch(() => {}), 1500)
    return () => clearInterval(timer)
  }, [reading, refresh])

  // When the last page finishes, tell the agent once so it carries on (merge, and the conflicts it finds).
  useEffect(() => {
    if (!data || data.completed || agent.sending) return
    const finished = data.sources.filter((s) => READ_DONE.includes(s.status)).map((s) => s.id)
    if (announced.current === null) { // first look at the data: pages read before this page opened are not news
      announced.current = new Set(['merge', 'identity'].includes(data.stage) ? [] : finished)
    }
    const fresh = finished.filter((id) => !announced.current.has(id))
    if (reading || fresh.length === 0 || !['merge', 'identity'].includes(data.stage)) return
    fresh.forEach((id) => announced.current.add(id))
    agent.send(SAY.read)
  }, [data, reading, agent])

  async function finishNow() {
    setFinishState('busy')
    const result = await onboarding.complete()
    if (!result) {
      setFinishState('failed') // refused (something is still open): the details form shows what
      return
    }
    await refresh().catch(() => {})
    agent.send(SAY.done)
  }

  useEffect(() => {
    if (clean && finishState === 'idle' && !agent.sending) finishNow()
  }, [clean, finishState, agent.sending]) // eslint-disable-line react-hooks/exhaustive-deps

  const retryRead = () => setReadFailed(false)

  function searchMore() {
    setSearchFlag(true)
    return agent.send(SAY.searchMore).finally(() => setSearchFlag(false))
  }
  const saveLink = (platform, url) => onboarding.setLink(platform, url)

  if (failed) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--pilot-surface)' }}>
        <Header />
        <Notice title="We can't open onboarding">
          {failed.message} <Link to={`/profile/${profileId}`} style={{ color: 'var(--brand)', fontWeight: 700 }}>Go to the profile</Link>
        </Notice>
      </div>
    )
  }

  async function answerIdentity(sourceId, isMine) {
    const next = await onboarding.identity(sourceId, isMine)
    if (next && !next.sources.some((s) => s.status === 'needs_identity')) agent.send(SAY.identity)
  }
  async function settle(conflictId, resolution) {
    const next = await onboarding.resolve(conflictId, resolution)
    if (next && !next.conflicts.some((c) => c.status === 'open') && !isClean(next)) agent.send(SAY.conflicts) // a clean state finishes by itself
  }
  async function saveField(key, value) {
    await onboarding.saveFields({ [key]: value })
  }
  async function useDraft(key, value) {
    if (await onboarding.saveFields({ [key]: value })) agent.dropDraft(key)
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--pilot-surface)' }}>
      <Header name={data?.profile.name} />
      <CelebrationOverlay trigger={agent.celebrate} />
      <div className="pilot-layout">
        <main className="ob-main">
          <div className={`ob-col${scene === 'completed' ? ' ob-col--wide' : ''}`}>
            {!data && <div className="pilot-shimmer" style={{ height: 120 }} />}
            {data && (
              <>
                {scene !== 'completed' && <OnboardingProgress profile={data.profile} category={data.category} stage={scene} />}
                {error && (
                  <div className="ob-error" role="alert" style={{ marginBottom: 8 }}>
                    ⚠ {error} <button className="ob-link" onClick={clearError}>Dismiss</button>
                  </div>
                )}
                {voice && !['completed', 'links', 'board'].includes(scene) && <AgentVoice text={voice} />}
                <div className={voice && !['links', 'board'].includes(scene) ? 'ob-voiced' : undefined}>
                  {scene === 'urls' && (
                    <UrlScene data={data} agentBusy={agentBusy} searching={searching} onDecide={onboarding.decide} onAdd={onboarding.addUrl}
                      readFailed={readFailed} onRetry={retryRead} onSearch={searchMore} />
                  )}
                  {scene === 'links' && (() => {
                    const items = pendingLinks(data)
                    return <LinkScene item={items[0]} index={1} total={items.length} busy={false} onSave={saveLink} />
                  })()}
                  {scene === 'board' && <ReadingScene data={data} agentBusy={agentBusy} searching={searching} finishing={finishing} onSearch={searchMore} onAdd={onboarding.addUrl} />}
                  {scene === 'identity' && <IdentityScene data={data} agentBusy={agentBusy} onAnswer={answerIdentity} />}
                  {scene === 'conflicts' && <ConflictScene data={data} agentBusy={agentBusy} onResolve={settle} />}
                  {scene === 'fields' && (
                    <FieldsScene data={data} drafts={agent.drafts} agentBusy={agentBusy} onSave={saveField} onSaveLink={saveLink} onUseDraft={useDraft}
                      onAskDraft={() => agent.send(SAY.draft)} onFinish={finishNow} />
                  )}
                  {scene === 'completed' && <DoneScene profileId={profileId} name={data.profile.name} location={data.profile.location} voice={voice} />}
                </div>
              </>
            )}
          </div>
        </main>
        <PilotChatPanel
          messages={agent.messages}
          sending={agent.sending}
          onSend={agent.send}
          placeholder="Ask me anything…"
          emptyText="I'll help you set up your profile. Ask me anything along the way."
          suggestions={['What will you do with my pages?', 'Can I skip a step?']}
        />
      </div>
    </div>
  )
}

export default OnboardingPage
