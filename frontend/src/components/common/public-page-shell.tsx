import PublicFooter from "@/components/common/public-footer";
import PublicHeader from "@/components/common/public-header";
import Link from "next/link";

type PublicPageShellProps = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
};

export default function PublicPageShell({ title, subtitle, children }: PublicPageShellProps) {
  return (
    <>
      <PublicHeader />
      <main className="min-h-screen bg-gradient-to-b from-sky-50/80 via-white to-white dark:from-slate-950 dark:via-slate-900 dark:to-slate-900 pt-4 pb-16">
        <div className="container mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <nav className="mb-8 text-sm text-muted-foreground">
            <Link href="/" className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
              Home
            </Link>
            <span className="mx-2">/</span>
            <span className="text-foreground">{title}</span>
          </nav>
          <header className="mb-10">
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-gray-900 dark:text-white">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-3 text-lg text-gray-600 dark:text-gray-300 leading-relaxed">{subtitle}</p>
            )}
          </header>
          <article className="space-y-6 text-gray-700 dark:text-gray-300 leading-relaxed [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-gray-900 [&_h2]:dark:text-white [&_h2]:mt-10 [&_h2]:mb-3 [&_h2:first-child]:mt-0 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:space-y-2 [&_a]:text-blue-600 [&_a]:dark:text-blue-400 [&_a]:hover:underline [&_strong]:text-gray-900 [&_strong]:dark:text-white">
            {children}
          </article>
        </div>
      </main>
      <PublicFooter />
    </>
  );
}
