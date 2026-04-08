"use client";

import { useState, useEffect, useCallback } from "react";
import { createArea, updateArea } from "@/services/camera.service";
import Button from "@/components/ui/Button";
import Section from "@/components/ui/Section";
import { useToast } from "@/context/ToastContext";
import RoiEditor from "./RoiEditor";

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
  const { showToast } = useToast();
  const [areaName, setAreaName] = useState("");
  const [roiPoints, setRoiPoints] = useState(DEFAULT_ROI);
  const [directionMode, setDirectionMode] = useState("BOTH");
  const [saving, setSaving] = useState(false);
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

    if (roiPoints.length < 3) {
      showToast("error", "ROI minimal 3 titik. Klik pada kamera untuk menambah titik.");
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
      showToast("success", "Counting area saved! Edge akan refresh config otomatis.");
      onSaved?.();
    } catch (e) {
      showToast("error", e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title="Area Hitung (Counting Area)">
      <div className="">
        {/* Interactive ROI Editor with live camera feed */}
        <div className="">
          <div className="flex items-center justify-between mb-2">
            <label className="label-text font-semibold ">
              ROI Polygon — Klik pada kamera untuk menambah titik
            </label>
            <button
              type="button"
              className="btn btn-xs btn-ghost"
              onClick={toggleJsonEdit}
            ></button>
            <Button variant="primary" loading={saving} onClick={handleSave}>
              Save Counting Area
            </Button>
          </div>
          <RoiEditor points={roiPoints} onChange={handleRoiChange} />
        </div>
      
      </div>
    </Section>
  );
}
