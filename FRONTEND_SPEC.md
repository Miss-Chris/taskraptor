# TaskRaptor Frontend Webapp Spec

## Purpose

Build the first committed web frontend for TaskRaptor as a React SPA that talks to the existing Django Ninja backend.

This document is intentionally implementation-oriented. It keeps the original product shape, tightens a few assumptions against the current backend, and turns delivery into a checklist.

---

## Reviewed Scope

### Confirmed Current Backend State

- Auth endpoints already exist at `/api/auth/register`, `/api/auth/login`, and `/api/auth/me`.
- Telegram webhook/reset endpoints already exist at `/api/telegram/webhook` and `/api/telegram/reset-webhook`.
- Web chat domain models and service helpers already exist:
  - `Channel`, `Conversation`, `WebChatMessage`
  - `get_or_create_default_web_channel`
  - `create_web_conversation`
  - `record_user_message`
  - `get_chat_history`
  - `handle_web_user_message`
- Task, automation, user settings, and LLM configuration models already exist.
- The `frontend/` directory exists but has no committed app yet.

### Review Notes And Spec Adjustments

- Use a Vite dev proxy first instead of requiring backend CORS work for local development.
  - Reason: the backend does not currently include `django-cors-headers`, and a dev proxy is the lighter MVP path.
  - CORS can still be added later if the frontend and backend must run on separate origins outside local dev.
- Treat `/api/auth/me` as identity-only.
  - It currently returns user identity fields, not `timezone` or `prompt_instructions`.
  - The settings page therefore still needs a dedicated `/api/settings` endpoint.
- Keep API key selection aligned to supported backend model keys.
  - The backend currently supports `system_free`, `deepseek/deepseek-chat`, `anthropic/claude-haiku-4-5-20251001`, and `anthropic/claude-sonnet-4-6`.
  - The frontend should not present arbitrary providers or model strings.
- Prefer polling for chat over sockets/SSE for MVP.
  - This matches the existing Telegram enqueue-and-process architecture.
  - It keeps the first web chat implementation operational without introducing streaming infrastructure.
- Keep tags derived from `Task.tags`.
  - No separate tag entity or tag CRUD is needed.

---

## Product Goals

- Let a user register, log in, and stay authenticated in the browser.
- Let a user create conversations and chat with the agent from the web app.
- Let a user browse and update tasks created by the agent.
- Let a user manage scheduled automations.
- Let a user connect Telegram from the web UI.
- Let a user view usage limits and optionally switch to their own API key.
- Let a user edit account-level settings relevant to automations and prompting.

Non-goals for MVP:

- WebSockets or token-streaming chat
- Multi-user collaboration
- Rich task editing forms beyond inline status and lightweight field updates
- Telegram disconnect flow beyond placeholder UX
- Advanced search, sorting, or analytics

---

## Recommended Tech Stack

- React 19
- Vite
- React Router
- Tailwind CSS
- shadcn/ui
- TanStack Query for API fetching, cache invalidation, polling, and mutation state
- `react-hook-form` plus `zod` for forms with lightweight validation
- `marked` or `react-markdown` for assistant message rendering

Notes:

- TanStack Query is worth adding here because the UI has repeated server state concerns: auth hydration, sidebar conversation lists, task filters, polling, and mutation-driven refreshes.
- Use a Vite `/api` proxy in development so the SPA can call the Django app without local CORS setup.

---

## Frontend Architecture

```text
React SPA (Vite)
  |
  |-- /api/* via dev proxy or same-origin deploy
  |
  |-- auth token in localStorage
  |
  |-- TanStack Query for fetch/mutate/poll
  |
  |-- route tree
      |-- /login
      |-- /register
      |-- /
      |-- /c/:id
      |-- /tasks
      |-- /tasks/upcoming
      |-- /automations
      |-- /settings
```

Suggested frontend structure:

- `frontend/src/app/`
  - app shell, router, providers
- `frontend/src/features/auth/`
  - auth pages, auth provider, token utilities
- `frontend/src/features/chat/`
  - chat routes, polling hook, message list, composer
- `frontend/src/features/tasks/`
  - task list views, filters, patch mutations
- `frontend/src/features/automations/`
  - automation list and form
- `frontend/src/features/settings/`
  - settings page, usage modal, API key modal
- `frontend/src/features/telegram/`
  - telegram status badge and join-code modal
- `frontend/src/lib/api.ts`
  - shared request wrapper, auth header injection, 401 handling

---

## UX Requirements

### Auth

- Login and register are separate routes.
- On success, store the bearer token in `localStorage`.
- On app boot, hydrate auth state from `localStorage`.
- If a protected API call returns `401`, clear the token and redirect to `/login`.

### App Shell

