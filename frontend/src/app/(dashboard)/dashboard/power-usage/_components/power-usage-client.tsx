"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  Activity,
  Calendar,
  Gauge,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { get } from "@/lib/fetch-client";
import { useSelectedMeter } from "@/contexts/selected-meter-context";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type Period = "week" | "month" | "year";

interface PowerUsageData {
  eligible: boolean;
  message?: string;
  meter_no?: string;
  meter_label?: string;
  period?: Period;
  range?: { start: string; end: string };
  summary?: {
    total_kwh: number;
    average_daily_kwh: number;
    peak_day_kwh: number;
    peak_day_date: string | null;
    lowest_day_kwh: number;
    lowest_day_date: string | null;
    days_with_data: number;
  };
  daily?: Array<{ date: string; kwh_used: number; source?: string | null }>;
  monthly?: Array<{
    month: number;
    label: string;
    total_kwh: number;
    average_daily_kwh: number;
  }>;
  available_years?: number[];
  available_meters?: Array<{ meter_no: string; label: string }>;
  data_source?: string;
}

const PERIOD_LABELS: Record<Period, string> = {
  week: "Weekly",
  month: "Monthly",
  year: "Annual",
};

function formatShortDate(iso: string) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatLongDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function PowerUsageClient() {
  const { meters, selectedMeter, setSelectedMeterNo } = useSelectedMeter();
  const amiMeters = useMemo(
    () => meters.filter((m) => m.architecture === "AMI"),
    [meters]
  );

  const [period, setPeriod] = useState<Period>("week");
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [month, setMonth] = useState<number>(new Date().getMonth() + 1);
  const [data, setData] = useState<PowerUsageData | null>(null);
  const [loading, setLoading] = useState(true);

  const meterNo = selectedMeter?.architecture === "AMI"
    ? selectedMeter.meter_number
    : amiMeters[0]?.meter_number;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ period });
      if (meterNo) params.set("meter_no", meterNo);
      if (period === "year") params.set("year", String(year));
      if (period === "month") {
        params.set("year", String(year));
        params.set("month", String(month));
      }
      const res = await get<{ success: boolean; data: PowerUsageData }>(
        `meter/power-usage/?${params.toString()}`
      );
      if (!res.error && res.data?.data) {
        setData(res.data.data);
        if (res.data.data.available_years?.length && !res.data.data.available_years.includes(year)) {
          setYear(res.data.data.available_years[0]);
        }
      } else {
        setData({ eligible: false, message: "Unable to load Energy Usage." });
      }
    } catch {
      setData({ eligible: false, message: "Unable to load Energy Usage." });
    } finally {
      setLoading(false);
    }
  }, [period, meterNo, year, month]);

  useEffect(() => {
    if (amiMeters.length) load();
    else {
      setLoading(false);
      setData({ eligible: false, message: "This is only for AMI meter users." });
    }
  }, [load, amiMeters.length]);

  const chartData = useMemo(() => {
    if (!data?.daily) return [];
    return data.daily.map((d) => ({
      ...d,
      label: formatShortDate(d.date),
    }));
  }, [data?.daily]);

  const monthlyChart = useMemo(() => data?.monthly ?? [], [data?.monthly]);

  if (!amiMeters.length && !loading) {
    return (
      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-muted-foreground" />
            Energy Usage
          </CardTitle>
          <CardDescription>AMI meter analytics</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            This is only for AMI meter users. Your account has STS (token-based) meters only.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Activity className="h-7 w-7 text-primary" />
            Energy Usage
          </h1>
          <p className="text-muted-foreground mt-1">
            Energy consumed (kWh) from your networked AMI meter
            {data?.meter_no ? ` · ${data.meter_label || data.meter_no}` : ""}
          </p>
        </div>
        {amiMeters.length > 1 && (
          <Select value={meterNo ?? ""} onValueChange={setSelectedMeterNo}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Select meter" />
            </SelectTrigger>
            <SelectContent>
              {amiMeters.map((m) => (
                <SelectItem key={m.meter_number} value={m.meter_number}>
                  {m.label || m.meter_number}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {(Object.keys(PERIOD_LABELS) as Period[]).map((p) => (
          <Button
            key={p}
            variant={period === p ? "default" : "outline"}
            size="sm"
            onClick={() => setPeriod(p)}
          >
            {PERIOD_LABELS[p]}
          </Button>
        ))}
        {period === "year" && data?.available_years && (
          <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
            <SelectTrigger className="w-[100px] h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {data.available_years.map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {period === "month" && (
          <>
            <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
              <SelectTrigger className="w-[120px] h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <SelectItem key={m} value={String(m)}>
                    {new Date(2000, m - 1, 1).toLocaleString(undefined, { month: "long" })}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
              <SelectTrigger className="w-[100px] h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(data?.available_years ?? [year]).map((y) => (
                  <SelectItem key={y} value={String(y)}>
                    {y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        )}
        {data?.data_source && (
          <Badge variant="secondary" className="ml-auto self-center">
            Source: {data.data_source}
          </Badge>
        )}
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
          <Skeleton className="h-80 rounded-xl md:col-span-4" />
        </div>
      ) : !data?.eligible ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">
              {data?.message ?? "This is only for AMI meter users."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryCard
              title="Total used"
              value={`${data.summary?.total_kwh ?? 0} kWh`}
              icon={<Zap className="h-4 w-4 text-amber-500" />}
              hint={data.range ? `${formatShortDate(data.range.start)} – ${formatShortDate(data.range.end)}` : undefined}
            />
            <SummaryCard
              title="Daily average"
              value={`${data.summary?.average_daily_kwh ?? 0} kWh`}
              icon={<Gauge className="h-4 w-4 text-blue-500" />}
              hint={`${data.summary?.days_with_data ?? 0} days with data`}
            />
            <SummaryCard
              title="Peak day"
              value={`${data.summary?.peak_day_kwh ?? 0} kWh`}
              icon={<TrendingUp className="h-4 w-4 text-emerald-500" />}
              hint={formatLongDate(data.summary?.peak_day_date)}
            />
            <SummaryCard
              title="Lowest day"
              value={`${data.summary?.lowest_day_kwh ?? 0} kWh`}
              icon={<TrendingDown className="h-4 w-4 text-slate-500" />}
              hint={formatLongDate(data.summary?.lowest_day_date)}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                {period === "year" ? "Monthly consumption" : "Daily consumption"}
              </CardTitle>
              <CardDescription>
                kWh used per {period === "year" ? "month" : "day"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  {period === "year" && monthlyChart.length > 0 ? (
                    <BarChart data={monthlyChart}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} unit=" kWh" />
                      <Tooltip
                        formatter={(v) => [`${v ?? 0} kWh`, "Used"]}
                        labelFormatter={(l) => l}
                      />
                      <Bar dataKey="total_kwh" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Total kWh" />
                    </BarChart>
                  ) : (
                    <AreaChart data={chartData}>
                      <defs>
                        <linearGradient id="usageFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 12 }} unit=" kWh" />
                      <Tooltip
                        formatter={(v) => [`${v ?? 0} kWh`, "Used"]}
                        labelFormatter={(_, payload) =>
                          payload?.[0]?.payload?.date
                            ? formatLongDate(payload[0].payload.date)
                            : ""
                        }
                      />
                      <Area
                        type="monotone"
                        dataKey="kwh_used"
                        stroke="#3b82f6"
                        fill="url(#usageFill)"
                        strokeWidth={2}
                        name="kWh used"
                      />
                    </AreaChart>
                  )}
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {period !== "year" && chartData.some((d) => d.kwh_used > 0) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  Daily breakdown
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2 font-medium">Date</th>
                        <th className="pb-2 font-medium text-right">kWh used</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...chartData].reverse().map((row) => (
                        <tr key={row.date} className="border-b border-muted/50">
                          <td className="py-2">{formatLongDate(row.date)}</td>
                          <td className={cn("py-2 text-right font-medium", row.kwh_used === 0 && "text-muted-foreground")}>
                            {row.kwh_used.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function SummaryCard({
  title,
  value,
  icon,
  hint,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  hint?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
      </CardContent>
    </Card>
  );
}
