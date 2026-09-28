"use client";

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { get } from '@/lib/fetch';

interface WalletData {
  wallet_balance: string;
  unit_balance: string;
  meter_units: number;
}

interface WalletContextType {
  walletData: WalletData;
  isLoading: boolean;
  refreshBalances: () => Promise<void>;
}

const WalletContext = createContext<WalletContextType | undefined>(undefined);

export function WalletProvider({ children, initialData }: { children: ReactNode; initialData: WalletData }) {
  const [walletData, setWalletData] = useState<WalletData>(initialData);
  const [isLoading, setIsLoading] = useState(false);

  const refreshBalances = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await get<any>("wallet/balance/");
      if (!response.error && response.data?.success) {
        setWalletData({
          wallet_balance: response.data.wallet?.balance || "0.00",
          unit_balance: response.data.unit_balance?.balance || "0.00",
          meter_units: response.data.total_meter_units || 0
        });
      }
    } catch (error) {
      console.error("Failed to refresh balances:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return (
    <WalletContext.Provider value={{ walletData, isLoading, refreshBalances }}>
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet() {
  const context = useContext(WalletContext);
  if (context === undefined) {
    throw new Error('useWallet must be used within a WalletProvider');
  }
  return context;
}