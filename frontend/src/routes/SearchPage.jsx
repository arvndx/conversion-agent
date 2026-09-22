import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import TopNav from '../components/layout/TopNav.jsx'
import Breadcrumb from '../components/layout/Breadcrumb.jsx'
import FiltersPanel from '../components/search/FiltersPanel.jsx'
import ResultCard from '../components/search/ResultCard.jsx'
import SortDropdown from '../components/search/SortDropdown.jsx'
import MapPlaceholder from '../components/search/MapPlaceholder.jsx'
import ScarcityBanner from '../components/search/ScarcityBanner.jsx'
import { getSearchFilters, searchProfiles } from '../api/search.js'

function SearchPage() {
  const [searchParams] = useSearchParams()
  const keyword = searchParams.get('keyword') || ''
  const initialLocation = searchParams.get('location') || ''

  const [filters, setFilters] = useState({ categories: [], locations: [], services: [], pro_slots_per_market: 5 })
  const [category, setCategory] = useState('')
  const [location, setLocation] = useState(initialLocation)
  const [service, setService] = useState('')
  const [minRating, setMinRating] = useState(0)
  const [minScore, setMinScore] = useState(0)
  const [sort, setSort] = useState('score')
  const [results, setResults] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSearchFilters().then(setFilters)
  }, [])

  useEffect(() => {
    setLoading(true)
    searchProfiles({ category, location, service, minRating, minScore, sort })
      .then((data) => {
        setResults(data.results)
        setCount(data.count)
      })
      .finally(() => setLoading(false))
  }, [category, location, service, minRating, minScore, sort])

  function onFilterChange(patch) {
    if ('category' in patch) setCategory(patch.category)
    if ('location' in patch) setLocation(patch.location)
    if ('service' in patch) setService(patch.service)
    if ('minRating' in patch) setMinRating(patch.minRating)
    if ('minScore' in patch) setMinScore(patch.minScore)
  }

  function onClear() {
    setCategory('')
    setLocation('')
    setService('')
    setMinRating(0)
    setMinScore(0)
  }

  const title = keyword || category || 'Professionals'
  const proTaken = results.filter((r) => r.is_pro).length

  return (
    <div>
      <TopNav initialKeyword={keyword} initialLocation={location} />
      <Breadcrumb
        items={[{ label: 'Search', to: '/search' }, { label: 'Professional Services' }, { label: 'Results' }]}
      />

      <div style={{ display: 'flex', gap: 24, padding: '0 24px 40px', maxWidth: 1280, margin: '0 auto' }}>
        <FiltersPanel
          categories={filters.categories}
          locations={filters.locations}
          services={filters.services}
          selectedCategory={category}
          selectedLocation={location}
          selectedService={service}
          minRating={minRating}
          minScore={minScore}
          onChange={onFilterChange}
          onClear={onClear}
        />

        <main style={{ flex: 1, minWidth: 0 }}>
          {!loading && location && (
            <ScarcityBanner
              location={location}
              category={category || title}
              proTaken={proTaken}
              proSlotsPerMarket={filters.pro_slots_per_market}
            />
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
            <h1 style={{ fontSize: 22, margin: 0 }}>Top {title} Profiles</h1>
            <SortDropdown value={sort} onChange={setSort} />
          </div>
          <div style={{ color: 'var(--ink-soft)', fontSize: 13, marginBottom: 16 }}>
            {loading ? 'Loading…' : `${count} search results found`}
          </div>

          {!loading && results.map((r) => <ResultCard key={r.id} profile={r} />)}
        </main>

        <MapPlaceholder results={results} />
      </div>
    </div>
  )
}

export default SearchPage
