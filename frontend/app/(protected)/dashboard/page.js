"use client";

import { useAuth } from "@/context/AuthContext";
import { useStats } from "@/hooks/useStats";
import { useEffect, useState } from "react";
import { fetchStatsPerSecond } from "@/services/stats.service";

import DateFilter from "@/components/dashboard/DateFilter";
import StatsGrid from "@/components/dashboard/StatsGrid";
import { LineChart, DoughnutChart } from "@/components/dashboard/Charts";
import CameraView from "@/components/dashboard/CameraView";
import StatsTable from "@/components/dashboard/StatsTable";
import ExportSection from "@/components/dashboard/ExportSection";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import Card from "@/components/ui/Card";
import Section from "@/components/ui/Section";

export default function DashboardPage() {
  const { user } = useAuth();
  const {
    day,
    today,
    daily,
    totalEvents,
    uniqueVisitors,
    totalIn,
    totalOut,
    error,
    reload,
    filterMode,
    setFilterMode,
    filterFrom,
    setFilterFrom,
    filterTo,
    setFilterTo,
  } = useStats();

  // State untuk data per second (granular)
  const [perSecond, setPerSecond] = useState([]);
  useEffect(() => {
    if (filterMode === "today") {
      fetchStatsPerSecond(today)
        .then(setPerSecond)
        .catch(() => setPerSecond([]));
    } else {
      setPerSecond([]);
    }
  }, [today, filterMode]);

  // Chart data: jika hari ini, pakai perSecond, jika range pakai daily
  const chartLabels =
    filterMode === "today"
      ? perSecond.map((r) => r.second.slice(11, 19)) // HH:MM:SS
      : daily.map((r) => r.stat_date || r.date || "-");
  const chartTotalEvents =
    filterMode === "today"
      ? perSecond.map((r) => r.count)
      : daily.map((r) => r.total_events);
  const chartUnique = daily.map((r) => r.unique_visitors);
  const chartIn = daily.map((r) => r.total_in);
  const chartOut = daily.map((r) => r.total_out);

  return (
    <>
      <Heading level={1} className="mb-4">
        Dashboard Monitoring Pengunjung
      </Heading>
      {error && <Alert variant="error">{error}</Alert>}

      {/* Date filter for period selection */}
      <DateFilter
        filterMode={filterMode}
        setFilterMode={setFilterMode}
        filterFrom={filterFrom}
        setFilterFrom={setFilterFrom}
        filterTo={filterTo}
        setFilterTo={setFilterTo}
        today={today}
      />

      <StatsGrid
        day={day}
        totalEvents={totalEvents}
        uniqueVisitors={uniqueVisitors}
        totalIn={totalIn}
        totalOut={totalOut}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 ">
        <div className="col-span-2 min-h-full">
          <CameraView />
        </div>
        <div className="p-0 py-6 lg:p-6">
          <Card>
            <h3 className="font-semibold mb-2">Distribusi Masuk vs Keluar</h3>
            <DoughnutChart
              labels={["Masuk", "Keluar"]}
              data={[totalIn, totalOut]}
              label="Distribusi"
            />
          </Card>
        </div>
      </div>

      {/* Chart Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 my-6">
        <Card>
          <h3 className="font-semibold mb-2">
            Tren Total Event per Hari / Realtime
          </h3>
          <LineChart
            labels={chartLabels}
            data={chartTotalEvents}
            label="Total Event"
            pollingInterval={filterMode === "today" ? 2000 : undefined}
            day={filterMode === "today" ? today : undefined}
          />
        </Card>

        <Card>
          <h3 className="font-semibold mb-2">Tren Pengunjung Unik</h3>
          <LineChart
            labels={chartLabels}
            data={chartUnique}
            label="Pengunjung Unik"
          />
        </Card>
        <Card className="">
          <h3 className="font-semibold mb-2">Tren Masuk</h3>
          <LineChart labels={chartLabels} data={chartIn} label="Masuk" />
        </Card>
        <Card className="">
          <h3 className="font-semibold mb-2">Tren Keluar</h3>
          <LineChart labels={chartLabels} data={chartOut} label="Keluar" />
        </Card>
      </div>

      <StatsTable daily={daily} />

      <ExportSection filterFrom={filterFrom} filterTo={filterTo} day={day} />
    </>
  );
}
