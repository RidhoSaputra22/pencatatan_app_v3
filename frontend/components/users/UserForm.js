"use client";

import { useState } from "react";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Button from "@/components/ui/Button";
import Section from "@/components/ui/Section";
import { useToast } from "@/context/ToastContext";

const ROLE_OPTIONS = [
  { value: "OPERATOR", label: "Operator / Petugas" },
  { value: "ADMIN", label: "Admin" },
];

/**
 * Form to create or edit a user.
 * @param {object} props
 * @param {function} props.onCreated - called after user created (create mode)
 * @param {object} [props.user] - user object for edit mode
 * @param {function} [props.onSaved] - called after user updated (edit mode)
 * @param {function} [props.onCancel] - called when cancel (edit mode)
 */
export default function UserForm({ onCreated, user, onSaved, onCancel }) {
  const { showToast } = useToast();
  const isEdit = !!user;
  const [username, setUsername] = useState(user?.username || "");
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState(user?.role || "OPERATOR");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (
      !fullName.trim() ||
      (!isEdit && (!username.trim() || !password.trim()))
    ) {
      showToast("error", "Semua field wajib diisi");
      return;
    }
    setSaving(true);
    try {
      if (isEdit) {
        // Edit mode
        const payload = { full_name: fullName, role };
        if (password) payload.password = password;
        await onSaved(user.user_id, payload);
        showToast("success", "User berhasil diupdate");
      } else {
        // Create mode
        await onCreated({ username, full_name: fullName, password, role });
        showToast("success", `User "${username}" berhasil dibuat`);
        setUsername("");
        setFullName("");
        setPassword("");
        setRole("OPERATOR");
      }
    } catch (e) {
      showToast("error",
        e.message || (isEdit ? "Gagal update user" : "Gagal membuat user"),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title={isEdit ? "Edit Pengguna" : "Tambah Pengguna Baru"}>
      <form onSubmit={handleSubmit} className="grid gap-4">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Input
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="username"
            required
            disabled={isEdit}
          />
          <Input
            label="Nama Lengkap"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Nama lengkap"
            required
          />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Input
            label={isEdit ? "Password baru (opsional)" : "Password"}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={isEdit ? "Password baru (opsional)" : "Password"}
            required={!isEdit}
          />
          <Select
            label="Role"
            options={ROLE_OPTIONS}
            value={role}
            onChange={(e) => setRole(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <Button variant="primary" loading={saving} className="w-fit">
            {isEdit ? "Simpan" : "Tambah User"}
          </Button>
          {isEdit && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onCancel}
              disabled={saving}
            >
              Batal
            </button>
          )}
        </div>
      </form>
    </Section>
  );
}
