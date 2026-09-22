import { Route, Routes } from 'react-router-dom'
import SearchPage from './routes/SearchPage.jsx'
import ProfileDetailPage from './routes/ProfileDetailPage.jsx'
import DashboardPage from './routes/DashboardPage.jsx'
import DashboardEntryPage from './routes/DashboardEntryPage.jsx'
import ManageProfilePage from './routes/ManageProfilePage.jsx'
import MockInboxPage from './routes/MockInboxPage.jsx'
import ClaimDetailsPage from './routes/ClaimDetailsPage.jsx'
import PricingPage from './routes/PricingPage.jsx'
import AgentWidget from './components/agent/AgentWidget.jsx'
import { AgentUIBridgeProvider } from './context/AgentUIBridgeContext.jsx'
import { AgentPanelProvider, AGENT_PANEL_WIDTH_CSS, useAgentPanel } from './context/AgentPanelContext.jsx'

// Shrinks the routed page content to make room for the docked assistant panel when it's
// open, instead of the panel floating on top and covering whatever's underneath (which is
// exactly what used to hide tour-highlighted elements sitting in the right 25% of a page).
function RoutedContent() {
  const { open } = useAgentPanel()
  return (
    <div style={{ marginRight: open ? AGENT_PANEL_WIDTH_CSS : 0, transition: 'margin-right 0.2s ease' }}>
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/profile/:id" element={<ProfileDetailPage />} />
        <Route path="/dashboard" element={<DashboardEntryPage />} />
        <Route path="/dashboard/:profileId" element={<DashboardPage />} />
        <Route path="/dashboard/:profileId/manage" element={<ManageProfilePage />} />
        <Route path="/dashboard/:profileId/upgrade" element={<PricingPage />} />
        <Route path="/inbox" element={<MockInboxPage />} />
        <Route path="/claim/:id/details" element={<ClaimDetailsPage />} />
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
