"use client"

import { Token } from "@/interface/token.interface";
import { CopyCheckIcon, CopyIcon } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";

export default function TransactionButton({txn}: {txn: Token}){
    const [trasactioIdCopied, setTrasactioIdCopied] = useState("");


    return <>
    <button
                onClick={() => {
                  navigator.clipboard.writeText(
                    txn.token
                  );
                  toast.success("Token to clipboard!");
                  setTrasactioIdCopied(txn.token);
                  setTimeout(() => setTrasactioIdCopied(""), 2000);
                }}
                className="w-full rounded-md border border-border bg-muted/40 p-2 text-left text-sm text-foreground transition-colors hover:bg-muted"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-[13px] text-foreground">
                    {txn.token}
                  </span>
                  {trasactioIdCopied === txn.token ? (
                    <CopyCheckIcon className="h-4 w-4 shrink-0 text-emerald-600" />
                  ) : (
                    <CopyIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                </div>
              </button>
    </>

}
