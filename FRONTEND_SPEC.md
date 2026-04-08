# TaskRaptor Frontend Webapp Spec

## Current State

The backend has a solid "core":

- **Models:** User, Task (with tags as JSONField), Conversation, Channel, WebChatMessage, AgentRun, MessageLog, LlmModel, Automation, TelegramJoinCode
- **Agent loop:** LiteLLM-based agent with tools (create/edit/delete task, run\_sql, respond\_to\_user)
- **Web chat service layer:** `channels/web.py` has `handle_web_user_message`, `get_chat_history`, conversation CRUD -- but no HTTP endpoints
- **Existing API:** Only `/api/auth/{register,login,me}` and `/api/telegram/{webhook,reset-webhook}`
- **Frontend:** Empty directory, no framework or files

---

## Tech Stack

- **React 19 + Vite** (SPA) -- simplest approach given separate Django API
- **React Router** for client-side routing
- **shadcn/ui + Tailwind CSS** for all components
- **Sidebar layout** from shadcn's sidebar component

---

## Architecture

```
React SPA (Vite)
    |
    |-- Bearer token -->  Django Ninja API (/api/*)
    |                         |
    |                         |-- enqueue --> Celery Worker
    |                         |                   |
    |                         |                   --> Agent Loop (LiteLLM)
    |                         |                         |
    |                         |                         --> Task CRUD + SQL --> PostgreSQL
    |                         |
    |                         --> PostgreSQL
    |
    |-- poll every 3s --> Django Ninja API
```

### Chat Flow (Polling)

1. **User sends message:** `POST /api/conversations/{id}/messages` records the `WebChatMessage`, enqueues a Celery task (`process_web_message`), returns immediately with `{ "message_id": int, "status": "processing" }`.
2. **Celery worker:** Runs the agent loop (same as Telegram path), persists assistant `WebChatMessage` rows via `WebConversation.send_message`.
3. **Frontend polls:** After sending, the frontend polls `GET /api/conversations/{id}/messages?after_id={last_seen_id}` every 3 seconds for up to 60 seconds. New assistant messages appear as they are persisted.
4. **Polling stops:** When the poll returns a message with `role=assistant` and no new messages arrive for a full poll cycle, or after 60 seconds, whichever comes first.

This mirrors the existing Telegram flow (webhook -> Celery task -> agent -> send reply) and avoids long-lived HTTP connections.

---

## Backend API Endpoints

All endpoints below need to be added. Auth uses existing `AuthBearer` from `accounts/bearer.py`. Response shapes use Django Ninja `Schema`.

### Conversations (`/api/conversations`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/conversations` | List user's conversations (web channel only), ordered by `updated_at` desc. Query param: `limit` (default 20). |
| POST | `/api/conversations` | Create a new web conversation. Optional `title` in body. Returns the conversation object. |
| GET | `/api/conversations/{id}/messages` | Paginated chat history. Query params: `limit` (default 50), `before_id` (cursor for older messages), `after_id` (cursor for newer messages -- used by polling). Uses existing `get_chat_history` (extended with `after_id`). |
| POST | `/api/conversations/{id}/messages` | Send a user message. Body: `{ "content": str }`. Records `WebChatMessage`, enqueues `process_web_message` Celery task, returns immediately with `{ "message_id": int, "status": "processing" }`. |

Leverages existing code in `channels/web.py` -- `get_chat_history` (needs `after_id` support), `record_user_message`, `create_web_conversation`. New Celery task `process_web_message` in `channels/tasks.py` calls `handle_user_incoming`.

#### Response Schemas

**ConversationOut:**
```json
{
  "id": 1,
  "title": "My conversation",
  "updated_at": "2026-04-08T12:00:00Z",
  "created_at": "2026-04-08T12:00:00Z"
}
```

**MessageOut:**
```json
{
  "id": 1,
  "role": "user | assistant",
  "content": "Hello!",
  "created_at": "2026-04-08T12:00:00Z"
}
```

**SendMessageOut:**
```json
{
  "message_id": 42,
  "status": "processing"
}
```

