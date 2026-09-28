'use client';

export const dynamic = "force-dynamic";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Activity, AlertCircle, AlertTriangle, CheckCircle2,
  CreditCard, Users, XCircle, Zap, ArrowRight, TrendingUp,
} from 'lucide-react';
import { get } from "@/lib/fetch-client";

interface DashboardData {
  total_users: number;
  active_users_30d: number;
  total_meters: number;
  active_meters: number;
  new_users_today: number;
  new_users_week: number;
  transactions_today: number;
  failed_transactions_today: number;
  failed_transaction_pct: number;
  active_loans: number;
  overdue_loans: number;
  flagged_accounts: number;
  system_status: "GREEN" | "AMBER" | "RED";
  recent_users: RecentUser[];
}

interface RecentUser {
  id: number;
  email: string;
  name: string;
  phone: string;
  email_verified: boolean;
  joined: string;
  has_meter: boolean;
}

const defaultData: DashboardData = {
  total_users: 0, active_users_30d: 0, total_meters: 0, active_meters: 0,
  new_users_today: 0, new_users_week: 0, transactions_today: 0,
  failed_transactions_today: 0, failed_transaction_pct: 0,
  active_loans: 0, overdue_loans: 0, flagged_accounts: 0,
  system_status: "GREEN", recent_users: [],
};

function SystemStatusBadge({ status }: { status: "GREEN" | "AMBER" | "RED" }) {
  if (status === "GREEN")
    return <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 font-medium"><CheckCircle2 className="h-3 w-3 mr-1.5" />All systems operational</Badge>;
  if (status === "AMBER")
    return <Badge className="bg-amber-50 text-amber-700 border-amber-200 font-medium"><AlertTriangle className="h-3 w-3 mr-1.5" />Degraded performance</Badge>;
  return <Badge className="bg-red-50 text-red-700 border-red-200 font-medium"><XCircle className="h-3 w-3 mr-1.5" />Service outage</Badge>;
}

