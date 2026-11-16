import "@/styles/globals.css";
import ConsumerRouter from "@/components/consumer/workspace";
import "./sandbox/sandbox.css";
import "@/styles/consumer-workspace.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "EnergyFlex | Dashboard",
  description: "",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {

  return (
        <ConsumerRouter>{children}</ConsumerRouter>     
  );
}
