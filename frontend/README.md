# Frontend (Next.js)

Next.js web app for the Energy Sharing platform. Run all commands below from this folder:

```powershell
cd D:\Energy-sharing-project\frontend
```

Full stack setup (backend, database, etc.) is in the repo root [`Readme.md`](../Readme.md).

## Getting started

Install dependencies (first time only, or after `package.json` changes):

```powershell
npm install
```

Start the development server:

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API must be running at `http://localhost:8000` (see `backend/`).

### Dashboard features (ThingsBoard / AMI)

- **Notification bell** — header on dashboard pages; polls `GET /meter/notifications/` for low-units alerts
- **AMI meter card** — on `/dashboard/tokens`; refresh reads live kWh via `GET /meter/check-units/`
- **USSD simulator** — http://localhost:3000/ussd-simulator (Manage `6`, Alerts `7`)

See [`docs/THINGSBOARD_INTEGRATION_GUIDE.md`](../docs/THINGSBOARD_INTEGRATION_GUIDE.md).

Production build:

```powershell
npm run build
npm start
```

---

## Troubleshooting: port in use / dev lock error

If you see errors like:

```text
⚠ Port 3000 is in use by process XXXXX, using available port 3001 instead.
⨯ Unable to acquire lock at ...\frontend\.next\dev\lock, is another instance of next dev running?
```

**Cause:** A previous `npm run dev` is still running (same terminal left open, background process, or a second terminal started). Only one dev server can run per project folder.

### Fix (Windows PowerShell)

Run these from `frontend/`:

**1. Find what is using port 3000**

```powershell
netstat -ano | findstr ":3000"
```

The last column is the **PID** (process ID). Example: `31700`.

**2. Stop that process**

```powershell
Stop-Process -Id 31700 -Force
```

Replace `31700` with the PID from step 1. If several `node` processes are left over from an old dev run, you can list them:

```powershell
Get-Process node -ErrorAction SilentlyContinue | Select-Object Id, ProcessName
```

Stop any that belong to this project’s dev server (often the one bound to port 3000, plus parent `npm` / `next dev` processes).

**3. Remove the stale lock file (only if step 2 did not clear it)**

```powershell
Remove-Item .next\dev\lock -Force -ErrorAction SilentlyContinue
```

Do this only when no `next dev` is running. If you get “file is in use”, go back to step 2.

**4. Start dev again (one terminal only)**

```powershell
npm run dev
```

### Prevention

- Stop the server with **Ctrl+C** in the terminal where `npm run dev` is running before starting it elsewhere.
- Do not run `npm run dev` in two terminals for the same `frontend/` folder.
- If the site already loads at [http://localhost:3000](http://localhost:3000), you do not need to start it again.

### Other warnings

`baseline-browser-mapping` “data is over two months old” is harmless. Update when convenient:

```powershell
npm i baseline-browser-mapping@latest -D
```

---

## Learn more

- [Next.js documentation](https://nextjs.org/docs)
- [Next.js deployment](https://nextjs.org/docs/app/building-your-application/deploying)


## Development chunk-load recovery

`npm run dev` uses Next.js's supported `--webpack` development compiler to avoid
intermittent Turbopack chunk-loading failures seen in this project's auth layout.
Production `npm run build` is unchanged. No dependency upgrade, static export,
authentication bypass or type-check suppression is involved. The auth layout uses
the root layout's fonts; its unused Inter download has been removed.

Stop the existing project dev server first (Ctrl+C in its terminal), then restart
with `npm run dev` and hard-refresh the browser (Ctrl+Shift+R). Do not run multiple
servers from the same output directory. If a clean restart is needed, preserve
only the generated development output rather than deleting source or dependencies:

```bash
# From frontend/, with the development server stopped:
mv .next/dev /tmp/gpawa-next-dev-backup-$(date +%Y%m%d-%H%M%S)
npm run dev
```

The old development cache remains in the backup path. Production output and the
Android build are unaffected. For deliberate Turbopack troubleshooting, stop the
Webpack server, move aside its generated .next/dev output in the same way, then
use `npm run dev:turbopack`. Only one compiler may use .next/dev at a time.
The initial failure was captured in the dev log; a later request served that
exact JavaScript asset and /auth/login/ with HTTP200. That establishes an
intermittent loading failure, not a reproducible PublicHeader component exception.
