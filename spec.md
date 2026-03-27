# TaskRaptor — product spec

_A living document. Updated as the product grows._

---

## What is this

TaskRaptor is a personal task management system controlled primarily through a Telegram bot. Users send natural language messages to the bot; an AI agent interprets them and manages tasks on their behalf. A web dashboard provides a secondary interface for reviewing and managing tasks.

The core thesis: task capture should have zero friction. If you can send a Telegram message, you can manage your backlog.

---

## Goals

- **Capture tasks wherever you are** — Telegram is the primary input surface. No app to open, no form to fill.
- **Let the agent do the thinking** — natural language in, structured tasks out. The agent handles intent extraction, scheduling suggestions, and reminders.
- **Stay organised with tags** — users are encouraged to tag tasks. Tags become a lightweight taxonomy the agent can search and reason over.
- **Scheduled nudges** — cron-driven reminders push task updates back to the user at useful intervals. The system is proactive, not just reactive.
- **Simple web dashboard** — for users who want a visual overview, manage tasks, see popular tags, and configure their account.

---

## Non-goals (for now)

- Multi-user collaboration or shared task lists
- Native mobile app
- Calendar two-way sync (read-only integration is a later milestone)
- Complex project/subtask hierarchies

---

## Architecture principles

- **Django monolith.** One codebase, one deployment unit. Complexity is earned, not assumed.
- **Dependency injection over mocking.** Functions receive their dependencies explicitly. Boundaries are tested with real infrastructure — no fake databases, no fake queues.
- **The agent is a tool-calling loop.** It receives context (recent messages + relevant tasks) and decides which tools to call. Tools are plain functions injected with a DB session.
- **User-owned Claude API keys.** No LLM cost exposure for the platform. Users bring their own.
- **Cookie-based session auth.** Simple, no token refresh complexity.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Django 5.x, Python 3.12 |
| API | Django Ninja |
| Frontend | React 18 + Vite (served by Django staticfiles) |
| Database | Postgres (`tsvector` full-text search, JSONB metadata) |
| Auth | Django sessions + cookies |
| Agent | Claude via Anthropic SDK (user-supplied API key) |
| Queue / scheduler | Celery + Redis + Celery Beat |
| Bot | Telegram webhook |
| Deployment | Railway / Render — 3 services: web, worker, beat |

---

## Domain concepts

**User** — a TaskRaptor account. Owns tasks, tags, and a Telegram channel. Stores their Claude API key (encrypted at rest).

**TelegramChannel** — a linked Telegram chat. Created when a user sends `JOIN <code>` to the bot. All subsequent messages from that chat are authenticated as the linked user.

**Task** — the core entity. Has a description, status, optional due date, tags, and a JSONB metadata field for future extensibility. Full-text searchable. Schema starts minimal and extends as needed.

**Tag** — a short label attached to tasks. User-scoped. Popular tags (by frequency) are surfaced in the dashboard and fed to the agent as context.

**ConversationMessage** — messages exchanged in a Telegram channel. The agent receives the last N as its context window.

---

## Agent behaviour

Invoked per Telegram message via Celery worker. Receives: the incoming message, last N conversation messages, full-text search results over the user's tasks (pseudo-RAG), and the user's popular tags.

Available tools: `create_task`, `update_task`, `complete_task`, `list_tasks`, `search_tasks`. Responds with plain text sent back to Telegram. No access to anything outside the user's own data.

---

## Telegram flows

**Linking:** User copies their join code from the dashboard → sends `JOIN <code>` to the bot → bot confirms → channel linked.

**Normal use:** Any message after linking is passed to the agent.

**Reminders:** Celery Beat queries tasks with upcoming due dates and sends proactive messages to linked channels.

---

## Milestones

### M1 — foundation ← current
Working cookie auth, simple task CRUD via the web dashboard. No agent yet. Establishes project structure, DI patterns, and E2E test harness.

### M2 — Telegram + agent
Webhook handler, JOIN flow, agent invocation via Celery. User can create and update tasks by chatting with the bot.

### M3 — search + tags
Full-text search via Postgres `tsvector`. Tag model and popular tags query. Agent receives tag context.

### M4 — scheduled reminders
Celery Beat jobs query due tasks and push Telegram messages.

### M5 — calendar integration
Read-only sync with Google Calendar / iCal.

---

## Testing philosophy

No mocking. E2E tests spin up real Postgres and Redis, exercise real Celery tasks, assert on real database state. Unit tests cover pure functions only. If a function touches a DB or queue, it belongs in E2E.