- Use a persistent left sidebar and a main content pane.
- Sidebar should be usable on desktop and collapse cleanly on smaller screens.
- Primary navigation belongs in the sidebar, not in scattered page headers.

### Chat

- The chat view is the default signed-in landing experience.
- If no conversation is selected, show an empty state with a clear `New Chat` action.
- User messages are visually distinct from assistant messages.
- Assistant content supports basic markdown rendering.
- After sending a message, the UI shows a pending/thinking state until polling settles.

### Tasks

- Tasks should be scannable first and editable second.
- Inline status updates should feel immediate.
- Filtering by status, tag, and simple search should work together.

### Automations

- Automation management is lightweight: list, create, edit, activate/deactivate, delete.
- Times should be shown in the user's configured timezone.

### Telegram And Usage

- Telegram connection state should be visible without leaving the main layout.
- Usage state should also be visible from the sidebar or a nearby persistent control.
- API key management should explain the effect of switching off `system_free`.

---

## Backend API Checklist

All new endpoints should use Django Ninja schemas and existing `AuthBearer`.

### Conversations: `/api/conversations`

- [ ] `GET /api/conversations`
  - Returns the authenticated user's web conversations only.
  - Ordered by `updated_at desc`.
  - Supports `limit` with a sensible default of `20`.
- [ ] `POST /api/conversations`
  - Creates a conversation on the user's default web channel.
  - Accepts optional `title`.
  - Returns the created conversation.
- [ ] `GET /api/conversations/{id}/messages`
  - Returns chat history ordered oldest to newest.
  - Supports `limit`.
  - Supports `before_id` for older-history pagination.
  - Supports `after_id` for polling new messages.
- [ ] `POST /api/conversations/{id}/messages`
  - Accepts `{ "content": string }`.
  - Persists the user message.
  - Enqueues a Celery task for processing.
  - Returns immediately with `{ "message_id": int, "status": "processing" }`.
- [ ] Add a Celery task for web chat processing in `api/channels/tasks.py`.
- [ ] Add tests for:
  - auth enforcement
  - conversation ownership checks
  - `after_id` polling behavior
  - task enqueue behavior
  - immediate response shape

Response shape targets:

**ConversationOut**

```json
{
  "id": 1,
  "title": "My conversation",
  "updated_at": "2026-04-08T12:00:00Z",
  "created_at": "2026-04-08T12:00:00Z"
}
```

**MessageOut**

```json
{
  "id": 1,
  "role": "user",
  "content": "Hello!",
  "created_at": "2026-04-08T12:00:00Z"
}
```

**SendMessageOut**

```json
{
  "message_id": 42,
  "status": "processing"
}
```

### Tasks: `/api/tasks`

- [ ] `GET /api/tasks`
  - Returns non-deleted tasks.
  - Supports `status`, `tag`, `search`, `limit`, and `offset`.
- [ ] `GET /api/tasks/upcoming`
  - Returns tasks with future `due_at`.
  - Ordered by `due_at asc`.
  - Default limit `20`.
- [ ] `GET /api/tasks/tags`
  - Returns distinct tag strings across the authenticated user's tasks.
- [ ] `PATCH /api/tasks/{id}`
  - Supports updates to `status`, `name`, `priority`, `tags`, and `due_at`.
  - Uses existing `update_task`.
- [ ] Add tests for:
  - ownership filtering
  - deleted-task exclusion
  - status/tag/search filters
  - task patch validation
  - `completed_at` behavior when status changes

**TaskOut**

```json
{
  "id": 1,
  "name": "Buy groceries",
  "status": "pending",
  "priority": 0,
  "due_at": "2026-04-10T09:00:00Z",
  "due_type": "time",
  "tags": ["shopping", "personal"],
  "remind_at": null,
  "completed_at": null,
  "created_at": "2026-04-08T12:00:00Z"
}
```

### Automations: `/api/automations`

- [ ] `GET /api/automations`
  - Returns the authenticated user's automations.
  - Includes enough channel data to label where the automation runs.
- [ ] `POST /api/automations`
  - Accepts `{ prompt, schedule_time, channel_id? }`.
  - Defaults to the web channel when `channel_id` is omitted.
- [ ] `PATCH /api/automations/{id}`
  - Supports `prompt`, `schedule_time`, `is_active`, and optional `channel_id`.
- [ ] `DELETE /api/automations/{id}`
  - Deletes the automation.
- [ ] Add tests for:
  - default web-channel behavior
  - ownership enforcement
  - update and delete flows

**AutomationOut**

```json
{
  "id": 1,
  "prompt": "Remind me about my daily standup",
  "schedule_time": "09:00:00",
  "is_active": true,
  "last_run_at": "2026-04-08T09:00:00Z",
  "created_at": "2026-04-08T12:00:00Z"
}
```

### Telegram: extend `/api/telegram`

