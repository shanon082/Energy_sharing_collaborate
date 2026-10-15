# Current repository integration — 15 October 2026

> Subsequent implemented phase (15 October 2026): Django now stores per-meter demo evidence and uses configured tariff snapshots. Shared web/mobile eligibility and stale-quote handling were updated; see [backend rollout](../backend/docs/METER_CREDIT_TARIFFS.md) and [validation](VALIDATION.md). Authentication/Keystore and the redesigned layouts remain preserved. The earlier integration report below is historical and its unchanged-backend claim applies only to that earlier phase.

The redesigned files were already present. No package was copied, extracted or applied. Integration uses the real App and injected SessionManager, with one mounted shared finance controller and a mobile presentation selected through its `view` prop. Omitting that prop retains the default Next.js presentation.

Restored behaviour includes capability-safe financial controls, stale timestamps, stored assessment/limit fields, pending recovery across tabs and network failures, exact quote/receipt binding, duplicate-submission protection and review-step Android Back handling. Browser testing also found and fixed an unbound browser timer in ForegroundPoller. MainActivity uses adjustResize for keyboard layout; physical-device checks remain required.

Welcome/login/signup and secure authentication/storage modules were not modified. Backend files and policies were not modified during integration. API is `https://shanonsimon.alwaysdata.net/api/v1`; all API browser tests use intercepted fixtures. PreviewApp and browser test adapters are not imported into the installed bundle.

See VALIDATION.md for final build evidence. Do not rerun the original overlay-copy instructions below: they are historical package notes, preserved for reference.

---

# gPawa mobile redesign — 14 October 2026

This package edits the supplied mobile source files. It is not an APK or a complete repository.

## What is implemented

- Five persistent navigation items: Home, Meters, Loans, Buy Units, Account.
- Pale blue background, navy typography, white rounded cards, blue/cyan action buttons and larger touch targets.
- Home: selected meter, server-backed cloud allocation, Apply for Loan and Buy Units shortcuts, assessment entry, activity and hardware status.
- Meters: selection cards, add-meter panel, cloud versus physical balance, usage and expandable delivery information.
- Account: profile summary, editable details, password, meters, history and logout.
- Shorter activity/onboarding copy. Technical explanations are behind expandable disclosures.
- A compact expandable demo badge. Existing finance disclosures and server guards are retained.
- Automatic score workflow retained; no new questionnaire, score calculation or financial API is introduced.
- Unknown balances remain unavailable; no invented physical meter readings.
- Legacy loan records and repayment applied/excess information remain accessible.

`Access.tsx` is byte-for-byte unchanged. Welcome, login and signup styling remains outside the new CSS scope. The optional preview opened from the welcome page is redesigned.

## Connected loan and payment screens

The supplied shared finance controller is now integrated with the mobile layout. Home shows its stored assessment, limit, active loan and recent receipts. Loans has separate My Loans and Apply for Loan views. Buy Units has a dedicated purchase flow. Loan repayment and receipt history use the same existing controller and API contracts.

The controller stays mounted when changing mobile tabs so pending recovery is retained. Its existing request IDs, quote hashes, consent, currency isolation, server settlement and assessment parsing remain in use. Late quote responses are discarded after relevant form changes; expired quotes cannot be submitted. A zero countdown does not display payment success without a settled server response.

The new `sandbox-mobile-view.tsx` supplies presentation. The shared controller defaults to its original web view, preserving existing Next.js callers. No new questionnaire or client-generated score was added. Home uses the stored sandbox assessment in sandbox mode, and the existing core eligibility card outside sandbox mode.

## Files

Changed existing sources:
- `mobile/src/App.tsx`
- `mobile/src/Activity.tsx`
- `mobile/src/Onboarding.tsx`
- `mobile/src/Profile.tsx`
- `mobile/src/PreviewApp.tsx`
- `mobile/src/consumer-navigation.ts`
- `mobile/src/format.ts`
- `mobile/src/style.css`
- `frontend/src/components/sandbox-consumer.tsx`

New sources:
- `mobile/src/ConsumerUI.tsx`
- `mobile/src/CreditSummary.tsx`
- `frontend/src/components/sandbox-mobile-view.tsx`

Unchanged supplied sources are included for reference: Access.tsx, Delivery.tsx, LoanQuote.tsx, PaymentActions.tsx, main.tsx, ui.tsx, use-native-back.ts.

The supplied `frontend/src/lib/sandbox.ts` contract is included unchanged. `preview/finance-preview.tsx` is a browser-only mock harness, not production code.

## Integration in your existing repository

1. Commit your current work or make a backup.
2. Review `mobile-redesign.patch`, especially App.tsx and navigation changes.
3. Merge the changed and new files at their matching `mobile/` and `frontend/` paths. Include BOTH shared component files. Keep existing API/auth modules, assets, package configuration and Android project. Compare the included sandbox.ts with your current contract before copying; do not overwrite newer repository work.
4. Update existing navigation tests that intentionally assert the old six-tab design. Test the five new tabs plus Activity and Usage as child screens.
5. Run the existing project checks:

   ```bash
   cd mobile
   npm run typecheck
   npm test
   ```

6. Run the existing Next.js type checks and shared finance tests too. Resolve integration mismatches before building. This package was produced from partial source attachments; the complete authenticated App and repository build have not been checked here.
7. After checking signed-in flows, use your existing documented Android build pipeline and signing configuration:

   ```bash
   npm run android:sync:debug
   cd android
   ./gradlew assembleDebug --no-daemon
   ```

Preserve the current alwaysdata HTTPS endpoint and existing debug signing identity. Do not generate a replacement signing key. No backend settings, migrations, credentials, feature flags, endpoints, signing keys or financial policies were changed. No deployment was performed.

## Previews

- `gpawa-finance-preview.html`: the actual revised shared finance component running against an isolated in-memory mock client. Use this to review Home, loan application, purchase, repayment and receipts. It makes no real API requests.
- `gpawa-redesign-preview.html`: the broader visual preview of Home, Meters, Loans, Buy Units and Account, using sample data.

Both are self-contained offline HTML files. Preview scores, balances, receipts and terms are fixtures; they do not prove hosted transactions work. No preview fixtures are imported by App.tsx.

## Completion checklist in the full repository

- Run full mobile and web checks against existing auth, API, dependencies and tests.
- Check signed-in data, no meter, multiple meters, pending assessment, unavailable API, rejected loans, pending/completed payments and logout.
- Verify quote totals, repayment applied/excess, receipt updates and pending recovery against the testing backend.
- Test Android Back, keyboard, safe-area insets and background/foreground behavior on the phone.
- Keep the short no-real-money statement at confirmation and cloud/physical distinctions.
- Build and install using the existing APK signing configuration. This package contains source and previews, not an APK.
