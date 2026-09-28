"use client";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  CheckCheck,
  Clock10Icon,
  EllipsisVertical,
  Zap,
  ShoppingCart,
  CreditCard,
} from "lucide-react";
import TransactionButton from "../../_components/txn-button";
import { Token } from "@/interface/token.interface";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface TokenListProps {
  tokens: Token[];
}

const TokenList = ({ tokens }: TokenListProps) => {
  const [selectedToken, setSelectedToken] = useState<Token | null>(null);

  if (!tokens || tokens.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No tokens found.
      </div>
    );
  }

  // Sort tokens by creation date (newest first)
  const sortedTokens = [...tokens].sort((a, b) => {
    const dateA = new Date(a.created_at || 0);
    const dateB = new Date(b.created_at || 0);
    return dateB.getTime() - dateA.getTime();
  });

  const getSourceIcon = (source: string) => {
    switch (source) {
      case "LOAN":
        return <Zap className="h-4 w-4 text-yellow-600" />;
      case "PURCHASE":
        return <ShoppingCart className="h-4 w-4 text-green-600" />;
      case "SHARE":
        return <CreditCard className="h-4 w-4 text-blue-600" />;
      default:
        return <CreditCard className="h-4 w-4 text-blue-600" />;
    }
  };

  const getSourceColor = (source: string) => {
    switch (source) {
      case "LOAN":
        return "text-yellow-600";
      case "PURCHASE":
        return "text-green-600";
      case "SHARE":
        return "text-blue-600";
      default:
        return "text-blue-600";
    }
  };

  const getSourceDisplayText = (token: Token) => {
    if (token.source === "LOAN" && token.loan_id) {
      return `Loan #${token.loan_id}`;
    }
    if (token.source === "PURCHASE") {
      return "Units Purchase";
    }
    if (token.source === "SHARE") {
      return "Shared Units";
    }
    return token.source_display || token.source;
  };

  return (
    <div className="w-full">
      <div className="flex flex-col gap-1 w-full">
        <h3 className="text-2xl text-left font-bold tracking-tight p-4">
          All Tokens
        </h3>

        <div className="rounded-md border overflow-x-auto w-full max-w-full">
          <Table className="w-full">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[100px]">Token ID</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Token</TableHead>
                <TableHead className="text-right">Units</TableHead>
                {/* <TableHead className="text-right">Date</TableHead> */}
                <TableHead className="text-right">&nbsp;</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedTokens.map((token) => (
                <TableRow key={token.id} className="hover:bg-muted/50">
                  <TableCell className="font-medium">#{token.id}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {getSourceIcon(token.source)}
                      <span
                        className={cn(
                          "text-sm font-medium",
                          getSourceColor(token.source)
                        )}
                      >
                        {getSourceDisplayText(token)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {token.is_used ? (
                        <>
                          <CheckCheck className="h-4 w-4 text-green-600" />
                          <span className="text-green-600 text-sm">Used</span>
                        </>
                      ) : (
                        <>
                          <Clock10Icon className="h-4 w-4 text-amber-600" />
                          <span className="text-amber-600 text-sm">Active</span>
                        </>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <TransactionButton txn={token} />
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    <span
                      className={cn({
                        "text-green-600": token.source === "PURCHASE",
                        "text-yellow-600": token.source === "LOAN",
                        "text-blue-600": token.source === "SHARE",
                      })}
                    >
                      {Number(token.units).toFixed(2)} units
                    </span>
                  </TableCell>
                  {/* <TableCell className="text-right text-sm text-muted-foreground">
                    {token.created_at
                      ? new Date(token.created_at).toLocaleDateString()
                      : "N/A"}
                  </TableCell> */}
                  {/* <TableCell className="text-sm text-muted-foreground">
                    {new Date(token.created_at).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </TableCell> */}
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger className="p-2 hover:bg-muted rounded">
                        <EllipsisVertical className="h-4 w-4" />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setSelectedToken(token)}>
                          View Details
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() =>
                            navigator.clipboard.writeText(token.token)
                          }
                        >
                          Copy Token
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Summary Stats */}
        {/* <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4 p-4">
          <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
            <div className="flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              <h4 className="font-semibold text-blue-800 dark:text-blue-300">
                Total Tokens
              </h4>
            </div>
            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-2">
              {tokens.length}
            </p>
          </div>

          <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg border border-green-200 dark:border-green-800">
            <div className="flex items-center gap-2">
              <ShoppingCart className="h-5 w-5 text-green-600 dark:text-green-400" />
              <h4 className="font-semibold text-green-800 dark:text-green-300">
                Purchased Units
              </h4>
            </div>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-2">
              {tokens.filter((t) => t.source === "PURCHASE").length}
            </p>
          </div>

          <div className="bg-yellow-50 dark:bg-yellow-900/20 p-4 rounded-lg border border-yellow-200 dark:border-yellow-800">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
              <h4 className="font-semibold text-yellow-800 dark:text-yellow-300">
                Loan Tokens
              </h4>
            </div>
            <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400 mt-2">
              {tokens.filter((t) => t.source === "LOAN").length}
            </p>
          </div>
        </div> */}
      </div>

      <Dialog
        open={Boolean(selectedToken)}
        onOpenChange={(open) => {
          if (!open) setSelectedToken(null);
        }}
      >
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Token Details</DialogTitle>
            <DialogDescription>
              Details for token #{selectedToken?.id ?? "-"}.
            </DialogDescription>
          </DialogHeader>

          {selectedToken && (
            <div className="space-y-2 text-sm">
              <p><strong>Token ID:</strong> {selectedToken.id}</p>
              <p><strong>Token:</strong> {selectedToken.token}</p>
              <p><strong>Source:</strong> {selectedToken.source_display || selectedToken.source}</p>
              <p><strong>Units:</strong> {Number(selectedToken.units).toFixed(2)} units</p>
              <p><strong>Status:</strong> {selectedToken.is_used ? "Used" : "Active"}</p>
              <p>
                <strong>Date:</strong>{" "}
                {selectedToken.created_at
                  ? new Date(selectedToken.created_at).toLocaleString()
                  : "N/A"}
              </p>
              {selectedToken.loan_id && (
                <p><strong>Loan ID:</strong> {selectedToken.loan_id}</p>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TokenList;
