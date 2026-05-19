# Distilled TI NextChat Demo

This folder is a local NextChat-based demo wired to the Distilled TI context
support-signal API. Users chat normally in NextChat; recent chat context is
sent to the backend through a server-side route, and admins review support
signals at `/support-admin`.

完整部署、验收和故障排查见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## Run

1. Start the Distilled TI backend on `http://127.0.0.1:8000`.
2. Copy `.env.template` to `.env.local` and set at least:

```env
DISTILLED_TI_API_BASE=http://127.0.0.1:8000
DISTILLED_TI_CONTEXT_API_KEY=
DISTILLED_TI_APPLICATION_ID=nextchat-support-demo
DISTILLED_TI_ADMIN_TOKEN=
```

3. Configure the chat model provider as usual for NextChat, for example
   `DEEPSEEK_API_KEY`, `DEEPSEEK_URL`, `CUSTOM_MODELS`, and `DEFAULT_MODEL`.
4. Install and run:

Recommended wrapper from the parent directory:

```powershell
cd ..
.\start-nextchat-demo.ps1 -Port 3101 -Install
```

Linux:

```bash
cd ..
PORT=3101 INSTALL=auto ./start-nextchat-demo.sh
```

Manual NextChat startup:

```powershell
npm install --ignore-scripts --legacy-peer-deps --package-lock=false
npm run dev
```

## Integration Points

- `app/components/support-signal-probe.tsx` observes the active chat session and
  sends debounced context snapshots to `/api/distilled/context`.
- `app/api/distilled/context/route.ts` forwards analysis requests to
  `POST /api/context/analyze` without exposing backend API keys to the browser.
- `app/api/distilled/alerts/route.ts` forwards admin alert queries to
  `GET /api/context/alerts`.
- `app/support-admin/page.tsx` shows recent medium/high/crisis support signals
  for human review.

The API is non-diagnostic. It should be used for authorized support and product
safety workflows, not covert medical diagnosis or automated clinical decisions.
