"use client";
import Features from "@/components/common/features";
import HowItWorks from "@/components/common/how-it-works";
import PublicFooter from "@/components/common/public-footer";
import PublicHeader from "@/components/common/public-header";
import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";

export default function Home() {
  const pillars = [
    "No hidden service fees",
    "Mobile telecom service provider payments",
    "ERA-compliant block tariffs",
    "Peer-to-peer unit sharing",
    "Statutory lending caps enforced",
    "STS & AMI meter support",
  ];

  return (
    <>
      <PublicHeader />

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-sky-50 via-emerald-50 to-blue-100 dark:from-slate-950 dark:via-emerald-950/30 dark:to-slate-900 pt-6 pb-12 sm:pt-8 sm:pb-14 md:pt-10 md:pb-16 lg:pt-12 lg:pb-20">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-emerald-400/20 blur-3xl" />
          <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-blue-500/20 blur-3xl" />
        </div>
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-center">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className="space-y-6 lg:space-y-8"
            >
              <span className="inline-flex items-center rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-cyan-700 dark:text-cyan-300">
                Energy Sharing and Borrowing Platform
              </span>
              <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight">
                <span className="block text-gray-900 dark:text-gray-100">Give Power,</span>
                <span className="block bg-gradient-to-r from-blue-600 via-emerald-500 to-blue-700 bg-clip-text text-transparent">
                  Get Power
                </span>
              </h1>

              <p className="text-lg sm:text-xl text-gray-600 dark:text-gray-300 max-w-xl leading-relaxed">
                gPawa lets households and institutions buy, share, and borrow energy units -
                no middleman, no branch visit, no delays.
              </p>

              <div className="flex flex-wrap gap-2">
                {pillars.map((item) => (
                  <span
                    key={item}
                    className="inline-flex items-center gap-1.5 rounded-full border border-white/40 bg-white/70 px-3 py-1 text-xs text-slate-700 backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200"
                  >
                    <CheckCircle2 className="h-3 w-3 text-blue-600 dark:text-blue-400" />
                    {item}
                  </span>
                ))}
              </div>

              <div className="flex flex-col sm:flex-row gap-4">
                <Link href="/auth/register">
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    className="group relative overflow-hidden px-8 py-4 bg-gradient-to-r from-blue-600 to-emerald-600 hover:from-blue-700 hover:to-emerald-700 text-white rounded-2xl font-semibold text-base transition-all shadow-lg shadow-blue-500/20"
                  >
                    <span className="relative z-10 flex items-center gap-2">
                      Get started free
                    </span>
                    <div className="absolute inset-0 bg-gradient-to-r from-blue-700 to-emerald-700 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </motion.button>
                </Link>
                <Link href="#how-it-works">
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    className="px-8 py-4 border-2 border-blue-600 text-blue-600 hover:bg-blue-50 dark:border-blue-400 dark:text-blue-300 dark:hover:bg-blue-900/20 rounded-2xl font-semibold text-base transition-all"
                  >
                    How it works
                  </motion.button>
                </Link>
              </div>

              <div className="grid max-w-xl grid-cols-3 gap-3 border-t border-slate-300/60 pt-4 dark:border-slate-700/60">
                <div>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">100%</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Transparent</p>
                </div>
                <div>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">0 UGX</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Hidden Fees</p>
                </div>
                <div>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">2.8%</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">Max Interest / Month</p>
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, delay: 0.3 }}
              className="relative h-64 sm:h-80 md:h-96 lg:h-[28rem]"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/15 to-emerald-500/15 rounded-3xl blur-2xl" />
              <Image
                src="/hero-network.png"
                alt="Community energy grid sharing"
                fill
                className="object-cover rounded-3xl shadow-2xl ring-1 ring-white/60 dark:ring-slate-800/70"
                priority
              />
            </motion.div>
          </div>
        </div>
      </section>

      <HowItWorks />
      <Features />
      

      <PublicFooter />
    </>
  );
}
