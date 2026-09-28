import type { Metadata } from "next";
import Link from "next/link";
import PublicPageShell from "@/components/common/public-page-shell";

export const metadata: Metadata = {
  title: "Privacy Policy | gPawa",
  description: "How gPawa collects, uses, and protects your personal information.",
};

export default function PrivacyPage() {
  const effectiveDate = "24 June 2025";

  return (
    <PublicPageShell
      title="Privacy Policy"
      subtitle={`Effective date: ${effectiveDate}. This policy explains how gPawa handles your information.`}
    >
      <h2>1. Who we are</h2>
      <p>
        gPawa (&ldquo;we&rdquo;, &ldquo;us&rdquo;) operates a digital platform for buying, sharing, and borrowing
        electricity units. This policy applies to the gPawa website, mobile application, USSD service, and related
        APIs.
      </p>

      <h2>2. Information we collect</h2>
      <p>We collect information needed to run the service safely and legally:</p>
      <ul>
        <li>
          <strong>Account data</strong> — name, email address, phone number, and password (stored in hashed form).
        </li>
        <li>
          <strong>Meter data</strong> — meter numbers, meter type (STS or AMI), and device identifiers needed for
          token delivery or smart-meter updates.
        </li>
        <li>
          <strong>Transaction data</strong> — purchases, shares, transfers, loan applications, repayments, amounts,
          timestamps, and payment references from mobile-money providers.
        </li>
        <li>
          <strong>Usage data</strong> — electricity consumption readings where available from connected smart meters.
        </li>
        <li>
          <strong>Technical data</strong> — IP address, browser or device type, and logs needed for security and
          fraud prevention.
        </li>
      </ul>

      <h2>3. How we use your information</h2>
      <ul>
        <li>Provide and improve the gPawa service</li>
        <li>Process payments and deliver units to your meter</li>
        <li>Send service notifications (for example share confirmations, low-balance alerts, loan reminders)</li>
        <li>Comply with financial and energy regulations applicable in Uganda</li>
        <li>Detect fraud, abuse, and unauthorized access</li>
        <li>Respond to support requests you send us</li>
      </ul>

      <h2>4. Legal basis</h2>
      <p>
        We process your data to perform our contract with you (providing the service), to meet legal obligations,
        and — where appropriate — with your consent (for example marketing emails, if offered and opted in).
      </p>

      <h2>5. Sharing with third parties</h2>
      <p>We do not sell your personal data. We may share limited information with:</p>
      <ul>
        <li>Mobile-money operators (for example MTN MoMo) to complete payments you initiate</li>
        <li>Telecom and USSD providers to deliver the dial-code service</li>
        <li>Meter and IoT platforms (for example ThingsBoard) to credit AMI meters and read usage</li>
        <li>Email and SMS providers to send notifications you expect from the service</li>
        <li>Regulators, courts, or law enforcement when required by law</li>
      </ul>
      <p>Each partner receives only what is necessary for their role.</p>

      <h2>6. Data retention</h2>
      <p>
        We keep account and transaction records for as long as your account is active and for a reasonable period
        afterward to meet legal, tax, and dispute-resolution requirements. You may request deletion subject to
        limits imposed by law and ongoing loan or fraud investigations.
      </p>

      <h2>7. Security</h2>
      <p>
        We use industry-standard measures including encrypted connections (HTTPS), hashed passwords, access
        controls for staff, and audit logging for sensitive actions. No system is perfectly secure; please use a
        strong password and keep your PIN private.
      </p>

      <h2>8. Your rights</h2>
      <p>Depending on applicable law, you may have the right to:</p>
      <ul>
        <li>Access a copy of your personal data</li>
        <li>Correct inaccurate information in your profile</li>
        <li>Request deletion where legally permitted</li>
        <li>Object to certain processing or withdraw consent</li>
      </ul>
      <p>
        To exercise these rights, contact us at{" "}
        <a href="mailto:gpawateam@gmail.com">gpawateam@gmail.com</a>.
      </p>

      <h2>9. Children</h2>
      <p>
        gPawa is not directed at children under 18. Accounts must be opened by adults or with appropriate guardian
        consent where local law allows.
      </p>

      <h2>10. Changes</h2>
      <p>
        We may update this policy from time to time. Material changes will be posted on this page with a new
        effective date. Continued use of gPawa after changes means you accept the updated policy.
      </p>

      <h2>11. Contact</h2>
      <p>
        Privacy questions: <a href="mailto:gpawateam@gmail.com">gpawateam@gmail.com</a> or our{" "}
        <Link href="/contact">contact page</Link>.
      </p>
    </PublicPageShell>
  );
}
