// A compact, project-owned dataset for the Primary Serving Area typeahead — deliberately NOT
// an external npm package (the closest fits ship 8-17MB of every country's cities, which would
// bloat this demo's bundle for no reason). All 50 states + DC, plus a real, curated spread of
// major/notable US cities per state. Not exhaustive — enough for a convincing, honest typeahead.

export const US_STATES = [
  'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut',
  'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa',
  'Kansas', 'Kentucky', 'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan',
  'Minnesota', 'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire',
  'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio',
  'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
  'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington', 'West Virginia',
  'Wisconsin', 'Wyoming', 'District of Columbia',
]

export const US_CITIES = [
  // Alabama
  'Birmingham, AL', 'Montgomery, AL', 'Huntsville, AL', 'Mobile, AL', 'Tuscaloosa, AL', 'Alabaster, AL', 'Auburn, AL',
  // Alaska
  'Anchorage, AK', 'Fairbanks, AK', 'Juneau, AK', 'Alakanuk, AK', 'Sitka, AK',
  // Arizona
  'Phoenix, AZ', 'Tucson, AZ', 'Mesa, AZ', 'Scottsdale, AZ', 'Chandler, AZ', 'Flagstaff, AZ', 'Tempe, AZ',
  // Arkansas
  'Little Rock, AR', 'Fayetteville, AR', 'Fort Smith, AR', 'Springdale, AR', 'Alma, AR',
  // California
  'Los Angeles, CA', 'San Francisco, CA', 'San Diego, CA', 'Sacramento, CA', 'San Jose, CA', 'Oakland, CA',
  'Fresno, CA', 'Long Beach, CA', 'Anaheim, CA', 'Santa Ana, CA', 'Alameda, CA', 'Alhambra, CA', 'Alpine, CA',
  'Berkeley, CA', 'Irvine, CA', 'Bakersfield, CA', 'Riverside, CA',
  // Colorado
  'Denver, CO', 'Colorado Springs, CO', 'Aurora, CO', 'Boulder, CO', 'Fort Collins, CO', 'Alamosa, CO',
  // Connecticut
  'Hartford, CT', 'New Haven, CT', 'Stamford, CT', 'Bridgeport, CT', 'Ansonia, CT',
  // Delaware
  'Wilmington, DE', 'Dover, DE', 'Newark, DE', 'Alderman, DE',
  // Florida
  'Miami, FL', 'Orlando, FL', 'Tampa, FL', 'Jacksonville, FL', 'Tallahassee, FL', 'St. Petersburg, FL',
  'Fort Lauderdale, FL', 'Alachua, FL', 'Altamonte Springs, FL', 'Boca Raton, FL',
  // Georgia
  'Atlanta, GA', 'Savannah, GA', 'Augusta, GA', 'Columbus, GA', 'Athens, GA', 'Alpharetta, GA', 'Newnan, GA',
  // Hawaii
  'Honolulu, HI', 'Hilo, HI', 'Kailua, HI', 'Kahului, HI',
  // Idaho
  'Boise, ID', 'Meridian, ID', 'Idaho Falls, ID', 'Alameda, ID',
  // Illinois
  'Chicago, IL', 'Springfield, IL', 'Aurora, IL', 'Naperville, IL', 'Peoria, IL', 'Alton, IL',
  // Indiana
  'Indianapolis, IN', 'Fort Wayne, IN', 'Evansville, IN', 'Bloomington, IN', 'Albany, IN',
  // Iowa
  'Des Moines, IA', 'Davenport, IA', 'Cedar Rapids, IA', 'Iowa City, IA', 'Ames, IA', 'Albia, IA',
  // Kansas
  'Wichita, KS', 'Topeka, KS', 'Overland Park, KS', 'Lawrence, KS', 'Alma, KS',
  // Kentucky
  'Louisville, KY', 'Lexington, KY', 'Bowling Green, KY', 'Frankfort, KY', 'Albany, KY',
  // Louisiana
  'New Orleans, LA', 'Baton Rouge, LA', 'Shreveport, LA', 'Lafayette, LA', 'Alexandria, LA',
  // Maine
  'Portland, ME', 'Augusta, ME', 'Bangor, ME', 'Alfred, ME',
  // Maryland
  'Baltimore, MD', 'Annapolis, MD', 'Rockville, MD', 'Frederick, MD', 'Aberdeen, MD',
  // Massachusetts
  'Boston, MA', 'Worcester, MA', 'Springfield, MA', 'Cambridge, MA', 'Amherst, MA',
  // Michigan
  'Detroit, MI', 'Grand Rapids, MI', 'Ann Arbor, MI', 'Lansing, MI', 'Albion, MI',
  // Minnesota
  'Minneapolis, MN', 'Saint Paul, MN', 'Rochester, MN', 'Duluth, MN', 'Albert Lea, MN',
  // Mississippi
  'Jackson, MS', 'Gulfport, MS', 'Hattiesburg, MS', 'Alcorn, MS',
  // Missouri
  'Kansas City, MO', 'St. Louis, MO', 'Springfield, MO', 'Columbia, MO', 'Alton, MO',
  // Montana
  'Billings, MT', 'Missoula, MT', 'Bozeman, MT', 'Helena, MT', 'Alberton, MT',
  // Nebraska
  'Omaha, NE', 'Lincoln, NE', 'Bellevue, NE', 'Alma, NE',
  // Nevada
  'Las Vegas, NV', 'Reno, NV', 'Henderson, NV', 'Carson City, NV', 'Alamo, NV',
  // New Hampshire
  'Manchester, NH', 'Nashua, NH', 'Concord, NH', 'Alton, NH',
  // New Jersey
  'Newark, NJ', 'Jersey City, NJ', 'Trenton, NJ', 'Princeton, NJ', 'Alpine, NJ',
  // New Mexico
  'Albuquerque, NM', 'Santa Fe, NM', 'Las Cruces, NM', 'Alamogordo, NM',
  // New York
  'New York, NY', 'Buffalo, NY', 'Rochester, NY', 'Albany, NY', 'Syracuse, NY', 'Alfred, NY',
  // North Carolina
  'Charlotte, NC', 'Raleigh, NC', 'Durham, NC', 'Greensboro, NC', 'Asheville, NC', 'Albemarle, NC',
  // North Dakota
  'Fargo, ND', 'Bismarck, ND', 'Grand Forks, ND', 'Alexander, ND',
  // Ohio
  'Columbus, OH', 'Cleveland, OH', 'Cincinnati, OH', 'Toledo, OH', 'Akron, OH', 'Alliance, OH',
  // Oklahoma
  'Oklahoma City, OK', 'Tulsa, OK', 'Norman, OK', 'Altus, OK',
  // Oregon
  'Portland, OR', 'Eugene, OR', 'Salem, OR', 'Bend, OR', 'Albany, OR',
  // Pennsylvania
  'Philadelphia, PA', 'Pittsburgh, PA', 'Allentown, PA', 'Erie, PA', 'Harrisburg, PA', 'Altoona, PA',
  // Rhode Island
  'Providence, RI', 'Warwick, RI', 'Cranston, RI',
  // South Carolina
  'Columbia, SC', 'Charleston, SC', 'Greenville, SC', 'Aiken, SC', 'Anderson, SC',
  // South Dakota
  'Sioux Falls, SD', 'Rapid City, SD', 'Aberdeen, SD',
  // Tennessee
  'Nashville, TN', 'Memphis, TN', 'Knoxville, TN', 'Chattanooga, TN', 'Alcoa, TN',
  // Texas
  'Houston, TX', 'Dallas, TX', 'Austin, TX', 'San Antonio, TX', 'Fort Worth, TX', 'El Paso, TX',
  'Alamo, TX', 'Alvin, TX', 'Amarillo, TX', 'Abilene, TX', 'Allen, TX',
  // Utah
  'Salt Lake City, UT', 'Provo, UT', 'Ogden, UT', 'Alpine, UT',
  // Vermont
  'Burlington, VT', 'Montpelier, VT', 'Albany, VT',
  // Virginia
  'Virginia Beach, VA', 'Richmond, VA', 'Norfolk, VA', 'Arlington, VA', 'Alexandria, VA',
  // Washington
  'Seattle, WA', 'Spokane, WA', 'Tacoma, WA', 'Olympia, WA', 'Algona, WA',
  // West Virginia
  'Charleston, WV', 'Huntington, WV', 'Morgantown, WV', 'Alderson, WV',
  // Wisconsin
  'Milwaukee, WI', 'Madison, WI', 'Green Bay, WI', 'Albany, WI',
  // Wyoming
  'Cheyenne, WY', 'Casper, WY', 'Laramie, WY', 'Alta, WY',
  // DC
  'Washington, DC',
]

// Merged list — states first (they're "places" too, per the "ala -> Alaska" example),
// then cities. Both match on a simple case-insensitive starts-with, per label.
const ALL_PLACES = [...US_STATES, ...US_CITIES]

export function suggestPlaces(query, limit = 8) {
  const q = query.trim().toLowerCase()
  if (!q) return []
  return ALL_PLACES.filter((place) => place.toLowerCase().startsWith(q)).slice(0, limit)
}
