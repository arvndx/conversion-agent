import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import SearchPage from './routes/SearchPage.jsx'
import ProfileDetailPage from './routes/ProfileDetailPage.jsx'
import DashboardPage from './routes/DashboardPage.jsx'
import DashboardEntryPage from './routes/DashboardEntryPage.jsx'
import ManageProfilePage from './routes/ManageProfilePage.jsx'
import MailboxPage from './routes/MailboxPage.jsx'
import SignInPage from './routes/SignInPage.jsx'
import OnboardingPage from './routes/OnboardingPage.jsx'
import NotFoundPage from './routes/NotFoundPage.jsx'
import PricingPage from './routes/PricingPage.jsx'
import AgentWidget from './components/agent/AgentWidget.jsx'
import { AgentUIBridgeProvider } from './context/AgentUIBridgeContext.jsx'
import { useAuth } from './context/AuthContext.jsx'
import { AgentPanelProvider, AGENT_PANEL_WIDTH_CSS, useAgentPanel } from './context/AgentPanelContext.jsx'

// Shrinks the routed page content to make room for the docked assistant panel when it's
// open, instead of the panel floating on top and covering whatever's underneath (which is
// exactly what used to hide tour-highlighted elements sitting in the right 25% of a page).
// Owner pages (dashboard, manage, upgrade) are for a finished profile: an owner who claimed but did not finish
// onboarding is sent back to it, however they got here (a bookmark, a typed address).
function OnboardedOnly({ children }) {
  const { profileId } = useParams()
  const { me } = useAuth()
  const unfinished = me?.authenticated && String(me.profile_id) === String(profileId) && me.onboarding_completed === false
  return unfinished ? <Navigate to={`/onboarding/${profileId}`} replace /> : children
}

function RoutedContent() {
  const { open } = useAgentPanel()
  return (
    <div style={{ marginRight: open ? AGENT_PANEL_WIDTH_CSS : 0, transition: 'margin-right 0.2s ease' }}>
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/profile/:id" element={<ProfileDetailPage />} />
        <Route path="/dashboard" element={<DashboardEntryPage />} />
        <Route path="/dashboard/:profileId" element={<OnboardedOnly><DashboardPage /></OnboardedOnly>} />
        <Route path="/dashboard/:profileId/manage" element={<OnboardedOnly><ManageProfilePage /></OnboardedOnly>} />
        <Route path="/dashboard/:profileId/upgrade" element={<OnboardedOnly><PricingPage /></OnboardedOnly>} />
        <Route path="/signin" element={<SignInPage />} />
        <Route path="/mailbox" element={<MailboxPage />} />
        <Route path="/mailbox/:email" element={<MailboxPage />} />
        <Route path="/onboarding/:id" element={<OnboardingPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </div>
  )
}

function App() {
  return (
    <AgentUIBridgeProvider>
      <AgentPanelProvider>
        <RoutedContent />
        <AgentWidget />
      </AgentPanelProvider>
    </AgentUIBridgeProvider>
  )
}

export default App
