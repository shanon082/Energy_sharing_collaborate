import { Suspense } from "react";
import { notFound } from "next/navigation"; 
import ResetPasswordForm from "./_components/form";

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ uid?: string; token?: string }>;
}) {
  const params = await searchParams;

  if (!params.uid || !params.token) {
    notFound();
  }

  return (
    <div className="min-h-screen overflow-hidden bg-gradient-to-br from-blue-50 via-emerald-50 to-blue-100 dark:from-blue-950 dark:via-emerald-900/20 dark:to-blue-900">
      <Suspense
        fallback={
          <div className="flex items-center justify-center min-h-screen">
            Loading...
          </div>
        }
      >
        <ResetPasswordForm uid={params.uid} token={params.token} />
      </Suspense>
    </div>
  );
}
