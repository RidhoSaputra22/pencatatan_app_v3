"use client";

import { useState, useCallback, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { fetchEvents, fetchVisitorDaily } from "@/services/stats.service";
import { formatNumber, todayISO } from "@/lib/utils";
import Table from "@/components/ui/Table";
import Section from "@/components/ui/Section";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Stat from "@/components/ui/Stat";
import Paragraph from "@/components/ui/Paragraph";
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
  const [eventSearch, setEventSearch] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState("ALL");
  const [eventDirectionFilter, setEventDirectionFilter] = useState("ALL");
  const [eventCameraFilter, setEventCameraFilter] = useState("ALL");
  const [visitorSearch, setVisitorSearch] = useState("");
  const [visitorNotesFilter, setVisitorNotesFilter] = useState("ALL");
  const [visitorDateFilter, setVisitorDateFilter] = useState("ALL");

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

  const eventCameraOptions = [
    { value: "ALL", label: "Semua Kamera" },
    ...Array.from(new Set(events.map((event) => String(event.camera_id))))
      .sort((a, b) => Number(a) - Number(b))
      .map((cameraId) => ({
        value: cameraId,
        label: `Camera ${cameraId}`,
      })),
  ];
  const eventTypeOptions = [
    { value: "ALL", label: "Semua Tipe" },
    { value: "CUSTOMER", label: "Pelanggan" },
    { value: "EMPLOYEE", label: "Pegawai" },
  ];
  const eventDirectionOptions = [
    { value: "ALL", label: "Semua Arah" },
    { value: "IN", label: "Masuk" },
    { value: "OUT", label: "Keluar" },
    { value: "UNKNOWN", label: "Tanpa Arah" },
  ];

  const normalizedEventSearch = eventSearch.trim().toLowerCase();
  const filteredEvents = events.filter((event) => {
    const matchesSearch =
      !normalizedEventSearch ||
      String(event.event_id).toLowerCase().includes(normalizedEventSearch) ||
      String(event.camera_id).toLowerCase().includes(normalizedEventSearch) ||
      String(event.area_id).toLowerCase().includes(normalizedEventSearch) ||
      String(event.track_id || "").toLowerCase().includes(normalizedEventSearch) ||
      String(event.employee_name || "").toLowerCase().includes(normalizedEventSearch) ||
      String(event.employee_id || "").toLowerCase().includes(normalizedEventSearch) ||
      String(event.visitor_key || "").toLowerCase().includes(normalizedEventSearch);

    const personType = event.person_type || "CUSTOMER";
    const matchesType =
      eventTypeFilter === "ALL" || personType === eventTypeFilter;

    const eventDirection = event.direction || "UNKNOWN";
    const matchesDirection =
      eventDirectionFilter === "ALL" ||
      eventDirection === eventDirectionFilter;

    const matchesCamera =
      eventCameraFilter === "ALL" ||
      String(event.camera_id) === eventCameraFilter;

    return matchesSearch && matchesType && matchesDirection && matchesCamera;
  });

  const eventRows = filteredEvents.map((e) => [
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

  const visitorDateOptions = [
    { value: "ALL", label: "Semua Tanggal" },
    ...Array.from(new Set(visitors.map((visitor) => String(visitor.visit_date))))
      .sort()
      .map((visitDate) => ({
        value: visitDate,
        label: visitDate,
      })),
  ];
  const visitorNotesOptions = [
    { value: "ALL", label: "Semua Catatan" },
    { value: "WITH_NOTES", label: "Ada Catatan" },
    { value: "WITHOUT_NOTES", label: "Tanpa Catatan" },
  ];

  const normalizedVisitorSearch = visitorSearch.trim().toLowerCase();
  const filteredVisitors = visitors.filter((visitor) => {
    const matchesSearch =
      !normalizedVisitorSearch ||
      String(visitor.visitor_daily_id).toLowerCase().includes(normalizedVisitorSearch) ||
      String(visitor.visitor_key || "").toLowerCase().includes(normalizedVisitorSearch) ||
      String(visitor.notes || "").toLowerCase().includes(normalizedVisitorSearch);

    const hasNotes = Boolean(visitor.notes?.trim());
    const matchesNotes =
      visitorNotesFilter === "ALL" ||
      (visitorNotesFilter === "WITH_NOTES" && hasNotes) ||
      (visitorNotesFilter === "WITHOUT_NOTES" && !hasNotes);

    const matchesVisitDate =
      visitorDateFilter === "ALL" ||
      String(visitor.visit_date) === visitorDateFilter;

    return matchesSearch && matchesNotes && matchesVisitDate;
  });

  const visitorRows = filteredVisitors.map((v) => [
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
  const filteredEventEmployees = filteredEvents.filter(
    (event) => event.person_type === "EMPLOYEE",
  ).length;
  const filteredEventIn = filteredEvents.filter(
    (event) => event.direction === "IN",
  ).length;
  const filteredEventOut = filteredEvents.filter(
    (event) => event.direction === "OUT",
  ).length;
  const filteredVisitorsWithNotes = filteredVisitors.filter(
    (visitor) => visitor.notes?.trim(),
  ).length;
  const filteredVisitorDays = new Set(
    filteredVisitors.map((visitor) => visitor.visit_date),
  ).size;
  const averageVisitMinutes = filteredVisitors.length
    ? filteredVisitors.reduce((sum, visitor) => {
        const durationMs =
          new Date(visitor.last_seen_at).getTime() -
          new Date(visitor.first_seen_at).getTime();
        return sum + Math.max(durationMs, 0);
      }, 0) /
        filteredVisitors.length /
        60000
    : 0;

  function resetEventFilters() {
    setEventSearch("");
    setEventTypeFilter("ALL");
    setEventDirectionFilter("ALL");
    setEventCameraFilter("ALL");
  }

  function resetVisitorFilters() {
    setVisitorSearch("");
    setVisitorNotesFilter("ALL");
    setVisitorDateFilter("ALL");
  }

  return (
    <div className="space-y-6">
      <div>
        <Heading level={1}>Data Kunjungan</Heading>
        <Paragraph>
          Lihat dan kelola data event kunjungan dan pengunjung unik harian.
        </Paragraph>
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {ignoredEmployeeEvents > 0 && (
        <Alert type="info" className="mt-3">
          Event pegawai terdeteksi: {ignoredEmployeeEvents}. Event ini tetap tampil di log, tetapi tidak masuk ke hitungan pelanggan.
        </Alert>
      )}

      {/* Date filter */}
      <Section title="Filter Periode">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,220px)_minmax(0,220px)_auto] md:items-end">
          <Input
            label="Dari"
            type="date"
            value={fromDate}
            max={toDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="input-sm"
          />
          <Input
            label="Sampai"
            type="date"
            value={toDate}
            min={fromDate}
            max={today}
            onChange={(e) => setToDate(e.target.value)}
            className="input-sm"
          />
          <div className="flex items-end">
            <Button
              variant="primary"
              loading={loading}
              onClick={load}
              className="btn-sm w-full md:w-fit"
            >
              Muat Data
            </Button>
          </div>
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
          

          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
            <Input
              label="Cari Event"
              value={eventSearch}
              onChange={(e) => setEventSearch(e.target.value)}
              placeholder="ID, visitor key, pegawai, kamera"
            />
            <Select
              label="Tipe Orang"
              options={eventTypeOptions}
              value={eventTypeFilter}
              onChange={(e) => setEventTypeFilter(e.target.value)}
            />
            <Select
              label="Arah"
              options={eventDirectionOptions}
              value={eventDirectionFilter}
              onChange={(e) => setEventDirectionFilter(e.target.value)}
            />
            <Select
              label="Kamera"
              options={eventCameraOptions}
              value={eventCameraFilter}
              onChange={(e) => setEventCameraFilter(e.target.value)}
            />
            <div className="flex items-end">
              <Button
                variant="neutral"
                outline
                isSubmit={false}
                onClick={resetEventFilters}
                className="w-full xl:w-fit"
              >
                Reset Filter
              </Button>
            </div>
          </div>

          <div className="mt-4">
            <Table
              columns={eventColumns}
              rows={eventRows}
              emptyText="Belum ada event kunjungan pada periode ini."
            />
          </div>
        </Section>
      )}

      {tab === "visitors" && (
        <Section title={`Pengunjung Unik Harian (${fromDate} s/d ${toDate})`}>
         

          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Input
              label="Cari Visitor"
              value={visitorSearch}
              onChange={(e) => setVisitorSearch(e.target.value)}
              placeholder="Visitor key atau catatan"
            />
            <Select
              label="Catatan"
              options={visitorNotesOptions}
              value={visitorNotesFilter}
              onChange={(e) => setVisitorNotesFilter(e.target.value)}
            />
            <Select
              label="Tanggal"
              options={visitorDateOptions}
              value={visitorDateFilter}
              onChange={(e) => setVisitorDateFilter(e.target.value)}
            />
            <div className="flex items-end">
              <Button
                variant="neutral"
                outline
                isSubmit={false}
                onClick={resetVisitorFilters}
                className="w-full xl:w-fit"
              >
                Reset Filter
              </Button>
            </div>
          </div>

          <div className="mt-4">
            <Table
              columns={visitorColumns}
              rows={visitorRows}
              emptyText="Belum ada data pengunjung unik pada periode ini."
            />
          </div>
        </Section>
      )}
    </div>
  );
}
