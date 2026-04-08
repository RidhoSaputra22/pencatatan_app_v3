"use client";

import { useState } from "react";
import { formatNumber } from "@/lib/utils";
import Table from "@/components/ui/Table";
import Section from "@/components/ui/Section";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Stat from "@/components/ui/Stat";

/**
 * Per-camera daily stats table.
 */
export default function StatsTable({ daily = [] }) {
  const [search, setSearch] = useState("");
  const [cameraFilter, setCameraFilter] = useState("ALL");
  const [activityFilter, setActivityFilter] = useState("ALL");

  const normalizedSearch = search.trim().toLowerCase();
  const cameraOptions = [
    { value: "ALL", label: "Semua Kamera" },
    ...Array.from(new Set(daily.map((row) => String(row.camera_id))))
      .sort((a, b) => Number(a) - Number(b))
      .map((cameraId) => ({
        value: cameraId,
        label: `Camera ${cameraId}`,
      })),
  ];

  const activityOptions = [
    { value: "ALL", label: "Semua Aktivitas" },
    { value: "WITH_VISITS", label: "Ada Pengunjung" },
    { value: "ACTIVE_ONLY", label: "Ada Aktivitas" },
    { value: "EMPTY", label: "Tanpa Aktivitas" },
  ];

  const filteredDaily = daily.filter((row) => {
    const matchesSearch =
      !normalizedSearch ||
      String(row.stat_date).toLowerCase().includes(normalizedSearch) ||
      String(row.camera_id).toLowerCase().includes(normalizedSearch);

    const matchesCamera =
      cameraFilter === "ALL" || String(row.camera_id) === cameraFilter;

    const matchesActivity =
      activityFilter === "ALL" ||
      (activityFilter === "WITH_VISITS" && Number(row.unique_visitors) > 0) ||
      (activityFilter === "ACTIVE_ONLY" && Number(row.total_events) > 0) ||
      (activityFilter === "EMPTY" && Number(row.total_events) === 0);

    return matchesSearch && matchesCamera && matchesActivity;
  });

  const totalEvents = filteredDaily.reduce(
    (sum, row) => sum + Number(row.total_events || 0),
    0,
  );
  const totalVisitors = filteredDaily.reduce(
    (sum, row) => sum + Number(row.unique_visitors || 0),
    0,
  );
  const totalIn = filteredDaily.reduce(
    (sum, row) => sum + Number(row.total_in || 0),
    0,
  );
  const totalOut = filteredDaily.reduce(
    (sum, row) => sum + Number(row.total_out || 0),
    0,
  );

  function resetFilters() {
    setSearch("");
    setCameraFilter("ALL");
    setActivityFilter("ALL");
  }

  const columns = [
    "Tanggal",
    "Camera ID",
    "Total Aktivitas",
    "Pengunjung Unik",
    "Pengunjung Masuk",
    "Pengunjung Keluar",
  ];

  const rows = filteredDaily.map((r) => [
    r.stat_date,
    r.camera_id,
    r.total_events,
    <strong key="u">{r.unique_visitors}</strong>,
    r.total_in,
    r.total_out,
  ]);

  return (
    <Section title="Statistik per Kamera">
      <p className="text-sm opacity-70 mb-3">
        Data diperbarui otomatis setiap 5 detik.
      </p>

      
      <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Input
          label="Cari Data"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Tanggal atau ID kamera"
        />
        <Select
          label="Kamera"
          options={cameraOptions}
          value={cameraFilter}
          onChange={(e) => setCameraFilter(e.target.value)}
        />
        <Select
          label="Aktivitas"
          options={activityOptions}
          value={activityFilter}
          onChange={(e) => setActivityFilter(e.target.value)}
        />
        <div className="flex items-end">
          <Button
            variant="ghost"
            isSubmit={false}
            onClick={resetFilters}
            className="w-fit"
          >
            Reset Filter
          </Button>
        </div>
      </div>

      <div className="mt-4 w-80 lg:w-full overflow-x-auto">
        <Table
          columns={columns}
          rows={rows}
          emptyText="Belum ada data. Jalankan edge worker (mode FAKE atau REAL)."
        />
      </div>
    </Section>
  );
}
