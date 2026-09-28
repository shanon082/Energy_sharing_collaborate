"use client";

import { CopyCheckIcon, CopyIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import toast from "react-hot-toast";

export default function LinkText({ txt }: { txt: string }) {
  const [trasactioIdCopied, setTrasactioIdCopied] = useState("");

  return (
    <div className="flex justify-between items-center gap-2">
      <Link
        href={txt}
        className="w-full rounded-md p-2 text-left text-sm font-medium bg-gray-50 text-gray-500 transition-all duration-75 hover:bg-gray-100"
      >
        {txt}
      </Link>
      <div
        className="bg-transparent cursor-pointer"
        onClick={() => {
          navigator.clipboard.writeText(txt);
          toast.success("Copied to clipboard");
          setTrasactioIdCopied(txt);
          setTimeout(() => setTrasactioIdCopied(""), 2000);
        }}
      >
        {trasactioIdCopied === txt ? (
          <CopyCheckIcon className="h-4 w-4" />
        ) : (
          <CopyIcon className="h-4 w-4" />
        )}
      </div>
    </div>
  );
}
