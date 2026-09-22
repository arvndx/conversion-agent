// The claim flow's full field set, grouped into pages of up to 5 — walked through one page
// at a time in the new agentic claim wizard. `page` numbers are 1-indexed and match the order
// the user pages through. `aiSuggest: true` fields get an "AI-generate" button in the UI that
// asks the agent to draft a suggestion from the user's other already-known fields.
export const CLAIM_FIELDS = [
  // Page 1 — mandatory fields live here
  { key: 'name', label: 'Name', required: true, page: 1 },
  { key: 'email', label: 'Email', required: true, page: 1 },
  { key: 'phone_number', label: 'Phone Number', required: true, page: 1 },
  { key: 'location', label: 'Location', page: 1 },
  { key: 'title', label: 'Title', placeholder: 'e.g. Board-Certified Dentist & Owner', page: 1 },

  // Page 2
  {
    key: 'business_timing',
    label: 'Business Timing',
    placeholder: 'e.g. Mon–Fri, 9 AM – 5 PM',
    page: 2,
    defaultSuggestion: 'Monday–Friday, 9 AM – 6 PM',
  },
  {
    key: 'service_area',
    label: 'Primary Serving Area',
    placeholder: 'e.g. Austin, TX and surrounding areas',
    page: 2,
    type: 'place-typeahead',
  },
  { key: 'website_url', label: 'Website', placeholder: 'e.g. https://yourbusiness.com', page: 2 },
  { key: 'license_number', label: 'License', placeholder: 'e.g. TX-DDS-88213', page: 2 },
  { key: 'products_services', label: 'Products & Services Offered', placeholder: 'e.g. Teeth whitening, Invisalign, root canals', page: 2, multiline: true },

  // Page 3
  {
    key: 'specialities',
    label: 'Specialities',
    placeholder: 'e.g. Cosmetic dentistry, pediatric care',
    page: 3,
    multiline: true,
    aiSuggest: true,
  },
  { key: 'memberships', label: 'Memberships', placeholder: 'e.g. American Dental Association', page: 3 },
  { key: 'year_started', label: 'Year Started', placeholder: 'e.g. 2012', page: 3, defaultSuggestion: '2015' },
  { key: 'awards', label: 'Awards Achieved', placeholder: 'e.g. Top Dentist 2023, Austin Monthly', page: 3 },
  { key: 'achievements', label: 'Achievements', placeholder: 'e.g. 500+ five-star reviews, 10,000 patients served', page: 3, multiline: true },

  // Page 4
  {
    key: 'hobbies',
    label: 'Hobbies',
    placeholder: 'e.g. Marathon running, woodworking',
    page: 4,
    quickPicks: ['Golf', 'Hiking', 'Reading', 'Cooking', 'Traveling', 'Gardening', 'Running'],
  },

  // Page 5 — final page, always last
  {
    key: 'bio',
    label: 'Description',
    placeholder: 'A short summary of you and your business',
    page: 5,
    multiline: true,
    aiSuggest: true,
  },
]

export const CLAIM_FIELD_LABELS = Object.fromEntries(CLAIM_FIELDS.map((f) => [f.key, f.label]))
export const CLAIM_PAGE_COUNT = Math.max(...CLAIM_FIELDS.map((f) => f.page))

export function fieldsForPage(page) {
  return CLAIM_FIELDS.filter((f) => f.page === page)
}
