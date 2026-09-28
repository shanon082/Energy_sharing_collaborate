"use client"
import { Provider } from "react-redux";
import store from "@/redux/store";
import { ReactNode } from "react";
 
function Providers({ children }: { children: ReactNode }) {
  return <Provider store={store}>{children}</Provider>;
}
 
export default Providers;