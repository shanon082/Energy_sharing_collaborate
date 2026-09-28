import Link from "next/link";

export default function PublicFooter() {
  const footerNavs = [
    { href: "/about", name: "About" },
    { href: "/contact", name: "Contact" },
    { href: "/privacy", name: "Privacy" },
    { href: "/terms", name: "Terms" },
    { href: "/license", name: "License" },
  ];

  return (
    <footer className="pt-12 bg-gradient-to-t from-slate-50 via-white to-white dark:from-slate-950 dark:via-slate-900 dark:to-slate-900">
      <div className="max-w-7xl mx-auto px-4 md:px-8">
        <div className="border-t border-gray-200/80 dark:border-slate-800/70 py-10 mt-10 flex flex-col sm:flex-row items-center justify-between gap-6">
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            &copy; {new Date().getFullYear()} gPawa Inc. All rights
            reserved.
          </p>
          <ul className="flex flex-wrap items-center justify-center gap-6">
            {footerNavs.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 text-sm font-medium transition-colors duration-200"
                >
                  {item.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  );
}
