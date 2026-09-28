"use client";

import { useEffect } from "react";

/** Marks the document as an app shell (no public-page body gradient). */
export default function AdminBodyShell({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    document.body.classList.add("app-shell");
    return () => document.body.classList.remove("app-shell");
  }, []);

  return <>{children}</>;
}
