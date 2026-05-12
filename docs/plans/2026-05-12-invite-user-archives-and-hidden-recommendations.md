# Plan: Invite Users, Long-Term Archives, And Hidden Relationship Recommendations

- Date: 2026-05-12
- Status: foundation implemented
- Scope: add an invite-only anonymous user layer, keep long-term history per user, prepare relationship graph analysis, and keep recommendation UI hidden behind a backend feature flag.

## Product Direction

Distilled TI should support two modes:

- Short anonymous session:
  - no invite required
  - uses the existing session secret/delete token flow
  - keeps the short TTL behavior
- Invite-backed anonymous user:
  - user enters an invite code
  - backend creates a random `user_id` and random public `handle`
  - no real name, phone, email, or school identity is required
  - sessions started after redeeming the invite are attached to that user and kept long-term

This allows behavior and report evolution to be observed over time while keeping the public identity layer pseudonymous.

## Privacy Boundary

- Public UI never asks for real identity.
- Public UI stores only `user_id`, `user_secret`, and random `handle` locally.
- Backend stores `user_secret_hash`, not the raw user secret.
- Admin can see anonymous user IDs, handles, invite edges, and aggregate profile/session results.
- Public recommendation UI is not exposed.
- The hidden recommendation endpoint is disabled unless `RELATIONSHIP_RECOMMENDATIONS_ENABLED=true`.
- User profile contains explicit opt-in flags:
  - `relationship_opt_in`
  - `recommendation_opt_in`

## Implemented Backend

- Added `UserProfile`, `UserAccessGrant`, `InviteCode`, `UserRelationship`, and `UserRecommendation` domain models.
- Added SQLite tables:
  - `user_profiles`
  - `invite_codes`
  - `user_relationships`
- Added `sessions.user_id`.
- Registered sessions now use `REGISTERED_SESSION_TTL_DAYS` instead of the short session TTL.
- Added a local bootstrap invite via `INVITE_BOOTSTRAP_CODE`.
- Added `backend/app/services/user_service.py`.
- Added public API:
  - `POST /api/invite/redeem`
  - `GET /api/user/me`
  - `PATCH /api/user/me`
  - `GET /api/user/sessions`
  - `POST /api/user/session/{session_id}/access`
- Added admin API:
  - `POST /api/admin/invites`
  - `GET /api/admin/invites`
  - `GET /api/admin/users`
  - `GET /api/admin/users/relationships`
  - `GET /api/admin/users/{user_id}/recommendations`

## Implemented Frontend

- Landing page now has an invite entry panel.
- Redeemed invite credentials are stored in local storage as an anonymous user credential.
- New sessions automatically attach to the local anonymous user when present.
- History page uses user-owned session history when a user credential exists.
- Added `/profile`:
  - shows random handle and invite source
  - shows long-term result archive
  - provides privacy/experiment opt-in toggles
  - lets users resume sessions or open available reports
- Admin page now shows:
  - anonymous users
  - invite creation and recent invites
  - invite relationship edges
  - hidden recommendation probe panel

## Recommendation Scope

The first recommendation implementation is intentionally conservative:

- It only runs in Admin.
- It only returns candidates if the backend flag is enabled.
- It requires the subject user to opt in.
- It excludes directly connected invite-relationship users.
- It uses report-ready sessions only.
- It scores candidates by core profile distance with a small same-cluster bonus.

This is enough to test the data shape without making a social feature visible to users.

## Not Done Yet

- No real login system, email, phone, password, OAuth, or campus SSO.
- No production-grade invite abuse controls.
- No public friend/recommendation UI.
- No user-to-user messaging.
- No share/export implementation beyond the existing report view.
- No graph visualization for Admin yet.
- No data deletion/export workflow beyond clearing local credentials and deleting sessions.
- No policy copy beyond the current entertainment/self-assessment warning.

## Next Slices

1. Add report export/share:
   - local JSON export
   - PNG/PDF style report snapshot
   - share token only if explicitly enabled
2. Improve Admin relationship graph:
   - invite tree
   - per-cluster user distribution
   - opt-in/recommendation readiness counters
3. Add user-facing archive polish:
   - per-report cards
   - evolution timeline across reports
   - compare latest report vs previous report
4. Only after privacy review, decide whether the hidden recommendation UI can move from Admin to Public.
