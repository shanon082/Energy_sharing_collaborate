# Synthetic consumer workspace review

These images were captured from the built Next.js production preview on
2026-11-17, using only loopback fixtures and isolated test TLS. They contain no
real account records, real payment authorizations or physical meter readings.
The example 5,000 principal / 5,250 due / 2,500 applied / 2,750 outstanding is a
controlled acceptance fixture, not an application fallback.

See [the handoff](../../WEB_CONSUMER_PARITY.md) for route scopes, tests, changed
files, exact deployment instructions and limitations. `browser-results.json`
records the completed journey and tested viewport widths.

Use `desktop-home.png`, `desktop-loans.png`, `desktop-buy-units.png`,
`desktop-apply-terms.png`, `desktop-activity.png` and `phone-home.png` for the main
review. Phone `-full.png` files include scrollable content in addition to the
separate actual viewport captures.
