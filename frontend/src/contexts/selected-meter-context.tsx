"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { get } from "@/lib/fetch-client";
import { WALLET_BALANCE_UPDATED } from "@/lib/wallet-events";
import type { UserMeter } from "@/interface/meter.interface";

const STORAGE_KEY = "gpawa_selected_meter_no";

interface SelectedMeterContextValue {
  meters: UserMeter[];
  selectedMeter: UserMeter | null;
  setSelectedMeterNo: (meterNo: string) => void;
  isLoading: boolean;
  refreshMeters: () => Promise<void>;
  walletBalance: number;
  refreshWallet: () => Promise<void>;
}

const SelectedMeterContext = createContext<SelectedMeterContextValue | null>(null);

function parseMeters(payload: any): UserMeter[] {
  const raw = payload?.data?.meters;
  if (!Array.isArray(raw)) return [];
  return raw.map((m: any) => ({
    meter_number: m.meter_number,
    static_ip: m.static_ip ?? null,
    units: Number(m.units) || 0,
    architecture: (m.architecture as UserMeter["architecture"]) || "STS",
    pending_units: Number(m.pending_units) || 0,
    status: m.status || "ACTIVE",
    label: m.label || "Home",
    has_iot_token: !!m.has_iot_token,
  }));
}

export function SelectedMeterProvider({ children }: { children: ReactNode }) {
  const [meters, setMeters] = useState<UserMeter[]>([]);
  const [selectedMeterNo, setSelectedMeterNoState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [walletBalance, setWalletBalance] = useState(0);

  const refreshWallet = useCallback(async () => {
    try {
      const res = await get<any>("wallet/balance/");
      if (!res.error && res.data?.success) {
        const bal = parseFloat(
          res.data?.wallet?.balance ?? res.data?.wallet_balance ?? "0"
        );
        setWalletBalance(Number.isFinite(bal) ? bal : 0);
      }
    } catch {
      /* keep last known balance */
    }
  }, []);

  const refreshMeters = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await get<any>("meter/my-meter/");
      if (!res.error && res.data?.success && res.data.data?.has_meter) {
        const list = parseMeters(res.data);
        setMeters(list);
        setSelectedMeterNoState((prev) => {
          const stored =
            typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
          const candidate = prev || stored;
          if (candidate && list.some((m) => m.meter_number === candidate)) {
            return candidate;
          }
          return list[0]?.meter_number ?? null;
        });
      } else {
        setMeters([]);
        setSelectedMeterNoState(null);
      }
    } catch {
      setMeters([]);
      setSelectedMeterNoState(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshMeters();
    refreshWallet();
  }, [refreshMeters, refreshWallet]);

  useEffect(() => {
    const onWalletUpdate = () => {
      refreshWallet();
    };
    window.addEventListener(WALLET_BALANCE_UPDATED, onWalletUpdate);
    window.addEventListener("focus", onWalletUpdate);
    return () => {
      window.removeEventListener(WALLET_BALANCE_UPDATED, onWalletUpdate);
      window.removeEventListener("focus", onWalletUpdate);
    };
  }, [refreshWallet]);

  useEffect(() => {
    if (selectedMeterNo && typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, selectedMeterNo);
    }
  }, [selectedMeterNo]);

  const setSelectedMeterNo = useCallback((meterNo: string) => {
    setSelectedMeterNoState(meterNo);
  }, []);

  const selectedMeter = useMemo(
    () => meters.find((m) => m.meter_number === selectedMeterNo) ?? meters[0] ?? null,
    [meters, selectedMeterNo]
  );

  const value = useMemo(
    () => ({
      meters,
      selectedMeter,
      setSelectedMeterNo,
      isLoading,
      refreshMeters,
      walletBalance,
      refreshWallet,
    }),
    [meters, selectedMeter, setSelectedMeterNo, isLoading, refreshMeters, walletBalance, refreshWallet]
  );

  return (
    <SelectedMeterContext.Provider value={value}>{children}</SelectedMeterContext.Provider>
  );
}

export function useSelectedMeter() {
  const ctx = useContext(SelectedMeterContext);
  if (!ctx) {
    throw new Error("useSelectedMeter must be used within SelectedMeterProvider");
  }
  return ctx;
}
