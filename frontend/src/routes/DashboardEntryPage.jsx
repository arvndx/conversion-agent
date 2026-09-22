import { Navigate } from 'react-router-dom'
import { useActiveProfile } from '../context/ActiveProfileContext.jsx'

const DEFAULT_PROFILE_ID = '2' // seeded claimed profile — used when no "viewing as" profile is remembered yet

function DashboardEntryPage() {
  const { activeProfileId } = useActiveProfile()
  return <Navigate to={`/dashboard/${activeProfileId || DEFAULT_PROFILE_ID}`} replace />
}

export default DashboardEntryPage
