"use client";

import React from "react";
import {
  LineChart as RechartsLineChart,
  BarChart as RechartsBarChart,
  PieChart as RechartsPieChart,
  AreaChart as RechartsAreaChart,
  ComposedChart as RechartsComposedChart,
  ScatterChart as RechartsScatterChart,
  RadarChart as RechartsRadarChart,
  RadialBarChart as RechartsRadialBarChart,
  Treemap as RechartsTreemap,
  Sankey as RechartsSankey,
  Line,
  Bar,
  Pie,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  Sector,
  RadialBar,
  Scatter,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Treemap as TreemapComponent,
  Sankey as SankeyComponent,
} from "recharts";
import { cn } from "@/lib/utils";

// Common color palette for consistent styling
export const CHART_COLORS = {
  primary: "#3b82f6",
  secondary: "#6b7280",
  success: "#10b981",
  danger: "#ef4444",
  warning: "#f59e0b",
  info: "#0ea5e9",
  purple: "#8b5cf6",
  pink: "#ec4899",
} as const;

export type ChartColor = keyof typeof CHART_COLORS;

function formatTooltipNumber(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

interface BaseChartProps {
  data: any[];
  className?: string;
  height?: number | `${number}%`;
  width?: number | `${number}%`;
  title?: string;
  description?: string;
  showLegend?: boolean;
  showTooltip?: boolean;
  showGrid?: boolean;
  colors?: string[];
}

// Line Chart Component
export const LineChart: React.FC<
  BaseChartProps & {
    lines: Array<{
      dataKey: string;
      name?: string;
      color?: ChartColor | string;
      strokeWidth?: number;
      strokeDasharray?: string;
    }>;
    xAxisKey: string;
    showXAxis?: boolean;
    showYAxis?: boolean;
    xAxisLabel?: string;
    yAxisLabel?: string;
  }
> = ({
  data,
  lines,
  xAxisKey,
  className,
  height = 300,
  width = "100%",
  title,
  description,
  showLegend = true,
  showTooltip = true,
  showGrid = true,
  colors,
  showXAxis = true,
  showYAxis = true,
  xAxisLabel,
  yAxisLabel,
}) => {
  return (
    <div className={cn("space-y-2", className)}>
      {title && (
        <div className="text-center space-y-1">
          <h3 className="font-semibold">{title}</h3>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      <ResponsiveContainer width={width} height={height}>
        <RechartsLineChart data={data}>
          {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
          {showXAxis && (
            <XAxis
              dataKey={xAxisKey}
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              label={xAxisLabel ? { value: xAxisLabel, position: "insideBottom", offset: -5 } : undefined}
            />
          )}
          {showYAxis && (
            <YAxis
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: "insideLeft" } : undefined}
            />
          )}
          {showTooltip && (
            <Tooltip
              contentStyle={{
                backgroundColor: "white",
                border: "1px solid #e5e7eb",
                borderRadius: "6px",
                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
              }}
              labelStyle={{ color: "#374151", fontWeight: 600 }}
            />
          )}
          {showLegend && <Legend />}
          {lines.map((line, index) => (
            <Line
              key={line.dataKey}
              type="monotone"
              dataKey={line.dataKey}
              name={line.name || line.dataKey}
              stroke={line.color ? (CHART_COLORS[line.color as ChartColor] || line.color) : (colors?.[index] || Object.values(CHART_COLORS)[index % Object.values(CHART_COLORS).length])}
              strokeWidth={line.strokeWidth || 2}
              strokeDasharray={line.strokeDasharray}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          ))}
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  );
};

// Bar Chart Component
export const BarChart: React.FC<
  BaseChartProps & {
    bars: Array<{
      dataKey: string;
      name?: string;
      color?: ChartColor | string;
      stackId?: string;
    }>;
    xAxisKey: string;
    showXAxis?: boolean;
    showYAxis?: boolean;
    xAxisLabel?: string;
    yAxisLabel?: string;
    barSize?: number;
    borderRadius?: number;
  }
> = ({
  data,
  bars,
  xAxisKey,
  className,
  height = 300,
  width = "100%",
  title,
  description,
  showLegend = true,
  showTooltip = true,
  showGrid = true,
  colors,
  showXAxis = true,
  showYAxis = true,
  xAxisLabel,
  yAxisLabel,
  barSize = 30,
  borderRadius = 4,
}) => {
  return (
    <div className={cn("space-y-2", className)}>
      {title && (
        <div className="text-center space-y-1">
          <h3 className="font-semibold">{title}</h3>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      <ResponsiveContainer width={width} height={height}>
        <RechartsBarChart data={data}>
          {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
          {showXAxis && (
            <XAxis
              dataKey={xAxisKey}
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              label={xAxisLabel ? { value: xAxisLabel, position: "insideBottom", offset: -5 } : undefined}
            />
          )}
          {showYAxis && (
            <YAxis
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: "insideLeft" } : undefined}
            />
          )}
          {showTooltip && (
            <Tooltip
              contentStyle={{
                backgroundColor: "white",
                border: "1px solid #e5e7eb",
                borderRadius: "6px",
                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
              }}
              labelStyle={{ color: "#374151", fontWeight: 600 }}
              formatter={(value) => [formatTooltipNumber(value), ""]}
            />
          )}
          {showLegend && <Legend />}
          {bars.map((bar, index) => (
            <Bar
              key={bar.dataKey}
              dataKey={bar.dataKey}
              name={bar.name || bar.dataKey}
              fill={bar.color ? (CHART_COLORS[bar.color as ChartColor] || bar.color) : (colors?.[index] || Object.values(CHART_COLORS)[index % Object.values(CHART_COLORS).length])}
              stackId={bar.stackId}
              barSize={barSize}
              radius={[borderRadius, borderRadius, 0, 0]}
            />
          ))}
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  );
};

// Pie Chart Component
export const PieChart: React.FC<
  BaseChartProps & {
    dataKey: string;
    nameKey: string;
    colors?: string[];
    innerRadius?: number;
    outerRadius?: number;
    showLabel?: boolean;
    labelType?: "value" | "name" | "percent";
  }
> = ({
  data,
  dataKey,
  nameKey,
  className,
  height = 300,
  width = "100%",
  title,
  description,
  showLegend = true,
  showTooltip = true,
  colors,
  innerRadius = 0,
  outerRadius = 80,
  showLabel = true,
  labelType = "value",
}) => {
  const getLabelContent = (entry: any) => {
    switch (labelType) {
      case "name":
        return entry[nameKey];
      case "percent":
        return `${((entry[dataKey] / data.reduce((acc, cur) => acc + cur[dataKey], 0)) * 100).toFixed(1)}%`;
      case "value":
      default:
        return entry[dataKey];
    }
  };

  return (
    <div className={cn("space-y-2", className)}>
      {title && (
        <div className="text-center space-y-1">
          <h3 className="font-semibold">{title}</h3>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      <ResponsiveContainer width={width} height={height}>
        <RechartsPieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={showLabel ? getLabelContent : undefined}
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            fill="#8884d8"
            dataKey={dataKey}
            nameKey={nameKey}
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={colors?.[index] || Object.values(CHART_COLORS)[index % Object.values(CHART_COLORS).length]}
              />
            ))}
          </Pie>
          {showTooltip && (
            <Tooltip
              contentStyle={{
                backgroundColor: "white",
                border: "1px solid #e5e7eb",
                borderRadius: "6px",
                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
              }}
              formatter={(value, name) => [
                formatTooltipNumber(value),
                typeof name === "string" ? name : "",
              ]}
            />
          )}
          {showLegend && <Legend />}
        </RechartsPieChart>
      </ResponsiveContainer>
    </div>
  );
};

// Area Chart Component
export const AreaChart: React.FC<
  BaseChartProps & {
    areas: Array<{
      dataKey: string;
      name?: string;
      color?: ChartColor | string;
      gradient?: boolean;
    }>;
    xAxisKey: string;
    showXAxis?: boolean;
    showYAxis?: boolean;
    xAxisLabel?: string;
    yAxisLabel?: string;
  }
> = ({
  data,
  areas,
  xAxisKey,
  className,
  height = 300,
  width = "100%",
  title,
  description,
  showLegend = true,
  showTooltip = true,
  showGrid = true,
  colors,
  showXAxis = true,
  showYAxis = true,
  xAxisLabel,
  yAxisLabel,
}) => {
  return (
    <div className={cn("space-y-2", className)}>
      {title && (
        <div className="text-center space-y-1">
          <h3 className="font-semibold">{title}</h3>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      <ResponsiveContainer width={width} height={height}>
        <RechartsAreaChart data={data}>
          {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
          {showXAxis && (
            <XAxis
              dataKey={xAxisKey}
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              label={xAxisLabel ? { value: xAxisLabel, position: "insideBottom", offset: -5 } : undefined}
            />
          )}
          {showYAxis && (
            <YAxis
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: "insideLeft" } : undefined}
            />
          )}
          {showTooltip && (
            <Tooltip
              contentStyle={{
                backgroundColor: "white",
                border: "1px solid #e5e7eb",
                borderRadius: "6px",
                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
              }}
              labelStyle={{ color: "#374151", fontWeight: 600 }}
            />
          )}
          {showLegend && <Legend />}
          {areas.map((area, index) => (
            <Area
              key={area.dataKey}
              type="monotone"
              dataKey={area.dataKey}
              name={area.name || area.dataKey}
              stroke={area.color ? (CHART_COLORS[area.color as ChartColor] || area.color) : (colors?.[index] || Object.values(CHART_COLORS)[index % Object.values(CHART_COLORS).length])}
              fill={area.color ? (CHART_COLORS[area.color as ChartColor] || area.color) : (colors?.[index] || Object.values(CHART_COLORS)[index % Object.values(CHART_COLORS).length])}
              fillOpacity={0.3}
              strokeWidth={2}
            />
          ))}
        </RechartsAreaChart>
      </ResponsiveContainer>
    </div>
  );
};

// Composed Chart Component (Mix of different chart types)
export const ComposedChart: React.FC<
  BaseChartProps & {
    xAxisKey: string;
    showXAxis?: boolean;
    showYAxis?: boolean;
    xAxisLabel?: string;
    yAxisLabel?: string;
    children: React.ReactNode;
  }
> = ({
  data,
  xAxisKey,
  className,
  height = 300,
  width = "100%",
  title,
  description,
  showLegend = true,
  showTooltip = true,
  showGrid = true,
  showXAxis = true,
  showYAxis = true,
  xAxisLabel,
  yAxisLabel,
  children,
}) => {
  return (
    <div className={cn("space-y-2", className)}>
      {title && (
        <div className="text-center space-y-1">
          <h3 className="font-semibold">{title}</h3>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      <ResponsiveContainer width={width} height={height}>
        <RechartsComposedChart data={data}>
          {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
          {showXAxis && (
            <XAxis
              dataKey={xAxisKey}
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              label={xAxisLabel ? { value: xAxisLabel, position: "insideBottom", offset: -5 } : undefined}
            />
          )}
          {showYAxis && (
            <YAxis
              stroke="#6b7280"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: "insideLeft" } : undefined}
            />
          )}
          {showTooltip && (
            <Tooltip
              contentStyle={{
                backgroundColor: "white",
                border: "1px solid #e5e7eb",
                borderRadius: "6px",
                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
              }}
              labelStyle={{ color: "#374151", fontWeight: 600 }}
            />
          )}
          {showLegend && <Legend />}
          {children}
        </RechartsComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

// Stat Card with Chart
export const StatCard: React.FC<{
  title: string;
  value: string | number;
  change?: {
    value: number;
    type: "increase" | "decrease" | "neutral";
  };
  chart?: React.ReactNode;
  description?: string;
  icon?: React.ReactNode;
  className?: string;
}> = ({ title, value, change, chart, description, icon, className }) => {
  return (
    <div className={cn("bg-white dark:bg-gray-800 rounded-lg border p-4", className)}>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            {icon}
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
              {title}
            </p>
          </div>
          <div className="flex items-end gap-2">
            <p className="text-2xl font-bold">{value}</p>
            {change && (
              <span
                className={cn(
                  "text-sm font-medium",
                  change.type === "increase"
                    ? "text-green-600"
                    : change.type === "decrease"
                    ? "text-red-600"
                    : "text-gray-600"
                )}
              >
                {change.type === "increase" ? "↑" : change.type === "decrease" ? "↓" : "→"}
                {Math.abs(change.value)}%
              </span>
            )}
          </div>
          {description && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {description}
            </p>
          )}
        </div>
        {chart && <div className="w-16 h-10">{chart}</div>}
      </div>
    </div>
  );
};

// Chart Skeleton Loader
export const ChartSkeleton: React.FC<{
  className?: string;
  height?: number | string;
}> = ({ className, height = 300 }) => {
  return (
    <div
      className={cn("animate-pulse bg-gray-200 dark:bg-gray-700 rounded", className)}
      style={{ height }}
    />
  );
};