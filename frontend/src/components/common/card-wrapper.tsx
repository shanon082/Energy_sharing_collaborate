"use client";
const CardWrapper = ({
  title,
  subtitle,
  children,
  variant = "default",
  containerClassName,
  cardClassName,
  maxWidth = "md",
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  variant?: "default" | "auth";
  containerClassName?: string;
  cardClassName?: string;
  maxWidth?: "md" | "lg" | "xl" | "2xl" | "4xl";
}) => {
  const maxWidthClass = {
    md: "sm:max-w-md",
    lg: "sm:max-w-lg",
    xl: "sm:max-w-xl",
    "2xl": "sm:max-w-2xl",
    "4xl": "sm:max-w-4xl",
  }[maxWidth ?? "md"];
  const containerBase =
    variant === "auth"
      ? "min-h-[calc(100dvh-4rem)] flex items-start justify-center px-4 py-4 sm:min-h-screen sm:items-center sm:px-6 sm:py-8"
      : "min-h-full flex flex-col justify-center py-10 sm:py-14 sm:px-6 lg:px-8";
  const cardBase =
    variant === "auth"
      ? "bg-white/95 dark:bg-card/95 backdrop-blur-sm py-5 px-4 shadow-xl shadow-blue-500/10 dark:shadow-black/30 rounded-2xl sm:px-10 border border-gray-200/70 dark:border-white/10 sm:max-h-[85vh] sm:overflow-y-auto"
      : "bg-white/95 dark:bg-card/95 backdrop-blur-sm py-8 px-5 shadow-xl shadow-blue-500/10 dark:shadow-black/30 sm:rounded-2xl sm:px-10 border border-gray-200/70 dark:border-white/10";

  return (
    <div className="relative">
      <div className={`${containerBase} ${containerClassName ?? ""}`}>
        <div className={`w-full sm:mx-auto sm:mt-8 sm:w-full ${maxWidthClass}`}>
          <div className={`${cardBase} ${cardClassName ?? ""}`}>
            <h1 className="py-2 text-center text-xl font-semibold text-gray-900 dark:text-white sm:py-3 sm:text-2xl">
              {title}
            </h1>
            {subtitle && (
              <p className="text-center text-sm text-gray-600 dark:text-gray-300 mb-4">
                {subtitle}
              </p>
            )}

            {children}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CardWrapper;
