"use client";

import { useState } from "react";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Section from "@/components/ui/Section";
import Textarea from "@/components/ui/Textarea";

const EMPLOYEE_CODE_MAX_LENGTH = 10;

export default function EmployeeForm({ onCreated, employee, onSaved, onCancel }) {
  const isEdit = !!employee;
  const [employeeCode, setEmployeeCode] = useState(employee?.employee_code || "");
  const [fullName, setFullName] = useState(employee?.full_name || "");
  const [notes, setNotes] = useState(employee?.notes || "");
  const [photoFile, setPhotoFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmedCode = employeeCode.trim();
    const trimmedName = fullName.trim();

    if (!trimmedCode || !trimmedName) {
      setError("Kode pegawai dan nama wajib diisi.");
      return;
    }
    if (trimmedCode.length > EMPLOYEE_CODE_MAX_LENGTH) {
      setError(
        `Kode pegawai maksimal ${EMPLOYEE_CODE_MAX_LENGTH} karakter.`,
      );
      return;
    }
    if (!isEdit && !photoFile) {
      setError("Foto referensi wajah wajib diunggah.");
      return;
    }

    const formData = new FormData();
    formData.append("employee_code", trimmedCode);
    formData.append("full_name", trimmedName);
    formData.append("notes", notes.trim());
    if (photoFile) {
      formData.append("photo", photoFile);
    }

    setSaving(true);
    setError("");
    setOk("");
    try {
      if (isEdit) {
        await onSaved(employee.employee_id, formData);
        setOk("Data pegawai berhasil diperbarui.");
      } else {
        await onCreated(formData);
        setOk(`Pegawai "${trimmedName}" berhasil ditambahkan.`);
        setEmployeeCode("");
        setFullName("");
        setNotes("");
        setPhotoFile(null);
      }
    } catch (err) {
      setError(err.message || "Gagal menyimpan data pegawai.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title={isEdit ? "Edit Pegawai" : "Tambah Pegawai"}>
      <form onSubmit={handleSubmit} className="grid gap-4">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Input
            label="Kode Pegawai"
            value={employeeCode}
            onChange={(e) =>
              setEmployeeCode(e.target.value.slice(0, EMPLOYEE_CODE_MAX_LENGTH))
            }
            placeholder="PGW-001"
            helpText={`Maksimal ${EMPLOYEE_CODE_MAX_LENGTH} karakter.`}
            maxLength={EMPLOYEE_CODE_MAX_LENGTH}
            required
          />
          <Input
            label="Nama Lengkap"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Nama pegawai"
            required
          />
        </div>
        <p className="text-xs text-base-content/60">
          Panjang kode pegawai: {employeeCode.length}/{EMPLOYEE_CODE_MAX_LENGTH}
        </p>

        <div className="grid gap-2">
          <label className="label">
            <span className="label-text font-medium">
              Foto Wajah Referensi
              {!isEdit && <span className="text-error ml-1">*</span>}
            </span>
          </label>
          <input
            type="file"
            accept="image/*"
            className="file-input file-input-bordered w-full"
            onChange={(e) => setPhotoFile(e.target.files?.[0] || null)}
          />
          <p className="text-sm text-base-content/70">
            Gunakan foto frontal dengan satu wajah yang jelas. Saat edit, unggah foto baru jika ingin mengganti embedding.
          </p>
          {isEdit && employee?.has_face_embedding && !photoFile && (
            <p className="text-sm text-success">Embedding wajah pegawai sudah tersimpan.</p>
          )}
          {photoFile && (
            <p className="text-sm text-info">File dipilih: {photoFile.name}</p>
          )}
        </div>

        <Textarea
          label="Catatan"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Catatan internal, misalnya divisi atau lokasi kerja."
          rows={3}
        />

        <div className="flex gap-2">
          <Button variant="primary" loading={saving} className="w-fit">
            {isEdit ? "Simpan Perubahan" : "Tambah Pegawai"}
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

        {error && <Alert type="error">{error}</Alert>}
        {ok && <Alert type="success">{ok}</Alert>}
      </form>
    </Section>
  );
}
