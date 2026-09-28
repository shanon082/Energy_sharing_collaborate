/** Dispatched after a successful unit purchase, share, or apply-to-meter. */
export const WALLET_BALANCE_UPDATED = "gpawa:wallet-balance-updated";

export function notifyWalletBalanceUpdated() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(WALLET_BALANCE_UPDATED));
  }
}
