import { motion } from "framer-motion";
import {
  CheckCircleIcon,
  BoltIcon,
  ChartBarIcon,
} from "@heroicons/react/24/outline";

export default function Features() {
  const features = [
    {
      icon: CheckCircleIcon,
      title: "Transparent Unit Purchases",
      desc: "Buy electricity using mobile payments and review clear transaction receipts and payment status.",
    },
    {
      icon: BoltIcon,
      title: "Meter-Ready Electricity",
      desc: "Buy units for supported STS and AMI meters, with delivery and allocation status shown in your account.",
    },
    {
      icon: ChartBarIcon,
      title: "Clear Loan Terms",
      desc: "Review your loan amount, repayment schedule, and applicable interest before you accept an offer.",
    },
    {
      icon: CheckCircleIcon,
      title: "Micro-Electricity Loans",
      desc: "EnergyFlex supports electricity loans capped at Uganda's statutory 2.8% per month, with a simple online application.",
    },
  ];

  return (
    <motion.section
      id="features"
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
      viewport={{ once: true }}
      className="scroll-mt-24 relative py-20 md:py-28 bg-gradient-to-bl from-white via-slate-50 to-emerald-50 dark:from-slate-950 dark:via-slate-900 dark:to-emerald-950"
    >
      <div className="container mx-auto px-4 md:px-8 max-w-7xl relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h3 className="text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 dark:text-white mb-4">
            Built for reliable electricity access
          </h3>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
            EnergyFlex brings electricity purchases and loan access together in one clear, easy-to-use service.
          </p>
        </motion.div>
        <div className="grid gap-8 md:grid-cols-2">
          {features.map((item, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 50 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: idx * 0.2 }}
              viewport={{ once: true }}
              className="group bg-white/90 dark:bg-slate-900/80 backdrop-blur-sm rounded-3xl p-8 shadow-lg hover:shadow-2xl transition-all border border-white/40 dark:border-slate-800/70 hover:border-emerald-300/50"
            >
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-blue-500 to-emerald-500 rounded-2xl flex items-center justify-center text-white shadow-lg group-hover:scale-110 transition-transform">
                  <item.icon className="w-6 h-6" />
                </div>
                <div className="flex-1">
                  <h4 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    {item.title}
                  </h4>
                  <p className="text-gray-600 dark:text-gray-300 leading-relaxed">
                    {item.desc}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(16,185,129,0.12)_0%,transparent_70%)] dark:bg-[radial-gradient(ellipse_at_center,rgba(34,197,94,0.14)_0%,transparent_70%)]"></div>
    </motion.section>
  );
}
