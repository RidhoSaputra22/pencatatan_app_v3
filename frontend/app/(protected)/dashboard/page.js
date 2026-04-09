"use client";

import { useAuth } from "@/context/AuthContext";
import { useStats } from "@/hooks/useStats";

import DateFilter from "@/components/dashboard/DateFilter";
import StatsGrid from "@/components/dashboard/StatsGrid";
import InsightsPanel from "@/components/dashboard/InsightsPanel";
import { LineChart, StackedBarChart, InOutDoughnutChart, AreaChart, HorizontalBarChart, RadarChart, PolarAreaChart } from "@/components/dashboard/Charts";
import CameraView from "@/components/dashboard/CameraView";
import StatsTable from "@/components/dashboard/StatsTable";
import ExportSection from "@/components/dashboard/ExportSection";
import Alert from "@/components/ui/Alert";
import Card from "@/components/ui/Card";
import { formatNumber } from "@/lib/utils";
import CountUp from "react-countup";
import { useMemo } from "react";

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
    ? daily.map((r) => r.total_in)
    : rangeIn;
  const barOut = isToday
    ? daily.map((r) => r.total_out)
    : rangeOut;
  const barChartLabels = isToday && daily.length > 0
    ? daily.map((r) => r.camera_id ? `Cam ${r.camera_id}` : r.stat_date || "-")
    : barLabels;

  // Active cameras count
  const activeCameras = new Set(daily.map((r) => r.camera_id).filter(Boolean)).size;

  // ---- Computed data for new charts ----

  // Time segment distribution (Pagi/Siang/Sore/Malam) for PolarArea
  const timeSegments = useMemo(() => {
    const segments = { "Pagi (06-11)": 0, "Siang (11-14)": 0, "Sore (14-18)": 0, "Malam (18-06)": 0 };
    if (hourlyData && hourlyData.labels) {
      hourlyData.labels.forEach((label, i) => {
        const h = parseInt(label.slice(0, 2), 10);
        const v = hourlyData.data[i] || 0;
        if (h >= 6 && h < 11) segments["Pagi (06-11)"] += v;
        else if (h >= 11 && h < 14) segments["Siang (11-14)"] += v;
        else if (h >= 14 && h < 18) segments["Sore (14-18)"] += v;
        else segments["Malam (18-06)"] += v;
      });
    }
    return { labels: Object.keys(segments), data: Object.values(segments) };
  }, [hourlyData]);

  // Radar chart: hourly pattern for in vs out (use hourly buckets)
  // Since we only have total per hour from perSecond, approximate 50/50 for radar demo
  // or use daily in/out ratios
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
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-success/10 text-success text-xs font-bold">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
                </span>
                Live
              </span>
            </div>
            <p className="text-sm text-base-content/50">
              Pantau aktivitas pengunjung secara real-time
            </p>
          </div>

          <div className="flex items-center gap-4">
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

      {/* ===== HERO SUMMARY BAR ===== */}
      <div className="card bg-gradient-to-r from-primary/5 via-base-100 to-info/5 shadow-lg border border-base-200/60 p-5">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-primary/10">
              <svg
                className="w-8 h-8 text-primary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.5"
                  d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
                />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-base-content/50">
                Total aktivitas hari ini
              </p>
              <p className="text-3xl font-extrabold text-base-content tracking-tight">
                <CountUp
                  end={totalEvents}
                  duration={1.5}
                  separator="."
                  preserveValue
                />
              </p>
            </div>
          </div>
          <div className="hidden sm:block h-12 w-px bg-base-300/50"></div>
          <div className="flex gap-8">
            <div className="text-center">
              <div className="flex items-center gap-1.5 text-success mb-1">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4.5 10.5 12 3m0 0 7.5 7.5M12 3v18"
                  />
                </svg>
                <span className="text-2xl font-bold">
                  <CountUp
                    end={totalIn}
                    duration={1.2}
                    separator="."
                    preserveValue
                  />
                </span>
              </div>
              <p className="text-xs text-base-content/40">Masuk</p>
            </div>
            <div className="text-center">
              <div className="flex items-center gap-1.5 text-error mb-1">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M19.5 13.5 12 21m0 0-7.5-7.5M12 21V3"
                  />
                </svg>
                <span className="text-2xl font-bold">
                  <CountUp
                    end={totalOut}
                    duration={1.2}
                    separator="."
                    preserveValue
                  />
                </span>
              </div>
              <p className="text-xs text-base-content/40">Keluar</p>
            </div>
            <div className="text-center">
              <div className="flex items-center gap-1.5 text-info mb-1">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <span className="text-2xl font-bold">
                  <CountUp
                    end={uniqueVisitors}
                    duration={1.2}
                    separator="."
                    preserveValue
                  />
                </span>
              </div>
              <p className="text-xs text-base-content/40">Unik</p>
            </div>
          </div>
        </div>
      </div>

      {/* ===== KPI CARDS ===== */}
      <StatsGrid
        totalEvents={totalEvents}
        uniqueVisitors={uniqueVisitors}
        totalIn={totalIn}
        totalOut={totalOut}
        changePercents={changePercents}
      />

      {/* ===== INSIGHTS ===== */}
      <InsightsPanel
        insights={insights}
        totalEvents={totalEvents}
        uniqueVisitors={uniqueVisitors}
      />

      {/* ===== CHARTS ROW 2: Doughnut + Camera (2 column) ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="!shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-base-content/80 flex items-center gap-2">
              <span className="w-1 h-5 bg-primary rounded-full"></span>
              {isToday ? "Tren Pengunjung per Jam" : "Tren Aktivitas per Hari"}
            </h3>
            {isToday && (
              <span className="text-[10px] px-2 py-0.5 bg-primary/10 text-primary rounded-full font-bold">
                LIVE
              </span>
            )}
          </div>
          <LineChart
            labels={chartLineLabels}
            data={chartLineData}
            label="Total Aktivitas"
            pollingInterval={isToday ? 5000 : undefined}
            day={isToday ? today : undefined}
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
      <ExportSection filterFrom={filterFrom} filterTo={filterTo} day={day} />
    </div>
  );
}
