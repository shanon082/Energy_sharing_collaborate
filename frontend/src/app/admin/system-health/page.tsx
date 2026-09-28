'use client';

export const dynamic = "force-dynamic";

import { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { get } from "@/lib/fetch-client";

interface ComponentHealth {
  status: "GREEN" | "AMBER" | "RED";
  description: string;
  latency_ms?: number;
  error?: string;
  celery_dispatch_ok?: boolean;
  celery_mode?: string;
}

interface SystemHealth {
  overall_status: "GREEN" | "AMBER" | "RED";
  components: Record<string, ComponentHealth>;
  timestamp: string;
}

interface ErrorEntry {
  timestamp: string;
  component: string;
  message: string;
  user: string;
  transaction_id: string;
}

interface HealthApiResponse {
  success?: boolean;
  overall_status: "GREEN" | "AMBER" | "RED";
  components: Record<string, ComponentHealth>;
  timestamp: string;
}

interface ErrorsApiResponse {
  success?: boolean;
  errors: ErrorEntry[];
}

const COMPONENT_LABELS: Record<string, string> = {
  api_gateway: "API Gateway",
  celery_dispatch: "Celery Dispatch",
  postgresql: "PostgreSQL Database",
  redis: "Redis Cache",
  cvs_sts_api: "CVS / STS Token API",
  africas_talking: "Africa's Talking (USSD/SMS)",
  mtn_momo: "MTN MoMo API",
  airtel_money: "Airtel Money API",
  firebase: "Firebase (Push Notifications)",
};

function StatusIcon({ status }: { status: "GREEN" | "AMBER" | "RED" }) {
  if (status === "GREEN") return <CheckCircle2 className="h-5 w-5 text-green-600" />;
  if (status === "AMBER") return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
  return <XCircle className="h-5 w-5 text-red-600" />;
}

function StatusBadge({ status }: { status: "GREEN" | "AMBER" | "RED" }) {
  const cls =
    status === "GREEN" ? "bg-green-100 text-green-800" :
    status === "AMBER" ? "bg-yellow-100 text-yellow-800" :
    "bg-red-100 text-red-800";
  const label = status === "GREEN" ? "Operational" : status === "AMBER" ? "Degraded / Simulated" : "Down";
  return <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}>{label}</span>;
}

export default function SystemHealthPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [errors, setErrors] = useState<ErrorEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'status' | 'errors'>('status');

  async function fetchHealth() {
    setLoading(true);
    try {
      const [healthRes, errorsRes] = await Promise.all([
        get<HealthApiResponse>('admin/system-health/'),
        get<ErrorsApiResponse>('admin/system-health/errors/'),
      ]);
      if (healthRes.data) setHealth(healthRes.data);
      if (errorsRes.data) setErrors(errorsRes.data.errors || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchHealth(); }, []);

  const overallBg =
    health?.overall_status === "GREEN" ? "bg-green-50 border-green-200" :
    health?.overall_status === "AMBER" ? "bg-yellow-50 border-yellow-200" :
    "bg-red-50 border-red-200";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">System Health</h1>
        <Button variant="outline" size="sm" onClick={fetchHealth}>
          <RefreshCw className="h-4 w-4 mr-2" /> Refresh
        </Button>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(9)].map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
      ) : health ? (
        <>
          {/* Overall status banner */}
          <div className={`rounded-lg border p-4 ${overallBg}`}>
            <div className="flex items-center gap-3">
              <StatusIcon status={health.overall_status} />
              <div>
                <p className="font-semibold text-lg">
                  {health.overall_status === "GREEN" ? "All Systems Operational" :
                   health.overall_status === "AMBER" ? "Partial Degradation — some services in pilot/simulation mode" : "System Outage"}
                </p>
                <p className="text-sm text-muted-foreground">
                  Last checked {new Date(health.timestamp).toLocaleTimeString()}
                </p>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-2 border-b">
            <button
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === 'status' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
              onClick={() => setTab('status')}
            >
              Component Status
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === 'errors' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
              onClick={() => setTab('errors')}
            >
              Error Log {errors.length > 0 && `(${errors.length})`}
            </button>
          </div>

          {tab === 'status' && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {Object.entries(health.components).map(([key, comp]) => (
                <Card key={key} className={comp.status === "RED" ? "border-red-200" : comp.status === "AMBER" ? "border-yellow-200" : ""}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <StatusIcon status={comp.status} />
                      <StatusBadge status={comp.status} />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="font-medium text-sm">{COMPONENT_LABELS[key] ?? key}</p>
                    {comp.latency_ms !== undefined && (
                      <p className="text-xs text-muted-foreground mt-1">{comp.latency_ms}ms latency</p>
                    )}
                    {comp.celery_dispatch_ok !== undefined && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Celery dispatch: {comp.celery_dispatch_ok ? "OK" : "Unavailable"}
                        {comp.celery_mode ? ` (${comp.celery_mode})` : ""}
                      </p>
                    )}
                    {comp.error && (
                      <p className="text-xs text-red-600 mt-1 truncate" title={comp.error}>{comp.error}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {tab === 'errors' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent Errors</CardTitle>
                <CardDescription>Failed transactions, payment errors, and server-side failures (last 50)</CardDescription>
              </CardHeader>
              <CardContent>
                {errors.length === 0 ? (
                  <div className="text-center py-8">
                    <CheckCircle2 className="h-8 w-8 text-green-500 mx-auto mb-2" />
                    <p className="text-muted-foreground">No recent errors</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-muted-foreground text-xs">
                          <th className="text-left py-2 pr-3">Timestamp</th>
                          <th className="text-left py-2 pr-3">Component</th>
                          <th className="text-left py-2 pr-3">Message</th>
                          <th className="text-left py-2">User</th>
                        </tr>
                      </thead>
                      <tbody>
                        {errors.map((e, i) => (
                          <tr key={i} className="border-b last:border-0">
                            <td className="py-2 pr-3 text-xs text-muted-foreground whitespace-nowrap">
                              {new Date(e.timestamp).toLocaleString()}
                            </td>
                            <td className="py-2 pr-3">
                              <Badge variant="outline" className="text-xs">{e.component}</Badge>
                            </td>
                            <td className="py-2 pr-3 text-xs text-red-700 max-w-xs truncate" title={e.message}>
                              {e.message}
                            </td>
                            <td className="py-2 text-xs text-muted-foreground">{e.user}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      ) : (
        <Card>
          <CardContent className="py-8 text-center">
            <XCircle className="h-8 w-8 text-red-500 mx-auto mb-2" />
            <p className="text-muted-foreground">Could not load system health data.</p>
            <p className="text-xs text-muted-foreground mt-1">Admin access required.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
