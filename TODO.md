# Phase 2 Implementation TODO

- [ ] Create AI client service (backend/app/services/ai_client.py) with Nvidia NIM provider + fallback logic
- [ ] Create AppSettings model + migration (AI providers JSON, Google OAuth client_id/secret encrypted)
- [ ] Create Settings API router (GET /settings, PATCH /settings) with encryption
- [ ] Update story_engine.py to use real LLM via ai_client (replace both mock implementations)
- [ ] Update GoogleAccount model: add password_encrypted field + create migration
- [ ] Implement real Google OAuth in google_accounts.py (authorize URL, callback, token exchange, refresh, real sync validation)
- [ ] Fix google_accounts.py list endpoint resilience (skip failed decryption)
- [ ] Create frontend Settings page (dashboard/settings/page.tsx) with provider reorder + OAuth credentials
- [ ] Wire frontend Story Engine pages to show real LLM content
- [ ] Update frontend types and api.ts for new Settings endpoints
- [ ] Run pytest (target 40+), smoke test live flow, npm run build
- [ ] Write PHASE2-REPORT.md with changes and test results