import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/tokens.css'
import './styles/pilot.css'
import './styles/onboarding.css'
import './styles/fields.css'
import './styles/app.css'
import './index.css'
import App from './App.jsx'
import { ActiveProfileProvider } from './context/ActiveProfileContext.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { ClaimCardProvider } from './components/claim/ClaimCard.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <ActiveProfileProvider>
        <AuthProvider>
          <ClaimCardProvider>
            <App />
          </ClaimCardProvider>
        </AuthProvider>
      </ActiveProfileProvider>
    </BrowserRouter>
  </StrictMode>,
)
