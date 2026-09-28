import verizonLogo from "@/assets/images/verizon.png";
import tMobile from "@/assets/images/tmobile.png";
import vodafone from "@/assets/images/vodafone.png";
import threeUk from "@/assets/images/three.png";
import emirates from "@/assets/images/emirates.png";
import singapore from "@/assets/images/singaporeairlines.png";
import klm from "@/assets/images/klm.png";
import airfrance from "@/assets/images/airfrance.png";
import Image from "next/image";
import { motion } from "framer-motion";

const logos = [
  threeUk,
  verizonLogo,
  tMobile,
  vodafone,
  emirates,
  singapore,
  airfrance,
  klm,
];

export default function Partners() {
  return (
    <section className="py-16 md:py-20 bg-gradient-to-b from-white via-slate-50 to-white dark:from-slate-950 dark:via-slate-900 dark:to-slate-900">
      <div className="max-w-7xl mx-auto px-4 md:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="max-w-2xl mx-auto text-center mb-16"
        >
          <h3 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Trusted by Leading Energy Innovators
          </h3>
          <p className="text-gray-600 dark:text-gray-300 text-lg">
            Partnering with global utilities and renewable leaders to power
            sustainable communities worldwide.
          </p>
        </motion.div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 sm:gap-8 lg:gap-12 justify-items-center">
          {logos.map((logo, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, delay: idx * 0.1 }}
              whileHover={{
                scale: 1.05,
                filter: "grayscale(0%) brightness(110%)",
              }}
              className="flex items-center justify-center p-4 bg-white/90 dark:bg-slate-900/80 rounded-2xl shadow-md hover:shadow-xl transition-all cursor-pointer grayscale hover:grayscale-0 border border-white/60 dark:border-slate-800/70"
            >
              <Image
                alt={`Partner ${idx + 1}`}
                src={logo}
                height={120}
                width={120}
                className="h-16 w-auto max-w-none transition-transform"
              />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
