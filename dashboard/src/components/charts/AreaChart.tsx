"use client";
import {
  ResponsiveContainer, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from "recharts";

interface Props {
  data: { date: string; value: number }[];
  color?: string;
  valueLabel?: string;
  formatValue?: (v: number) => string;
  height?: number;
  threshold?: number;
}

export default function SimpleAreaChart({
  data,
  color = "#4f6ef7",
  valueLabel = "Value",
  formatValue = (v) => String(v),
  height = 200,
  threshold,
}: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <defs>
          <linearGradient id={`grad-${color.replace("#","")}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={color} stopOpacity={0.25}/>
            <stop offset="95%" stopColor={color} stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e2235" vertical={false}/>
        <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false}
          tickFormatter={(v) => v.slice(5)} />
        <YAxis tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false}
          tickFormatter={formatValue} />
        <Tooltip
          contentStyle={{ background: "#1a1f2e", border: "1px solid #252b3b", borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: "#94a3b8" }}
          itemStyle={{ color: color }}
          formatter={(v: number) => [formatValue(v), valueLabel]}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          fill={`url(#grad-${color.replace("#","")})`}
          dot={false}
          activeDot={{ r: 4, fill: color }}
        />
        {threshold != null && (
          <ReferenceLine
            y={threshold}
            stroke="#ef4444"
            strokeDasharray="5 3"
            strokeWidth={1.5}
            label={{
              value: `Budget ${formatValue(threshold)}`,
              fill: "#ef4444",
              fontSize: 10,
              position: "insideTopRight",
            }}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
