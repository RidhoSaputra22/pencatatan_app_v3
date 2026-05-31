"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { useAuth } from "@/context/AuthContext";
import { fetchEvents, fetchVisitorDaily } from "@/services/stats.service";
import { todayISO } from "@/lib/utils";
import Table from "@/components/ui/Table";
import Section from "@/components/ui/Section";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Paragraph from "@/components/ui/Paragraph";
import StatsGrid from "@/components/dashboard/StatsGrid";

const PERIOD_OPTIONS = [
  { value: "daily", label: "Harian" },
  { value: "monthly", label: "Bulanan" },
  { value: "yearly", label: "Tahunan" },
];

function getMonthStart(monthValue) {
  return `${monthValue}-01`;
}

function getMonthEnd(monthValue) {
  const [year, month] = monthValue.split("-").map(Number);
  const lastDay = new Date(year, month, 0).getDate();
  return `${monthValue}-${String(lastDay).padStart(2, "0")}`;
}

function buildAppliedPeriod({
  periodType,
  selectedDay,
  fromTime,
  toTime,
  fromMonth,
  toMonth,
  fromYear,
  toYear,
}) {
  if (periodType === "daily") {
    return {
      periodType,
      fromDate: selectedDay,
      toDate: selectedDay,
      fromDateTime: `${selectedDay}T${fromTime}:00`,
      toDateTime: `${selectedDay}T${toTime}:59`,
      displayLabel: `${selectedDay} ${fromTime} s/d ${toTime}`,
      summaryLabel: `Tanggal ${selectedDay}, jam ${fromTime} - ${toTime}`,
    };
  }

  if (periodType === "monthly") {
    const fromDate = getMonthStart(fromMonth);
    const toDate = getMonthEnd(toMonth);
    return {
      periodType,
      fromDate,
      toDate,
      fromDateTime: null,
      toDateTime: null,
      displayLabel: `${fromDate} s/d ${toDate}`,
      summaryLabel: `Bulan ${fromMonth} s/d ${toMonth}`,
    };
  }

  const fromDate = `${fromYear}-01-01`;
  const toDate = `${toYear}-12-31`;
  return {
    periodType,
    fromDate,
    toDate,
    fromDateTime: null,
    toDateTime: null,
    displayLabel: `${fromDate} s/d ${toDate}`,
    summaryLabel: `Tahun ${fromYear} s/d ${toYear}`,
  };
}

export default function VisitsPage() {
  const { user } = useAuth();
  const today = todayISO();
  const currentMonth = today.slice(0, 7);
  const currentYear = today.slice(0, 4);

  const [periodType, setPeriodType] = useState("daily");
  const [selectedDay, setSelectedDay] = useState(today);
  const [fromTime, setFromTime] = useState("00:00");
  const [toTime, setToTime] = useState("23:59");
  const [fromMonth, setFromMonth] = useState(currentMonth);
  const [toMonth, setToMonth] = useState(currentMonth);
  const [fromYear, setFromYear] = useState(currentYear);
  const [toYear, setToYear] = useState(currentYear);
  const [appliedPeriod, setAppliedPeriod] = useState(() =>
    buildAppliedPeriod({
      periodType: "daily",
      selectedDay: today,
      fromTime: "00:00",
      toTime: "23:59",
      fromMonth: currentMonth,
      toMonth: currentMonth,
      fromYear: currentYear,
      toYear: currentYear,
    }),
  );
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

  const load = useCallback(async (period) => {
    setLoading(true);
    setError("");
    try {
      const [eventsData, visitorsData] = await Promise.all([
        fetchEvents(period.fromDate, period.toDate, {
          fromDateTime: period.fromDateTime,
          toDateTime: period.toDateTime,
        }).catch(() => []),
        fetchVisitorDaily(period.fromDate, period.toDate, {
          fromDateTime: period.fromDateTime,
          toDateTime: period.toDateTime,
        }).catch(() => []),
      ]);
      setEvents(eventsData);
      setVisitors(visitorsData);
    } catch (e) {
      setError(e.message || "Gagal memuat data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(appliedPeriod);
  }, [appliedPeriod, load]);

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
  const day = appliedPeriod.displayLabel;
  const customerEvents = events.filter((e) => e.person_type !== "EMPLOYEE");
  const ignoredEmployeeEvents = events.filter((e) => e.person_type === "EMPLOYEE").length;
  const uniqueVisitors = visitors.length;
  const totalIn = uniqueVisitors;
  const totalOut = customerEvents.filter((e) => e.direction === "OUT").length;
  const totalEvents = totalIn + totalOut;

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

  function handleFromTimeChange(value) {
    setFromTime(value);
    if (value > toTime) {
      setToTime(value);
    }
  }

  function handleToTimeChange(value) {
    setToTime(value);
    if (value < fromTime) {
      setFromTime(value);
    }
  }

  function handleFromMonthChange(value) {
    setFromMonth(value);
    if (value > toMonth) {
      setToMonth(value);
    }
  }

  function handleToMonthChange(value) {
    setToMonth(value);
    if (value < fromMonth) {
      setFromMonth(value);
    }
  }

  function handleFromYearChange(value) {
    setFromYear(value);
    if (value > toYear) {
      setToYear(value);
    }
  }

  function handleToYearChange(value) {
    setToYear(value);
    if (value < fromYear) {
      setFromYear(value);
    }
  }

  function handleApplyPeriod() {
    setAppliedPeriod(
      buildAppliedPeriod({
        periodType,
        selectedDay,
        fromTime,
        toTime,
        fromMonth,
        toMonth,
        fromYear,
        toYear,
      }),
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Heading level={1}>Data Kunjungan</Heading>
        <Paragraph>
          Lihat dan kelola data event kunjungan dan pengunjung unik berdasarkan periode.
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
                loading={loading}
                onClick={handleApplyPeriod}
                className="btn-sm w-full xl:w-fit"
              >
                Muat Data
              </Button>
            </div>
          </div>

          <p className="text-sm text-base-content/60">
            Rentang aktif: {appliedPeriod.summaryLabel}
          </p>
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
        <Section title={`Event Kunjungan (${appliedPeriod.displayLabel})`}>
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
        <Section title={`Pengunjung Unik (${appliedPeriod.displayLabel})`}>
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