- [ ] `GET /api/telegram/status`
  - Returns whether the user has an active, non-archived Telegram channel.
  - Includes `bot_name`.
- [ ] `POST /api/telegram/join-code`
  - Generates a fresh join code.
  - Invalidates previous unredeemed codes.
  - Returns `code`, `expires_at`, and `bot_name`.
- [ ] Add tests for:
  - connected/not-connected cases
  - join code generation
  - auth enforcement

**TelegramStatusOut**

```json
{
  "connected": true,
  "bot_name": "TaskRaptorBot"
}
```

**JoinCodeOut**

```json
{
  "code": "AB12CD",
  "expires_at": "2026-04-08T12:15:00Z",
  "bot_name": "TaskRaptorBot"
}
```

### Settings And Usage: `/api/settings`

- [ ] `GET /api/settings`
  - Returns `timezone` and `prompt_instructions`.
- [ ] `PATCH /api/settings`
  - Updates `timezone` and/or `prompt_instructions`.
- [ ] `GET /api/settings/usage`
  - Returns usage and model state from the user's active `LlmModel`.
- [ ] `POST /api/settings/api-key`
  - Accepts a supported `model_key` plus `api_key`.
  - Creates or updates the user's active non-system model config.
- [ ] `DELETE /api/settings/api-key`
  - Removes the user's own key-backed config and returns them to `system_free`.
- [ ] Add tests for:
  - settings reads/writes
  - invalid timezone or model key handling
  - own-key activation
  - revert-to-system-free flow

Recommended usage response:

```json
{
  "model_key": "system_free",
  "quota": 100,
  "quota_used": 42,
  "quota_expires_at": "2026-05-01T00:00:00Z",
  "has_own_key": false
}
```

---

## Frontend Screen Checklist

### 1. Auth Pages: `/login`, `/register`

- [ ] Build login page with username and password.
- [ ] Build register page with username, email, and password.
- [ ] Handle success by saving token and redirecting to `/`.
- [ ] Show inline API errors for invalid credentials or duplicate username.
- [ ] Prevent authenticated users from revisiting auth pages unnecessarily.

Acceptance criteria:

- A new user can register and land in the app.
- An existing user can log in and refresh the browser without losing the session.

### 2. App Shell

- [ ] Add a left sidebar using shadcn patterns.
- [ ] Add responsive collapse behavior for smaller screens.
- [ ] Add primary nav items:
  - [ ] `New Chat`
  - [ ] recent conversations
  - [ ] `All Tasks`
  - [ ] `Upcoming Tasks`
  - [ ] tag shortcuts
  - [ ] `Automations`
  - [ ] Telegram status trigger
  - [ ] usage/API key trigger
  - [ ] `Settings`
- [ ] Load recent conversations and tags once authenticated.
- [ ] Keep shell visible while page content changes.

Acceptance criteria:

- The signed-in app feels like one persistent product shell rather than disconnected pages.

### 3. Chat View: `/`, `/c/:id`

- [ ] Add empty-state chat landing view.
- [ ] Add conversation route with header and title.
- [ ] Render message history oldest to newest.
- [ ] Render user messages right-aligned and assistant messages left-aligned.
- [ ] Support markdown in assistant messages.
- [ ] Add composer with disabled/loading state during sends.
- [ ] On send:
  - [ ] optimistically add the user message
  - [ ] call `POST /api/conversations/{id}/messages`
  - [ ] start polling `GET /api/conversations/{id}/messages?after_id=...`
- [ ] Poll every 3 seconds for up to 60 seconds.
- [ ] Stop polling when:
  - [ ] no new messages arrive for one full cycle after at least one assistant message was received, or
  - [ ] the 60-second timeout is reached
- [ ] Show failure state if the send or polling request fails.

Acceptance criteria:

- A user can start a conversation, send a message, and see the assistant reply arrive without a full page reload.

### 4. All Tasks View: `/tasks`

- [ ] Render a list or table with:
  - [ ] name
  - [ ] status
  - [ ] priority
  - [ ] due date
  - [ ] tags
- [ ] Add status filter.
- [ ] Add tag filter.
- [ ] Add name search.
- [ ] Add inline status mutation.
- [ ] Add loading, empty, and error states.

Acceptance criteria:

- Task data is discoverable and status changes are reflected immediately in the UI.

### 5. Upcoming Tasks View: `/tasks/upcoming`

- [ ] Reuse task presentation from the all-tasks view.
- [ ] Sort by due date ascending.
- [ ] Group tasks into:
  - [ ] Today
  - [ ] Tomorrow
  - [ ] This Week
  - [ ] Later

Acceptance criteria:

- The user can scan near-term work faster than in the generic task list.

### 6. Automations View: `/automations`

