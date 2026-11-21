# Consumer web contrast fix — 22 November 2026

The light consumer workspace inherited dark-theme card/input foreground tokens
when a saved site preference selected dark mode. Reproduced on actual local Next
routes: labels were rgb(244,247,250) on white (1.08:1), input values1.05:1.
`before.json` and `before-dark-preference.png` record the synthetic reproduction.

The workspace now owns a coherent light semantic palette, including Tailwind
aliases, native control color scheme, explicit card/field text and readable disabled
states. Body is slightly softer, input boundaries stronger, pending notices distinct,
and token values larger. Keyboard focus remains visible on light and dark surfaces.
The existing layout and global public/staff theme behavior remain intact.

Final production CSS was checked without injected styles on Home, Meters, Loans,
Request Loan, Buy Units, Activity and Account under saved light/dark preferences:
14 combinations, zero browser runtime errors. The lowest sampled form/receipt/
muted/disabled text contrast was 5.38:1; samples are in `results.json`. This is
focused contrast evidence, not a claim of a complete accessibility audit. A390px
phone-width check passed without horizontal overflow. Token inputs are masked.

- [Buy Units, saved dark preference](buy-units-dark.png)
- [Buy Units, light preference](buy-units-light.png)
- [Phone-width Buy Units](buy-units-phone.png)
- [Request Loan](request-loan-dark.png)
- [Loan balances and tokens](loans-dark.png)
- [Dashboard](dashboard-dark.png)
- [Meters](meters-dark.png)
- [Account](account-dark.png)
- [Activity](activity-dark.png)

All browser data is synthetic from the isolated loopback HTTPS API. No live hosted
account/payment/provider or physical-device testing occurred. The owned preview
was stopped afterward.

Validation: `node --test --test-concurrency=1 tests/*.test.mjs` from frontend passed
14 test files; `npm run build -- --webpack` passed strict type checking and49 pages.
Existing middleware-convention/browser-mapping-age warnings remain unchanged.
`git diff --check` passed. No new application dependencies or business-rule changes.

Deploy the updated frontend commit to the existing Vercel project (root frontend,
existing API_URL and authentication configuration). No deployment/commit/push was
performed here. Backend, Android sources, signing identity, feature flags and
financial/device restrictions were unchanged. No APK rebuild/migration is needed
for this web-only stylesheet fix. Earlier release archives remain historical.
