"use client";

import Link from "next/link";
import { useState } from "react";
import { formatNumber } from "@/lib/utils";
import Table from "@/components/ui/Table";
import Section from "@/components/ui/Section";
import { useToast } from "@/context/ToastContext";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Stat from "@/components/ui/Stat";

const ROLE_FILTER_OPTIONS = [
  { value: "ALL", label: "Semua Role" },
  { value: "ADMIN", label: "Admin" },
  { value: "OPERATOR", label: "Operator" },
];

const STATUS_FILTER_OPTIONS = [
  { value: "ALL", label: "Semua Status" },
  { value: "ACTIVE", label: "Aktif" },
  { value: "INACTIVE", label: "Nonaktif" },
];

/**
 * Table listing all users with edit/deactivate actions.
 */
export default function UserTable({ users = [], onDelete }) {
  const { showToast } = useToast();
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  async function handleDelete(user) {
    if (!confirm(`Yakin ingin menonaktifkan user "${user.username}"?`)) return;
    try {
      await onDelete(user.user_id);
      showToast("success", `User "${user.username}" berhasil dinonaktifkan`);
    } catch (e) {
      showToast("error", e.message || "Gagal menonaktifkan user");
    }
  }

  function resetFilters() {
    setSearch("");
    setRoleFilter("ALL");
    setStatusFilter("ALL");
  }

  const normalizedSearch = search.trim().toLowerCase();
  const filteredUsers = users.filter((user) => {
    const matchesSearch =
      !normalizedSearch ||
      user.username?.toLowerCase().includes(normalizedSearch) ||
      user.full_name?.toLowerCase().includes(normalizedSearch);

    const matchesRole =
      roleFilter === "ALL" || user.role === roleFilter;

    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "ACTIVE" && user.is_active) ||
      (statusFilter === "INACTIVE" && !user.is_active);

    return matchesSearch && matchesRole && matchesStatus;
  });

  const totalUsers = users.length;
  const activeUsers = users.filter((user) => user.is_active).length;
  const adminUsers = users.filter((user) => user.role === "ADMIN").length;
  const operatorUsers = users.filter((user) => user.role === "OPERATOR").length;
  const filterIsActive =
    normalizedSearch || roleFilter !== "ALL" || statusFilter !== "ALL";

  const columns = ["ID", "Username", "Nama Lengkap", "Role", "Status", "Aksi"];

  const rows = filteredUsers.map((u) => [
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
      <Link href={`/users/${u.user_id}/edit`} className="btn btn-ghost btn-sm">
        Edit
      </Link>
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
    <>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            title="Total Pengguna"
            value={formatNumber(totalUsers)}
            description="Seluruh akun yang terdaftar"
            tone="primary"
          />
          <Stat
            title="Akun Aktif"
            value={formatNumber(activeUsers)}
            description="Masih dapat mengakses sistem"
            tone="success"
          />
          <Stat
            title="Admin"
            value={formatNumber(adminUsers)}
            description={`${formatNumber(operatorUsers)} operator terdaftar`}
            tone="warning"
          />
          <Stat
            title="Tampil di Tabel"
            value={formatNumber(filteredUsers.length)}
            description={
              filterIsActive
                ? "Hasil setelah filter diterapkan"
                : "Semua data sedang ditampilkan"
            }
            tone="neutral"
          />
        </div>
      <Section title="Daftar Pengguna">

        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Input
            label="Cari Pengguna"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Username atau nama lengkap"
          />
          <Select
            label="Role"
            options={ROLE_FILTER_OPTIONS}
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          />
          <Select
            label="Status"
            options={STATUS_FILTER_OPTIONS}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
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
            emptyText="Belum ada pengguna."
          />
        </div>
      </Section>
    </>
  );
}
