"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertCircle,
  CheckCircle,
  Zap,
  X,
  Wifi,
  Battery,
  RefreshCw,
  Edit,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { post, get, patch } from "@/lib/fetch-client";
import { getApiErrorMessage } from "@/lib/api-response";
import { Label } from "@/components/ui/label";
import MeterArchitecturePicker, {
  type MeterArchitecture,
} from "./meter-architecture-picker";
import { isValidMeterNumber, METER_NO_MAX_LENGTH } from "@/lib/meter-validation";

interface MeterManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  userData: any;
}

const emptyForm = () => ({
  meter_no: "",
  iot_device_token: "",
  architecture: "STS" as MeterArchitecture,
  label: "",
});

export default function MeterManagementModal({
  isOpen,
  onClose,
  onSuccess,
}: MeterManagementModalProps) {
  const [meterData, setMeterData] = useState<any>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingMeterNo, setEditingMeterNo] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [formData, setFormData] = useState(emptyForm());

  const fetchMeterData = async () => {
    setIsRefreshing(true);
    try {
      const response = await get<any>("meter/my-meter/");
      if (!response.error && response.data) {
        setMeterData(response.data);
        const meters: any[] = response.data?.data?.meters ?? [];
        if (!response.data.success || !response.data.data.has_meter) {
          setFormOpen(true);
        }
        if (meters.length === 0) {
          setFormData(emptyForm());
        }
      }
    } catch {
      setMessage({ type: "error", text: "Failed to load meter data" });
    } finally {
      setIsRefreshing(false);
      setIsFetching(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setMeterData(null);
      setFormOpen(false);
      setEditingMeterNo(null);
      setFormData(emptyForm());
      setIsFetching(true);
      fetchMeterData();
    }
  }, [isOpen]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const startAdd = () => {
    setEditingMeterNo(null);
    setFormData(emptyForm());
    setFormOpen(true);
    setMessage(null);
  };

  const startEdit = (meter: any) => {
    setEditingMeterNo(meter.meter_number);
    setFormData({
      meter_no: meter.meter_number || "",
      iot_device_token: "",
      architecture: (meter.architecture as MeterArchitecture) || "STS",
      label: meter.label || "",
    });
    setFormOpen(true);
    setMessage(null);
  };

  const cancelForm = () => {
    setFormOpen(false);
    setEditingMeterNo(null);
    setFormData(emptyForm());
    setMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const isUpdate = editingMeterNo !== null;

    if (!isValidMeterNumber(formData.meter_no)) {
      setMessage({ type: "error", text: "Please enter a meter number" });
      return;
    }

    if (formData.architecture === "AMI" && !formData.iot_device_token.trim() && !isUpdate) {
      setMessage({ type: "error", text: "ThingsBoard device access token is required for AMI meters" });
      return;
    }

    setIsLoading(true);
    setMessage(null);

    const payload: Record<string, string> = {
      meter_no: formData.meter_no.trim(),
      architecture: formData.architecture,
    };
    if (formData.label.trim()) payload.label = formData.label.trim();
    if (formData.architecture === "AMI" && formData.iot_device_token.trim()) {
      payload.iot_device_token = formData.iot_device_token.trim();
    }
    if (isUpdate && editingMeterNo) {
      payload.current_meter_no = editingMeterNo;
    }

    try {
      const endpoint = isUpdate ? "meter/update/" : "meter/register/";
      const response = isUpdate
        ? await patch<any>(endpoint, payload)
        : await post<any>(endpoint, payload);

      if (response.error) {
        setMessage({
          type: "error",
          text: getApiErrorMessage(
            response.error,
            isUpdate ? "Failed to update meter" : "Failed to register meter"
          ),
        });
      } else {
        setMessage({
          type: "success",
          text: isUpdate ? "Meter updated successfully!" : "Meter registered successfully!",
        });
        cancelForm();
        await fetchMeterData();
        setTimeout(() => onSuccess(), 1500);
      }
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Network error. Please try again." });
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const hasMeter = meterData?.success && meterData.data.has_meter;
  const allMeters: any[] = meterData?.data?.meters ?? [];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <Card className="w-full max-w-lg relative my-4">
        <Button
          variant="ghost"
          size="icon"
          className="absolute right-2 top-2 h-6 w-6"
          onClick={() => {
            cancelForm();
            onClose();
          }}
          disabled={isLoading}
        >
          <X className="h-4 w-4" />
        </Button>

        <CardHeader className="text-center pb-4">
          <div className="flex items-center justify-center w-12 h-12 bg-blue-100 rounded-full mb-3 mx-auto">
            <Zap className="h-6 w-6 text-blue-600" />
          </div>
          <CardTitle className="text-lg">
            {isFetching && !meterData
              ? "Loading Meter Details"
              : hasMeter
              ? "Manage Your Meters"
              : "Register Your Electricity Meter"}
          </CardTitle>
          <CardDescription>
            {isFetching && !meterData
              ? "Please wait while we load your meter details"
              : hasMeter
              ? "One login can manage multiple meters — e.g. all rental units under a landlord account."
              : "Choose STS or AMI platform, then register your first meter."}
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

          {isFetching && !meterData && (
            <div className="py-8 text-center text-gray-600">Loading meter information...</div>
          )}

          {!isFetching && meterData && !formOpen && (
            <div className="mb-6 p-4 bg-gray-50 rounded-lg border">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Your meters</h3>
                <Button variant="ghost" size="sm" onClick={fetchMeterData} disabled={isRefreshing}>
                  <RefreshCw className={`h-4 w-4 mr-1 ${isRefreshing ? "animate-spin" : ""}`} />
                  Refresh
                </Button>
              </div>

              {hasMeter ? (
                <div className="space-y-3">
                  {allMeters.map((m) => (
                    <div key={m.meter_number} className="bg-white p-3 rounded border space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-mono text-sm font-semibold">{m.meter_number}</p>
                          {m.label && m.label !== "Home" && (
                            <p className="text-xs text-muted-foreground">{m.label}</p>
                          )}
                          <p className="text-xs text-muted-foreground mt-1">
                            {m.architecture === "AMI" ? "AMI platform" : "STS platform"}
                            {m.architecture === "AMI" && m.has_iot_token ? " · ThingsBoard linked" : ""}
                          </p>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => startEdit(m)}>
                          <Edit className="h-3.5 w-3.5 mr-1" />
                          Edit
                        </Button>
                      </div>
                      <div className="flex items-baseline text-sm">
                        <Battery className="h-3.5 w-3.5 text-purple-500 mr-1" />
                        <span className="font-semibold text-green-600">
                          {Number(m.units || 0).toFixed(2)}
                        </span>
                        <span className="ml-1 text-gray-600">kWh</span>
                      </div>
                    </div>
                  ))}

                  <Button onClick={startAdd} className="w-full" variant="outline">
                    <Plus className="h-4 w-4 mr-2" />
                    Add another meter
                  </Button>
                </div>
              ) : (
                <div className="text-center py-6">
                  <Zap className="h-12 w-12 text-yellow-500 mx-auto mb-3" />
                  <h4 className="font-medium text-yellow-800 mb-2">No Meter Registered</h4>
                  <p className="text-sm text-yellow-700 mb-4">
                    Register a meter to start using electricity services.
                  </p>
                  <Button onClick={startAdd} className="w-full">
                    <Zap className="h-4 w-4 mr-2" />
                    Register Meter
                  </Button>
                </div>
              )}
            </div>
          )}

          {formOpen && !isFetching && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <MeterArchitecturePicker
                value={formData.architecture}
                onChange={(arch) =>
                  setFormData((prev) => ({
                    ...prev,
                    architecture: arch,
                    iot_device_token: arch === "STS" ? "" : prev.iot_device_token,
                  }))
                }
                disabled={isLoading}
              />

              <div className="space-y-2">
                <Label htmlFor="label">Unit label (optional)</Label>
                <Input
                  id="label"
                  name="label"
                  type="text"
                  value={formData.label}
                  onChange={handleInputChange}
                  placeholder="e.g. Flat 2B, Shop front"
                  disabled={isLoading}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="meter_no">
                  Meter Number <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="meter_no"
                  name="meter_no"
                  type="text"
                  value={formData.meter_no}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      meter_no: e.target.value,
                    }))
                  }
                  placeholder="Enter meter number"
                  maxLength={METER_NO_MAX_LENGTH}
                  required
                  disabled={isLoading}
                  className={cn(
                    !isValidMeterNumber(formData.meter_no) &&
                      formData.meter_no.length > 0 &&
                      "border-destructive"
                  )}
                />
                {!isValidMeterNumber(formData.meter_no) && formData.meter_no.length > 0 && (
                  <p className="text-xs text-destructive">Please enter a meter number</p>
                )}
              </div>

              {formData.architecture === "AMI" && (
                <div className="space-y-2">
                  <Label htmlFor="iot_device_token">
                    ThingsBoard access token <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="iot_device_token"
                    name="iot_device_token"
                    type="text"
                    value={formData.iot_device_token}
                    onChange={handleInputChange}
                    placeholder="Device access token from your utility"
                    required
                    disabled={isLoading}
                    className="font-mono text-sm"
                  />
                </div>
              )}

              <div className="text-xs text-muted-foreground space-y-1">
                <p>• Find meter number on your electricity bill or meter display</p>
                {formData.architecture === "AMI" && (
                  <p>• Contact your utility for the ThingsBoard device access token</p>
                )}
              </div>

              <div className="flex gap-2 pt-4">
                {hasMeter && (
                  <Button
                    type="button"
                    variant="outline"
                    className="flex-1"
                    onClick={cancelForm}
                    disabled={isLoading}
                  >
                    Cancel
                  </Button>
                )}
                <Button
                  type="submit"
                  className={hasMeter ? "flex-1" : "w-full"}
                  disabled={
                    isLoading ||
                    !formData.meter_no ||
                    (formData.architecture === "AMI" &&
                      !formData.iot_device_token.trim() &&
                      !editingMeterNo)
                  }
                >
                  {isLoading ? (
                    <>
                      <Zap className="h-4 w-4 mr-2 animate-spin" />
                      {editingMeterNo ? "Updating..." : "Registering..."}
                    </>
                  ) : (
                    <>
                      <Zap className="h-4 w-4 mr-2" />
                      {editingMeterNo ? "Update Meter" : "Register Meter"}
                    </>
                  )}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
