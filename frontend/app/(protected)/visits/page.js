"use client";

import { useState, useCallback, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { fetchEvents, fetchVisitorDaily } from "@/services/stats.service";
import { todayISO } from "@/lib/utils";
import Table from "@/components/ui/Table";
import Section from "@/components/ui/Section";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import Input from "@/components/ui/Input";
import StatsGrid from "@/components/dashboard/StatsGrid";

export default function VisitsPage() {
  const { user } = useAuth();
  const today = todayISO();

  const [fromDate, setFromDate] = useState(today);
  const [toDate, setToDate] = useState(today);
  const [events, setEvents] = useState([]);
  const [visitors, setVisitors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("events"); // "events" | "visitors"

  // Only admin can access this page
  if (user?.role !== "ADMIN") {
    return (
      <>
        <Heading level={1}>Data Kunjungan</Heading>
        <Alert type="error">
          Hanya Admin yang bisa mengakses halaman ini.
        </Alert>
      </>
    );
  }

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [eventsData, visitorsData] = await Promise.all([
        fetchEvents(fromDate, toDate).catch(() => []),
        fetchVisitorDaily(fromDate, toDate).catch(() => []),
      ]);
      setEvents(eventsData);
      setVisitors(visitorsData);
    } catch (e) {
      setError(e.message || "Gagal memuat data");
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate]);

  useEffect(() => {
    load();
  }, [load]);

  const eventColumns = [
    "ID",
    "Camera",
    "Area",
    "Waktu",
    "Track ID",
    "Visitor Key",
    "Tipe",
    "Pegawai",
    "Arah",
    "Match Score",
    "Confidence",
  ];
  const eventRows = events.map((e) => [
    e.event_id,
    e.camera_id,
    e.area_id,
    new Date(e.event_time).toLocaleString("id-ID"),
    e.track_id || "-",
    <span key="vk" className="font-mono text-xs">
      {e.visitor_key?.substring(0, 16)}...
    </span>,
    <span
      key="type"
      className={`badge badge-sm ${e.person_type === "EMPLOYEE" ? "badge-warning" : "badge-success"}`}
    >
      {e.person_type || "CUSTOMER"}
    </span>,
    e.employee_name || (e.employee_id ? `Pegawai #${e.employee_id}` : "-"),
    <span
      key="d"
      className={`badge badge-sm ${e.direction === "IN" ? "badge-success" : e.direction === "OUT" ? "badge-error" : "badge-ghost"}`}
    >
      {e.direction || "-"}
    </span>,
    e.face_match_score != null ? `${(e.face_match_score * 100).toFixed(1)}%` : "-",
    e.confidence_avg ? (e.confidence_avg * 100).toFixed(1) + "%" : "-",
  ]);

  const visitorColumns = [
    "ID",
    "Tanggal",
    "Visitor Key",
    "Pertama Terlihat",
    "Terakhir Terlihat",
    "Catatan",
  ];
  const visitorRows = visitors.map((v) => [
    v.visitor_daily_id,
    v.visit_date,
    <span key="vk" className="font-mono text-xs">
      {v.visitor_key?.substring(0, 16)}...
    </span>,
    new Date(v.first_seen_at).toLocaleString("id-ID"),
    new Date(v.last_seen_at).toLocaleString("id-ID"),
    v.notes || "-",
  ]);

  // Calculate stats for StatsGrid
  const day = fromDate === toDate ? fromDate : `${fromDate} s/d ${toDate}`;
  const customerEvents = events.filter((e) => e.person_type !== "EMPLOYEE");
  const ignoredEmployeeEvents = events.filter((e) => e.person_type === "EMPLOYEE").length;
  const totalEvents = customerEvents.length;
  const uniqueVisitors = visitors.length;
  const totalIn = customerEvents.filter((e) => e.direction === "IN").length;
  const totalOut = customerEvents.filter((e) => e.direction === "OUT").length;

  return (
    <>
      <h1>Data Kunjungan</h1>
      <p className="text-sm opacity-70">
        Lihat dan kelola data event kunjungan dan pengunjung unik harian.
      </p>

      {error && <Alert type="error">{error}</Alert>}
      {ignoredEmployeeEvents > 0 && (
        <Alert type="info" className="mt-3">
          Event pegawai terdeteksi: {ignoredEmployeeEvents}. Event ini tetap tampil di log, tetapi tidak masuk ke hitungan pelanggan.
        </Alert>
      )}

      {/* Date filter */}
      <Section title="Filter Periode">
        <div className="flex flex-wrap items-end gap-3">
          <Input
            label="Dari"
            type="date"
            value={fromDate}
            max={toDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="input-sm w-40"
          />
          <Input
            label="Sampai"
            type="date"
            value={toDate}
            min={fromDate}
            max={today}
            onChange={(e) => setToDate(e.target.value)}
            className="input-sm w-40"
          />
          <Button
            variant="primary"
            loading={loading}
            onClick={load}
            className="btn-sm"
          >
            Muat Data
          </Button>
        </div>
      </Section>

      {/* Summary cards */}
      <StatsGrid
        day={day}
        totalEvents={totalEvents}
        uniqueVisitors={uniqueVisitors}
        totalIn={totalIn}
        totalOut={totalOut}
      />

      {/* Tab switch */}
      <div className="tabs tabs-boxed mt-6 w-fit">
        <button
          className={`tab ${tab === "events" ? "tab-active" : ""}`}
          onClick={() => setTab("events")}
        >
          Event Kunjungan ({events.length})
        </button>
        <button
          className={`tab ${tab === "visitors" ? "tab-active" : ""}`}
          onClick={() => setTab("visitors")}
        >
          Pengunjung Unik ({visitors.length})
        </button>
      </div>

      {/* Tables */}
      {tab === "events" && (
        <Section title={`Event Kunjungan (${fromDate} s/d ${toDate})`}>
          <Table
            columns={eventColumns}
            rows={eventRows}
            emptyText="Belum ada event kunjungan pada periode ini."
          />
        </Section>
      )}

      {tab === "visitors" && (
        <Section title={`Pengunjung Unik Harian (${fromDate} s/d ${toDate})`}>
          <Table
            columns={visitorColumns}
            rows={visitorRows}
            emptyText="Belum ada data pengunjung unik pada periode ini."
          />
        </Section>
      )}
    </>
  );
}
