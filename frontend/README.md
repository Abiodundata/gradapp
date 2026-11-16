# GradApp Frontend

Responsive React interface for GradApp.

## Screens

| Route | Screen | Use case |
|---|---|---|
| (signed out) | Sign in / create account | Register/Login |
| `/` | Discover: search, filters, sorting, pagination | Search Graduate Programs, Advanced Search/Filter |
| `/programs/:id` | Program details, faculty, funding, similar programs, verification badge, admin retrieval panel | View Program Details, Retrieve Program Information |
| `/recommendations` | Ranked programs with fit score, reasons, cautions and score breakdown | Get Personalized Recommendations |
| `/faculty` | Faculty search and "match my research interests" | View Faculty Profiles |
| `/funding` | Funding search and filters | Search Funding |
| `/saved` | Shortlist with status, notes and personal target dates | Save Programs |
| `/deadlines` | Timeline of application, personal and funding deadlines | Track Application Deadlines |
| `/compare` | Side-by-side table of 2 to 4 programs | Compare Programs |
| `/ask`, `/ask/:id` | Saved chats (new / continue / delete), answers citing GradApp records or web sources, web results saved to GradApp | Ask AI Questions |
| `/profile` | Student profile form | Create Academic/Student Profile |
| `/admin/users` | User list with activate/deactivate and admin toggles (admins only) | Manage Users |

## Structure

```
src/
  api.js            API client: JSON, readable errors, automatic token refresh, session expiry
  context.jsx       Auth, saved-programs and compare state
  components/       Layout (navigation, compare tray) and shared UI
  pages/            One file per screen
  test/             Vitest + Testing Library tests
```

## Run locally

```bash
cp .env.example .env
npm install
npm run dev
```

The app opens at `http://localhost:5173` and expects the Django API at `http://localhost:8000/api`
(`VITE_API_URL`).

## Test and build

```bash
npm test
npm run build
```

## Docker

```bash
docker build -t gradapp-frontend .
docker run --rm -p 3000:80 gradapp-frontend
```
