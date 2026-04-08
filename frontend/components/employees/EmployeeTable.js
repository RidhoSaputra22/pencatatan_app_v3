"use client";

import { formatDateTime } from "@/lib/utils";
import Section from "@/components/ui/Section";
import Table from "@/components/ui/Table";
import { useToast } from "@/context/ToastContext";

export default function EmployeeTable({ employees = [], onDelete, onEditClick }) {
  const { showToast } = useToast();

  async function handleDeactivate(employee) {
    if (!confirm(`Nonaktifkan pegawai "${employee.full_name}"?`)) return;
    try {
      await onDelete(employee.employee_id);
      showToast("success", `Pegawai "${employee.full_name}" berhasil dinonaktifkan.`);
    } catch (e) {
      showToast("error", e.message || "Gagal menonaktifkan pegawai.");
    }
  }

  const columns = [
    "Kode",
    "Nama",
    "Face Registry",
    "Status",
    "Diperbarui",
    "Aksi",
  ];

  const rows = employees.map((employee) => [
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
      <button
        type="button"
        onClick={() => onEditClick(employee)}
        className="btn btn-ghost btn-sm"
      >
        Edit
      </button>
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
    <Section title="Daftar Pegawai">
      <Table
        columns={columns}
        rows={rows}
        emptyText="Belum ada pegawai yang terdaftar."
      />
    </Section>
  );
}
