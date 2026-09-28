import type { Metadata } from "next";
import Link from "next/link";
import PublicPageShell from "@/components/common/public-page-shell";

export const metadata: Metadata = {
  title: "Terms of Service | gPawa",
  description: "Terms and conditions for using the gPawa energy sharing platform.",
};

export default function TermsPage() {
  return (
    <PublicPageShell
      title="Terms of Service"
      subtitle="Please read these terms before using gPawa. By creating an account or using the service, you agree to them."
    >
      <h2>1. The service</h2>
      <p>
        gPawa provides a platform to purchase electricity units, share units between registered meters, apply for
        micro-electricity loans, and view transaction history. Availability may vary by pilot site, meter type, and
        payment method.
      </p>

      <h2>2. Eligibility</h2>
      <p>
        You must be at least 18 years old (or the age of majority in your jurisdiction) and able to enter a binding
        contract. You must provide accurate registration information and keep your credentials secure.
      </p>

      <h2>3. Your account</h2>
      <ul>
        <li>You are responsible for all activity under your account.</li>
        <li>Do not share your password or transaction PIN with anyone.</li>
        <li>Notify us promptly if you suspect unauthorized access.</li>
        <li>One person should not maintain multiple accounts to evade limits or fraud controls.</li>
      </ul>

      <h2>4. Payments and units</h2>
      <ul>
        <li>Units are sold using published tariff blocks; VAT and regulatory charges apply as shown at checkout.</li>
        <li>Mobile-money payments are processed by your telecom provider; failed or reversed payments may delay unit delivery.</li>
        <li>STS token meters receive keypad codes; AMI meters are credited over the network when connectivity allows.</li>
        <li>We are not liable for delays caused by third-party networks, utilities, or incorrect meter numbers you enter.</li>
      </ul>

      <h2>5. Sharing and transfers</h2>
      <p>
        When you share units, you confirm the recipient meter number and amount. Shares are generally final once
        confirmed with your password or PIN. Only share with people you trust — gPawa records the transaction but
        cannot reverse informal agreements between users except where required by law or our refund policy.
      </p>

      <h2>6. Loans</h2>
      <p>
        Loan offers depend on eligibility, credit signals, and programme rules. Interest and fees are capped in line
        with Ugandan money-lender regulations (currently 2.8% per month maximum). Late repayment may attract penalties
        within legal limits. Default may affect future credit and service access.
      </p>

      <h2>7. Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>Use gPawa for fraud, money laundering, or unauthorized resale of units</li>
        <li>Attempt to bypass security, tariffs, or lending limits</li>
        <li>Interfere with the platform or other users&apos; accounts</li>
        <li>Provide false meter or identity information</li>
      </ul>

      <h2>8. Suspension and termination</h2>
      <p>
        We may suspend or close accounts that violate these terms, pose a fraud risk, or are required by law.
        You may close your account by contacting support, subject to settling outstanding loans or disputes.
      </p>

      <h2>9. Disclaimers</h2>
      <p>
        gPawa is provided &ldquo;as is&rdquo; during pilot operation. We strive for high availability but do not
        guarantee uninterrupted service. Electricity delivery ultimately depends on meters, grids, and partner systems
        outside our direct control.
      </p>

      <h2>10. Limitation of liability</h2>
      <p>
        To the fullest extent permitted by law, gPawa&apos;s liability is limited to the fees you paid to us for the
        affected transaction in the preceding twelve months. We are not liable for indirect or consequential losses.
      </p>

      <h2>11. Governing law</h2>
      <p>
        These terms are governed by the laws of the Republic of Uganda. Disputes should first be raised with our
        support team; unresolved matters may be referred to competent courts in Uganda.
      </p>

      <h2>12. Contact</h2>
      <p>
        Questions about these terms: <Link href="/contact">contact us</Link> or email{" "}
        <a href="mailto:gpawateam@gmail.com">gpawateam@gmail.com</a>.
      </p>

      <p className="text-sm text-muted-foreground">
        See also our <Link href="/privacy">Privacy Policy</Link>.
      </p>
    </PublicPageShell>
  );
}
