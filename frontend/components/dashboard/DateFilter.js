"use client";

import Input from "@/components/ui/Input";

const PRESETS = [
  { key: "today", label: "Hari Ini" },
  { key: "yesterday", label: "Kemarin" },
  { key: "7days", label: "7 Hari" },
  { key: "30days", label: "30 Hari" },
  { key: "month", label: "Bulan Ini" },
  { key: "range", label: "Custom" },
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
    <div className="flex flex-wrap items-center gap-2">
      {/* Pill tabs */}
      <div className="flex flex-wrap gap-1">
        {PRESETS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setFilterMode(key)}
            className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${
              filterMode === key
                ? "bg-primary text-white shadow-sm"
                : "bg-base-200 text-base-content/70 hover:bg-base-300"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Custom date range inputs */}
      {filterMode === "range" && (
        <div className="flex items-center gap-2 ml-2">
          <Input
            type="date"
            className="input-sm w-36"
            value={filterFrom}
            max={filterTo || today}
            onChange={(e) => setFilterFrom(e.target.value)}
          />
          <span className="text-sm text-base-content/50">—</span>
          <Input
            type="date"
            className="input-sm w-36"
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
