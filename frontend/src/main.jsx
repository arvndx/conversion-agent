import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/tokens.css'
import './index.css'
import App from './App.jsx'
import { ActiveProfileProvider } from './context/ActiveProfileContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <ActiveProfileProvider>
        <App />
      </ActiveProfileProvider>
    </BrowserRouter>
  </StrictMode>,
)
