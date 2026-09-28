"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Loader2, Search, CheckCircle2, UserCheck, EyeOff } from "lucide-react";
import { lookupLoanByPhone, payForSomeone } from "../actions";

interface LoanOwner {
  id: number;
  name: string;
  phone: string;
}

interface OwnerLoan {
  id: number;
  loan_id: string;
  outstanding_balance: number;
  total_amount_due: number;
  status: string;
}

type IdentityChoice = "named" | "anonymous";

export default function PayForSomeone() {
  const [phone, setPhone] = useState("");
  const [looking, setLooking] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [owner, setOwner] = useState<LoanOwner | null>(null);
  const [loan, setLoan] = useState<OwnerLoan | null>(null);

  const [payAmount, setPayAmount] = useState("");
  const [payFull, setPayFull] = useState(true);
  const [identity, setIdentity] = useState<IdentityChoice>("named");
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState("");
  const [success, setSuccess] = useState<string | null>(null);

  const formatPhone = (input: string) => {
    const digits = input.replace(/\D/g, "");
    if (digits.startsWith("0")) return "256" + digits.slice(1);
    if (digits.startsWith("256")) return digits;
    return "256" + digits;
  };

  const handleLookup = async () => {
    setLookupError("");
    setOwner(null);
    setLoan(null);
    setSuccess(null);
    const formatted = formatPhone(phone);
    if (formatted.length < 12) {
      setLookupError("Enter a valid Ugandan phone number (e.g. 0712345678).");
      return;
    }
    setLooking(true);
    try {
      const res = await lookupLoanByPhone(formatted);
      if (res.error || !res.data) {
        setLookupError(
          typeof res.error === "string"
            ? res.error
            : "No outstanding loan found for that number."
        );
        return;
      }
      setOwner(res.data.owner);
      setLoan(res.data.loan);
      setPayAmount(String(Math.round(res.data.loan.outstanding_balance)));
      setPayFull(true);
    } catch {
      setLookupError("Network error. Please try again.");
    } finally {
      setLooking(false);
    }
  };

  const handlePay = async () => {
    if (!owner || !loan) return;
    setPayError("");
    const amount = parseFloat(payAmount);
    if (!amount || amount <= 0) {
      setPayError("Enter a valid payment amount.");
      return;
    }
    if (amount > loan.outstanding_balance) {
      setPayError(`Amount cannot exceed outstanding balance of UGX ${loan.outstanding_balance.toLocaleString()}.`);
      return;
    }
    setPaying(true);
    try {
      const res = await payForSomeone({
        owner_phone: formatPhone(phone),
        loan_id: loan.id,
        amount,
        is_anonymous: identity === "anonymous",
      });
      if (res.error || !res.data) {
        setPayError(
          typeof res.error === "string" ? res.error : "Payment failed. Please try again."
        );
        return;
      }
      setSuccess(res.data.message);
      setOwner(null);
      setLoan(null);
      setPhone("");
      setPayAmount("");
    } catch {
      setPayError("Network error. Please try again.");
    } finally {
      setPaying(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Pay for Someone</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Enter another customer's phone number to look up and pay off their outstanding loan on their behalf.
        </p>
      </div>

      {success && (
        <Alert className="border-green-200 bg-green-50/80 dark:border-green-800 dark:bg-green-900/20">
          <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
          <AlertDescription className="text-green-800 dark:text-green-300">{success}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Label htmlFor="pfs-phone">Customer phone number</Label>
        <div className="flex gap-2">
          <Input
            id="pfs-phone"
            placeholder="07XXXXXXXX or 2567XXXXXXXX"
            value={phone}
            onChange={(e) => {
              setPhone(e.target.value);
              setLookupError("");
              setOwner(null);
              setLoan(null);
            }}
            onKeyDown={(e) => e.key === "Enter" && handleLookup()}
            disabled={looking || paying}
          />
          <Button onClick={handleLookup} disabled={looking || !phone.trim() || paying} variant="outline" className="shrink-0">
            {looking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            <span className="ml-2">Look up</span>
          </Button>
        </div>
        {lookupError && <p className="text-sm text-destructive">{lookupError}</p>}
      </div>

      {owner && loan && (
        <Card className="dark:border-white/10">
          <CardContent className="pt-5 space-y-5">
            <div className="flex items-center gap-3 pb-3 border-b dark:border-white/10">
              <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center">
                <UserCheck className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="font-semibold">{owner.name}</p>
                <p className="text-xs text-muted-foreground">{owner.phone}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-lg border dark:border-white/10 px-3 py-2">
                <p className="text-xs text-muted-foreground">Loan ID</p>
                <p className="font-mono font-semibold mt-0.5">{loan.loan_id}</p>
              </div>
              <div className="rounded-lg border dark:border-white/10 px-3 py-2">
                <p className="text-xs text-muted-foreground">Outstanding</p>
                <p className="font-semibold mt-0.5 text-destructive">
                  UGX {loan.outstanding_balance.toLocaleString()}
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Button
                  size="sm"
                  variant={payFull ? "default" : "outline"}
                  onClick={() => {
                    setPayFull(true);
                    setPayAmount(String(Math.round(loan.outstanding_balance)));
                  }}
                  className={payFull ? "gpawa-gradient text-white" : ""}
                >
                  Pay full balance
                </Button>
                <Button
                  size="sm"
                  variant={!payFull ? "default" : "outline"}
                  onClick={() => { setPayFull(false); setPayAmount(""); }}
                  className={!payFull ? "gpawa-gradient text-white" : ""}
                >
                  Partial amount
                </Button>
              </div>

              {!payFull && (
                <div className="space-y-1">
                  <Label htmlFor="pfs-amount">Amount (UGX)</Label>
                  <Input
                    id="pfs-amount"
                    type="number"
                    min={1}
                    max={loan.outstanding_balance}
                    value={payAmount}
                    onChange={(e) => setPayAmount(e.target.value)}
                    placeholder="Enter amount"
                    disabled={paying}
                  />
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <Label className="flex items-center gap-1.5">
                <EyeOff className="h-3.5 w-3.5" />
                Identity
              </Label>
              <Select value={identity} onValueChange={(v) => setIdentity(v as IdentityChoice)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="named">Show my name to the recipient</SelectItem>
                  <SelectItem value="anonymous">Stay anonymous (shown as "anonymous benefactor")</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Admins always see the full record regardless of your choice.
              </p>
            </div>

            {payError && <p className="text-sm text-destructive">{payError}</p>}

            <Button
              className="w-full gpawa-gradient text-white"
              onClick={handlePay}
              disabled={paying || !payAmount}
            >
              {paying ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" />Processing…</>
              ) : (
                `Pay UGX ${payAmount ? Number(payAmount).toLocaleString() : "—"} for ${owner.name}`
              )}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
