"use client";

import { useAuth } from "@/context/AuthContext";
import { useStats } from "@/hooks/useStats";

import DateFilter from "@/components/dashboard/DateFilter";
import StatsGrid from "@/components/dashboard/StatsGrid";
import InsightsPanel from "@/components/dashboard/InsightsPanel";
import { LineChart, StackedBarChart } from "@/components/dashboard/Charts";
import CameraView from "@/components/dashboard/CameraView";
import StatsTable from "@/components/dashboard/StatsTable";
import ExportSection from "@/components/dashboard/ExportSection";
import Alert from "@/components/ui/Alert";
import Card from "@/components/ui/Card";

export default function DashboardPage() {
  const { user } = useAuth();
  const {
    day,
    today,
    daily,
    perSecond,
    hourlyData,
    totalEvents,
    uniqueVisitors,
    totalIn,
    totalOut,
    changePercents,
    insights,
    lastUpdatedAt,
    error,
    reload,
    filterMode,
    setFilterMode,
    filterFrom,
    setFilterFrom,
    filterTo,
    setFilterTo,
  } = useStats();

  // Chart data for range modes
  const rangeLabels = daily.map((r) => r.stat_date || r.date || "-");
  const rangeIn = daily.map((r) => r.total_in);
  const rangeOut = daily.map((r) => r.total_out);

  // Decide which data to use for charts
  const isToday = filterMode === "today";
  const chartLineLabels = isToday ? hourlyData.labels : rangeLabels;
  const chartLineData = isToday
    ? hourlyData.data
    : daily.map((r) => r.total_events);
  const barLabels = isToday ? hourlyData.labels : rangeLabels;
  const barIn = isToday
    ? (() => {
        // aggregate perSecond into hourly for in/out (not available per-second, use daily)
        // For today mode, use hourlyData for total, but in/out from daily
        return daily.map((r) => r.total_in);
      })()
    : rangeIn;
  const barOut = isToday
    ? daily.map((r) => r.total_out)
    : rangeOut;
  // For today single-day bar chart, use daily data labels if available
  const barChartLabels = isToday && daily.length > 0
    ? daily.map((r) => r.camera_id ? `Cam ${r.camera_id}` : r.stat_date || "-")
    : barLabels;

  return (
    <div className="space-y-8">
      {/* ===== HEADER: Title + Live Status + Last Update + Date Filter ===== */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-base-content">
              Dashboard Monitoring
            </h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-success/10 text-success text-xs font-semibold">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
              </span>
              Live
            </span>
          </div>
          {lastUpdatedAt && (
            <span className="text-xs text-base-content/40">
              Terakhir diperbarui:{" "}
              {lastUpdatedAt.toLocaleTimeString("id-ID", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
          )}
        </div>

        {/* Date filter pills */}
        <DateFilter
          filterMode={filterMode}
          setFilterMode={setFilterMode}
          filterFrom={filterFrom}
          setFilterFrom={setFilterFrom}
          filterTo={filterTo}
          setFilterTo={setFilterTo}
          today={today}
        />
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {/* ===== KPI CARDS ===== */}
      <StatsGrid
        totalEvents={totalEvents}
        uniqueVisitors={uniqueVisitors}
        totalIn={totalIn}
        totalOut={totalOut}
        changePercents={changePercents}
      />

      {/* ===== INSIGHTS ===== */}
      <InsightsPanel insights={insights} />

      {/* ===== CHARTS: 2 columns ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <Card>
          <h3 className="font-semibold mb-4 text-base-content/80">
            {isToday ? "Tren Pengunjung per Jam" : "Tren Aktivitas per Hari"}
          </h3>
          <LineChart
            labels={chartLineLabels}
            data={chartLineData}
            label="Total Aktivitas"
            pollingInterval={isToday ? 5000 : undefined}
            day={isToday ? today : undefined}
            color="#6366f1"
          />
        </Card>

        <Card>
          <h3 className="font-semibold mb-4 text-base-content/80">
            Perbandingan Masuk vs Keluar
          </h3>
          <StackedBarChart
            labels={barChartLabels}
            dataIn={barIn}
            dataOut={barOut}
          />
        </Card>
      </div>

      {/* ===== STATS TABLE ===== */}
      <StatsTable daily={daily} />

      {/* ===== LIVE CAMERA (compact, below) ===== */}
      <CameraView />

      {/* ===== EXPORT ===== */}
      <ExportSection filterFrom={filterFrom} filterTo={filterTo} day={day} />
    </div>
  );
}
