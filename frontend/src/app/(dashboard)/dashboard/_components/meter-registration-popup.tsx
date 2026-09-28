"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle, CheckCircle, Zap, X } from "lucide-react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { post, get } from "@/lib/fetch-client";
import { getApiErrorMessage } from "@/lib/api-response";
import MeterArchitecturePicker, {
  type MeterArchitecture,
} from "./meter-architecture-picker";
import { isValidMeterNumber, METER_NO_MAX_LENGTH } from "@/lib/meter-validation";

interface MeterRegistrationPopupProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  forceCompletion?: boolean;
}

export default function MeterRegistrationPopup({
  isOpen,
  onClose,
  onSuccess,
  forceCompletion = false,
}: MeterRegistrationPopupProps) {
  const [architecture, setArchitecture] = useState<MeterArchitecture>("STS");
  const [meterNo, setMeterNo] = useState("");
  const [iotDeviceToken, setIotDeviceToken] = useState("");
  const [label, setLabel] = useState("");
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleArchChange = (arch: MeterArchitecture) => {
    setArchitecture(arch);
    if (arch === "STS") setIotDeviceToken("");
  };

  useEffect(() => {
    if (isOpen) {
      const checkAdmin = async () => {
        try {
          const response = await get<{ is_admin?: boolean; user_role?: string }>(
            "auth/get-user-config/"
          );
          if (response.error) {
            if (response.status === 401) {
              window.location.href = "/auth/login?session=expired";
            }
            return;
          }
          const userData = response.data;
          if (userData?.is_admin || userData?.user_role === "ADMIN") {
            onSuccess();
          }
        } catch {
          /* ignore */
        }
      };
      checkAdmin();
    }
  }, [isOpen, onSuccess]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isValidMeterNumber(meterNo)) {
      setMessage({ type: "error", text: "Please enter a meter number" });
      return;
    }

    if (architecture === "AMI" && !iotDeviceToken.trim()) {
      setMessage({ type: "error", text: "ThingsBoard device access token is required for AMI meters" });
      return;
    }

    setIsLoading(true);
    setMessage(null);

    const payload: Record<string, string> = {
      meter_no: meterNo.trim(),
      architecture,
    };
    if (label.trim()) payload.label = label.trim();
    if (architecture === "AMI") {
      payload.iot_device_token = iotDeviceToken.trim();
    }

    try {
      const response = await post<any>("meter/register/", payload);
      if (response.error) {
        setMessage({ type: "error", text: getApiErrorMessage(response.error, "Failed to register meter") });
      } else {
        setMessage({ type: "success", text: "Meter registered successfully!" });
        setTimeout(() => onSuccess(), 1500);
      }
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Network error. Please try again." });
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const canSubmit =
    isValidMeterNumber(meterNo) &&
    (architecture === "STS" || iotDeviceToken.trim().length > 0);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <Card className="w-full max-w-lg relative my-4">
        {!forceCompletion && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-2 top-2 h-6 w-6"
            onClick={onClose}
            disabled={isLoading}
          >
            <X className="h-4 w-4" />
          </Button>
        )}

        <CardHeader className="text-center pb-4">
          <div className="flex items-center justify-center w-12 h-12 bg-blue-100 rounded-full mb-3 mx-auto">
            <Zap className="h-6 w-6 text-blue-600" />
          </div>
          <CardTitle className="text-lg">
            {forceCompletion ? "Step 1: Register Your Electricity Meter" : "Register Your Electricity Meter"}
          </CardTitle>
          <CardDescription>
            {forceCompletion
              ? "Choose STS or AMI, then add your first meter. You can register more meters later (e.g. rental units) under the same login."
              : "One account can manage multiple meters and sub-meters — ideal for landlords with several rental units."}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {message && (
            <Alert
              className={cn(
                "mb-4",
                message.type === "success" ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"
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
              <AlertDescription className={message.type === "success" ? "text-green-700" : "text-red-700"}>
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
              <Label htmlFor="meterNo">
                Meter Number <span className="text-destructive">*</span>
              </Label>
              <Input
                id="meterNo"
                type="text"
                value={meterNo}
                onChange={(e) => setMeterNo(e.target.value)}
                placeholder="Enter meter number"
                maxLength={METER_NO_MAX_LENGTH}
                required
                disabled={isLoading}
                className={cn(
                  !isValidMeterNumber(meterNo) && meterNo.length > 0 && "border-destructive"
                )}
              />
              {!isValidMeterNumber(meterNo) && meterNo.length > 0 && (
                <p className="text-xs text-destructive">Please enter a meter number</p>
              )}
            </div>

            {architecture === "AMI" && (
              <div className="space-y-2">
                <Label htmlFor="iotDeviceToken">
                  ThingsBoard access token <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="iotDeviceToken"
                  type="text"
                  value={iotDeviceToken}
                  onChange={(e) => setIotDeviceToken(e.target.value)}
                  placeholder="Device access token from your utility"
                  required
                  disabled={isLoading}
                  className="font-mono text-sm"
                />
              </div>
            )}

            <div className="text-xs text-muted-foreground space-y-1">
              <p>• Find your meter number on your electricity bill or the meter display</p>
              {architecture === "AMI" && (
                <p>• Contact your utility for the ThingsBoard device access token</p>
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
                  {forceCompletion ? "Continue to Next Step" : "Register Meter"}
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
