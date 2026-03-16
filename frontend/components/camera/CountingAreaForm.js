"use client";

import { useState, useEffect, useCallback } from "react";
import { createArea, updateArea } from "@/services/camera.service";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Button from "@/components/ui/Button";
import Section from "@/components/ui/Section";
import RoiEditor from "./RoiEditor";

const DIRECTION_OPTIONS = [
  { value: "BOTH", label: "BOTH (Masuk & Keluar)" },
  { value: "IN", label: "IN (Masuk saja)" },
  { value: "OUT", label: "OUT (Keluar saja)" },
];

const DEFAULT_ROI = [
  [50, 50],
  [1230, 50],
  [1230, 670],
  [50, 670],
];

/**
 * Form to create / edit a counting area (ROI) for a camera.
 * Uses the interactive RoiEditor with live camera feed.
 */
export default function CountingAreaForm({ areas = [], onSaved }) {
  const [areaName, setAreaName] = useState("Gate Masuk");
  const [roiPoints, setRoiPoints] = useState(DEFAULT_ROI);
  const [directionMode, setDirectionMode] = useState("BOTH");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [showJson, setShowJson] = useState(false);
  const [jsonEdit, setJsonEdit] = useState("");

  useEffect(() => {
    if (areas.length > 0) {
      const a = areas[0];
      setAreaName(a.name || "");
      setDirectionMode(a.direction_mode || "BOTH");
      const roi = a.roi_polygon;
      if (Array.isArray(roi) && roi.length > 0) {
        setRoiPoints(roi);
      }
    }
  }, [areas]);

  const handleRoiChange = useCallback((pts) => {
    setRoiPoints(pts);
    setOk("");
  }, []);

  // Toggle manual JSON editing
  const toggleJsonEdit = () => {
    if (!showJson) {
      setJsonEdit(JSON.stringify(roiPoints, null, 2));
    } else {
      // Try applying the edited JSON
      try {
        const parsed = JSON.parse(jsonEdit);
        if (Array.isArray(parsed)) {
          setRoiPoints(parsed);
        }
      } catch {
        // ignore invalid JSON
      }
    }
    setShowJson(!showJson);
  };

  async function handleSave() {
    setSaving(true);
    setError("");
    setOk("");

    if (roiPoints.length < 3) {
      setError("ROI minimal 3 titik. Klik pada kamera untuk menambah titik.");
      setSaving(false);
      return;
    }

    try {
      if (areas.length > 0) {
        await updateArea(areas[0].area_id, {
          name: areaName,
          roi_polygon: roiPoints,
          direction_mode: directionMode,
        });
      } else {
        await createArea({
          camera_id: 1,
          name: areaName,
          roi_polygon: roiPoints,
          direction_mode: directionMode,
        });
      }
      setOk("Counting area saved! Edge akan refresh config otomatis.");
      onSaved?.();
    } catch (e) {
      setError(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title="Area Hitung (Counting Area)">
      <div className="grid gap-4">
        {/* Name & Direction */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Input
            label="Nama Area"
            value={areaName}
            onChange={(e) => setAreaName(e.target.value)}
            placeholder="Gate Masuk"
          />
          <Select
            label="Direction Mode"
            options={DIRECTION_OPTIONS}
            value={directionMode}
            onChange={(e) => setDirectionMode(e.target.value)}
          />
        </div>

        {/* Interactive ROI Editor with live camera feed */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="label-text font-semibold ">
              ROI Polygon — Klik pada kamera untuk menambah titik
            </label>
            <button
              type="button"
              className="btn btn-xs btn-ghost"
              onClick={toggleJsonEdit}
            >
              {showJson ? "✓ Terapkan JSON" : "{ } Edit JSON"}
            </button>
          </div>
          <RoiEditor points={roiPoints} onChange={handleRoiChange} />
        </div>

        {/* Optional JSON editor */}
        {showJson && (
          <div>
            <textarea
              className="textarea textarea-bordered w-full font-mono text-xs"
              rows={4}
              value={jsonEdit}
              onChange={(e) => setJsonEdit(e.target.value)}
              placeholder='[[50,50],[1230,50],[1230,670],[50,670]]'
            />
            <p className="text-xs opacity-50 mt-1">
              Edit JSON secara manual, lalu klik "Terapkan JSON" untuk meng-update visual.
            </p>
          </div>
        )}

        {/* Save button */}
        <Button variant="secondary" loading={saving} onClick={handleSave}>
          Save Counting Area
        </Button>

        {error && <p className="text-error text-sm">{error}</p>}
        {ok && <p className="text-success text-sm">{ok}</p>}
      </div>
    </Section>
  );
}
