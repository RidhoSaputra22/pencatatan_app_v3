"use client";

import { useMemo } from "react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Section from "@/components/ui/Section";
import Select from "@/components/ui/Select";

const PERIOD_OPTIONS = [
  { value: "daily", label: "Harian" },
  { value: "monthly", label: "Bulanan" },
  { value: "yearly", label: "Tahunan" },
];

export default function DateFilter({
  periodType,
  setPeriodType,
  selectedDay,
  setSelectedDay,
  fromTime,
  handleFromTimeChange,
  toTime,
  handleToTimeChange,
  fromMonth,
  handleFromMonthChange,
  toMonth,
  handleToMonthChange,
  fromYear,
  handleFromYearChange,
  toYear,
  handleToYearChange,
  appliedSummaryLabel,
  applyPeriod,
  loading = false,
  today,
}) {
  const currentMonth = today.slice(0, 7);
  const currentYear = today.slice(0, 4);
  const yearOptions = useMemo(() => {
    const currentYearNumber = Number(currentYear);
    return Array.from(
      { length: currentYearNumber - 2000 + 1 },
      (_, index) => {
        const year = String(currentYearNumber - index);
        return { value: year, label: year };
      },
    );
  }, [currentYear]);

  return (
    <Section title="Filter Periode" className="mt-0">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {PERIOD_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setPeriodType(option.value)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                periodType === option.value
                  ? "bg-primary text-primary-content shadow-md shadow-primary/20"
                  : "bg-base-200 text-base-content/70 hover:bg-base-300"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4 xl:items-end">
          {periodType === "daily" && (
            <>
              <Input
                label="Tanggal"
                type="date"
                value={selectedDay}
                max={today}
                onChange={(e) => setSelectedDay(e.target.value)}
                className="input-sm"
              />
              <Input
                label="Dari Jam"
                type="time"
                value={fromTime}
                max={toTime}
                onChange={(e) => handleFromTimeChange(e.target.value)}
                className="input-sm"
              />
              <Input
                label="Sampai Jam"
                type="time"
                value={toTime}
                min={fromTime}
                onChange={(e) => handleToTimeChange(e.target.value)}
                className="input-sm"
              />
            </>
          )}

          {periodType === "monthly" && (
            <>
              <Input
                label="Dari Bulan"
                type="month"
                value={fromMonth}
                max={toMonth}
                onChange={(e) => handleFromMonthChange(e.target.value)}
                className="input-sm"
              />
              <Input
                label="Sampai Bulan"
                type="month"
                value={toMonth}
                min={fromMonth}
                max={currentMonth}
                onChange={(e) => handleToMonthChange(e.target.value)}
                className="input-sm"
              />
            </>
          )}

          {periodType === "yearly" && (
            <>
              <Select
                label="Dari Tahun"
                options={yearOptions}
                value={fromYear}
                onChange={(e) => handleFromYearChange(e.target.value)}
              />
              <Select
                label="Sampai Tahun"
                options={yearOptions}
                value={toYear}
                onChange={(e) => handleToYearChange(e.target.value)}
              />
            </>
          )}

          <div className="flex items-end">
            <Button
              variant="primary"
              isSubmit={false}
              loading={loading}
              onClick={applyPeriod}
              className="btn-sm w-full xl:w-fit"
            >
              Muat Data
            </Button>
          </div>
        </div>

        <p className="text-sm text-base-content/60">
          Rentang aktif: {appliedSummaryLabel}
        </p>
      </div>
    </Section>
  );
}
