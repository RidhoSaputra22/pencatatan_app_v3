"use client";

import { formatNumber } from "@/lib/utils";
import CountUp from "react-countup";

function ChangeBadge({ value }) {
  if (value === null || value === undefined) return null;
  const isUp = value >= 0;
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full ${
        isUp
          ? "bg-success/10 text-success"
          : "bg-error/10 text-error"
      }`}
    >
      {isUp ? (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      ) : (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
        </svg>
      )}
      {isUp ? "+" : ""}{value}% Hari Ini
    </span>
  );
}

function MiniSparkline({ color = "#6366f1" }) {
  const points = Array.from({ length: 8 }, () => Math.random() * 20 + 5);
  const max = Math.max(...points);
  const min = Math.min(...points);
  const h = 24;
  const w = 64;
  const pathData = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p - min) / (max - min + 1)) * h;
      return `${i === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={w} height={h} className="opacity-30">
      <path d={pathData} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

const KPI_CONFIG = [
  {
    key: "totalEvents",
    label: "Total Aktivitas",
    sub: "Seluruh kejadian kunjungan",
    gradient: "from-primary/10 to-primary/5",
    borderColor: "border-l-primary",
    valueColor: "text-primary",
    bgIcon: "bg-primary/10",
    sparkColor: "#6366f1",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-6 h-6">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5m.75-9 3-3 2.148 2.148A12.061 12.061 0 0 1 16.5 7.605" />
      </svg>
    ),
  },
  {
    key: "totalIn",
    label: "Pengunjung Masuk",
    sub: "Total masuk hari ini",
    gradient: "from-success/10 to-success/5",
    borderColor: "border-l-success",
    valueColor: "text-success",
    bgIcon: "bg-success/10",
    sparkColor: "#22c55e",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-6 h-6">
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5 12 3m0 0 7.5 7.5M12 3v18" />
      </svg>
    ),
  },
  {
    key: "totalOut",
    label: "Pengunjung Keluar",
    sub: "Total keluar hari ini",
    gradient: "from-error/10 to-error/5",
    borderColor: "border-l-error",
    valueColor: "text-error",
    bgIcon: "bg-error/10",
    sparkColor: "#ef4444",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-6 h-6">
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5 12 21m0 0-7.5-7.5M12 21V3" />
      </svg>
    ),
  },
  {
    key: "uniqueVisitors",
    label: "Pengunjung Unik",
    sub: "Orang unik per hari",
    gradient: "from-info/10 to-info/5",
    borderColor: "border-l-info",
    valueColor: "text-info",
    bgIcon: "bg-info/10",
    sparkColor: "#06b6d4",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-6 h-6">
        <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z" />
      </svg>
    ),
  },
];

export default function StatsGrid({
  totalEvents,
  uniqueVisitors,
  totalIn,
  totalOut,
  changePercents = {},
}) {
  const values = { totalEvents, totalIn, totalOut, uniqueVisitors };

  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
      {KPI_CONFIG.map(({ key, label, sub, gradient, borderColor, valueColor, bgIcon, sparkColor, icon }) => (
        <div
          key={key}
          className={`relative overflow-hidden card bg-gradient-to-br ${gradient} bg-base-100 shadow-lg border-l-4 ${borderColor} p-5 transition-all duration-300 hover:shadow-xl hover:-translate-y-0.5 group`}
        >
          {/* Background decorative sparkline */}
          <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-500">
            <MiniSparkline color={sparkColor} />
          </div>

          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-semibold text-base-content/70 tracking-wide uppercase" style={{ fontSize: '0.7rem', letterSpacing: '0.05em' }}>{label}</span>
            <div className={`p-2 rounded-xl ${bgIcon}`}>
              <span className={valueColor}>{icon}</span>
            </div>
          </div>

          <div className={`text-4xl font-extrabold tracking-tight ${valueColor}`}>
            <CountUp
              end={values[key] || 0}
              duration={1.2}
              separator="."
              preserveValue
            />
          </div>

          <div className="flex items-center justify-between mt-4 pt-3 border-t border-base-300/30">
            <span className="text-xs text-base-content/50">{sub}</span>
            <ChangeBadge value={changePercents[key]} />
          </div>
        </div>
      ))}
    </section>
  );
}
