"use client";

import { useEffect, useMemo, useState } from "react";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Heading from "@/components/ui/Heading";
import Section from "@/components/ui/Section";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { API_BASE } from "@/lib/constants";
import {
  deleteRecording,
  downloadRecording,
  downloadRecordingArchive,
  fetchRecordingList,
} from "@/services/recording.service";
import {
  fetchRuntimeConfig,
  updateRuntimeConfig,
} from "@/services/runtime-config.service";

const AUTO_REFRESH_MS = 30000;
const PREVIEW_RETRY_MS = 5000;
const RECORDING_SAVE_MODE_KEY = "EDGE_RECORDING_SAVE_MODE";
const RECORDING_CONFIG_KEYS = [
  "EDGE_RECORDING_ENABLED",
  RECORDING_SAVE_MODE_KEY,
  "EDGE_RECORDING_SEGMENT_MINUTES",
  "EDGE_RECORDING_FPS",
  "EDGE_RECORDING_MAX_GAP_SECONDS",
];

function isTruthy(value) {
  return ["1", "true", "yes", "on"].includes(String(value).toLowerCase());
}

function pickRecordingValues(values = {}) {
  return RECORDING_CONFIG_KEYS.reduce((result, key) => {
    result[key] = values[key] ?? "";
    return result;
  }, {});
}

function formatRecordingMode(value) {
  return value === "raw" ? "Raw" : "Deteksi";
}

function formatDateLabel(dateKey) {
  if (!dateKey) return "Tanpa Tanggal";
  const [year, month, day] = String(dateKey).split("-").map(Number);
  if (!year || !month || !day) return dateKey;
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(new Date(year, month - 1, day));
}

function recordingDateKey(value) {
  if (!value) return "tanpa-tanggal";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "tanpa-tanggal";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getFieldHint(item) {
  return String(item?.hint || item?.help || "").trim();
}

function formatConfigValue(item, value) {
  if (!item) return String(value ?? "-");
  if (item.type === "bool") return isTruthy(value) ? "Aktif" : "Nonaktif";
  if (item.type === "select") {
    const option = (item.options || []).find((candidate) => candidate.value === value);
    return option?.label || String(value ?? "-");
  }
  if ((value ?? "") === "") return "-";
  if (item.unit) return `${value} ${item.unit}`;
  return String(value);
}

function formatFieldRange(item) {
  if (!item) return "";
  const parts = [];
  if (item.min !== undefined) parts.push(`min ${item.min}`);
  if (item.max !== undefined) parts.push(`max ${item.max}`);
  return parts.join(" • ");
}

function modeDescription(mode) {
  if (mode === "raw") {
    return "Simpan frame bersih tanpa kotak deteksi, garis ROI, atau overlay info.";
  }
  return "Simpan hasil video yang sama seperti preview, lengkap dengan overlay deteksi.";
}

function FolderArchiveIcon({ active = false }) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={`h-12 w-12 shrink-0 ${active ? "text-primary" : "text-warning"}`}
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M8 19a6 6 0 0 1 6-6h11l5 6h20a6 6 0 0 1 6 6v20a6 6 0 0 1-6 6H14a6 6 0 0 1-6-6V19Z"
        fill="currentColor"
        opacity={active ? "0.95" : "0.82"}
      />
      <path
        d="M8 24h48"
        stroke="rgba(255,255,255,0.55)"
        strokeWidth="2.5"
      />
      <path
        d="M16 34h20"
        stroke="rgba(255,255,255,0.8)"
        strokeLinecap="round"
        strokeWidth="4"
      />
      <path
        d="M16 42h28"
        stroke="rgba(255,255,255,0.55)"
        strokeLinecap="round"
        strokeWidth="4"
      />
    </svg>
  );
}

function VideoFileIcon() {
  return (
    <svg
      viewBox="0 0 48 48"
      className="h-10 w-10 shrink-0 text-info"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M14 6h14l10 10v22a4 4 0 0 1-4 4H14a4 4 0 0 1-4-4V10a4 4 0 0 1 4-4Z"
        fill="currentColor"
        opacity="0.2"
      />
      <path
        d="M28 6v10h10"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      <path
        d="M20 20h8a4 4 0 0 1 4 4v4a4 4 0 0 1-4 4h-8a4 4 0 0 1-4-4v-4a4 4 0 0 1 4-4Z"
        stroke="currentColor"
        strokeWidth="2.4"
      />
      <path
        d="m24 23 5 3-5 3v-6Z"
        fill="currentColor"
      />
    </svg>
  );
}

function BackChevronIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-4 w-4"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="m15 6-6 6 6 6"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}

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

function recordingFieldStep(item) {
  if (item.type === "int") return 1;
  if (item.type === "float") return item.max && item.max <= 1 ? 0.01 : 0.1;
  return undefined;
}

function RecordingConfigField({ item, value, changed, onChange }) {
  const inputId = `recording-config-${item.key}`;
  const hint = getFieldHint(item);
  const rangeText = formatFieldRange(item);

  if (item.type === "bool") {
    return (
      <div
        className={`rounded-2xl border p-4 transition ${
          changed
            ? "border-primary/60 bg-primary/10"
            : "border-base-300 bg-base-100/90"
        }`}
      >
        <label
          htmlFor={inputId}
          className="flex cursor-pointer items-start justify-between gap-4"
        >
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-base-content">
                {item.label}
              </span>
              <Badge type={isTruthy(value) ? "success" : "ghost"} size="sm">
                {isTruthy(value) ? "Aktif" : "Nonaktif"}
              </Badge>
              {changed && (
                <Badge type="warning" size="sm" outline>
                  Belum disimpan
                </Badge>
              )}
            </span>
            {hint && (
              <span className="mt-2 block text-xs leading-5 text-base-content/65">
                {hint}
              </span>
            )}
          </span>
          <input
            id={inputId}
            type="checkbox"
            className="toggle toggle-primary mt-1 shrink-0"
            checked={isTruthy(value)}
            onChange={(event) => onChange(item.key, event.target.checked ? "true" : "false")}
          />
        </label>
      </div>
    );
  }

  const isNumber = item.type === "int" || item.type === "float";

  return (
    <div
      className={`rounded-2xl border p-4 transition ${
        changed
          ? "border-primary/60 bg-primary/10"
          : "border-base-300 bg-base-100/90"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <label
              htmlFor={inputId}
              className="text-sm font-semibold text-base-content"
            >
              {item.label}
            </label>
            {changed && (
              <Badge type="warning" size="sm" outline>
                Diubah
              </Badge>
            )}
          </div>
          {hint && (
            <p className="mt-2 text-xs leading-5 text-base-content/65">{hint}</p>
          )}
        </div>
        {rangeText && (
          <Badge type="ghost" size="sm" className="px-2 py-2">
            {rangeText}
          </Badge>
        )}
      </div>

      <div className="mt-4 flex min-h-12 overflow-hidden rounded-xl border border-base-300 bg-base-100/90 focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/25">
        <input
          id={inputId}
          type={isNumber ? "number" : "text"}
          min={item.min}
          max={item.max}
          step={recordingFieldStep(item)}
          className="input h-12 min-w-0 flex-1 border-0 bg-transparent px-4 shadow-none outline-none focus:outline-none"
          value={value ?? ""}
          onChange={(event) => onChange(item.key, event.target.value)}
        />
        {item.unit && (
          <span className="flex shrink-0 items-center border-l border-base-300 bg-base-200/70 px-4 text-xs font-semibold uppercase tracking-[0.08em] text-base-content/55">
            {item.unit}
          </span>
        )}
      </div>
    </div>
  );
}

function RecordingModeOption({
  option,
  active,
  disabled,
  loading,
  onSelect,
}) {
  return (
    <button
      type="button"
      className={`w-full rounded-2xl border p-4 text-left transition ${
        active
          ? "border-primary bg-primary/12 shadow-sm"
          : "border-base-300 bg-base-100/85 hover:border-primary/40 hover:bg-base-100"
      }`}
      aria-pressed={active}
      disabled={disabled}
      onClick={() => onSelect(option.value)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold">{option.label}</p>
            {active && (
              <Badge type="primary" size="sm">
                Aktif
              </Badge>
            )}
          </div>
          <p className="mt-2 text-xs leading-5 text-base-content/65">
            {modeDescription(option.value)}
          </p>
        </div>
        <span
          className={`mt-1 h-3 w-3 shrink-0 rounded-full ${
            active ? "bg-primary shadow-[0_0_0_5px_rgba(168,85,247,0.16)]" : "bg-base-300"
          }`}
        />
      </div>

      {loading && (
        <div className="mt-3 flex items-center gap-2 text-xs text-primary">
          <span className="loading loading-spinner loading-xs" />
          Menyimpan mode...
        </div>
      )}
    </button>
  );
}

export default function RecordingLibrary() {
  const { user, loading: authLoading } = useAuth();
  const { showToast } = useToast();
  const isAdmin = user?.role === "ADMIN";
  const [recordings, setRecordings] = useState([]);
  const [selectedFilename, setSelectedFilename] = useState("");
  const [activeDateKey, setActiveDateKey] = useState("");
  const [archiveView, setArchiveView] = useState("folders");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [deletingFilename, setDeletingFilename] = useState("");
  const [downloadingFilename, setDownloadingFilename] = useState("");
  const [downloadingDateKey, setDownloadingDateKey] = useState("");
  const [lastSyncedAt, setLastSyncedAt] = useState("");
  const [videoLoadError, setVideoLoadError] = useState("");
  const [runtimeConfig, setRuntimeConfig] = useState(null);
  const [recordingValues, setRecordingValues] = useState({});
  const [originalRecordingValues, setOriginalRecordingValues] = useState({});
  const [configLoading, setConfigLoading] = useState(true);
  const [configSaving, setConfigSaving] = useState(false);
  const [savingMode, setSavingMode] = useState("");
  const [configError, setConfigError] = useState("");

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

  function syncRecordingConfig(data) {
    const pickedValues = pickRecordingValues(data.values || {});
    setRuntimeConfig(data);
    setRecordingValues(pickedValues);
    setOriginalRecordingValues(pickedValues);
  }

  async function loadRecordingConfig({ silent = false } = {}) {
    if (!isAdmin) {
      setConfigLoading(false);
      return;
    }

    if (!silent) setConfigLoading(true);
    setConfigError("");
    try {
      const data = await fetchRuntimeConfig();
      syncRecordingConfig(data);
    } catch (error) {
      const message = error.message || "Gagal memuat konfigurasi rekaman.";
      setConfigError(message);
      if (!silent) showToast("error", message);
    } finally {
      setConfigLoading(false);
    }
  }

  useEffect(() => {
    loadRecordings();

    const timer = window.setInterval(() => {
      loadRecordings({ silent: true });
    }, AUTO_REFRESH_MS);

    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!isAdmin) {
      setConfigLoading(false);
      return;
    }
    loadRecordingConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, isAdmin]);

  const recordingGroups = useMemo(() => {
    const grouped = new Map();

    recordings.forEach((recording) => {
      const dateKey = recordingDateKey(
        recording.recorded_from || recording.recorded_until || recording.uploaded_at,
      );
      if (!grouped.has(dateKey)) {
        grouped.set(dateKey, {
          dateKey,
          dateLabel: formatDateLabel(dateKey),
          items: [],
          totalSizeMb: 0,
          latestRecordedUntil: "",
        });
      }

      const group = grouped.get(dateKey);
      group.items.push(recording);
      group.totalSizeMb += Number(recording.size_mb || 0);
      group.latestRecordedUntil =
        group.latestRecordedUntil && group.latestRecordedUntil > (recording.recorded_until || "")
          ? group.latestRecordedUntil
          : recording.recorded_until || group.latestRecordedUntil;
    });

    return Array.from(grouped.values())
      .map((group) => ({
        ...group,
        items: group.items.sort((left, right) =>
          String(right.recorded_from || right.uploaded_at || "").localeCompare(
            String(left.recorded_from || left.uploaded_at || ""),
          ),
        ),
      }))
      .sort((left, right) => right.dateKey.localeCompare(left.dateKey));
  }, [recordings]);

  const activeDateGroup =
    recordingGroups.find((group) => group.dateKey === activeDateKey) ||
    recordingGroups[0] ||
    null;
  const activeGroupRecordings = activeDateGroup?.items || [];
  const isFolderView = archiveView === "folders";

  const selectedRecording =
    recordings.find((item) => item.filename === selectedFilename) || recordings[0] || null;
  const selectedRecordingUrl = selectedRecording ? buildRecordingUrl(selectedRecording) : "";
  const currentRecordingMode = recordingValues[RECORDING_SAVE_MODE_KEY] || "detection";
  const recordingItems = useMemo(() => {
    const itemByKey = new Map((runtimeConfig?.items || []).map((item) => [item.key, item]));
    return RECORDING_CONFIG_KEYS.map((key) => itemByKey.get(key)).filter(Boolean);
  }, [runtimeConfig]);
  const modeItem =
    recordingItems.find((item) => item.key === RECORDING_SAVE_MODE_KEY) || null;
  const recordingTuningItems = recordingItems.filter(
    (item) =>
      item.key !== RECORDING_SAVE_MODE_KEY && item.key !== "EDGE_RECORDING_ENABLED",
  );
  const recordingToggleItem =
    recordingItems.find((item) => item.key === "EDGE_RECORDING_ENABLED") || null;
  const changedRecordingValues = useMemo(() => {
    const changed = {};
    for (const key of RECORDING_CONFIG_KEYS) {
      if (
        String(recordingValues[key] ?? "") !==
        String(originalRecordingValues[key] ?? "")
      ) {
        changed[key] = recordingValues[key] ?? "";
      }
    }
    return changed;
  }, [recordingValues, originalRecordingValues]);
  const changedRecordingCount = Object.keys(changedRecordingValues).length;
  const recordingOverview = [
    {
      label: "Mode Aktif",
      value: formatRecordingMode(currentRecordingMode),
      tone: currentRecordingMode === "raw" ? "warning" : "primary",
    },
    {
      label: "Rekaman Otomatis",
      value: isTruthy(recordingValues.EDGE_RECORDING_ENABLED) ? "Aktif" : "Nonaktif",
      tone: isTruthy(recordingValues.EDGE_RECORDING_ENABLED) ? "success" : "ghost",
    },
    {
      label: "Durasi Segmen",
      value: formatConfigValue(
        recordingItems.find((item) => item.key === "EDGE_RECORDING_SEGMENT_MINUTES"),
        recordingValues.EDGE_RECORDING_SEGMENT_MINUTES || "10",
      ),
      tone: "secondary",
    },
    {
      label: "FPS Rekam",
      value: formatConfigValue(
        recordingItems.find((item) => item.key === "EDGE_RECORDING_FPS"),
        recordingValues.EDGE_RECORDING_FPS || "0",
      ),
      tone: "accent",
    },
  ];

  useEffect(() => {
    if (recordingGroups.length === 0) {
      setActiveDateKey("");
      setArchiveView("folders");
      return;
    }

    setActiveDateKey((current) => {
      if (current && recordingGroups.some((group) => group.dateKey === current)) {
        return current;
      }
      return recordingGroups[0].dateKey;
    });
  }, [recordingGroups]);

  useEffect(() => {
    if (!activeDateGroup || activeGroupRecordings.length === 0) return;
    if (selectedFilename && activeGroupRecordings.some((item) => item.filename === selectedFilename)) {
      return;
    }
    setSelectedFilename(activeGroupRecordings[0].filename);
  }, [activeDateGroup, activeGroupRecordings, selectedFilename]);

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

  function handleConfigChange(key, value) {
    setRecordingValues((current) => ({ ...current, [key]: value }));
    setConfigError("");
  }

  async function saveRecordingConfig(payload, successMessage) {
    if (!isAdmin) return;
    setConfigSaving(true);
    setConfigError("");
    try {
      const result = await updateRuntimeConfig(payload);
      syncRecordingConfig(result);
      showToast("success", successMessage || "Konfigurasi rekaman tersimpan.");
    } catch (error) {
      const message = error.message || "Gagal menyimpan konfigurasi rekaman.";
      setConfigError(message);
      showToast("error", message);
    } finally {
      setConfigSaving(false);
      setSavingMode("");
    }
  }

  async function handleSaveMode(mode) {
    setSavingMode(mode);
    await saveRecordingConfig(
      { ...changedRecordingValues, [RECORDING_SAVE_MODE_KEY]: mode },
      `Mode simpan rekaman: ${formatRecordingMode(mode)}.`,
    );
  }

  async function handleSaveRecordingConfig() {
    if (!changedRecordingCount) {
      showToast("info", "Tidak ada konfigurasi rekaman yang berubah.");
      return;
    }
    await saveRecordingConfig(changedRecordingValues);
  }

  async function handleDownloadRecording(filename) {
    setDownloadingFilename(filename);
    try {
      await downloadRecording(filename);
      showToast("success", `Unduhan rekaman "${filename}" dimulai.`);
    } catch (error) {
      showToast("error", error.message || "Gagal mengunduh rekaman.");
    } finally {
      setDownloadingFilename("");
    }
  }

  async function handleDownloadDateArchive(dateKey) {
    setDownloadingDateKey(dateKey);
    try {
      await downloadRecordingArchive(dateKey);
      showToast("success", `Unduhan arsip tanggal ${formatDateLabel(dateKey)} dimulai.`);
    } catch (error) {
      showToast("error", error.message || "Gagal mengunduh arsip per tanggal.");
    } finally {
      setDownloadingDateKey("");
    }
  }

  function handleSelectDateGroup(group) {
    setActiveDateKey(group.dateKey);
    setArchiveView("recordings");
    setVideoLoadError("");
    if (group.items[0]) {
      setSelectedFilename(group.items[0].filename);
    }
  }

  function handleBackToFolders() {
    setArchiveView("folders");
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
              Halaman ini khusus untuk melihat arsip rekaman CCTV yang dibuat
              otomatis dari hasil video yang sudah diproses. Setiap file berisi
              segmen rekaman 10 menit dan baru muncul setelah segmennya selesai
              disimpan.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isAdmin && (
              <Badge
                type={currentRecordingMode === "raw" ? "warning" : "success"}
                className="px-3 py-3"
              >
                Mode {formatRecordingMode(currentRecordingMode)}
              </Badge>
            )}
            <Badge type="secondary" className="px-3 py-3">
              Auto segment {recordingValues.EDGE_RECORDING_SEGMENT_MINUTES || 10} menit
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
        <Card
          compact
          className="border border-base-300 bg-base-100 shadow-none"
        >
          <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">
            Total Rekaman
          </p>
          <p className="mt-2 text-3xl font-bold">{summary.totalFiles}</p>
        </Card>
        <Card
          compact
          className="border border-base-300 bg-base-100 shadow-none"
        >
          <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">
            Total Ukuran
          </p>
          <p className="mt-2 text-3xl font-bold">
            {formatSize(summary.totalSizeMb)}
          </p>
        </Card>
        <Card
          compact
          className="border border-base-300 bg-base-100 shadow-none"
        >
          <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">
            Rekaman Terbaru
          </p>
          <p className="mt-2 text-sm font-medium text-base-content/80">
            {formatDateTime(summary.latestRecordedUntil)}
          </p>
        </Card>
      </div>

      {isAdmin && (
        <Section title="Konfigurasi Rekaman" className="mt-0">
          {configLoading ? (
            <div className="flex min-h-24 items-center justify-center">
              <span className="loading loading-dots loading-md" />
            </div>
          ) : (
            <div className="space-y-5">
              {configError && (
                <div className="rounded-xl border border-error/40 bg-error/10 px-4 py-3 text-sm text-error">
                  {configError}
                </div>
              )}

              <div className="rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/12 via-base-100 to-info/10 p-5">
                <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-base-content/50">
                      Kontrol Rekaman
                    </p>
                    <p className="mt-2 text-xl font-semibold text-base-content">
                      Atur bagaimana segmen CCTV disimpan dari halaman ini.
                    </p>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-base-content/65">
                      Ubah mode simpan, durasi segmen, dan parameter encoder tanpa
                      pindah ke halaman konfigurasi utama.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {recordingOverview.map((item) => (
                      <div
                        key={item.label}
                        className="rounded-2xl border border-base-300/80 bg-base-100/85 p-4"
                      >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-base-content/45">
                          {item.label}
                        </p>
                        <div className="mt-2 flex items-center justify-between gap-3">
                          <p className="text-base font-semibold text-base-content">
                            {item.value}
                          </p>
                          <Badge type={item.tone} size="sm">
                            Live
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
                <div className="space-y-4 rounded-2xl border border-base-300 bg-base-100/70 p-5">
                  <div className="space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-base-content/50">
                      Mode Simpan
                    </p>
                    <p className="text-lg font-semibold text-base-content">
                      Pilih format hasil rekaman
                    </p>
                    {modeItem?.hint && (
                      <p className="max-w-2xl text-sm leading-6 text-base-content/65">
                        {modeItem.hint}
                      </p>
                    )}
                  </div>

                  <div className="grid gap-3 lg:grid-cols-2">
                    {(modeItem?.options || []).map((option) => (
                      <RecordingModeOption
                        key={option.value}
                        option={option}
                        active={currentRecordingMode === option.value}
                        disabled={configSaving}
                        loading={savingMode === option.value}
                        onSelect={handleSaveMode}
                      />
                    ))}
                  </div>

                  {recordingToggleItem && (
                    <RecordingConfigField
                      item={recordingToggleItem}
                      value={recordingValues[recordingToggleItem.key] ?? ""}
                      changed={Object.prototype.hasOwnProperty.call(
                        changedRecordingValues,
                        recordingToggleItem.key,
                      )}
                      onChange={handleConfigChange}
                    />
                  )}
                </div>

                <div className="space-y-4 rounded-2xl border border-base-300 bg-base-100/70 p-5">
                  <div className="space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-base-content/50">
                      Tuning
                    </p>
                    <p className="text-lg font-semibold text-base-content">
                      Parameter segmen dan encoder
                    </p>
                    <p className="text-sm leading-6 text-base-content/65">
                      Setiap field menampilkan hint agar perubahan lebih aman dan
                      mudah dipahami.
                    </p>
                  </div>

                  <div className="grid gap-4">
                    {recordingTuningItems.map((item) => (
                      <RecordingConfigField
                        key={item.key}
                        item={item}
                        value={recordingValues[item.key] ?? ""}
                        changed={Object.prototype.hasOwnProperty.call(
                          changedRecordingValues,
                          item.key,
                        )}
                        onChange={handleConfigChange}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-4 rounded-2xl border border-base-300 bg-base-100/70 p-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge type={changedRecordingCount ? "warning" : "success"} outline>
                    {changedRecordingCount ? `${changedRecordingCount} perubahan` : "Siap"}
                  </Badge>
                  <Badge type="ghost" outline>
                    Tersimpan di runtime config
                  </Badge>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="ghost"
                    outline
                    size="sm"
                    isSubmit={false}
                    onClick={() => loadRecordingConfig()}
                    disabled={configSaving}
                  >
                    Muat Ulang Config
                  </Button>
                  <Button
                    size="sm"
                    isSubmit={false}
                    loading={configSaving && !savingMode}
                    disabled={!changedRecordingCount || configSaving}
                    onClick={handleSaveRecordingConfig}
                  >
                    Simpan Konfigurasi
                  </Button>
                </div>
              </div>
            </div>
          )}
        </Section>
      )}

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(360px,0.9fr)]">
        <Section title="Preview Rekaman" className="mt-0">
          {loading ? (
            <div className="flex min-h-[360px] items-center justify-center">
              <span className="loading loading-dots loading-lg"></span>
            </div>
          ) : !selectedRecording ? (
            <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-dashed border-base-300 bg-base-200/40 px-6 text-center">
              <p className="text-lg font-semibold">
                Belum ada rekaman tersedia
              </p>
              <p className="mt-2 max-w-lg text-sm text-base-content/60">
                Biarkan edge worker berjalan sampai satu segmen 10 menit
                selesai, lalu rekaman akan muncul di halaman ini.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {selectedRecording.preview_ready === false ? (
                <div className="flex aspect-video w-full flex-col items-center justify-center rounded-2xl border border-base-300 bg-black/70 px-6 text-center text-white">
                  <p className="text-lg font-semibold">
                    Preview sedang disiapkan
                  </p>
                  <p className="mt-2 max-w-lg text-sm text-white/70">
                    Rekaman ini masih dikonversi ke format yang kompatibel
                    dengan browser. Halaman akan mencoba memuat ulang otomatis
                    beberapa detik lagi.
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
                  <p className="mt-1 break-all text-sm font-medium">
                    {selectedRecording.filename}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-base-content/50">
                    Ukuran
                  </p>
                  <p className="mt-1 text-sm font-medium">
                    {formatSize(selectedRecording.size_mb)}
                  </p>
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
                <Badge type="secondary">
                  Segmen {selectedRecording.segment_minutes || 10} menit
                </Badge>
                {selectedRecording.camera_id && (
                  <Badge type="ghost">
                    Kamera {selectedRecording.camera_id}
                  </Badge>
                )}
                <a
                  href={selectedRecordingUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-ghost btn-sm"
                >
                  Buka Preview
                </a>
                <Button
                  variant="secondary"
                  size="sm"
                  outline
                  loading={downloadingFilename === selectedRecording.filename}
                  disabled={downloadingDateKey !== ""}
                  onClick={() => handleDownloadRecording(selectedRecording.filename)}
                  isSubmit={false}
                >
                  Unduh Video
                </Button>
                {activeDateGroup && (
                  <Button
                    variant="ghost"
                    size="sm"
                    outline
                    loading={downloadingDateKey === activeDateGroup.dateKey}
                    disabled={downloadingFilename !== ""}
                    onClick={() => handleDownloadDateArchive(activeDateGroup.dateKey)}
                    isSubmit={false}
                  >
                    Unduh Tanggal
                  </Button>
                )}
                {isAdmin && (
                  <Button
                    variant="error"
                    size="sm"
                    outline
                    loading={deletingFilename === selectedRecording.filename}
                    disabled={
                      deletingFilename !== "" &&
                      deletingFilename !== selectedRecording.filename
                    }
                    onClick={() => handleDelete(selectedRecording.filename)}
                    isSubmit={false}
                  >
                    Hapus
                  </Button>
                )}
              </div>
            </div>
          )}
        </Section>

        <Section title="Daftar Rekaman" className="mt-0 h-full">
          <div className="space-y-4">
            <div className="flex flex-col gap-3 rounded-2xl border border-base-300 bg-base-100/70 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
                {!isFolderView && (
              <div className="flex min-w-0 items-center gap-3">
                {!isFolderView && activeDateGroup && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm btn-square shrink-0"
                    aria-label="Kembali ke folder tanggal"
                    onClick={handleBackToFolders}
                  >
                    <BackChevronIcon />
                  </button>
                )}
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-base-content/45">
                    {isFolderView ? "Arsip Tanggal" : "Isi Arsip"}
                  </p>
                  <p className="mt-1 truncate text-lg font-semibold text-base-content">
                    {isFolderView
                      ? "Folder Rekaman"
                      : activeDateGroup?.dateLabel || "Daftar Rekaman"}
                  </p>
                  <p className="mt-1 text-sm text-base-content/65">
                    {isFolderView
                      ? "Pilih folder tanggal untuk membuka daftar recording pada hari tersebut."
                      : "Pilih recording untuk preview, unduh file asli, atau unduh arsip satu tanggal."}
                  </p>
                </div>
              </div>
                )}

              <div className="flex flex-wrap items-center gap-2 text-xs text-base-content/55">
                {!isFolderView && activeDateGroup ? (
                  <>
                    <Badge type="secondary" outline>
                      {activeGroupRecordings.length} video
                    </Badge>
                    <Badge type="ghost" outline>
                      {formatSize(activeDateGroup.totalSizeMb)}
                    </Badge>
                  </>
                ) : (
                  <Badge type="ghost" outline>
                    {recordingGroups.length} folder tanggal
                  </Badge>
                )}
                <span>Sinkron terakhir: {formatDateTime(lastSyncedAt)}</span>
              </div>
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
              <div className="rounded-2xl border border-base-300 bg-base-100/70 p-4">
                {isFolderView ? (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-base-content/45">
                          Pilih Folder
                        </p>
                        <p className="mt-1 text-sm text-base-content/70">
                          Sentuh satu folder tanggal untuk berpindah ke daftar recording di hari itu.
                        </p>
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                      {recordingGroups.map((group) => (
                        <div
                          key={group.dateKey}
                          className="rounded-2xl border border-base-300 bg-base-100 p-4 transition hover:border-primary/40 hover:bg-base-100"
                        >
                          <button
                            type="button"
                            className="w-full text-left"
                            onClick={() => handleSelectDateGroup(group)}
                          >
                            <div className="flex items-start gap-3">
                              <FolderArchiveIcon />
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="truncate text-sm font-semibold text-base-content">
                                    {group.dateLabel}
                                  </p>
                                </div>
                                <div className="mt-2 space-y-1 text-xs text-base-content/60">
                                  <p>{group.items.length} footage</p>
                                  <p>{formatSize(group.totalSizeMb)}</p>
                                  <p>
                                    Rekaman terakhir: {formatDateTime(group.latestRecordedUntil)}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </button>

                          <div className="mt-4 flex flex-wrap items-center gap-2">
                            <Button
                              variant="primary"
                              size="xs"
                              onClick={() => handleSelectDateGroup(group)}
                              isSubmit={false}
                            >
                              Buka Folder
                            </Button>
                            <Button
                              variant="secondary"
                              size="xs"
                              outline
                              loading={downloadingDateKey === group.dateKey}
                              disabled={downloadingFilename !== ""}
                              onClick={() => handleDownloadDateArchive(group.dateKey)}
                              isSubmit={false}
                            >
                              Unduh ZIP
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : activeDateGroup ? (
                  <div className="space-y-4">
                    <div className="flex flex-col gap-3 rounded-2xl border border-base-300 bg-base-100/80 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-base-content/45">
                            Arsip Aktif
                          </p>
                          <p className="mt-1 text-lg font-semibold text-base-content">
                            {activeDateGroup.dateLabel}
                          </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge type="secondary" outline>
                            {activeGroupRecordings.length} video
                          </Badge>
                          <Badge type="ghost" outline>
                            {formatSize(activeDateGroup.totalSizeMb)}
                          </Badge>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          outline
                          loading={downloadingDateKey === activeDateGroup.dateKey}
                          disabled={downloadingFilename !== ""}
                          onClick={() => handleDownloadDateArchive(activeDateGroup.dateKey)}
                          isSubmit={false}
                        >
                          Unduh Arsip Tanggal
                        </Button>
                      </div>
                    </div>

                    <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
                      {activeGroupRecordings.map((recording) => {
                        const active =
                          selectedRecording?.filename === recording.filename;
                        return (
                          <div
                            key={recording.filename}
                            className={`rounded-2xl border p-4 transition ${
                              active
                                ? "border-primary bg-primary/10 shadow-sm"
                                : "border-base-300 bg-base-100 hover:border-primary/40"
                            }`}
                          >
                            <div className="flex flex-col gap-4">
                              <button
                                type="button"
                                className="w-full text-left"
                                onClick={() => {
                                  setVideoLoadError("");
                                  setSelectedFilename(recording.filename);
                                }}
                              >
                                <div className="flex items-start gap-3">
                                  <VideoFileIcon />
                                  <div className="min-w-0 flex-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <p className="truncate text-sm font-semibold">
                                        {recording.filename}
                                      </p>
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
                                    <div className="mt-2 grid gap-1 text-xs text-base-content/60 sm:grid-cols-2">
                                      <p>Mulai: {formatDateTime(recording.recorded_from)}</p>
                                      <p>Selesai: {formatDateTime(recording.recorded_until)}</p>
                                      <p>Ukuran: {formatSize(recording.size_mb)}</p>
                                      <p>Kamera: {recording.camera_id || "-"}</p>
                                    </div>
                                  </div>
                                </div>
                              </button>

                              <div className="flex flex-wrap items-center gap-2">
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
                                  variant="secondary"
                                  size="xs"
                                  outline
                                  loading={downloadingFilename === recording.filename}
                                  disabled={downloadingDateKey !== ""}
                                  onClick={() => handleDownloadRecording(recording.filename)}
                                  isSubmit={false}
                                >
                                  Unduh
                                </Button>
                                {isAdmin && (
                                  <Button
                                    variant="error"
                                    size="xs"
                                    outline
                                    loading={deletingFilename === recording.filename}
                                    disabled={
                                      deletingFilename !== "" &&
                                      deletingFilename !== recording.filename
                                    }
                                    onClick={() => handleDelete(recording.filename)}
                                    isSubmit={false}
                                  >
                                    Hapus
                                  </Button>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </Section>
      </div>
    </div>
  );
}