### Tasks (`/api/tasks`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks` | List tasks (non-deleted). Query params: `status`, `tag`, `search` (name contains), `limit`, `offset`. |
| GET | `/api/tasks/upcoming` | Tasks with `due_at` in the future, ordered by `due_at` asc. Limit 20. |
| GET | `/api/tasks/tags` | Distinct tags across user's tasks (extracted from JSONField). Returns `string[]`. |
| PATCH | `/api/tasks/{id}` | Update task fields (status, name, priority, tags, due\_at). Uses existing `update_task` from `tasks/services.py`. |

#### Response Schemas

**TaskOut:**
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

### Automations (`/api/automations`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/automations` | List user's automations with channel info. |
| POST | `/api/automations` | Create automation. Body: `{ prompt, schedule_time, channel_id? }`. Defaults to web channel. |
| PATCH | `/api/automations/{id}` | Update automation (prompt, schedule\_time, is\_active). |
| DELETE | `/api/automations/{id}` | Delete automation. |

#### Response Schemas

**AutomationOut:**
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

### Telegram (`/api/telegram`) -- extend existing router

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/telegram/status` | Returns `{ connected: bool, bot_name: str }`. Checks if user has an active (non-archived) Telegram channel. |
| POST | `/api/telegram/join-code` | Generate a new `TelegramJoinCode`. Returns `{ code, expires_at, bot_name }`. |

#### Response Schemas

**TelegramStatusOut:**
```json
{
  "connected": true,
  "bot_name": "TaskRaptorBot"
}
```

**JoinCodeOut:**
```json
{
  "code": "AB12CD",
  "expires_at": "2026-04-08T12:15:00Z",
  "bot_name": "TaskRaptorBot"
}
```

### Settings and Usage (`/api/settings`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | Returns user settings: `timezone`, `prompt_instructions`. |
| PATCH | `/api/settings` | Update `timezone` and/or `prompt_instructions`. |
| GET | `/api/settings/usage` | Returns LLM usage from user's active `LlmModel`. |
| POST | `/api/settings/api-key` | Set user's own API key. Body: `{ model_key, api_key }`. Creates/updates `LlmModel`. Removes quota limits. |
| DELETE | `/api/settings/api-key` | Remove own API key, revert to system\_free model. |

#### Response Schemas

**SettingsOut:**
```json
{
  "timezone": "America/New_York",
  "prompt_instructions": "Be concise."
}
```

**UsageOut:**
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

## Frontend Screens

### 1. Auth Pages (`/login`, `/register`)

- Simple centered card with username/password (and email for register)
- On success, store token in localStorage, redirect to `/`
- No complex flows -- matches existing `RegisterIn` / `LoginIn` schemas

### 2. App Shell (Layout)

- **shadcn Sidebar** (collapsible) on the left + main content area
- Sidebar sections (top to bottom):
  - **"New Chat" button** -- creates conversation, navigates to it
  - **Recent Conversations** -- last 5, clicking navigates to `/c/{id}`
  - **Divider**
  - **All Tasks** link -> `/tasks`
  - **Upcoming Tasks** link -> `/tasks/upcoming`
  - **Tags** section -- show up to 8 tags as badges/chips, clicking filters tasks view
  - **Automations** link -> `/automations`
  - **Divider**
  - **Telegram indicator** -- "Connect Telegram" or "Telegram Connected" badge. Clicking opens a modal with join code + instructions
  - **Usage counter** -- "X / Y messages used" with a small "Remove limits" button that opens API key modal
  - **Divider**
  - **Settings** link -> `/settings` (gear icon)

### 3. Chat View (`/`, `/c/{id}`)

- Default route. If no conversation selected, show a welcome/empty state with "New Chat" prompt.
- Message list: user messages right-aligned, assistant messages left-aligned, rendered with markdown support.
- Input bar at the bottom with send button.
- After sending a message, show a "thinking" indicator while polling for the agent's response (poll `GET /conversations/{id}/messages?after_id={last_msg_id}` every 3s, up to 60s).
- New assistant messages appear incrementally as the agent produces them.
- Conversation title in the header area.

### 4. All Tasks View (`/tasks`)

- Table/list of tasks with columns: name, status (badge), priority, due date, tags (badges)
- Inline status toggle (pending -> in\_progress -> completed)
- Filter bar: by status, by tag (from sidebar click or dropdown)
- Simple search by name
- Empty state when no tasks

### 5. Upcoming Tasks View (`/tasks/upcoming`)

- Similar to All Tasks but pre-filtered to tasks with future `due_at`
- Sorted by due date ascending
- Grouped by day (Today, Tomorrow, This Week, Later)

### 6. Automations View (`/automations`)

- List of automations: prompt (truncated), schedule time, active toggle
- "Add Automation" button opens a simple form (prompt textarea, time picker, active toggle)
- Edit/delete actions per row

### 7. Settings View (`/settings`)

- User info (read-only: username, email)
- Timezone selector
- Custom prompt instructions textarea
- API Key section: current model, add/remove own key
- Danger zone: (placeholder for future account actions)

### 8. Telegram Connect Modal

- Triggered from sidebar indicator
- If not connected: shows "Generate Code" button, then displays the 6-char code with instructions ("Open Telegram, find @BotName, send `JOIN CODE`")
- If connected: shows "Telegram Connected" status with option to disconnect (future)

### 9. API Key / Usage Modal

- Shows current usage (quota\_used / quota)
- "Use your own API key" form: select model provider (Anthropic, DeepSeek), paste key
- Explanation that own key removes message limits

---

## Implementation Order

Each phase delivers a working increment. Backend endpoints are built alongside the screens that need them.

### Phase 1: Scaffold + Auth

- Vite + React + React Router + Tailwind + shadcn/ui setup in `frontend/`
- Auth pages (login, register)
- Auth context/provider with token management
- Protected route wrapper
- **Backend:** No changes (existing auth endpoints suffice)

### Phase 2: App Shell + Chat (core experience)

- Sidebar layout with shadcn sidebar
- Chat view: message list, input bar, polling-based loading state
- Recent conversations in sidebar (last 5)
- New conversation button
- **Backend:** Add `conversations` router with all 4 endpoints. Add `process_web_message` Celery task. Extend `get_chat_history` with `after_id` support. Configure CORS.

### Phase 3: Tasks Views

- All Tasks list view with status badges, filters
- Upcoming Tasks view
- Tags section in sidebar
- **Backend:** Add `tasks` router (`GET /tasks`, `GET /tasks/upcoming`, `GET /tasks/tags`, `PATCH /tasks/{id}`)

### Phase 4: Telegram + Usage

- Telegram status indicator in sidebar
- Telegram connect modal with join code flow
- Usage counter in sidebar
- API key modal
- **Backend:** Add `GET /telegram/status`, `POST /telegram/join-code`, `GET /settings/usage`, `POST /settings/api-key`, `DELETE /settings/api-key`

### Phase 5: Automations + Settings

- Automations list + CRUD view
- Settings page
- **Backend:** Add `automations` router, `GET /settings`, `PATCH /settings`

---

## Key Decisions

- **Async chat via Celery + polling:** `POST /conversations/{id}/messages` returns immediately after recording the user message and enqueuing the agent work. The frontend polls for new messages every 3 seconds for up to 60 seconds. This mirrors the existing Telegram architecture and avoids blocking HTTP connections.
- **New Celery task:** `process_web_message(conversation_id, message_text, user_id)` in `channels/tasks.py`. Calls `handle_user_incoming` (same function Telegram uses). Agent replies are persisted as `WebChatMessage` rows by `WebConversation.send_message` during the agent run.
- **Polling endpoint:** `GET /conversations/{id}/messages?after_id=X` returns messages with `id > X`, used by the polling loop to fetch only new messages.
- **Tags are derived, not a separate entity:** Tags come from the `Task.tags` JSONField. The `/tasks/tags` endpoint extracts distinct values. No Tag CRUD needed.
- **Web channel is auto-created:** On first conversation creation, `get_or_create_default_web_channel` handles it transparently.
- **No WebSocket for MVP:** Polling is sufficient. Real-time features (SSE streaming, live typing indicators) are post-MVP.
- **CORS:** Django backend will need `django-cors-headers` configured for the Vite dev server origin.
