"use client";

import { useState, useEffect, useRef } from "react";
import {
  uploadFootage,
  fetchFootageList,
  deleteFootage,
  setFootageAsSource,
} from "@/services/camera.service";
import Section from "@/components/ui/Section";
import { useToast } from "@/context/ToastContext";

const ACCEPTED_FORMATS = ".mp4,.avi,.mkv,.mov,.flv,.wmv,.webm";

export default function FootageUpload({ camera, onSourceChanged }) {
  const { showToast } = useToast();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [loadingFiles, setLoadingFiles] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadFiles();
  }, []);

  async function loadFiles() {
    setLoadingFiles(true);
    try {
      const list = await fetchFootageList();
      setFiles(list);
    } catch (e) {
      console.error("Failed to load footage list:", e);
    } finally {
      setLoadingFiles(false);
    }
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadProgress(`Mengupload ${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)...`);

    try {
      const result = await uploadFootage(file, { setAsSource: false, cameraId: 1 });
      showToast("success", `File "${result.filename}" berhasil diupload (${result.size_mb} MB)`);
      setUploadProgress("");
      await loadFiles();
    } catch (err) {
      showToast("error", err.message || "Gagal mengupload file");
      setUploadProgress("");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleSetSource(filename) {
    try {
      const result = await setFootageAsSource(filename, 1);
      showToast("success", result.message || `Footage "${filename}" diset sebagai sumber kamera`);
      onSourceChanged?.();
    } catch (err) {
      showToast("error", err.message || "Gagal mengset footage sebagai sumber");
    }
  }

  async function handleDelete(filename) {
    if (!confirm(`Hapus file "${filename}"?`)) return;
    try {
      await deleteFootage(filename);
      showToast("success", `File "${filename}" berhasil dihapus`);
      await loadFiles();
    } catch (err) {
      showToast("error", err.message || "Gagal menghapus file");
    }
  }

  const isCurrentSource = (filePath) => camera?.stream_url === filePath;

  return (
    <Section title="Upload Footage CCTV">
      <p className="text-sm opacity-70 mb-3">
        Upload file rekaman CCTV dari komputer Anda. File akan diproses oleh edge worker
        (YOLOv5 + tracking) untuk menghitung pengunjung.
      </p>

      {/* Upload area */}
      <div className="border-2 border-dashed border-base-300 rounded-lg p-6 text-center mb-4 hover:border-primary transition-colors">
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_FORMATS}
          onChange={handleUpload}
          disabled={uploading}
          className="hidden"
          id="footage-upload"
        />
        <label
          htmlFor="footage-upload"
          className={`cursor-pointer flex flex-col items-center gap-2 ${uploading ? "opacity-50 pointer-events-none" : ""}`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <span className="text-sm font-medium">
            {uploading ? "Mengupload..." : "Klik untuk memilih file video"}
          </span>
          <span className="text-xs opacity-50">
            Format: MP4, AVI, MKV, MOV, FLV, WMV, WEBM (maks 500 MB)
          </span>
        </label>
      </div>

      {uploading && uploadProgress && (
        <div className="mb-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="loading loading-spinner loading-sm"></span>
            <span>{uploadProgress}</span>
          </div>
          <progress className="progress progress-primary w-full mt-1"></progress>
        </div>
      )}

      {/* File list */}
      <div className="mt-2">
        <h4 className="text-sm font-semibold mb-2">
          File Footage Tersimpan {files.length > 0 && `(${files.length})`}
        </h4>

        {loadingFiles ? (
          <div className="text-center py-4">
            <span className="loading loading-dots loading-md"></span>
          </div>
        ) : files.length === 0 ? (
          <p className="text-sm opacity-50 py-4 text-center">
            Belum ada footage yang diupload.
          </p>
        ) : (
          <div className="divide-y divide-base-200 border border-base-200 rounded-lg overflow-hidden">
            {files.map((f) => (
              <div
                key={f.filename}
                className={`flex items-center justify-between px-4 py-3 hover:bg-base-200 transition-colors ${isCurrentSource(f.path) ? "bg-primary/5 border-l-4 border-l-primary" : ""}`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium truncate">{f.filename}</span>
                    {isCurrentSource(f.path) && (
                      <span className="badge badge-primary badge-sm">Aktif</span>
                    )}
                  </div>
                  <div className="text-xs opacity-50 mt-0.5">
                    {f.size_mb} MB — {new Date(f.uploaded_at).toLocaleString("id-ID")}
                  </div>
                </div>
                <div className="flex gap-1 ml-2 shrink-0">
                  {!isCurrentSource(f.path) && (
                    <button
                      onClick={() => handleSetSource(f.filename)}
                      className="btn btn-primary btn-xs"
                      title="Gunakan sebagai sumber kamera"
                    >
                      ▶ Gunakan
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(f.filename)}
                    className="btn btn-error btn-outline btn-xs"
                    title="Hapus file"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Section>
  );
}
