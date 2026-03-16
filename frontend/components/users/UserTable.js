"use client";

import { useState } from "react";
import Table from "@/components/ui/Table";
import Section from "@/components/ui/Section";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";
import UserForm from "@/components/users/UserForm";

const ROLE_OPTIONS = [
  { value: "OPERATOR", label: "Operator" },
  { value: "ADMIN", label: "Admin" },
];

/**
 * Table listing all users with edit/deactivate actions.
 */
export default function UserTable({ users = [], onDelete, onEditClick }) {
  const [error, setError] = useState("");

  async function handleDelete(user) {
    if (!confirm(`Yakin ingin menonaktifkan user "${user.username}"?`)) return;
    try {
      await onDelete(user.user_id);
    } catch (e) {
      setError(e.message || "Gagal menonaktifkan user");
    }
  }

  const columns = ["ID", "Username", "Nama Lengkap", "Role", "Status", "Aksi"];

  const rows = users.map((u) => [
    u.user_id,
    u.username,
    u.full_name,
    <span
      key="r"
      className={`badge ${u.role === "ADMIN" ? "badge-warning" : "badge-info"} badge-sm`}
    >
      {u.role}
    </span>,
    <span
      key="s"
      className={`badge ${u.is_active ? "badge-success" : "badge-error"} badge-sm`}
    >
      {u.is_active ? "Aktif" : "Nonaktif"}
    </span>,
    <div key="actions" className="flex gap-1">
      <button onClick={() => onEditClick(u)} className="btn btn-ghost btn-sm">
        Edit
      </button>
      {u.is_active && (
        <button
          onClick={() => handleDelete(u)}
          className="btn btn-ghost btn-sm text-error"
        >
          Nonaktifkan
        </button>
      )}
    </div>,
  ]);

  return (
    <Section title="Daftar Pengguna">
      {error && <Alert variant="error">{error}</Alert>}
      <Table columns={columns} rows={rows} emptyText="Belum ada pengguna." />
    </Section>
  );
}
