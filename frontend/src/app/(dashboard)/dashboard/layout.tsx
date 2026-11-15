import "@/styles/globals.css";
import ConsumerRouter from "@/components/consumer/workspace";
import "./sandbox/sandbox.css";
import "@/styles/consumer-workspace.css";
import type { Metadata } from "next";
import { Inter as FontSans } from "next/font/google";


const fontSans = FontSans({
  subsets: ["latin"],
  variable: "--font-sans",
})

export const metadata: Metadata = {
  title: "gPawa | Dashboard",
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
