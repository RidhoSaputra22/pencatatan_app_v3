"use client";

import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { useStats } from "@/hooks/useStats";

import DateFilter from "@/components/dashboard/DateFilter";
import StatsGrid from "@/components/dashboard/StatsGrid";
import { LineChart, StackedBarChart, InOutDoughnutChart, AreaChart, HorizontalBarChart, RadarChart } from "@/components/dashboard/Charts";
import CameraView from "@/components/dashboard/CameraView";
import StatsTable from "@/components/dashboard/StatsTable";
import ExportSection from "@/components/dashboard/ExportSection";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { APP_ENV, ROLE_ADMIN } from "@/lib/constants";
import { useMemo, useState } from "react";

export default function DashboardPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const {
    day,
    today,
    daily,
    hourlyData,
    totalEvents,
    totalIn,
    totalOut,
    currentInside,
    loading,
    changePercents,
    insights,
    lastUpdatedAt,
    clientPollingEnabled,
    error,
    reload,
    filterFrom,
    filterTo,
    filterFromDateTime,
    filterToDateTime,
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
    isSingleDayView,
    isCurrentDayView,
    isLivePeriod,
  } = useStats();
  const [isResettingDaily, setIsResettingDaily] = useState(false);

  // Chart data for range modes
  const rangeLabels = daily.map((r) => r.stat_date || r.date || "-");
  const rangeIn = daily.map((r) => r.total_in);
  const rangeOut = daily.map((r) => r.total_out);

  // Decide which data to use for charts
  const chartLineLabels = isSingleDayView ? hourlyData.labels : rangeLabels;
  const chartLineData = isSingleDayView
    ? hourlyData.data
    : daily.map((r) => r.total_events);
  const barLabels = isSingleDayView ? hourlyData.labels : rangeLabels;
  const barIn = isSingleDayView
    ? daily.map((r) => r.total_in)
    : rangeIn;
  const barOut = isSingleDayView
    ? daily.map((r) => r.total_out)
    : rangeOut;
  const barChartLabels = isSingleDayView && daily.length > 0
    ? daily.map((r) => r.camera_id ? `Cam ${r.camera_id}` : r.stat_date || "-")
    : barLabels;

  // Active cameras count
  const activeCameras = new Set(daily.map((r) => r.camera_id).filter(Boolean)).size;

  // Radar chart: hourly pattern for in vs out (use hourly buckets)
  // Since we only have total per hour from per-second buckets, approximate by in/out ratio.
  const radarData = useMemo(() => {
    if (!hourlyData || !hourlyData.labels) return { labels: [], dataIn: [], dataOut: [] };
    const ratio = totalEvents > 0 ? totalIn / totalEvents : 0.5;
    return {
      labels: hourlyData.labels.filter((_, i) => i % 2 === 0), // every 2h
      dataIn: hourlyData.data.filter((_, i) => i % 2 === 0).map((v) => Math.round(v * ratio)),
      dataOut: hourlyData.data.filter((_, i) => i % 2 === 0).map((v) => Math.round(v * (1 - ratio))),
    };
  }, [hourlyData, totalIn, totalEvents]);

  // Horizontal bar: daily stats (event, unique) for range mode
  const hBarData = useMemo(() => {
    const sliced = daily.slice(0, 8);
    return {
      labels: sliced.map((r) => r.stat_date || r.date || "-"),
      data: sliced.map((r) => r.total_events || 0),
    };
  }, [daily]);

  const showDevResetTools = APP_ENV.trim().toLowerCase() === "dev" && user?.role === ROLE_ADMIN;
  const resetTargetDay = useMemo(() => {
    if (filterFrom && filterTo && filterFrom === filterTo) {
      return filterFrom;
    }
    return null;
  }, [filterFrom, filterTo]);

  async function handleResetDaily() {
    if (!showDevResetTools || !resetTargetDay || isResettingDaily) {
      return;
    }

    const confirmed = window.confirm(
      `Reset semua data visitor untuk ${resetTargetDay}? Aksi ini hanya untuk mode dev dan tidak bisa dibatalkan.`,
    );
    if (!confirmed) {
      return;
    }

    setIsResettingDaily(true);
    try {
      const { resetDailyStats } = await import("@/services/stats.service");
      const result = await resetDailyStats(resetTargetDay);
      await reload();
      const deleted = result?.deleted || {};
      showToast(
        "success",
        `${result?.message || `Data visitor untuk ${resetTargetDay} berhasil direset`}. ` +
          `Event: ${deleted.visit_events ?? 0}, harian: ${deleted.visitor_daily ?? 0}, statistik: ${deleted.daily_stats ?? 0}.`,
      );
    } catch (err) {
      showToast("error", err.message || "Gagal mereset data visitor harian.");
    } finally {
      setIsResettingDaily(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* ===== HEADER ===== */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-extrabold text-base-content tracking-tight">
                Dashboard Pengunjung
              </h1>
              {isLivePeriod ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-success/10 text-success text-xs font-bold">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
                  </span>
                  Live
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-base-200 px-3 py-1 text-xs font-bold text-base-content/70">
                  Arsip
                </span>
              )}
              {isLivePeriod && clientPollingEnabled === false && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-warning/10 px-3 py-1 text-xs font-bold text-warning">
                  Auto Refresh Off
                </span>
              )}
            </div>
            <p className="text-sm text-base-content/50">
              Pantau aktivitas pengunjung secara real-time
            </p>
          </div>

          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              outline
              size="sm"
              isSubmit={false}
              loading={loading}
              onClick={reload}
            >
              Muat Ulang
            </Button>
            {lastUpdatedAt && (
              <div className="flex items-center gap-2 text-xs text-base-content/50 bg-base-200/50 px-3 py-1.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse"></span>
                Update terakhir{" "}
                {lastUpdatedAt.toLocaleTimeString("id-ID", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            )}
            {activeCameras > 0 && (
              <div className="flex items-center gap-2 text-xs text-base-content/50 bg-base-200/50 px-3 py-1.5 rounded-full">
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
                {activeCameras} Kamera Aktif
              </div>
            )}
          </div>
        </div>

        <DateFilter
          periodType={periodType}
          setPeriodType={setPeriodType}
          selectedDay={selectedDay}
          setSelectedDay={setSelectedDay}
          fromTime={fromTime}
          handleFromTimeChange={handleFromTimeChange}
          toTime={toTime}
          handleToTimeChange={handleToTimeChange}
          fromMonth={fromMonth}
          handleFromMonthChange={handleFromMonthChange}
          toMonth={toMonth}
          handleToMonthChange={handleToMonthChange}
          fromYear={fromYear}
          handleFromYearChange={handleFromYearChange}
          toYear={toYear}
          handleToYearChange={handleToYearChange}
          appliedSummaryLabel={appliedSummaryLabel}
          applyPeriod={applyPeriod}
          loading={loading}
          today={today}
        />

        {showDevResetTools && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3">
            <span className="inline-flex items-center rounded-full bg-warning/20 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.2em] text-warning">
              Dev Only
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-base-content">
                Reset harian dashboard
              </p>
              <p className="text-xs text-base-content/60">
                {resetTargetDay
                  ? `Hapus data visitor untuk ${resetTargetDay}.`
                  : "Pilih tepat satu hari agar reset harian bisa dijalankan."}
              </p>
            </div>
            <Button
              variant="warning"
              size="sm"
              outline
              isSubmit={false}
              loading={isResettingDaily}
              disabled={!resetTargetDay}
              onClick={handleResetDaily}
              className="ml-auto"
            >
              Reset Harian
            </Button>
          </div>
        )}
      </div>

      {error && <Alert variant="error">{error}</Alert>}

     
      {/* ===== KPI CARDS ===== */}
      <StatsGrid
        totalEvents={totalEvents}
        totalIn={totalIn}
        totalOut={totalOut}
        currentInside={currentInside}
        changePercents={changePercents}
        hiddenKeys={isCurrentDayView ? ["totalEvents"] : ["totalEvents", "currentInside"]}
      />

    
    

      {/* ===== CHARTS ROW 2: Doughnut + Camera (2 column) ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="!shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-base-content/80 flex items-center gap-2">
              <span className="w-1 h-5 bg-primary rounded-full"></span>
              {isSingleDayView ? "Tren Pengunjung per Jam" : "Tren Aktivitas per Hari"}
            </h3>
            {isLivePeriod && (
              <span className="text-[10px] px-2 py-0.5 bg-primary/10 text-primary rounded-full font-bold">
                LIVE
              </span>
            )}
          </div>
          <LineChart
            labels={chartLineLabels}
            data={chartLineData}
            label="Total Aktivitas"
            color="#6366f1"
          />
        </Card>

        <div className="">
          <CameraView />
        </div>
      </div>

      {/* ===== CHARTS ROW 1: Line + Bar (2 column) ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="!shadow-lg">
          <h3 className="font-bold text-base-content/80 mb-4 flex items-center gap-2">
            <span className="w-1 h-5 bg-info rounded-full"></span>
            Distribusi Masuk / Keluar
          </h3>
          <InOutDoughnutChart totalIn={totalIn} totalOut={totalOut} />
        </Card>
        <Card className="!shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-base-content/80 flex items-center gap-2">
              <span className="w-1 h-5 bg-success rounded-full"></span>
              Perbandingan Masuk dan Keluar
            </h3>
          </div>
          <StackedBarChart
            labels={barChartLabels}
            dataIn={barIn}
            dataOut={barOut}
          />
        </Card>
      </div>

      {/* ===== CHARTS ROW 3: Area + Radar (2 column) ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <Card className="!shadow-lg col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-base-content/80 flex items-center gap-2">
              <span className="w-1 h-5 bg-success rounded-full"></span>
              Overlay Masuk vs Keluar
            </h3>
          </div>
          <AreaChart labels={barChartLabels} dataIn={barIn} dataOut={barOut} />
        </Card>

        <Card className="!shadow-lg col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-base-content/80 flex items-center gap-2">
              <span className="w-1 h-5 bg-accent rounded-full"></span>
              Ranking Aktivitas Harian
            </h3>
          </div>
          {hBarData.labels.length > 0 ? (
            <HorizontalBarChart
              labels={hBarData.labels}
              data={hBarData.data}
              label="Total Aktivitas"
            />
          ) : (
            <div className="flex items-center justify-center h-48 text-base-content/40 text-sm">
              Belum ada data
            </div>
          )}
        </Card>

        <Card className="!shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-base-content/80 flex items-center gap-2">
              <span className="w-1 h-5 bg-secondary rounded-full"></span>
              Pola Aktivitas per Jam
            </h3>
          </div>
          {radarData.labels.length > 0 ? (
            <RadarChart
              labels={radarData.labels}
              dataIn={radarData.dataIn}
              dataOut={radarData.dataOut}
            />
          ) : (
            <div className="flex items-center justify-center h-48 text-base-content/40 text-sm">
              Belum ada data
            </div>
          )}
        </Card>
      </div>

      {/* ===== STATS TABLE ===== */}
      <StatsTable daily={daily} />

      {/* ===== EXPORT ===== */}
      <ExportSection
        filterFrom={filterFrom}
        filterTo={filterTo}
        filterFromDateTime={filterFromDateTime}
        filterToDateTime={filterToDateTime}
        day={day}
        totalEvents={totalEvents}
        totalIn={totalIn}
        totalOut={totalOut}
        insights={insights}
      />
    </div>
  );
}
