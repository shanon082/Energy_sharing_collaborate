import Link from "next/link";

export default function FeatureUnavailable() {
  return (
    <main className="p-6 space-y-4">
      <h1 className="text-xl font-semibold">Feature unavailable</h1>
      <p>This feature is currently disabled. Existing records remain available.</p>
      <Link href="/dashboard" className="underline">Return to dashboard</Link>
    </main>
  );
}
