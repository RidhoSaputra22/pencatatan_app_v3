"use client";

import { useState, useEffect } from "react";
import { updateCamera, discoverCameras } from "@/services/camera.service";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import Section from "@/components/ui/Section";
import { useToast } from "@/context/ToastContext";

/**
 * Form to edit camera settings (name, location, stream_url).
 * Includes "Find Cameras" to detect active video devices on the system.
 */
export default function CameraForm({ camera, onSaved }) {
  const { showToast } = useToast();
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [streamUrl, setStreamUrl] = useState("");
  const [saving, setSaving] = useState(false);

  // Camera discovery state
  const [discovering, setDiscovering] = useState(false);
  const [devices, setDevices] = useState([]);
  const [showDevices, setShowDevices] = useState(false);

  useEffect(() => {
    if (camera) {
      setName(camera.name || "");
      setLocation(camera.location || "");
      setStreamUrl(camera.stream_url || "");
    }
  }, [camera]);

  async function handleDiscover() {
    setDiscovering(true);
    setDevices([]);
    setShowDevices(true);
    try {
      const found = await discoverCameras();
      setDevices(found);
      if (found.length === 0) {
        showToast("warning", "Tidak ditemukan kamera yang aktif di komputer ini.");
      }
    } catch (e) {
      showToast("error", e.message || "Gagal mendeteksi kamera");
    } finally {
      setDiscovering(false);
    }
  }

  function handleSelectDevice(device) {
    setStreamUrl(String(device.index));
    setShowDevices(false);
    showToast("success",
      `Kamera "${device.name}" (${device.device}) dipilih — index ${device.index}`,
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      await updateCamera(1, {
        name: name || null,
        location: location || null,
        stream_url: streamUrl || null,
      });
      showToast("success", "Camera saved. Edge will refresh config automatically.");
      onSaved?.();
    } catch (e) {
      showToast("error", e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const statusBadge = (status) => {
    const map = {
      available: {
        color: "bg-green-100 text-green-800 border-green-300",
        label: "Tersedia",
      },
      "no-frame": {
        color: "bg-yellow-100 text-yellow-800 border-yellow-300",
        label: "No Frame",
      },
      unavailable: {
        color: "bg-red-100 text-red-800 border-red-300",
        label: "Tidak Tersedia",
      },
      error: {
        color: "bg-red-100 text-red-800 border-red-300",
        label: "Error",
      },
      unknown: {
        color: "bg-gray-100 text-gray-800 border-gray-300",
        label: "Unknown",
      },
    };
    const s = map[status] || map.unknown;
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full border ${s.color}`}>
        {s.label}
      </span>
    );
  };

  return (
    <Section title="Camera Settings (ID=1)">
      <div className="grid gap-4">
        <Input
          label="Nama Kamera"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Masukkan nama kamera"
        />
        <Input
          label="Lokasi"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Masukkan lokasi kamera"
        />

        {/* Stream URL + Find Cameras */}
        <div>
          <label className="block text-sm font-medium mb-1">Stream URL</label>
          <div className="flex gap-2">
            <Input
              type="text"
              className="input input-bordered flex-1"
              value={streamUrl}
              onChange={(e) => setStreamUrl(e.target.value)}
              placeholder="0 (webcam) atau rtsp://ip:port/stream atau http://..."
            />
            <button
              type="button"
              onClick={handleDiscover}
              disabled={discovering}
              className="btn btn-outline"
            >
              {discovering ? (
                <>
                  <span className="loading loading-spinner loading-xs mr-1"></span>
                  Scanning...
                </>
              ) : (
                <>🔍 Find Cameras</>
              )}
            </button>
          </div>
        </div>

        {/* Device discovery results */}
        {showDevices && (
          <div className="border border-base-300 rounded-sm overflow-hidden">
            <div className="bg-base-200 px-4 py-2 flex justify-between items-center">
              <span className="text-sm font-semibold">
                📷 Kamera Terdeteksi{" "}
                {devices.length > 0 && `(${devices.length})`}
              </span>
              <button
                type="button"
                onClick={() => setShowDevices(false)}
                className="btn btn-ghost btn-xs"
              >
                ✕
              </button>
            </div>
            {discovering ? (
              <div className="p-4 text-center text-sm text-gray-500">
                <span className="loading loading-dots loading-md"></span>
                <p className="mt-2">
                  Mendeteksi kamera... ini mungkin perlu beberapa detik.
                </p>
              </div>
            ) : devices.length === 0 ? (
              <div className="p-4 text-center text-sm text-gray-500">
                Tidak ada kamera terdeteksi.
              </div>
            ) : (
              <div className="divide-y divide-base-300">
                {devices.map((d) => (
                  <div
                    key={d.device}
                    className="flex items-center justify-between px-4 py-3 hover:bg-base-200 transition-colors"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{d.name}</span>
                        {statusBadge(d.status)}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {d.device} — index: {d.index}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSelectDevice(d)}
                      disabled={
                        d.status === "unavailable" || d.status === "error"
                      }
                      className="btn btn-primary btn-xs"
                    >
                      Pilih
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <Button variant="primary" loading={saving} onClick={handleSave}>
          Save Camera
        </Button>
      </div>
    </Section>
  );
}
