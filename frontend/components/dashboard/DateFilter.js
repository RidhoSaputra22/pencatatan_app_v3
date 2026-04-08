"use client";

import Input from "@/components/ui/Input";

const PRESETS = [
  { key: "today", label: "Hari Ini", icon: "○" },
  { key: "yesterday", label: "Kemarin" },
  { key: "7days", label: "7 Hari" },
  { key: "30days", label: "30 Hari" },
  { key: "month", label: "Bulan Ini" },
  { key: "range", label: "Pilih Tanggal", icon: "📅" },
];

export default function DateFilter({
  filterMode,
  setFilterMode,
  filterFrom,
  setFilterFrom,
  filterTo,
  setFilterTo,
  today,
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="inline-flex bg-base-200/60 rounded-xl p-1 gap-0.5">
        {PRESETS.map(({ key, label, icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => setFilterMode(key)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
              filterMode === key
                ? "bg-primary text-white shadow-md shadow-primary/25"
                : "text-base-content/60 hover:text-base-content hover:bg-base-300/50"
            }`}
          >
            {icon && <span className="mr-1">{icon}</span>}
            {label}
          </button>
        ))}
      </div>

      {filterMode === "range" && (
        <div className="flex items-center gap-2 ml-1 bg-base-200/40 rounded-lg px-3 py-1.5">
          <Input
            type="date"
            className="input-sm w-36 bg-transparent border-0 focus:outline-none"
            value={filterFrom}
            max={filterTo || today}
            onChange={(e) => setFilterFrom(e.target.value)}
          />
          <span className="text-sm text-base-content/30 font-bold">→</span>
          <Input
            type="date"
            className="input-sm w-36 bg-transparent border-0 focus:outline-none"
            value={filterTo}
            min={filterFrom}
            max={today}
            onChange={(e) => setFilterTo(e.target.value)}
          />
        </div>
      )}
    </div>
  );
}
