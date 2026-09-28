'use client';

export const dynamic = "force-dynamic";

import { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { BarChart3, Download, FileText } from 'lucide-react';
import { get } from "@/lib/fetch-client";

const REPORT_TYPES = [
  { value: "daily_transaction_summary", label: "Daily Transaction Summary" },
  { value: "user_adoption", label: "User Adoption Report" },
  { value: "credit_loan", label: "Credit & Loan Report" },
  { value: "transfer_activity", label: "Transfer Activity Report" },
  { value: "revenue_summary", label: "Revenue Summary" },
  { value: "meter_registration", label: "Meter Registration Report" },
  { value: "fraud_flags", label: "Fraud & Flags Report" },
  { value: "system_performance", label: "System Performance Report" },
  { value: "social_impact", label: "Social Impact Report" },
];

function today() { return new Date().toISOString().slice(0, 10); }
function daysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const [reportType, setReportType] = useState('daily_transaction_summary');
  const [dateFrom, setDateFrom] = useState(daysAgo(30));
  const [dateTo, setDateTo] = useState(today());
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState<any>(null);

  async function generateReport() {
    setLoading(true);
    setReportData(null);
    try {
      const params = new URLSearchParams({
        type: reportType,
        date_from: dateFrom,
        date_to: dateTo,
      });
      const res = await get<any>(`admin/reports/?${params}`);
      if (res.data?.success) {
        setReportData(res.data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function exportJSON() {
    if (!reportData) return;
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${reportType}-${dateFrom}-to-${dateTo}.json`;
    a.click();
  }

  const reportLabel = REPORT_TYPES.find(r => r.value === reportType)?.label ?? reportType;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Reports & Analytics</h1>
      </div>

      {/* Report configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" /> Generate Report
          </CardTitle>
          <CardDescription>Select a report type and date range</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <Select value={reportType} onValueChange={setReportType}>
              <SelectTrigger className="md:col-span-2">
                <SelectValue placeholder="Report type" />
              </SelectTrigger>
              <SelectContent>
                {REPORT_TYPES.map(r => (
                  <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <Button className="mt-4" onClick={generateReport} disabled={loading}>
            <BarChart3 className="h-4 w-4 mr-2" />
            {loading ? "Generating…" : "Generate Report"}
          </Button>
        </CardContent>
      </Card>

      {/* Results */}
      {loading && (
        <Card>
          <CardContent className="pt-6 space-y-3">
            <Skeleton className="h-6 w-64" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </CardContent>
        </Card>
      )}

      {reportData && !loading && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">{reportLabel}</CardTitle>
                <CardDescription>
                  {reportData.period?.from} to {reportData.period?.to} · Generated {new Date(reportData.generated_at).toLocaleString()}
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={exportJSON}>
                <Download className="h-4 w-4 mr-2" /> Export JSON
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <ReportDisplay type={reportType} data={reportData.data} />
          </CardContent>
        </Card>
      )}

      {/* Available reports list */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Available Report Types</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {REPORT_TYPES.map(r => (
              <button
                key={r.value}
                onClick={() => setReportType(r.value)}
                className={`text-left p-3 rounded-lg border text-sm transition-colors hover:bg-muted ${reportType === r.value ? 'border-primary bg-muted' : ''}`}
              >
                <FileText className="h-4 w-4 mb-1 text-muted-foreground" />
                <div className="font-medium">{r.label}</div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ReportDisplay({ type, data }: { type: string; data: any }) {
  if (!data) return <p className="text-muted-foreground">No data</p>;

  // Generic key-value display for all report types
  return (
    <div className="space-y-4">
      {/* Numeric KPIs at top */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries(data)
          .filter(([, v]) => typeof v === 'number')
          .map(([k, v]) => (
            <div key={k} className="rounded-lg bg-muted p-3">
              <p className="text-2xl font-bold">{(v as number).toLocaleString()}</p>
              <p className="text-xs text-muted-foreground capitalize mt-0.5">
                {k.replace(/_/g, ' ')}
              </p>
            </div>
          ))}
      </div>

      {/* Array data as table */}
      {Object.entries(data)
        .filter(([, v]) => Array.isArray(v) && (v as any[]).length > 0)
        .map(([k, arr]) => {
          const rows = arr as Record<string, any>[];
          const cols = Object.keys(rows[0]);
          return (
            <div key={k}>
              <h3 className="text-sm font-medium mb-2 capitalize">{k.replace(/_/g, ' ')}</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border rounded-lg">
                  <thead className="bg-muted">
                    <tr>
                      {cols.map(c => (
                        <th key={c} className="text-left px-3 py-2 text-xs text-muted-foreground capitalize">
                          {c.replace(/_/g, ' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={i} className="border-t">
                        {cols.map(c => (
                          <td key={c} className="px-3 py-2 text-xs">
                            {typeof row[c] === 'number' ? Number(row[c]).toLocaleString() : String(row[c] ?? '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
    </div>
  );
}
