"use client";

import { useEffect, useState } from "react";
import { Loader2, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FormError } from "@/components/common/form-error";
import { getApiErrorMessage } from "@/lib/api-response";
import { isValidMeterNumber, METER_NO_MAX_LENGTH } from "@/lib/meter-validation";
import { registerMeter } from "../actions";
import type { MeterArchitecture } from "@/interface/meter.interface";

interface AddMeterDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

const emptyForm = () => ({
  meter_no: "",
  architecture: "STS" as MeterArchitecture,
  label: "",
  iot_device_token: "",
});

export default function AddMeterDialog({ open, onOpenChange, onSuccess }: AddMeterDialogProps) {
  const [form, setForm] = useState(emptyForm());
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      setForm(emptyForm());
      setError("");
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!isValidMeterNumber(form.meter_no)) {
      setError("Enter a meter number.");
      return;
    }
    if (form.architecture === "AMI" && !form.iot_device_token.trim()) {
      setError("ThingsBoard device access token is required for AMI meters.");
      return;
    }

    setIsPending(true);
    try {
      const payload: Parameters<typeof registerMeter>[0] = {
        meter_no: form.meter_no.trim(),
        architecture: form.architecture,
      };
      if (form.label.trim()) payload.label = form.label.trim();
      if (form.architecture === "AMI") {
        payload.iot_device_token = form.iot_device_token.trim();
      }

      const res = await registerMeter(payload);
      if (res.data?.success) {
        onSuccess();
      } else {
        setError(getApiErrorMessage(res.error, res.data?.error ?? "Failed to register meter."));
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setIsPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !isPending && onOpenChange(o)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add new meter</DialogTitle>
          <DialogDescription>
            Register an STS or AMI meter to your account. AMI meters need the ThingsBoard device
            access token from your utility or installer.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="meter-type">Meter type</Label>
            <Select
              value={form.architecture}
              onValueChange={(v) =>
                setForm((prev) => ({
                  ...prev,
                  architecture: v as MeterArchitecture,
                  iot_device_token: v === "STS" ? "" : prev.iot_device_token,
                }))
              }
              disabled={isPending}
            >
              <SelectTrigger id="meter-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="STS">STS — keypad token meter</SelectItem>
                <SelectItem value="AMI">AMI — networked (ThingsBoard)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="meter-label">Given name</Label>
            <Input
              id="meter-label"
              value={form.label}
              onChange={(e) => setForm((p) => ({ ...p, label: e.target.value }))}
              placeholder="e.g. Home, Shop, Flat 2B"
              disabled={isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="meter-no">
              Meter number <span className="text-destructive">*</span>
            </Label>
            <Input
              id="meter-no"
              value={form.meter_no}
              onChange={(e) => setForm((p) => ({ ...p, meter_no: e.target.value }))}
              placeholder="Meter number"
              maxLength={METER_NO_MAX_LENGTH}
              required
              disabled={isPending}
              className="font-mono"
            />
          </div>

          {form.architecture === "AMI" && (
            <div className="space-y-2">
              <Label htmlFor="device-token">
                ThingsBoard access token <span className="text-destructive">*</span>
              </Label>
              <Input
                id="device-token"
                value={form.iot_device_token}
                onChange={(e) => setForm((p) => ({ ...p, iot_device_token: e.target.value }))}
                placeholder="Device access token"
                required
                disabled={isPending}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Used to push top-ups and read live balance from ThingsBoard.
              </p>
            </div>
          )}

          <FormError message={error} />

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending} className="gpawa-gradient text-white gap-2">
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4" />
                  Save meter
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
