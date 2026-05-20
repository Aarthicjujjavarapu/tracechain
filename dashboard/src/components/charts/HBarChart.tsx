"use client";
import {
  ResponsiveContainer, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Cell
} from "recharts";

interface Props {
  data: { label: string; value: number }[];
  color?: string;
  formatValue?: (v: number) => string;
  height?: number;
}

const COLORS = ["#4f6ef7","#6b7ffa","#8b95fb","#a8affb","#c4c8fc"];

export default function HBarChart({
  data,
  color,
  formatValue = (v) => String(v),
  height = 220,
}: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e2235" horizontal={false}/>
        <XAxis type="number" tick={{ fill:"#475569", fontSize:11 }} axisLine={false} tickLine={false}
          tickFormatter={formatValue}/>
        <YAxis type="category" dataKey="label" tick={{ fill:"#94a3b8", fontSize:12 }} axisLine={false} tickLine={false} width={110}/>
        <Tooltip
          contentStyle={{ background:"#1a1f2e", border:"1px solid #252b3b", borderRadius:8, fontSize:12 }}
          labelStyle={{ color:"#94a3b8" }}
          formatter={(v: number) => [formatValue(v)]}
          cursor={{ fill:"rgba(255,255,255,0.03)" }}
        />
        <Bar dataKey="value" radius={[0,4,4,0]} maxBarSize={24}>
          {data.map((_, i) => (
            <Cell key={i} fill={color || COLORS[i % COLORS.length]}/>
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
