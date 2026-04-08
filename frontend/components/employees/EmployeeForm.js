"use client";

import { useEffect, useRef, useState } from "react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Section from "@/components/ui/Section";
import Textarea from "@/components/ui/Textarea";
import { useToast } from "@/context/ToastContext";

const EMPLOYEE_CODE_MAX_LENGTH = 10;

function resolveEmployeePhotoUrl(path) {
  if (!path) {
    return "";
  }

  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const normalizedPath = path.replace(/\\/g, "/");
  const storageIndex = normalizedPath.toLowerCase().lastIndexOf("/storage/");
  if (storageIndex >= 0) {
    return normalizedPath.slice(storageIndex);
  }

  if (normalizedPath.toLowerCase().startsWith("storage/")) {
    return `/${normalizedPath}`;
  }

  return normalizedPath.startsWith("/") ? normalizedPath : `/${normalizedPath}`;
}

export default function EmployeeForm({ onCreated, employee, onSaved, onCancel }) {
  const { showToast } = useToast();
  const isEdit = !!employee;
  const fileInputRef = useRef(null);
  const [employeeCode, setEmployeeCode] = useState(employee?.employee_code || "");
  const [fullName, setFullName] = useState(employee?.full_name || "");
  const [notes, setNotes] = useState(employee?.notes || "");
  const [photoFile, setPhotoFile] = useState(null);
  const [photoObjectUrl, setPhotoObjectUrl] = useState("");
  const [previewLoadFailed, setPreviewLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const storedPhotoUrl = resolveEmployeePhotoUrl(employee?.face_image_path);
  const photoPreviewUrl = photoObjectUrl || storedPhotoUrl;
  const isShowingStoredPhoto = !photoObjectUrl && !!storedPhotoUrl;
  const canRenderPreview = !!photoPreviewUrl && !previewLoadFailed;

  useEffect(() => {
    if (!photoFile) {
      setPhotoObjectUrl("");
      return;
    }

    const nextObjectUrl = URL.createObjectURL(photoFile);
    setPhotoObjectUrl(nextObjectUrl);

    return () => {
      URL.revokeObjectURL(nextObjectUrl);
    };
  }, [photoFile]);

  useEffect(() => {
    setPreviewLoadFailed(false);
  }, [photoPreviewUrl]);

  function clearSelectedPhoto() {
    setPhotoFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmedCode = employeeCode.trim();
    const trimmedName = fullName.trim();

    if (!trimmedCode || !trimmedName) {
      showToast("error", "Kode pegawai dan nama wajib diisi.");
      return;
    }
    if (trimmedCode.length > EMPLOYEE_CODE_MAX_LENGTH) {
      showToast("error",
        `Kode pegawai maksimal ${EMPLOYEE_CODE_MAX_LENGTH} karakter.`,
      );
      return;
    }
    if (!isEdit && !photoFile) {
      showToast("error", "Foto referensi wajah wajib diunggah.");
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
    try {
      if (isEdit) {
        await onSaved(employee.employee_id, formData);
        showToast("success", "Data pegawai berhasil diperbarui.");
      } else {
        await onCreated(formData);
        showToast("success", `Pegawai "${trimmedName}" berhasil ditambahkan.`);
        setEmployeeCode("");
        setFullName("");
        setNotes("");
        clearSelectedPhoto();
      }
    } catch (err) {
      showToast("error", err.message || "Gagal menyimpan data pegawai.");
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
            ref={fileInputRef}
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
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-info">File dipilih: {photoFile.name}</p>
              <button
                type="button"
                className="btn btn-ghost btn-sm w-fit"
                onClick={clearSelectedPhoto}
                disabled={saving}
              >
                Batalkan pilihan foto
              </button>
            </div>
          )}
          {(photoPreviewUrl || (isEdit && employee?.has_face_embedding)) && (
            <div className="rounded-box border border-base-300 bg-base-200/30 p-3">
              <p className="text-sm font-medium text-base-content">
                {isShowingStoredPhoto ? "Foto referensi tersimpan" : "Preview foto baru"}
              </p>
              <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-start">
                {canRenderPreview ? (
                  <img
                    src={photoPreviewUrl}
                    alt={
                      isShowingStoredPhoto
                        ? `Foto referensi ${fullName || employee?.full_name || "pegawai"}`
                        : `Preview upload ${photoFile?.name || "foto pegawai"}`
                    }
                    className="h-56 w-full max-w-xs rounded-xl border border-base-300 bg-base-100 object-cover shadow-sm"
                    onError={() => setPreviewLoadFailed(true)}
                  />
                ) : (
                  <div className="flex h-56 w-full max-w-xs items-center justify-center rounded-xl border border-dashed border-base-300 bg-base-100 px-4 text-center text-sm text-base-content/60">
                    {isShowingStoredPhoto
                      ? "Foto referensi tersimpan, tetapi file gambar belum bisa dimuat."
                      : "Preview foto belum bisa ditampilkan."}
                  </div>
                )}
                <div className="grid gap-1 text-sm text-base-content/70">
                 
                  {photoFile && <p>Nama file: {photoFile.name}</p>}
                  {previewLoadFailed && isShowingStoredPhoto && (
                    <p className="text-warning">
                      Pastikan backend dan proxy frontend sudah dimuat ulang agar path `/storage/...` aktif.
                    </p>
                  )}
                </div>
              </div>
            </div>
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
      </form>
    </Section>
  );
}