- [ ] Render automation list with prompt, schedule time, and active state.
- [ ] Add `Add Automation` action.
- [ ] Add create form with prompt, time, and active toggle.
- [ ] Add edit action.
- [ ] Add delete action.
- [ ] Reflect timezone context in displayed schedule times.

Acceptance criteria:

- A user can create, edit, enable/disable, and delete an automation from the web app.

### 7. Settings View: `/settings`

- [ ] Show identity summary from `/api/auth/me`.
- [ ] Show editable timezone.
- [ ] Show editable prompt instructions.
- [ ] Save settings changes with clear success/error state.
- [ ] Include API key section or entry point to API key modal.
- [ ] Leave room for future account actions without overbuilding the page now.

Acceptance criteria:

- A user can update timezone and standing prompt instructions without leaving the app shell.

### 8. Telegram Connect Modal

- [ ] Show current Telegram connection status.
- [ ] If not connected:
  - [ ] allow join-code generation
  - [ ] show code
  - [ ] show bot name
  - [ ] show concise instructions
- [ ] If connected:
  - [ ] show connected state
  - [ ] note that disconnect is future work unless backend support is added now

Acceptance criteria:

- A user can generate a valid join code and understand how to complete the flow in Telegram.

### 9. Usage And API Key Modal

- [ ] Show current `model_key`, `quota`, `quota_used`, and expiry if present.
- [ ] Show whether the user is on `system_free` or a personal API key.
- [ ] Offer only supported backend model keys.
- [ ] Let the user submit a new key-backed config.
- [ ] Let the user remove their own key and revert to `system_free`.

Acceptance criteria:

- A user can understand their current quota state and switch between system and personal key usage.

---

## Delivery Plan Checklist

### Phase 1: Frontend Scaffold And Auth

- [ ] Initialize Vite React app in `frontend/`.
- [ ] Add Tailwind and shadcn/ui.
- [ ] Add React Router.
- [ ] Add TanStack Query.
- [ ] Add auth provider and token storage.
- [ ] Add login/register routes.
- [ ] Add protected-route handling.
- [ ] Configure Vite dev proxy for `/api`.

Phase exit criteria:

- A user can register, log in, refresh, and remain authenticated.

### Phase 2: Chat And App Shell

- [ ] Build the persistent shell and sidebar.
- [ ] Implement conversation list and new-conversation flow.
- [ ] Implement chat route and message rendering.
- [ ] Implement polling flow.
- [ ] Add backend conversation router and web-message Celery task.
- [ ] Add backend tests for the new conversation endpoints.

Phase exit criteria:

- Chat works end to end from the browser against the Django backend.

### Phase 3: Task Surfaces

- [ ] Implement all-tasks page.
- [ ] Implement upcoming-tasks page.
- [ ] Implement sidebar tag shortcuts.
- [ ] Add backend task endpoints and tests.

Phase exit criteria:

- The user can browse and update tasks from the web app.

### Phase 4: Telegram And Usage

- [ ] Implement Telegram status badge and modal.
- [ ] Implement usage/API key modal.
- [ ] Add backend Telegram status/join-code endpoints and tests.
- [ ] Add backend usage/API-key endpoints and tests.

Phase exit criteria:

- The user can connect Telegram and manage usage/key state from the app.

### Phase 5: Automations And Settings

- [ ] Implement automations CRUD UI.
- [ ] Implement settings page.
- [ ] Add backend automations router and tests.
- [ ] Add backend settings endpoints and tests.

Phase exit criteria:

- The web app covers the primary product surfaces already present in the backend domain model.

---

## Cross-Cutting Implementation Checklist

- [ ] Use one shared API client with bearer-token injection.
- [ ] Normalize backend errors into user-readable UI messages.
- [ ] Add loading and empty states on every route.
- [ ] Guard every endpoint by authenticated ownership on the backend.
- [ ] Add route-level skeletons or placeholders to reduce layout shift.
- [ ] Keep task and automation times timezone-aware in the UI.
- [ ] Ensure the shell works on mobile widths.
- [ ] Add a basic 404 route.
- [ ] Add frontend lint/format tooling as part of the scaffold.
- [ ] Add backend tests for every new router.
- [ ] Add frontend smoke coverage if test tooling is introduced during scaffold.

---

## Open Decisions

- [ ] Decide whether the frontend ships as a separate deployable SPA or is eventually served by Django in production.
- [ ] Decide whether conversation titles are user-provided only or later auto-generated from first message content.
- [ ] Decide whether API key entry should live only in a modal or also on the settings page.
- [ ] Decide whether task editing beyond status should be inline, modal-based, or deferred.
- [ ] Decide whether Telegram disconnect should be backend-backed in MVP or explicitly deferred.

Current recommendation:

- Separate SPA during development, same-origin deployment later if operational simplicity matters.

