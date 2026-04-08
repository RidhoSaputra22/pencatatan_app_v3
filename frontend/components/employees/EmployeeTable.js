"use client";

import Link from "next/link";
import { useState } from "react";
import { formatDateTime, formatNumber } from "@/lib/utils";
import Section from "@/components/ui/Section";
import Table from "@/components/ui/Table";
import { useToast } from "@/context/ToastContext";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Stat from "@/components/ui/Stat";

const STATUS_FILTER_OPTIONS = [
  { value: "ALL", label: "Semua Status" },
  { value: "ACTIVE", label: "Aktif" },
  { value: "INACTIVE", label: "Nonaktif" },
];

const FACE_FILTER_OPTIONS = [
  { value: "ALL", label: "Semua Face Registry" },
  { value: "READY", label: "Siap Digunakan" },
  { value: "MISSING", label: "Belum Ada Embedding" },
];

export default function EmployeeTable({ employees = [], onDelete }) {
  const { showToast } = useToast();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [faceFilter, setFaceFilter] = useState("ALL");

  async function handleDeactivate(employee) {
    if (!confirm(`Nonaktifkan pegawai "${employee.full_name}"?`)) return;
    try {
      await onDelete(employee.employee_id);
      showToast("success", `Pegawai "${employee.full_name}" berhasil dinonaktifkan.`);
    } catch (e) {
      showToast("error", e.message || "Gagal menonaktifkan pegawai.");
    }
  }

  function resetFilters() {
    setSearch("");
    setStatusFilter("ALL");
    setFaceFilter("ALL");
  }

  const normalizedSearch = search.trim().toLowerCase();
  const filteredEmployees = employees.filter((employee) => {
    const matchesSearch =
      !normalizedSearch ||
      employee.employee_code?.toLowerCase().includes(normalizedSearch) ||
      employee.full_name?.toLowerCase().includes(normalizedSearch);

    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "ACTIVE" && employee.is_active) ||
      (statusFilter === "INACTIVE" && !employee.is_active);

    const matchesFace =
      faceFilter === "ALL" ||
      (faceFilter === "READY" && employee.has_face_embedding) ||
      (faceFilter === "MISSING" && !employee.has_face_embedding);

    return matchesSearch && matchesStatus && matchesFace;
  });

  const activeEmployees = employees.filter((employee) => employee.is_active).length;
  const readyEmbeddings = employees.filter((employee) => employee.has_face_embedding).length;
  const employeesWithoutEmbedding = employees.filter((employee) => !employee.has_face_embedding).length;
  const filterIsActive =
    normalizedSearch || statusFilter !== "ALL" || faceFilter !== "ALL";

  const columns = [
    "Kode",
    "Nama",
    "Face Registry",
    "Status",
    "Diperbarui",
    "Aksi",
  ];

  const rows = filteredEmployees.map((employee) => [
    <span key="code" className="font-mono text-xs">
      {employee.employee_code}
    </span>,
    employee.full_name,
    <span
      key="face"
      className={`badge badge-sm ${employee.has_face_embedding ? "badge-success" : "badge-warning"}`}
    >
      {employee.has_face_embedding ? "Siap" : "Belum ada"}
    </span>,
    <span
      key="status"
      className={`badge badge-sm ${employee.is_active ? "badge-info" : "badge-ghost"}`}
    >
      {employee.is_active ? "Aktif" : "Nonaktif"}
    </span>,
    formatDateTime(employee.updated_at),
    <div key="actions" className="flex gap-1">
      <Link
        href={`/employees/${employee.employee_id}/edit`}
        className="btn btn-ghost btn-sm"
      >
        Edit
      </Link>
      {employee.is_active && (
        <button
          type="button"
          onClick={() => handleDeactivate(employee)}
          className="btn btn-ghost btn-sm text-error"
        >
          Nonaktifkan
        </button>
      )}
    </div>,
  ]);

  return (
    <>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            title="Total Pegawai"
            value={formatNumber(employees.length)}
            description="Seluruh data pegawai"
            tone="primary"
          />
          <Stat
            title="Pegawai Aktif"
            value={formatNumber(activeEmployees)}
            description="Masih ikut proses pengecualian"
            tone="success"
          />
          <Stat
            title="Face Registry Siap"
            value={formatNumber(readyEmbeddings)}
            description={`${formatNumber(employeesWithoutEmbedding)} pegawai belum punya embedding`}
            tone="info"
          />
          <Stat
            title="Tampil di Tabel"
            value={formatNumber(filteredEmployees.length)}
            description={
              filterIsActive
                ? "Hasil setelah filter diterapkan"
                : "Semua data sedang ditampilkan"
            }
            tone="neutral"
          />
        </div>
      <Section title="Daftar Pegawai">
        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Input
            label="Cari Pegawai"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Kode atau nama pegawai"
          />
          <Select
            label="Status"
            options={STATUS_FILTER_OPTIONS}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          />
          <Select
            label="Face Registry"
            options={FACE_FILTER_OPTIONS}
            value={faceFilter}
            onChange={(e) => setFaceFilter(e.target.value)}
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

        <div className="mt-4">
          <Table
            columns={columns}
            rows={rows}
            emptyText="Belum ada pegawai yang terdaftar."
          />
        </div>
      </Section>
    </>
  );
}
