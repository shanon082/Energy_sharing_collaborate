export const dynamic = "force-dynamic";

import TokensPageClient from "./_components/tokens-page-client";
import DesktopSidebar from "../_components/desktop-sidebar";
import RightHeader from "../_components/right-header";
import { get } from "@/lib/fetch";
import { Token } from "@/interface/token.interface";

async function getTokens(): Promise<Token[]> {
  try {
    const response = await get<any>("meter/token/");
    if (response.error) return [];
    return Array.isArray(response.data?.data)
      ? response.data.data
      : response.data?.results ?? [];
  } catch {
    return [];
  }
}

const TokensPage = async () => {
  const tokens = await getTokens();

  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex min-w-0 flex-col overflow-x-hidden">
        <RightHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <TokensPageClient initialTokens={tokens} />
        </main>
      </div>
    </div>
  );
};

export default TokensPage;
