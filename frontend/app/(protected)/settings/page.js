"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import {
  fetchRuntimeConfig,
  updateRuntimeConfig,
} from "@/services/runtime-config.service";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Heading from "@/components/ui/Heading";

const SETTINGS_HIDDEN_GROUP_IDS = new Set(["recording"]);

function isTruthy(value) {
  return ["1", "true", "yes", "on"].includes(String(value).toLowerCase());
}

function groupItems(items) {
  return items.reduce((acc, item) => {
    if (!acc[item.group]) acc[item.group] = [];
    acc[item.group].push(item);
    return acc;
  }, {});
}

function fieldStep(item) {
  if (item.type === "int") return 1;
  if (item.type === "float") return item.max && item.max <= 1 ? 0.01 : 0.1;
  return undefined;
}

function fieldSurfaceClass(changed) {
  return [
    "group flex min-h-14 items-center overflow-hidden rounded-md border bg-base-100/80 shadow-sm transition",
    changed
      ? "border-primary/70 ring-1 ring-primary/20"
      : "border-base-300/90 hover:border-base-content/20",
    "focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/25",
  ].join(" ");
}

function InfoTooltip({ text, aliases = [] }) {
  if (!text && !aliases.length) return null;

  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        className="flex h-5 w-5 items-center justify-center rounded-full border border-base-content/25 text-[11px] font-bold leading-none text-base-content/60 transition hover:border-primary hover:bg-primary hover:text-primary-content focus:border-primary focus:bg-primary focus:text-primary-content focus:outline-none"
        aria-label="Info parameter"
      >
        i
      </button>
      <span className="pointer-events-none absolute left-0 top-7 z-40 hidden w-80 max-w-[calc(100vw-3rem)] rounded-md border border-base-300 bg-base-100 p-3 text-xs font-normal leading-relaxed text-base-content shadow-2xl group-hover:block group-focus-within:block">
        {text && <span>{text}</span>}
        {aliases.length > 0 && (
          <span className="mt-2 block border-t border-base-300/60 pt-2 font-mono text-[11px] text-base-content/60">
            Alias env: {aliases.join(", ")}
          </span>
        )}
      </span>
    </span>
  );
}

