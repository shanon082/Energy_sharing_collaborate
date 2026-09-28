"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { post } from "@/lib/fetch";
import { getApiErrorMessage } from "@/lib/api-response";
import { Loader2, CheckCircle, AlertCircle, Smartphone, DollarSign } from "lucide-react";
import { useWallet } from "@/app/contexts/walletContext";

type WalletActionResponse = {
  success: boolean;
  message?: string;
  wallet_balance?: string;
  reference?: string;
  amount?: string;
  phone_number?: string;
};

export default function Deposit() {
  const [amount, setAmount] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [transaction, setTransaction] = useState<any>(null);
  
  const { refreshBalances } = useWallet();

  const submit = async () => {
    // Validation
    if (!amount || parseFloat(amount) <= 0) {
      setError("Please enter a valid amount");
      return;
    }
    
    if (!phoneNumber) {
      setError("Please enter your phone number");
      return;
    }

    setLoading(true);
    setMessage(null);
    setError(null);
    setTransaction(null);

    const response = await post<WalletActionResponse>("wallet/deposit/", {
      amount,
      phone_number: phoneNumber,
    });

    setLoading(false);
    
    if (response.error) {
      setError(getApiErrorMessage(response.error, "Deposit failed"));
      return;
    }

    if (response.data?.success) {
      setMessage(response.data.message || "Deposit completed successfully!");
      setTransaction({
        amount: response.data.amount,
        reference: response.data.reference,
        phone: response.data.phone_number,
        balance: response.data.wallet_balance,
      });
      setAmount("");
      setPhoneNumber("");
      
      // Refresh balances in real-time
      await refreshBalances();
      
      // Clear success message after 5 seconds
      setTimeout(() => setMessage(null), 5000);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DollarSign className="h-5 w-5 text-green-500" />
          Deposit Money
        </CardTitle>
        <CardDescription>
          Add money to your wallet using MTN Mobile Money (Sandbox)
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="amount">Amount (UGX)</Label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              id="amount"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              type="number"
              placeholder="Enter amount"
              className="pl-9"
              disabled={loading}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="phone">MTN Mobile Money Number</Label>
          <div className="relative">
            <Smartphone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              id="phone"
              value={phoneNumber}
              onChange={(event) => setPhoneNumber(event.target.value)}
              type="tel"
              placeholder="e.g., 07xxxxxxxxx or 2567xxxxxxxx"
              className="pl-9"
              disabled={loading}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Enter your MTN Uganda phone number (format: 077XXXXXXX or 25677XXXXXXX)
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-md bg-red-50 text-red-800">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {message && (
          <div className="flex items-center gap-2 p-3 rounded-md bg-green-50 text-green-800">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm">{message}</span>
          </div>
        )}

        {transaction && (
          <div className="p-3 rounded-md bg-blue-50">
            <p className="text-sm font-medium text-blue-800 mb-2">Transaction Details:</p>
            <div className="space-y-1 text-sm text-gray-900">
              <p>Amount: <strong>UGX {parseFloat(transaction.amount).toLocaleString()}</strong></p>
              <p>Phone: <strong>{transaction.phone}</strong></p>
              <p>Reference: <strong>{transaction.reference}</strong></p>
              <p>New Balance: <strong>UGX {parseFloat(transaction.balance).toLocaleString()}</strong></p>
            </div>
          </div>
        )}

        <Button 
          onClick={submit} 
          disabled={loading || !amount || !phoneNumber} 
          className="w-full bg-green-600 hover:bg-green-700"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Processing Deposit...
            </>
          ) : (
            <>
              <Smartphone className="mr-2 h-4 w-4" />
              Deposit via Mobile Money
            </>
          )}
        </Button>

        <div className="text-xs text-muted-foreground bg-yellow-50 p-2 rounded">
          <strong>Sandbox Mode:</strong> This is a simulation. No actual money will be deducted from your mobile money account.
          Deposits are instantly credited to your wallet for testing purposes.
        </div>
      </CardContent>
    </Card>
  );
}