# Plan: Invite Users, Long-Term Archives, And Hidden Relationship Recommendations

- Date: 2026-05-12
- Status: foundation implemented; public share/social/evolution slice added on 2026-05-13
- Scope: add an invite-only anonymous user layer, keep long-term history per user, prepare relationship graph analysis, and keep recommendation UI hidden behind a backend feature flag.

## Product Direction

Distilled TI should support two modes:

- Short anonymous session:
  - no invite required
  - uses the existing session secret/delete token flow
  - keeps the short TTL behavior
- Invite-backed anonymous user:
  - user enters an invite code
  - user enters an email address for uniqueness
  - backend creates a random `user_id` and random public `handle`
  - no real name, phone, or school identity is required
  - sessions started after redeeming the invite are attached to that user and kept long-term

This allows behavior and report evolution to be observed over time while keeping the public identity layer pseudonymous.

## Privacy Boundary

- Public UI asks for email only to enforce one account per person; it does not ask for real name, phone, or school identity.
- Public UI stores only `user_id`, `user_secret`, and random `handle` locally.
- Backend stores a normalized email hash for uniqueness; it does not return raw email or email hash in user/profile responses.
- Backend stores `user_secret_hash`, not the raw user secret.
- Admin can see anonymous user IDs, handles, invite edges, and aggregate profile/session results.
- Public recommendation UI now exists as a `/profile` Social Lab shell.
- Recommendation results are controlled by `RELATIONSHIP_RECOMMENDATIONS_ENABLED`, user opt-in, and report-ready data.
- User profile contains explicit opt-in flags:
  - `relationship_opt_in`
  - `recommendation_opt_in`

## Implemented Backend

- Added `UserProfile`, `UserAccessGrant`, `InviteCode`, `UserRelationship`, and `UserRecommendation` domain models.
- Added SQLite tables:
  - `user_profiles`
  - `invite_codes`
  - `user_relationships`
- `user_profiles.email_hash` has a unique index so one normalized email can only register one anonymous profile.
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

This is enough to test the data shape while keeping real recommendations constrained by explicit opt-in and available report history.

## 2026-05-13 Update

Implemented after the foundation slice:

- `POST /api/invite/redeem` now requires `invite_code + email`; duplicate normalized emails return `email_already_registered`.
- API profile responses expose `email_registered`, not raw email or email hash.
- Every invite-backed anonymous user now gets a personal share invite owned by that user.
- New users who redeem another user's personal share invite now create an anonymous `invited` relationship edge.
- Existing users who open another person's share link now call `POST /api/user/invite/claim` instead of silently skipping attribution.
- Claiming a share invite creates an anonymous `invited` relationship edge while preserving the claimant's own personal invite code.
- `/profile` now exposes:
  - personal share link copy/preview
  - public Social Lab shell
  - long-term session archive resume/report buttons
- `/evolution` now exposes:
  - invite-link copy
  - history row resume/report actions
- `/report` share/export now includes:
  - sharer handle
  - sharer invite code
  - `/share?...` URL inside exported JSON
- `RELATIONSHIP_RECOMMENDATIONS_ENABLED` defaults to `true` for this prototype branch, but recommendation results still require user opt-in and report-ready data.

## Not Done Yet

- No email verification, password login, OAuth, phone login, or campus SSO.
- No production-grade invite abuse controls.
- Public recommendation UI exists as a Social Lab shell, but useful candidates still require both opt-in and report-ready sessions.
- No user-to-user messaging.
- No PNG/PDF report export yet; JSON export exists and includes share metadata.
- No graph visualization for Admin yet.
- No production data deletion/export workflow beyond clearing local credentials, deleting sessions, and local JSON export.
- No policy copy beyond the current entertainment/self-assessment warning.

## Next Slices

1. Improve Admin relationship graph:
   - invite tree
   - per-cluster user distribution
   - opt-in/recommendation readiness counters
2. Add PNG/PDF style report snapshot export.
3. Improve user-facing archive polish:
   - per-report cards
   - compare latest report vs previous report once enough sessions exist
4. Add invite abuse controls, public opt-in copy review, and share-link throttling before broader public exposure.
