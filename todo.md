# TaskRaptor V1 Launch Checklist

## Current Status

- [x] Backend has auth, Telegram linking/webhook handling, the core agent loop, task tools, web-channel services, scheduled automations, and LLM quota fields.
- [x] Backend test suite passes with `SECRET_KEY=test-secret uv run pytest` from `api/` (`74 passed, 5 deselected` during audit).
- [x] Frontend has a committed Vite/React scaffold with login, register, protected app shell, sidebar, and Telegram status/join-code client helpers.
- [ ] Backend tests do not run out-of-the-box without setting `SECRET_KEY`; test settings still inherit the required local secret.
- [ ] Frontend is not yet a usable product surface: chat, task views, automations, settings, usage, and API-key management are missing or placeholders.
- [ ] Frontend build was not verified during audit because dependencies were not installed in `frontend/node_modules`.

## V1 Product Decisions

- [x] V1 is web-app first; Telegram is supported as an add-on channel.
- [x] Hosted open signup is allowed until the hosted instance reaches 200 users max.
- [x] Hosted free quota is 50 agent runs/month/user.
- [x] Users can bring their own LLM API key in v1.
- [x] Basic daily scheduled prompt automations are in v1.
- [x] Task UI supports inline basics: status, name, priority, due date, and tags.

## Launch Blockers

### Backend API

- [ ] Add authenticated web conversation and message endpoints for creating conversations, listing conversations, loading history, sending messages, and polling for assistant replies.
- [ ] Add a web-chat Celery task so send-message requests return quickly while agent work happens asynchronously.
- [ ] Add authenticated task endpoints for listing, filtering, upcoming tasks, distinct tags, and inline task updates using existing task services.
- [ ] Add authenticated automation CRUD endpoints using the existing automation model and default web channel behavior.
- [ ] Add authenticated settings endpoints for timezone, standing prompt instructions, usage, and API-key management.
- [ ] Enforce hosted registration cap at 200 users max with a clear API error once the cap is reached.
- [ ] Change hosted free quota enforcement to 50 agent runs/month/user rather than token-based quota accounting.
- [ ] Add backend tests for every new router, including auth enforcement, ownership checks, quota behavior, and common validation failures.

### Frontend

- [ ] Replace the placeholder home with the real chat landing and conversation route.
- [ ] Wire the sidebar to live conversations, new-chat creation, task routes, automations, settings, usage/API-key, and Telegram connect actions.
- [ ] Implement message history rendering, send-message flow, pending state, and polling for assistant replies.
- [ ] Implement all-tasks and upcoming-tasks views with search/filtering and inline edits for status, name, priority, due date, and tags.
- [ ] Implement automation list, create, edit, enable/disable, and delete flows.
- [ ] Implement settings for timezone and standing prompt instructions.
- [ ] Implement usage/API-key UI showing the 50 agent runs/month/user hosted quota and BYOK state.
- [ ] Polish Telegram connect UX around connection status, join-code generation, bot name, expiry, and clear next steps.
- [ ] Add loading, empty, error, and mobile states for every launch route.

### Agent Core

- [ ] Add reliable agent-run accounting that increments once per user-visible agent run and supports the 50 runs/month/user quota.
- [ ] Define and implement monthly quota reset behavior for hosted users.
- [ ] Return user-facing quota errors that explain the monthly cap and BYOK path.
- [ ] Re-check tool ownership boundaries, especially SQL/task access and conversation scoping.
- [ ] Improve failure logging for LLM errors, tool errors, Celery failures, and webhook processing failures.
- [ ] Keep live LLM tests separate from default CI while preserving enough scripted coverage for core behavior.

### Open Source Readiness

- [ ] Update `README.md` with current architecture, local setup, test commands, and development workflow.
- [ ] Add `.env.example` for backend settings, Telegram settings, database, Redis/Celery, hosted quota flags, and LLM provider keys.
- [ ] Document self-host setup, including how to disable hosted signup caps or configure them explicitly.
- [ ] Document BYOK behavior and which model keys are supported.
- [ ] Add license and contribution basics before public launch.
- [ ] Remove or update stale repo orientation that says the frontend has no committed app.

### Deployment And Operations

- [ ] Add production settings guidance for `DEBUG`, `ALLOWED_HOSTS`, secrets, database, Redis, Celery workers, and Celery beat.
- [ ] Decide and document whether the frontend deploys as a separate SPA or same-origin behind the backend.
- [ ] Add deploy-time migration and static/frontend build steps.
- [ ] Document Telegram webhook setup and reset procedure.
- [ ] Add a launch smoke test covering registration, login, chat, task creation, quota display, Telegram link-code generation, and automation creation.
- [ ] Add basic operational logging/monitoring targets for failed agent runs, quota denials, webhook errors, and Celery task failures.

### Polish And Cleanup

- [ ] Make backend tests run without manually exporting `SECRET_KEY`, preferably via a safe test default.
- [ ] Install frontend dependencies and verify `npm run build` from `frontend/`.
- [ ] Remove placeholder sidebar items, placeholder home text, and hard-coded example tags.
- [ ] Run a mobile layout pass for auth pages, app shell, chat, task lists, automations, settings, and modals.
- [ ] Review copy for open-source hosted quota messaging: 50 agent runs/month/user and 200 hosted users max.
- [ ] Keep `FRONTEND_SPEC.md` or replace it with shorter docs so it does not conflict with actual implementation status.

## Post-V1 Nice-To-Haves

- [ ] Streaming assistant responses over SSE or WebSockets.
- [ ] Telegram disconnect and relink management from the web UI.
- [ ] Conversation title auto-generation.
- [ ] Advanced task search, saved filters, analytics, or bulk editing.
- [ ] Multi-user workspaces or collaboration.
- [ ] Rich automation schedules beyond one daily time.
- [ ] Admin dashboard for hosted usage and user cap management.

## Verification

- [ ] Run `SECRET_KEY=test-secret uv run pytest` from `api/`.
- [ ] Run `npm ci && npm run build` from `frontend/`.
- [ ] Confirm `git diff -- todo.md` contains only this intended checklist.
