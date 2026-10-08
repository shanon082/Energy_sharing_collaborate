import { useEffect } from "react";
import { Capacitor } from "@capacitor/core";
import { App } from "@capacitor/app";

export function useNativeBack(onBack: () => void) {
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let disposed = false;
    let listener: { remove: () => Promise<void> } | undefined;
    void App.addListener("backButton", onBack).then((handle) => {
      if (disposed) void handle.remove(); else listener = handle;
    });
    return () => { disposed = true; if (listener) void listener.remove(); };
  }, [onBack]);
}
