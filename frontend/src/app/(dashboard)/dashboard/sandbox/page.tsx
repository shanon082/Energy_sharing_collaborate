import Link from "next/link";
import SandboxWeb from "@/components/sandbox-web";
import "./sandbox.css";

export const dynamic = "force-dynamic";
export default function SandboxPage() {
  return <main className="sandbox-page"><Link href="/dashboard">Return to dashboard</Link><h1>Consumer sandbox</h1><SandboxWeb /></main>;
}
