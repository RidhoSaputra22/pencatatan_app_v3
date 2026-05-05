"use client";

import { useEffect, useMemo, useState } from "react";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Heading from "@/components/ui/Heading";
import Section from "@/components/ui/Section";
import { useToast } from "@/context/ToastContext";
import { API_BASE } from "@/lib/constants";
import { deleteRecording, fetchRecordingList } from "@/services/recording.service";

const AUTO_REFRESH_MS = 30000;
const PREVIEW_RETRY_MS = 5000;

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

function formatSize(sizeMb) {
  const numeric = Number(sizeMb || 0);
  if (!Number.isFinite(numeric)) return "0 MB";
  if (numeric >= 1024) return `${(numeric / 1024).toFixed(2)} GB`;
  return `${numeric.toFixed(2)} MB`;
}

function buildRecordingUrl(recording) {
  if (!recording) return "";
  const relativePlaybackUrl =
    recording.playback_url || `/api/recordings/${encodeURIComponent(recording.filename)}/media`;
  const versionToken = encodeURIComponent(
    recording.preview_updated_at || recording.recorded_until || recording.uploaded_at || "",
  );
  if (API_BASE) {
    return `${API_BASE}${relativePlaybackUrl}?v=${versionToken}`;
  }
  return `${relativePlaybackUrl}?v=${versionToken}`;
}

