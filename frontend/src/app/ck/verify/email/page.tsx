import { Suspense } from "react";
import VerifyEmail from "./_components/verify";

export default function Page() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <VerifyEmail />
    </Suspense>
  );
}

