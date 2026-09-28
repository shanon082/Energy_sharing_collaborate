"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Smartphone,
  Wallet,
  Share2,
  Zap,
  Phone,
  Monitor,
} from "lucide-react";

const steps = [
  {
    number: "1",
    title: "Create your free account",
    description:
      "Sign up with your email and phone number. Verify your email, then log in on the web, mobile app, or USSD.",
    icon: Smartphone,
  },
  {
    number: "2",
    title: "Register your electricity meter",
    description:
      "Add your meter number once. gPawa supports prepaid token meters (STS) and smart networked meters (AMI).",
    icon: Zap,
  },
  {
    number: "3",
    title: "Buy electricity units",
    description:
      "Pay with mobile money (for example MTN MoMo). Your payment is converted to kilowatt-hours (kWh) using official block tariffs — no hidden fees.",
    icon: Wallet,
  },
  {
    number: "4",
    title: "Use, share, or borrow",
    description:
      "Load units onto your meter, send kWh to family or a neighbor, or apply for a small electricity loan if you are short. Interest is capped at Uganda's legal maximum of 2.8% per month.",
    icon: Share2,
  },
];

const channels = [
  {
    icon: Monitor,
    name: "Web portal",
    detail: "Full dashboard — buy units, share, loans, and meter history.",
  },
  {
    icon: Smartphone,
    name: "Mobile app",
    detail: "Same features on your Android phone, wherever you have data.",
  },
  {
    icon: Phone,
    name: "USSD",
    detail: "Dial the service code on any basic phone — no smartphone required.",
  },
];

export default function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="scroll-mt-24 relative py-20 md:py-28 bg-white dark:bg-slate-950 border-t border-slate-200/60 dark:border-slate-800/60"
    >
      <div className="container mx-auto px-4 md:px-8 max-w-7xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="text-center mb-14"
        >
          <p className="text-sm font-semibold uppercase tracking-widest text-blue-600 dark:text-blue-400 mb-3">
            How it works
          </p>
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Electricity in four simple steps
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
            No branch visit, no agent in the middle. You buy real electricity units, see exactly what you pay for,
            and move power between meters when someone you trust needs help.
          </p>
        </motion.div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-16">
          {steps.map((step, idx) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              viewport={{ once: true }}
              className="relative rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 p-6"
            >
              <div className="flex items-center gap-3 mb-4">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-emerald-600 text-white font-bold text-sm">
                  {step.number}
                </span>
                <step.icon className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{step.title}</h3>
              <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">{step.description}</p>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="rounded-3xl bg-gradient-to-br from-blue-50 to-emerald-50 dark:from-blue-950/40 dark:to-emerald-950/30 border border-blue-100 dark:border-slate-800 p-8 md:p-10"
        >
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2 text-center">
            Use gPawa your way
          </h3>
          <p className="text-center text-gray-600 dark:text-gray-300 mb-8 max-w-xl mx-auto text-sm">
            The same wallet and meter work across all channels — start on USSD and finish on the web, or the other way around.
          </p>
          <div className="grid gap-4 sm:grid-cols-3">
            {channels.map((ch) => (
              <div
                key={ch.name}
                className="flex flex-col items-center text-center rounded-2xl bg-white/80 dark:bg-slate-900/80 p-5 border border-white/60 dark:border-slate-700/60"
              >
                <ch.icon className="h-8 w-8 text-blue-600 dark:text-blue-400 mb-3" />
                <p className="font-semibold text-gray-900 dark:text-white">{ch.name}</p>
                <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{ch.detail}</p>
              </div>
            ))}
          </div>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/register"
              className="inline-flex px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-blue-600 to-emerald-600 hover:from-blue-700 hover:to-emerald-700 shadow-md transition-all"
            >
              Create free account
            </Link>
            <Link
              href="/about"
              className="inline-flex px-6 py-3 rounded-xl font-semibold text-blue-600 dark:text-blue-400 border-2 border-blue-600/30 hover:bg-blue-50 dark:hover:bg-blue-950/30 transition-all"
            >
              Learn more about gPawa
            </Link>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