export default function RecordingLibrary() {
  const { showToast } = useToast();
  const [recordings, setRecordings] = useState([]);
  const [selectedFilename, setSelectedFilename] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [deletingFilename, setDeletingFilename] = useState("");
  const [lastSyncedAt, setLastSyncedAt] = useState("");
  const [videoLoadError, setVideoLoadError] = useState("");

  async function loadRecordings({ silent = false } = {}) {
    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const result = await fetchRecordingList();
      setRecordings(result);
      setLastSyncedAt(new Date().toISOString());
      setVideoLoadError("");
      setSelectedFilename((current) => {
        if (result.length === 0) return "";
        if (current && result.some((item) => item.filename === current)) return current;
        return result[0].filename;
      });
    } catch (error) {
      showToast("error", error.message || "Gagal memuat rekaman CCTV");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadRecordings();

    const timer = window.setInterval(() => {
      loadRecordings({ silent: true });
    }, AUTO_REFRESH_MS);

    return () => window.clearInterval(timer);
  }, []);

  const selectedRecording =
    recordings.find((item) => item.filename === selectedFilename) || recordings[0] || null;
  const selectedRecordingUrl = selectedRecording ? buildRecordingUrl(selectedRecording) : "";

  useEffect(() => {
    if (!selectedRecording || selectedRecording.preview_ready !== false) return undefined;

    const retryTimer = window.setTimeout(() => {
      loadRecordings({ silent: true });
    }, PREVIEW_RETRY_MS);

    return () => window.clearTimeout(retryTimer);
  }, [selectedRecording?.filename, selectedRecording?.preview_ready]);

  const summary = useMemo(() => {
    const totalSizeMb = recordings.reduce((sum, item) => sum + Number(item.size_mb || 0), 0);
    return {
      totalFiles: recordings.length,
      totalSizeMb,
      latestRecordedUntil: recordings[0]?.recorded_until || recordings[0]?.uploaded_at || "",
    };
  }, [recordings]);

  async function handleDelete(filename) {
    if (!window.confirm(`Hapus rekaman "${filename}"?`)) return;

    setDeletingFilename(filename);
    try {
      const result = await deleteRecording(filename);
      showToast("success", result.message || "Rekaman berhasil dihapus");
      await loadRecordings({ silent: true });
    } catch (error) {
      showToast("error", error.message || "Gagal menghapus rekaman");
    } finally {
      setDeletingFilename("");
    }
  }

  return (
    <div className="space-y-6">
      <Section className="mt-0">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <Heading level={1} className="mb-2">
              Rekaman CCTV
            </Heading>
            <p className="text-sm leading-6 text-base-content/70">
              Halaman ini khusus untuk melihat arsip rekaman CCTV yang dibuat otomatis dari hasil
              video yang sudah diproses. Setiap file berisi segmen rekaman 10 menit dan baru
              muncul setelah segmennya selesai disimpan.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge type="secondary" className="px-3 py-3">
              Auto segment 10 menit
            </Badge>
            <Button
              variant="primary"
              size="sm"
              onClick={() => loadRecordings({ silent: true })}
              loading={refreshing}
              isSubmit={false}
            >
              Muat Ulang
            </Button>
          </div>
        </div>
      </Section>

      <div className="grid gap-4 md:grid-cols-3">
        <Card compact className="border border-base-300 bg-base-100 shadow-none">
          <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">Total Rekaman</p>
          <p className="mt-2 text-3xl font-bold">{summary.totalFiles}</p>
        </Card>
        <Card compact className="border border-base-300 bg-base-100 shadow-none">
          <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">Total Ukuran</p>
          <p className="mt-2 text-3xl font-bold">{formatSize(summary.totalSizeMb)}</p>
        </Card>
        <Card compact className="border border-base-300 bg-base-100 shadow-none">
          <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">Rekaman Terbaru</p>
          <p className="mt-2 text-sm font-medium text-base-content/80">
            {formatDateTime(summary.latestRecordedUntil)}
          </p>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(360px,0.9fr)]">
        <Section title="Preview Rekaman" className="mt-0">
          {loading ? (
            <div className="flex min-h-[360px] items-center justify-center">
              <span className="loading loading-dots loading-lg"></span>
            </div>
          ) : !selectedRecording ? (
            <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-dashed border-base-300 bg-base-200/40 px-6 text-center">
              <p className="text-lg font-semibold">Belum ada rekaman tersedia</p>
              <p className="mt-2 max-w-lg text-sm text-base-content/60">
                Biarkan edge worker berjalan sampai satu segmen 10 menit selesai, lalu rekaman akan
                muncul di halaman ini.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {selectedRecording.preview_ready === false ? (
                <div className="flex aspect-video w-full flex-col items-center justify-center rounded-2xl border border-base-300 bg-black/70 px-6 text-center text-white">
                  <p className="text-lg font-semibold">Preview sedang disiapkan</p>
                  <p className="mt-2 max-w-lg text-sm text-white/70">
                    Rekaman ini masih dikonversi ke format yang kompatibel dengan browser. Halaman
                    akan mencoba memuat ulang otomatis beberapa detik lagi.
                  </p>
                </div>
              ) : (
                <video
                  key={selectedRecordingUrl}
                  controls
                  preload="metadata"
                  className="aspect-video w-full rounded-2xl border border-base-300 bg-black"
                  onLoadedData={() => setVideoLoadError("")}
                  onError={() =>
                    setVideoLoadError(
                      "Video belum bisa diputar. Silakan muat ulang beberapa detik lagi atau buka file langsung.",
                    )
                  }
                >
                  <source src={selectedRecordingUrl} type="video/mp4" />
                  Browser ini tidak mendukung pemutaran video.
                </video>
              )}

              {videoLoadError && (
                <div className="rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning-content">
                  {videoLoadError}
                </div>
              )}

              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">
                    Nama File
                  </p>
                  <p className="mt-1 break-all text-sm font-medium">{selectedRecording.filename}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">
                    Ukuran
                  </p>
                  <p className="mt-1 text-sm font-medium">{formatSize(selectedRecording.size_mb)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">
                    Mulai Rekam
                  </p>
                  <p className="mt-1 text-sm font-medium">
                    {formatDateTime(selectedRecording.recorded_from)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">
                    Selesai Rekam
                  </p>
                  <p className="mt-1 text-sm font-medium">
                    {formatDateTime(selectedRecording.recorded_until)}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Badge type="secondary">Segmen {selectedRecording.segment_minutes || 10} menit</Badge>
                {selectedRecording.camera_id && (
                  <Badge type="ghost">Kamera {selectedRecording.camera_id}</Badge>
                )}
                <a
                  href={selectedRecordingUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-ghost btn-sm"
                >
                  Buka File
                </a>
                <Button
                  variant="error"
                  size="sm"
                  outline
                  loading={deletingFilename === selectedRecording.filename}
                  disabled={deletingFilename !== "" && deletingFilename !== selectedRecording.filename}
                  onClick={() => handleDelete(selectedRecording.filename)}
                  isSubmit={false}
                >
                  Hapus
                </Button>
              </div>
            </div>
          )}
        </Section>

        <Section title="Daftar Rekaman" className="mt-0">
          <div className="mb-3 flex items-center justify-between text-xs text-base-content/55">
            <span>Menampilkan rekaman otomatis yang sudah selesai disimpan.</span>
            <span>Sinkron terakhir: {formatDateTime(lastSyncedAt)}</span>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-10">
              <span className="loading loading-dots loading-lg"></span>
            </div>
          ) : recordings.length === 0 ? (
            <p className="rounded-xl border border-dashed border-base-300 px-4 py-8 text-center text-sm text-base-content/60">
              Belum ada rekaman CCTV yang bisa ditampilkan.
            </p>
          ) : (
            <div className="space-y-3">
              {recordings.map((recording) => {
                const active = selectedRecording?.filename === recording.filename;
                return (
                  <button
                    key={recording.filename}
                    type="button"
                    className={`w-full rounded-2xl border p-4 text-left transition ${
                      active
                        ? "border-primary bg-primary/10 shadow-sm"
                        : "border-base-300 bg-base-100 hover:border-primary/40 hover:bg-base-200/30"
                    }`}
                    onClick={() => {
                      setVideoLoadError("");
                      setSelectedFilename(recording.filename);
                    }}
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-semibold">{recording.filename}</p>
                          <Badge type="secondary" size="sm">
                            Rekaman Otomatis
                          </Badge>
                          {recording.preview_ready === false && (
                            <Badge type="warning" size="sm">
                              Menyiapkan Preview
                            </Badge>
                          )}
                          {active && (
                            <Badge type="primary" size="sm">
                              Dipilih
                            </Badge>
                          )}
                        </div>
                        <div className="mt-2 space-y-1 text-xs text-base-content/60">
                          <p>Mulai: {formatDateTime(recording.recorded_from)}</p>
                          <p>Selesai: {formatDateTime(recording.recorded_until)}</p>
                          <p>
                            Ukuran: {formatSize(recording.size_mb)} | Kamera {recording.camera_id || "-"}
                          </p>
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-2">
                        <Button
                          variant="primary"
                          size="xs"
                          onClick={() => {
                            setVideoLoadError("");
                            setSelectedFilename(recording.filename);
                          }}
                          isSubmit={false}
                        >
                          Lihat
                        </Button>
                        <Button
                          variant="error"
                          size="xs"
                          outline
                          loading={deletingFilename === recording.filename}
                          disabled={deletingFilename !== "" && deletingFilename !== recording.filename}
                          onClick={() => handleDelete(recording.filename)}
                          isSubmit={false}
                        >
                          Hapus
                        </Button>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}
