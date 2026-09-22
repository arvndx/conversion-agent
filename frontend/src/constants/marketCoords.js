// Real market-center coordinates — this app has no Maps API key/billing, so exact
// street-level geocoding per business isn't available; every map in the app places
// markers at the business's real market center instead. Shared so the search results
// map and any single-profile map always agree on the same real coordinates.
export const MARKET_COORDS = {
  'Austin, TX': [30.2672, -97.7431],
  'Houston, TX': [29.7604, -95.3698],
  'Los Angeles, CA': [34.0522, -118.2437],
  'San Francisco, CA': [37.7749, -122.4194],
  'Davenport, IA': [41.5236, -90.5776],
  'Newnan, GA': [33.3809, -84.7997],
}
