import type { Metadata } from "next";
import PublicPageShell from "@/components/common/public-page-shell";

export const metadata: Metadata = {
  title: "About | EnergyFlex",
  description: "Learn about EnergyFlex — micro-loans for households and communities in Uganda.",
};

export default function AboutPage() {
  return (
    <PublicPageShell
      title="About EnergyFlex"
      subtitle="A digital platform for buying electricity units and applying for loans — fairly and transparently."
    >
      <h2>Our mission</h2>
      <p>
        EnergyFlex helps households, campuses, and community mini-grids buy electricity units and access
        transparent electricity loans without queues, opaque fees, or unnecessary middlemen.
      </p>

      <h2>What we do</h2>
      <ul>
        <li>
          <strong>Buy units</strong> — Pay with mobile money and receive kilowatt-hours (kWh) credited to your wallet
          or meter, priced with ERA-compliant block tariffs.
        </li>
        <li>
          <strong>Borrow units</strong> — Apply for a small electricity loan when you are short, with interest capped
          at Uganda&apos;s statutory maximum of 2.8% per month.
        </li>
        <li>
          <strong>Track usage</strong> — View balances, transactions, and (for smart meters) daily consumption from
          your dashboard.
        </li>
      </ul>

      <h2>Who it is for</h2>
      <p>
        EnergyFlex is built for everyday electricity consumers — families, students, small businesses, and institutions
        that need a straightforward way to purchase electricity or apply for a short-term loan.
      </p>

      <h2>Built for trust and compliance</h2>
      <ul>
        <li>Transparent pricing — you see units and amounts before you confirm.</li>
        <li>Official tariff blocks aligned with Uganda Electricity Regulatory Authority (ERA) guidance.</li>
        <li>Lending limits and interest caps enforced in software, not left to informal agreements.</li>
        <li>Purchases, loan applications, and repayments are recorded for your history and authorized staff review.</li>
      </ul>

      <h2>Technology</h2>
      <p>
        EnergyFlex works with standard prepaid token meters (STS) and networked smart meters (AMI) connected through
        industry platforms such as ThingsBoard. You can use the service on the web, Android mobile app, or USSD
        on a basic phone — the same account works everywhere.
      </p>

      <h2>Pilot programme</h2>
      <p>
        EnergyFlex is developed as part of energy-access research and pilot deployments in Uganda. Features and
        coverage may expand over time as we partner with utilities, campuses, and community operators.
      </p>
    </PublicPageShell>
  );
}
