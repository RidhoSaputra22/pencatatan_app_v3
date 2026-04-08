"use client";

import { formatNumber } from "@/lib/utils";

export default function InsightsPanel({ insights = {}, totalEvents = 0, uniqueVisitors = 0 }) {
  const { busyLabel, busyPercent, peakHour, ratio } = insights;
  const hasData = busyLabel || peakHour || ratio;

  if (!hasData) return null;

  // Compute occupancy rate (unique vs total)
  const occupancyRate = totalEvents > 0
    ? Math.round((uniqueVisitors / totalEvents) * 100)
    : 0;

  const insightItems = [
    busyLabel && busyPercent !== null && {
      icon: busyLabel === "ramai" ? (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      ) : (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
        </svg>
      ),
      label: "Perbandingan",
      value: (
        <>
          Hari ini lebih <strong>{busyLabel}</strong> <span className="font-bold">{Math.abs(busyPercent)}%</span>
        </>
      ),
      sub: "dibanding kemarin",
      color: busyLabel === "ramai" ? "text-success" : "text-error",
      bg: busyLabel === "ramai" ? "bg-success/10" : "bg-error/10",
      iconBg: busyLabel === "ramai" ? "bg-success/20" : "bg-error/20",
    },
    peakHour && {
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      label: "Jam Terpadat",
      value: peakHour,
      sub: "waktu paling sibuk",
      color: "text-warning",
      bg: "bg-warning/10",
      iconBg: "bg-warning/20",
    },
    ratio && {
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      ),
      label: "Rasio Masuk/Keluar",
      value: `${ratio} : 1`,
      sub: "perbandingan arah",
      color: "text-info",
      bg: "bg-info/10",
      iconBg: "bg-info/20",
    },
    totalEvents > 0 && {
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
      label: "Total Pengunjung",
      value: formatNumber(totalEvents),
      sub: (
        <span className="flex items-center gap-1.5">
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[10px] font-bold">
            {occupancyRate}%
          </span>
          <span>pengunjung unik</span>
        </span>
      ),
      color: "text-primary",
      bg: "bg-primary/10",
      iconBg: "bg-primary/20",
    },
  ].filter(Boolean);

  return (
    <div className="card bg-base-100 shadow-lg p-5">
      <h3 className="text-sm font-bold text-base-content/70 mb-4 flex items-center gap-2">
        <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        Insight Ringkas
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {insightItems.map((item, i) => (
          <div
            key={i}
            className={`relative overflow-hidden rounded-xl ${item.bg} p-4 transition-all duration-200 hover:scale-[1.02]`}
          >
            <div className="flex items-start gap-3">
              <div className={`p-2 rounded-lg ${item.iconBg} ${item.color} shrink-0`}>
                {item.icon}
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold text-base-content/50 uppercase tracking-wider mb-1">{item.label}</p>
                <p className={`text-base font-bold ${item.color} leading-snug`}>{item.value}</p>
                <p className="text-xs text-base-content/40 mt-1">{item.sub}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
