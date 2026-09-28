import type { Metadata } from "next";
import Link from "next/link";
import PublicPageShell from "@/components/common/public-page-shell";

export const metadata: Metadata = {
  title: "Contact | gPawa",
  description: "Get in touch with the gPawa team for support, partnerships, and general enquiries.",
};

const SUPPORT_EMAIL = "gpawateam@gmail.com";

export default function ContactPage() {
  return (
    <PublicPageShell
      title="Contact us"
      subtitle="We are here to help with account issues, meter registration, and partnership enquiries."
    >
      <div className="not-prose grid gap-6 sm:grid-cols-2 mb-10">
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/50 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">General &amp; support</h2>
          <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
            Questions about your account, meter, payments, or sharing units.
          </p>
          <a
            href={`mailto:${SUPPORT_EMAIL}?subject=gPawa%20support%20request`}
            className="text-blue-600 dark:text-blue-400 font-medium hover:underline"
          >
            {SUPPORT_EMAIL}
          </a>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
            We aim to respond within 2 business days.
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-900/50 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Partnerships</h2>
          <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
            Utilities, campuses, mini-grid operators, and research collaborators.
          </p>
          <a
            href={`mailto:${SUPPORT_EMAIL}?subject=gPawa%20partnership%20enquiry`}
            className="text-blue-600 dark:text-blue-400 font-medium hover:underline"
          >
            {SUPPORT_EMAIL}
          </a>
        </div>
      </div>

      <h2>Before you write</h2>
      <p>Including the following helps us resolve your issue faster:</p>
      <ul>
        <li>The email or phone number on your gPawa account</li>
        <li>Your meter number (if applicable)</li>
        <li>A short description of what you tried and any error message you saw</li>
        <li>Screenshots for payment or sharing issues (if you can)</li>
      </ul>

      <h2>Self-service</h2>
      <p>Many tasks do not require contacting us:</p>
      <ul>
        <li>
          <Link href="/auth/forgot-password">Reset your password</Link> from the login page
        </li>
        <li>
          <Link href="/auth/register">Register a new account</Link> if you have not signed up yet
        </li>
        <li>
          <Link href="/#how-it-works">How gPawa works</Link> — step-by-step guide on the home page
        </li>
      </ul>

      <h2>Location</h2>
      <p>
        gPawa is operated from Uganda, serving pilot communities and partner sites across East Africa.
        There is no public walk-in office at this time; please use email for all enquiries.
      </p>

      <h2>Security</h2>
      <p>
        Never share your password, PIN, or one-time codes with anyone — including people claiming to be
        gPawa staff. We will never ask for your full password by email or phone.
      </p>
    </PublicPageShell>
  );
}