function ConfigField({ item, value, changed, onChange }) {
  const inputId = `config-${item.key}`;
  const commonLabel = (
    <div className="label pb-1">
      <span className="flex min-w-0 items-center gap-2">
        <label className="label-text truncate font-semibold" htmlFor={inputId}>
          {item.label}
        </label>
        <InfoTooltip text={item.hint || item.help} aliases={item.aliases || []} />
      </span>
      <span className="flex items-center gap-2">
        {changed && <Badge type="primary">Diubah</Badge>}
        <Badge type={item.restart_required ? "warning" : "success"} outline>
          {item.restart_required ? "Restart" : "Live"}
        </Badge>
      </span>
    </div>
  );

  let control = null;
  if (item.type === "bool") {
    control = (
      <label className={fieldSurfaceClass(changed)}>
        <span className="flex min-w-0 flex-1 items-center px-4 text-sm font-medium text-base-content/75">
          {isTruthy(value) ? "Aktif" : "Nonaktif"}
        </span>
        <span className="flex h-full items-center border-l border-base-300/80 bg-base-200/60 px-4">
          <input
            id={inputId}
            type="checkbox"
            className="toggle toggle-primary"
            checked={isTruthy(value)}
            onChange={(event) => onChange(item.key, event.target.checked ? "true" : "false")}
          />
        </span>
      </label>
    );
  } else if (item.type === "select") {
    control = (
      <div className={fieldSurfaceClass(changed)}>
        <select
          id={inputId}
          className="select w-full flex-1 border-0 bg-transparent pl-4 pr-4 text-base shadow-none outline-none focus:outline-none focus:ring-0"
          value={value ?? ""}
          onChange={(event) => onChange(item.key, event.target.value)}
        >
          {(item.options || []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    );
  } else {
    const isNumber = item.type === "int" || item.type === "float";
    control = (
      <div className={fieldSurfaceClass(changed)}>
        <input
          id={inputId}
          type={isNumber ? "number" : "text"}
          min={item.min}
          max={item.max}
          step={fieldStep(item)}
          className={[
            "input w-full flex-1 border-0 bg-transparent pl-4 shadow-none outline-none focus:outline-none focus:ring-0",
            item.unit ? "pr-3" : "pr-4",
          ].join(" ")}
          value={value ?? ""}
          onChange={(event) => onChange(item.key, event.target.value)}
        />
        {item.unit && (
          <span className="flex h-full shrink-0 items-center border-l border-base-300/80 bg-base-200/60 px-3 text-xs font-semibold uppercase tracking-[0.08em] text-base-content/55">
            {item.unit}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="form-control min-w-0">
      {commonLabel}
      <div className="min-w-0">{control}</div>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const isAdmin = user?.role === "ADMIN";
  const [config, setConfig] = useState(null);
  const [values, setValues] = useState({});
  const [originalValues, setOriginalValues] = useState({});
  const [activeGroup, setActiveGroup] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saveResult, setSaveResult] = useState(null);

  async function loadConfig() {
    if (!isAdmin) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const data = await fetchRuntimeConfig();
      setConfig(data);
      setValues(data.values || {});
      setOriginalValues(data.values || {});
      const visibleGroups = (data.groups || []).filter(
        (group) => !SETTINGS_HIDDEN_GROUP_IDS.has(group.id),
      );
      setActiveGroup((current) =>
        current && visibleGroups.some((group) => group.id === current)
          ? current
          : visibleGroups[0]?.id || "",
      );
      setSaveResult(null);
    } catch (err) {
      setError(err.message || "Gagal memuat konfigurasi runtime.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  const visibleGroups = useMemo(
    () => (config?.groups || []).filter((group) => !SETTINGS_HIDDEN_GROUP_IDS.has(group.id)),
    [config],
  );
  const visibleItems = useMemo(
    () =>
      (config?.items || []).filter((item) => !SETTINGS_HIDDEN_GROUP_IDS.has(item.group)),
    [config],
  );
  const itemsByGroup = useMemo(() => groupItems(visibleItems), [visibleItems]);
  const changedValues = useMemo(() => {
    const changed = {};
    for (const item of visibleItems) {
      if (String(values[item.key] ?? "") !== String(originalValues[item.key] ?? "")) {
        changed[item.key] = values[item.key] ?? "";
      }
    }
    return changed;
  }, [visibleItems, values, originalValues]);

  const changedCount = Object.keys(changedValues).length;
  const hasRestartChange = visibleItems.some(
    (item) => item.restart_required && Object.prototype.hasOwnProperty.call(changedValues, item.key),
  );

  function handleChange(key, value) {
    setValues((current) => ({ ...current, [key]: value }));
    setSaveResult(null);
  }

  async function handleSubmit(event) {
    event?.preventDefault();
    if (!changedCount) {
      showToast("info", "Tidak ada konfigurasi yang berubah.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const result = await updateRuntimeConfig(changedValues);
      setConfig(result);
      setValues(result.values || {});
      setOriginalValues(result.values || {});
      setSaveResult(result);
      showToast("success", "Konfigurasi runtime tersimpan.");
    } catch (err) {
      setError(err.message || "Gagal menyimpan konfigurasi runtime.");
      showToast("error", err.message || "Gagal menyimpan konfigurasi runtime.");
    } finally {
      setSaving(false);
    }
  }

  if (!isAdmin) {
    return (
      <>
        <Heading level={1}>Konfigurasi Runtime</Heading>
        <Alert type="warning">Hanya admin yang dapat mengubah konfigurasi sistem.</Alert>
      </>
    );
  }

  return (
    <>
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <Heading level={1} className="mb-1">
            Konfigurasi Runtime
          </Heading>
          <p className="text-sm text-base-content/60">
            YOLO, tracking, ReID, stream, dan face filtering.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="ghost"
            outline
            size="sm"
            isSubmit={false}
            onClick={loadConfig}
            disabled={loading || saving}
          >
            Muat Ulang
          </Button>
          <Button
            size="sm"
            isSubmit={false}
            onClick={handleSubmit}
            loading={saving}
            disabled={loading || !changedCount}
          >
            Simpan
          </Button>
        </div>
      </div>

      {error && <Alert type="error" className="mb-4">{error}</Alert>}
      {hasRestartChange && (
        <Alert type="warning" className="mb-4">
          Ada perubahan yang aktif setelah service terkait di-restart.
        </Alert>
      )}
      {saveResult?.changed?.length > 0 && (
        <Alert type={saveResult.restart_required ? "warning" : "success"} className="mb-4">
          {saveResult.changed.length} konfigurasi tersimpan
          {saveResult.restart_required ? "; sebagian membutuhkan restart." : " dan akan dipolling edge worker."}
        </Alert>
      )}

      <Card compact className="mb-5">
        <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
          <div>
            <div className="text-xs font-semibold uppercase text-base-content/40">
              File config {config?.storage_driver ? `(${config.storage_driver})` : ""}
            </div>
            <div className="mt-1 break-all font-mono text-xs">{config?.config_path || "-"}</div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase text-base-content/40">Perubahan</div>
            <div className="mt-1 text-lg font-bold">{changedCount}</div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase text-base-content/40">Status</div>
            <div className="mt-1">
              <Badge type={loading ? "warning" : "success"}>{loading ? "Memuat" : "Siap"}</Badge>
            </div>
          </div>
        </div>
      </Card>

      <div className="tabs tabs-boxed mb-5 w-full overflow-x-auto rounded-md bg-base-100 p-1">
        {visibleGroups.map((group) => (
          <button
            key={group.id}
            type="button"
            className={`tab whitespace-nowrap ${activeGroup === group.id ? "tab-active" : ""}`}
            onClick={() => setActiveGroup(group.id)}
          >
            {group.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit}>
        {loading ? (
          <Card>
            <div className="flex min-h-32 items-center justify-center">
              <span className="loading loading-spinner loading-md" />
            </div>
          </Card>
        ) : (
          visibleGroups
            .filter((group) => group.id === activeGroup)
            .map((group) => (
              <Card key={group.id}>
                <div className="mb-5 flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div>
                    <Heading level={2} className="mb-1">
                      {group.label}
                    </Heading>
                    <p className="text-sm text-base-content/55">{group.description}</p>
                  </div>
                  <Badge type="neutral" outline>
                    {(itemsByGroup[group.id] || []).length} item
                  </Badge>
                </div>
                <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
                  {(itemsByGroup[group.id] || []).map((item) => (
                    <ConfigField
                      key={item.key}
                      item={item}
                      value={values[item.key] ?? ""}
                      changed={Object.prototype.hasOwnProperty.call(changedValues, item.key)}
                      onChange={handleChange}
                    />
                  ))}
                </div>
                <div className="mt-6 flex justify-end">
                  <Button loading={saving} disabled={!changedCount || saving}>
                    Simpan Perubahan
                  </Button>
                </div>
              </Card>
            ))
        )}
      </form>
    </>
  );
}
