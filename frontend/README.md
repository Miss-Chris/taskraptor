# React + TypeScript + Vite + shadcn/ui

This is the TaskRaptor frontend: Vite, React, TypeScript, Tailwind 4, and shadcn/ui (radix-luma).

## Development

1. Start the Django API (from `../api/`):

   ```bash
   uv run python manage.py runserver
   ```

2. Start Vite (proxies `/api` → `http://127.0.0.1:8000`):

   ```bash
   npm run dev
   ```

3. Open the app, register or log in. Session tokens are stored in `localStorage` under `taskraptor_auth_token`.

Routes:

- `/login` — sign in with email + password
- `/register` — create an account
- `/` — home (requires auth)

## Adding components

```bash
npx shadcn@latest add button
```

UI primitives live under `src/components/ui/`.

## Using components

```tsx
import { Button } from "@/components/ui/button"
```
