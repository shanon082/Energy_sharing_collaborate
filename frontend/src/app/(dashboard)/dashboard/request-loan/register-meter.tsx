"use client";

import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { registerMeter, prototypeEnrollmentEnabled } from "./register-meter/action";
import { isValidMeterNumber, METER_NO_MAX_LENGTH } from "@/lib/meter-validation";

interface RegisterMeterProps {
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

export default function RegisterMeter({ onSuccess, onError }: RegisterMeterProps) {
  const [meterNo, setMeterNo] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [prototype, setPrototype] = useState<boolean | null>(null);
  useEffect(() => {
    let active = true;
    void prototypeEnrollmentEnabled().then(value => { if (active) setPrototype(value); })
      .catch(() => { if (active) setMessage("Could not check enrollment availability. Refresh to retry."); });
    return () => { active = false; };
  }, []);
  const router = useRouter();
  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (prototype === null || isLoading) return;
    if (!isValidMeterNumber(meterNo)) { setMessage("Please enter a valid meter number."); return; }
    setIsLoading(true); setMessage(null);
    try {
      const result = await registerMeter({ meter_no: meterNo.trim() });
      if (result.success) {
        setMessage(result.success); router.refresh();
        setMeterNo(""); onSuccess?.();
      } else {
        const error = result.error || "Could not confirm your request. Retrying the same number is safe.";
        setMessage(error); onError?.(error);
      }
    } catch (cause) {
      const error = cause instanceof Error ? cause.message : "Could not confirm your request.";
      setMessage(error); onError?.(error);
    } finally { setIsLoading(false); }
  };
  return <Card className="w-full max-w-lg mx-auto">
    <CardHeader><CardTitle>{prototype ? "Add your meter" : "Request meter verification"}</CardTitle>
      <CardDescription>{prototype ? "For prototype testing, we assume the entered meter number belongs to you. Ownership and live readings are not verified with the electricity provider. Hardware connection is pending." : "Physical enrollment requires staff to verify your right to use the meter and assign it."}</CardDescription>
    </CardHeader>
    <CardContent>
      {message && <Alert className="mb-4"><AlertDescription>{message}</AlertDescription></Alert>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <label htmlFor="meterNo" className="text-sm font-medium">Meter number</label>
        <Input id="meterNo" value={meterNo} onChange={(event) => setMeterNo(event.target.value)}
          placeholder="Number printed on your meter" maxLength={METER_NO_MAX_LENGTH} required disabled={isLoading} />
        <p className="text-xs text-muted-foreground">Device addresses, keys and meter platform are configured by authorized staff.</p>
        <Button type="submit" className="w-full" disabled={isLoading || prototype === null || !isValidMeterNumber(meterNo)}>
          {isLoading ? "Recording…" : prototype ? "Add your meter" : "Request verification"}
        </Button>
        <Button type="button" variant="link" disabled={isLoading} onClick={() => router.push("/dashboard/request-loan")}>View assigned meters</Button>
      </form>
    </CardContent>
  </Card>;
}