function StatCard({
  title, value, sub, icon, accent = "blue", alert = false, onClick,
}: {
  title: string; value: number; sub?: string;
  icon: React.ReactNode; accent?: string; alert?: boolean;
  onClick?: () => void;
}) {
  const accents: Record<string, string> = {
    blue:   "border-l-blue-500   bg-blue-500/5",
    green:  "border-l-emerald-500 bg-emerald-500/5",
    indigo: "border-l-indigo-500 bg-indigo-500/5",
    red:    "border-l-red-500    bg-red-500/5",
    amber:  "border-l-amber-500  bg-amber-500/5",
    orange: "border-l-orange-500 bg-orange-500/5",
  };

  return (
    <Card
      className={`border-l-4 ${accents[accent] ?? accents.blue} shadow-none transition-shadow ${
        onClick ? "cursor-pointer hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" : ""
      }`}
      onClick={onClick}
      onKeyDown={(event) => {
        if (!onClick) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick();
        }
      }}
      tabIndex={onClick ? 0 : -1}
      role={onClick ? "button" : undefined}
      aria-label={onClick ? `${title} details` : undefined}
    >
      <CardHeader className="flex flex-row items-center justify-between pb-1 pt-4 px-5">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</span>
        <div className="h-8 w-8 rounded-lg bg-background flex items-center justify-center border border-border">
          {icon}
        </div>
      </CardHeader>
      <CardContent className="px-5 pb-4">
        <p className={`text-3xl font-bold tracking-tight ${alert && value > 0 ? 'text-red-600' : ''}`}>
          {value.toLocaleString()}
        </p>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export default function AdminDashboard() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData>(defaultData);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function fetchDashboard() {
      try {
        const res = await get<any>("admin/dashboard/");
        if (cancelled) return;
        if (res.data) setData({ ...defaultData, ...res.data });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchDashboard();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <DashboardSkeleton />;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
          <p className="text-sm text-muted-foreground mt-0.5">gPawa Admin · real-time platform metrics</p>
        </div>
        <SystemStatusBadge status={data.system_status} />
      </div>

      {/* Row 1: primary KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Users"
          value={data.total_users}
          sub={`${data.active_users_30d} active last 30 days`}
          icon={<Users className="h-4 w-4 text-blue-600" />}
          accent="blue"
          onClick={() => router.push('/admin/users')}
        />
        <StatCard
          title="Registered Meters"
          value={data.total_meters}
          sub={`${data.active_meters} active`}
          icon={<Zap className="h-4 w-4 text-emerald-600" />}
          accent="green"
          onClick={() => router.push('/admin/meters')}
        />
        <StatCard
          title="Transactions Today"
          value={data.transactions_today}
          sub={data.failed_transactions_today > 0
            ? `${data.failed_transactions_today} failed (${data.failed_transaction_pct}%)`
            : "No failures today"}
          icon={<Activity className="h-4 w-4 text-indigo-600" />}
          accent="indigo"
          onClick={() => router.push('/admin/transactions')}
        />
        <StatCard
          title="Failed Transactions"
          value={data.failed_transactions_today}
          sub={`${data.failed_transaction_pct}% failure rate`}
          icon={<XCircle className="h-4 w-4 text-red-500" />}
          accent="red"
          alert
          onClick={() => router.push('/admin/transactions?status=FAILED')}
        />
      </div>

      {/* Row 2: credit + flags */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          title="Active Loans"
          value={data.active_loans}
          sub="Currently disbursed"
          icon={<CreditCard className="h-4 w-4 text-amber-600" />}
          accent="amber"
          onClick={() => router.push('/admin/loans')}
        />
        <StatCard
          title="Overdue Loans"
          value={data.overdue_loans}
          sub="Past due date"
          icon={<AlertCircle className="h-4 w-4 text-orange-600" />}
          accent="orange"
          alert
          onClick={() => router.push('/admin/loans')}
        />
        <StatCard
          title="Flagged Accounts"
          value={data.flagged_accounts}
          sub="Awaiting review"
          icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
          accent="amber"
          alert
          onClick={() => router.push('/admin/users?status=flagged')}
        />
      </div>

      {/* Quick actions */}
      <Card className="shadow-none">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {[
            { label: "Users",        icon: Users,         href: "/admin/users"        },
            { label: "Meters",       icon: Zap,           href: "/admin/meters"       },
            { label: "Loans",        icon: CreditCard,    href: "/admin/loans"        },
            { label: "Transactions", icon: Activity,      href: "/admin/transactions" },
          ].map(({ label, icon: Icon, href }) => (
            <Button key={href} variant="outline" size="sm" onClick={() => router.push(href)}
              className="gap-2 text-xs font-medium h-8">
              <Icon className="h-3.5 w-3.5" />{label}
            </Button>
          ))}
          {data.flagged_accounts > 0 && (
            <Button variant="outline" size="sm"
              onClick={() => router.push('/admin/transactions?flagged=true')}
              className="gap-2 text-xs font-medium h-8 border-amber-300 text-amber-700 hover:bg-amber-50">
              <AlertTriangle className="h-3.5 w-3.5" />
              Review {data.flagged_accounts} flag{data.flagged_accounts > 1 ? 's' : ''}
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Recent registrations */}
      <Card className="shadow-none">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-sm font-semibold">Recent Registrations</CardTitle>
              <CardDescription className="text-xs mt-0.5">
                {data.new_users_today} today · {data.new_users_week} this week
              </CardDescription>
            </div>
            <Button variant="ghost" size="sm" className="text-xs gap-1.5 h-7"
              onClick={() => router.push('/admin/users')}>
              View all <ArrowRight className="h-3 w-3" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {data.recent_users.length > 0 ? (
            <div className="overflow-x-auto -mx-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground">
                    <th className="text-left py-2 px-2 font-medium">Name</th>
                    <th className="text-left py-2 px-2 font-medium hidden sm:table-cell">Email</th>
                    <th className="text-left py-2 px-2 font-medium hidden md:table-cell">Phone</th>
                    <th className="text-left py-2 px-2 font-medium">Joined</th>
                    <th className="text-left py-2 px-2 font-medium">KYC</th>
                    <th className="text-left py-2 px-2 font-medium">Meter</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_users.map((u) => (
                    <tr
                      key={u.id}
                      className="border-b last:border-0 hover:bg-muted/40 cursor-pointer transition-colors"
                      onClick={() => router.push(`/admin/users/${u.id}`)}
                    >
                      <td className="py-2.5 px-2 font-medium whitespace-nowrap">{u.name}</td>
                      <td className="py-2.5 px-2 text-muted-foreground hidden sm:table-cell text-xs">{u.email}</td>
                      <td className="py-2.5 px-2 text-muted-foreground hidden md:table-cell text-xs">{u.phone || '—'}</td>
                      <td className="py-2.5 px-2 text-muted-foreground whitespace-nowrap text-xs">{u.joined}</td>
                      <td className="py-2.5 px-2">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          u.email_verified
                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400'
                            : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                        }`}>
                          {u.email_verified ? 'Verified' : 'Pending'}
                        </span>
                      </td>
                      <td className="py-2.5 px-2">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          u.has_meter
                            ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-400'
                            : 'bg-gray-100 text-gray-500 dark:bg-gray-800'
                        }`}>
                          {u.has_meter ? 'Active' : 'None'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">No registrations yet</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="flex justify-between">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-6 w-44" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="shadow-none">
            <CardHeader className="pb-1 pt-4 px-5"><Skeleton className="h-3 w-24" /></CardHeader>
            <CardContent className="px-5 pb-4"><Skeleton className="h-9 w-16 mt-1" /><Skeleton className="h-3 w-32 mt-2" /></CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {[...Array(3)].map((_, i) => (
          <Card key={i} className="shadow-none">
            <CardHeader className="pb-1 pt-4 px-5"><Skeleton className="h-3 w-24" /></CardHeader>
            <CardContent className="px-5 pb-4"><Skeleton className="h-9 w-16 mt-1" /></CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
