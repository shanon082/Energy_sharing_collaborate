"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileTextIcon, PlusCircle, Heart } from "lucide-react";
import LoanList from "../../myloans/_components/loan-list";
import SimpleLoanForm from "../../request-loan/_components/simple-loan-form";
import PayForSomeone from "./pay-for-someone";

interface LoansClientProps {
  loans: any[];
  defaultTab: string;
}

export default function LoansClient({ loans, defaultTab }: LoansClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = searchParams.get("tab") ?? defaultTab;

  const setTab = (value: string) => {
    router.push(`?tab=${value}`, { scroll: false });
  };

  return (
    <Tabs value={tab} onValueChange={setTab} className="w-full">
      <TabsList className="w-full max-w-md grid grid-cols-3 mb-6">
        <TabsTrigger value="my-loans" className="gap-1.5 text-xs sm:text-sm">
          <FileTextIcon className="h-3.5 w-3.5" />
          My Loans
        </TabsTrigger>
        <TabsTrigger value="apply" className="gap-1.5 text-xs sm:text-sm">
          <PlusCircle className="h-3.5 w-3.5" />
          Apply
        </TabsTrigger>
        <TabsTrigger value="pay-for-someone" className="gap-1.5 text-xs sm:text-sm">
          <Heart className="h-3.5 w-3.5" />
          Pay for Someone
        </TabsTrigger>
      </TabsList>

      <TabsContent value="my-loans">
        <div className="rounded-lg border border-dashed dark:border-white/10 shadow-sm">
          <div className="flex flex-col gap-1 w-full p-4">
            <LoanList loans={loans} />
          </div>
        </div>
      </TabsContent>

      <TabsContent value="apply">
        <div className="flex justify-center">
          <div className="flex flex-col gap-1 w-full max-w-2xl">
            <SimpleLoanForm />
          </div>
        </div>
      </TabsContent>

      <TabsContent value="pay-for-someone">
        <PayForSomeone />
      </TabsContent>
    </Tabs>
  );
}
