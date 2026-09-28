"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle, Zap } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { registerMeter } from "./register-meter/action";
import MeterArchitecturePicker, {
  type MeterArchitecture,
} from "../_components/meter-architecture-picker";
import { isValidMeterNumber, METER_NO_MAX_LENGTH } from "@/lib/meter-validation";

interface RegisterMeterProps {
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

export default function RegisterMeter({ onSuccess, onError }: RegisterMeterProps) {
  const [architecture, setArchitecture] = useState<MeterArchitecture>("STS");
  const [meterNo, setMeterNo] = useState("");
  const [staticIp, setStaticIp] = useState("");
  const [label, setLabel] = useState("");
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const isValidIP = (v: string) =>
    /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/.test(
      v
    );

  const handleArchChange = (arch: MeterArchitecture) => {
    setArchitecture(arch);
    if (arch === "STS") setStaticIp("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isValidMeterNumber(meterNo)) {
      setMessage({ type: "error", text: "Please enter a meter number" });
      return;
    }

    if (architecture === "AMI" && !isValidIP(staticIp)) {
      setMessage({ type: "error", text: "Please enter a valid IP address for your AMI meter" });
      return;
    }

    setIsLoading(true);
    setMessage(null);

    const payload: {
      meter_no: string;
      architecture: MeterArchitecture;
      static_ip?: string;
      label?: string;
    } = {
      meter_no: meterNo.trim(),
      architecture,
    };
    if (label.trim()) payload.label = label.trim();
    if (architecture === "AMI") {
      payload.static_ip = staticIp.trim();
    }

    try {
      const result = await registerMeter(payload);

      if (result.success) {
        setMessage({
          type: "success",
          text: "Meter registered successfully! You can now apply for micro-electricity loans.",
        });
        setMeterNo("");
        setStaticIp("");
        setLabel("");
        setArchitecture("STS");

        if (onSuccess) {
          setTimeout(() => onSuccess(), 1500);
        } else {
          setTimeout(() => router.push("/dashboard/request-loan"), 2000);
        }
      } else {
        const errorMsg = result.error || "Failed to register meter";
        setMessage({ type: "error", text: errorMsg });
        onError?.(errorMsg);
      }
    } catch (err: any) {
      const errorMsg = err.message || "Network error. Please check your connection and try again.";
      setMessage({ type: "error", text: errorMsg });
      onError?.(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const canSubmit =
    isValidMeterNumber(meterNo) && (architecture === "STS" || isValidIP(staticIp));

  return (
    <Card className="w-full max-w-lg mx-auto">
      <CardHeader className="text-center">
        <div className="flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4 mx-auto">
          <Zap className="h-8 w-8 text-blue-600" />
        </div>
        <CardTitle className="text-xl">Register Electricity Meter</CardTitle>
        <CardDescription>
          Choose STS or AMI platform. You can add more meters later under the same login (e.g. rental
          units).
        </CardDescription>
      </CardHeader>

      <CardContent>
        {message && (
          <Alert
            className={cn(
              "mb-4",
              message.type === "success"
                ? "border-green-200 bg-green-50"
                : "border-red-200 bg-red-50"
            )}
          >
            {message.type === "success" ? (
              <CheckCircle className="h-4 w-4 text-green-600" />
            ) : (
              <AlertCircle className="h-4 w-4 text-red-600" />
            )}
            <AlertTitle className={message.type === "success" ? "text-green-800" : "text-red-800"}>
              {message.type === "success" ? "Success!" : "Error"}
            </AlertTitle>
            <AlertDescription
              className={message.type === "success" ? "text-green-700" : "text-red-700"}
            >
              {message.text}
            </AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <MeterArchitecturePicker
            value={architecture}
            onChange={handleArchChange}
            disabled={isLoading}
          />

          <div className="space-y-2">
            <Label htmlFor="meterLabel">Unit label (optional)</Label>
            <Input
              id="meterLabel"
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Flat 2B, Shop front"
              disabled={isLoading}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="meterNo" className="text-sm font-medium text-foreground">
              Meter Number <span className="text-destructive">*</span>
            </label>
            <Input
              id="meterNo"
              type="text"
              value={meterNo}
              onChange={(e) => setMeterNo(e.target.value)}
              placeholder="Enter your meter number"
              maxLength={METER_NO_MAX_LENGTH}
              required
              disabled={isLoading}
              className={cn(
                !isValidMeterNumber(meterNo) && meterNo.length > 0 && "border-destructive",
                "w-full"
              )}
            />
            {!isValidMeterNumber(meterNo) && meterNo.length > 0 && (
              <p className="text-xs text-destructive">Please enter a meter number</p>
            )}
          </div>

          {architecture === "AMI" && (
            <div className="space-y-2">
              <label htmlFor="staticIp" className="text-sm font-medium text-foreground">
                Static IP Address <span className="text-destructive">*</span>
              </label>
              <Input
                id="staticIp"
                type="text"
                value={staticIp}
                onChange={(e) => setStaticIp(e.target.value)}
                placeholder="192.168.1.100"
                required
                disabled={isLoading}
                className={cn(
                  !isValidIP(staticIp) && staticIp.length > 0 && "border-destructive",
                  "w-full"
                )}
              />
              {!isValidIP(staticIp) && staticIp.length > 0 && (
                <p className="text-xs text-destructive">Please enter a valid IP address</p>
              )}
            </div>
          )}

          <div className="text-xs text-muted-foreground space-y-1">
            <p>• Find your meter number on your electricity bill or meter display</p>
            {architecture === "AMI" && (
              <p>• Contact your Electricity Utility for the static IP address</p>
            )}
          </div>

          <Button type="submit" className="w-full" disabled={isLoading || !canSubmit}>
            {isLoading ? (
              <>
                <Zap className="h-4 w-4 mr-2 animate-spin" />
                Registering...
              </>
            ) : (
              <>
                <Zap className="h-4 w-4 mr-2" />
                Register Meter
              </>
            )}
          </Button>

          <div className="text-center pt-2">
            <Button
              type="button"
              variant="link"
              onClick={() => router.push("/dashboard/request-loan")}
              disabled={isLoading}
              className="text-sm p-0 h-auto"
            >
              I already have a registered meter
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
