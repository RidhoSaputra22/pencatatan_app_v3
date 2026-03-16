"use client";

import Section from "@/components/ui/Section";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";

/**
 * Date range filter component for dashboard.
 * Allows switching between "Hari Ini" and custom date range.
 */
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
    <Section title="Filter Periode">
      <div className="flex flex-wrap items-end gap-3 ">
        {/* Mode toggle */}
        <div className="flex gap-1">
          <Button
            size="sm"
            variant={filterMode === "today" ? "primary" : "ghost"}
            className={filterMode === "today" ? "text-white" : ""}
            onClick={() => {
              setFilterMode("today");
              setFilterFrom(today);
              setFilterTo(today);
            }}
          >
            Hari Ini
          </Button>
          <Button
            size="sm"
            variant={filterMode === "range" ? "primary" : "ghost"}
            className={filterMode === "range" ? "text-white" : ""}
            onClick={() => setFilterMode("range")}
          >
            Rentang Tanggal
          </Button>
        </div>

        {/* Date range inputs */}
        {filterMode === "range" && (
          <>
            <div className="flex">
              <label className="label py-0 ">
                <span className="label-text text-xs">Dari</span>
              </label>
              <Input
                type="date"
                className="input-sm w-40"
                value={filterFrom}
                max={filterTo || today}
                onChange={(e) => setFilterFrom(e.target.value)}
              />
            </div>
            <div className="flex">
              <label className="label py-0 ">
                <span className="label-text text-xs">Sampai</span>
              </label>
              <Input
                type="date"
                className="input-sm w-40"
                value={filterTo}
                min={filterFrom}
                max={today}
                onChange={(e) => setFilterTo(e.target.value)}
              />
            </div>
          </>
        )}
      </div>
    </Section>
  );
}
