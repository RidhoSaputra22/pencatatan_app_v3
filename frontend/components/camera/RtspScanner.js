"use client";

import { useState, useEffect } from "react";
import {
  fetchSubnets,
  scanNetwork,
  testRtspUrl,
} from "@/services/camera.service";
import Section from "@/components/ui/Section";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import Alert from "@/components/ui/Alert";

/**
 * Scan the local network for RTSP cameras.
 * Admin can discover cameras, test their URLs, and use them as sources.
 */
export default function RtspScanner({ onSelectUrl }) {
  const [subnets, setSubnets] = useState([]);
  const [selectedSubnet, setSelectedSubnet] = useState("");
  const [customSubnet, setCustomSubnet] = useState("");
  const [scanning, setScanning] = useState(false);
  const [cameras, setCameras] = useState([]);
  const [error, setError] = useState("");
  const [testingUrl, setTestingUrl] = useState(null);
  const [testResults, setTestResults] = useState({});

  // Load subnets on mount
  useEffect(() => {
    async function loadSubnets() {
      try {
        const data = await fetchSubnets();
        setSubnets(data.subnets || []);
        if (data.subnets?.length > 0) {
          setSelectedSubnet(data.subnets[0]);
        }
      } catch {
        // Ignore — user can enter manually
      }
    }
    loadSubnets();
  }, []);

  async function handleScan() {
    const subnet = customSubnet.trim() || selectedSubnet;
    if (!subnet) {
      setError("Pilih atau masukkan subnet untuk di-scan");
      return;
    }
    setScanning(true);
    setError("");
    setCameras([]);
    setTestResults({});
    try {
      const data = await scanNetwork({ subnet });
      setCameras(data.cameras || []);
      if ((data.cameras || []).length === 0) {
        setError("Tidak ditemukan kamera RTSP di jaringan ini.");
      }
    } catch (e) {
      setError(e.message || "Gagal melakukan scan jaringan");
    } finally {
      setScanning(false);
    }
  }

  async function handleTestRtsp(url) {
    setTestingUrl(url);
    try {
      const result = await testRtspUrl(url);
      setTestResults((prev) => ({ ...prev, [url]: result }));
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [url]: { ok: false, error: "Gagal test" },
      }));
    } finally {
      setTestingUrl(null);
    }
  }

  function handleUseUrl(url) {
    onSelectUrl?.(url);
  }

  return (
    <Section title="Scan Jaringan RTSP">
      <p className="text-sm opacity-70 mb-4">
        Temukan kamera RTSP yang tersedia di jaringan lokal (LAN) server.
        Scanner akan memeriksa port RTSP umum (554, 8554) pada semua IP dalam subnet.
      </p>

      {/* Subnet Selection */}
      <div className="flex flex-col sm:flex-row gap-2 mb-4">
        <div className="flex-1">
          <label className="block text-xs font-medium mb-1 opacity-70">
            Subnet
          </label>
          <div className="flex gap-2">
            {subnets.length > 0 ? (
              <select
                className="select select-bordered select-sm flex-1"
                value={selectedSubnet}
                onChange={(e) => {
                  setSelectedSubnet(e.target.value);
                  setCustomSubnet("");
                }}
              >
                {subnets.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                className="input input-bordered input-sm flex-1"
                placeholder="192.168.1.0/24"
                value={customSubnet}
                onChange={(e) => setCustomSubnet(e.target.value)}
              />
            )}
            {subnets.length > 0 && (
              <input
                type="text"
                className="input input-bordered input-sm w-40"
                placeholder="Custom subnet..."
                value={customSubnet}
                onChange={(e) => setCustomSubnet(e.target.value)}
              />
            )}
          </div>
        </div>
        <div className="flex items-end">
          <Button
            variant="primary"
            size="sm"
            loading={scanning}
            onClick={handleScan}
          >
            {scanning ? "Scanning..." : "🔍 Scan Jaringan"}
          </Button>
        </div>
      </div>

      {scanning && (
        <div className="text-center py-6">
          <span className="loading loading-dots loading-lg"></span>
          <p className="text-sm opacity-70 mt-2">
            Scanning jaringan... ini bisa memakan waktu 10-30 detik.
          </p>
        </div>
      )}

      {error && !scanning && (
        <Alert type="warning" className="mb-3">
          {error}
        </Alert>
      )}

      {/* Results */}
      {cameras.length > 0 && !scanning && (
        <div className="border border-base-300 rounded-lg overflow-hidden">
          <div className="bg-base-200 px-4 py-2">
            <span className="text-sm font-semibold">
              📷 Kamera Ditemukan ({cameras.length})
            </span>
          </div>
          <div className="divide-y divide-base-300">
            {cameras.map((cam, idx) => {
              const tr = testResults[cam.url];
              return (
                <div
                  key={`${cam.ip}-${cam.port}-${idx}`}
                  className="px-4 py-3 hover:bg-base-200 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm">
                          {cam.ip}:{cam.port}
                        </span>
                        <Badge
                          type={
                            cam.status === "accessible"
                              ? "success"
                              : cam.status === "port_open"
                              ? "warning"
                              : "neutral"
                          }
                          size="xs"
                        >
                          {cam.status === "accessible"
                            ? "Accessible"
                            : cam.status === "port_open"
                            ? "Port Open"
                            : cam.status}
                        </Badge>
                      </div>
                      <div className="text-xs opacity-60 break-all">
                        {cam.url}
                      </div>
                      {cam.resolution && (
                        <div className="text-xs opacity-60 mt-0.5">
                          Resolusi: {cam.resolution[0]}×{cam.resolution[1]}
                        </div>
                      )}
                      {/* Test result */}
                      {tr && (
                        <div
                          className={`text-xs mt-1 ${
                            tr.ok ? "text-success" : "text-error"
                          }`}
                        >
                          {tr.ok
                            ? `✅ OK — ${tr.resolution?.[0]}×${tr.resolution?.[1]}`
                            : `❌ ${tr.error}`}
                        </div>
                      )}
                    </div>
                    <div className="flex gap-1.5 shrink-0">
                      <button
                        className="btn btn-outline btn-xs"
                        onClick={() => handleTestRtsp(cam.url)}
                        disabled={testingUrl === cam.url}
                      >
                        {testingUrl === cam.url ? (
                          <span className="loading loading-spinner loading-xs"></span>
                        ) : (
                          "Test"
                        )}
                      </button>
                      <button
                        className="btn btn-primary btn-xs"
                        onClick={() => handleUseUrl(cam.url)}
                      >
                        Gunakan
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Manual RTSP URL input */}
      <div className="mt-4 p-3 bg-base-200 rounded-lg">
        <h4 className="text-sm font-semibold mb-2">Format RTSP Umum</h4>
        <div className="text-xs space-y-1 opacity-80">
          <div>
            <strong>Hikvision:</strong>{" "}
            <code className="bg-base-300 px-1 rounded">
              rtsp://user:pass@IP:554/Streaming/Channels/101
            </code>
          </div>
          <div>
            <strong>Dahua:</strong>{" "}
            <code className="bg-base-300 px-1 rounded">
              rtsp://user:pass@IP:554/cam/realmonitor?channel=1&subtype=0
            </code>
          </div>
          <div>
            <strong>Generic:</strong>{" "}
            <code className="bg-base-300 px-1 rounded">
              rtsp://user:pass@IP:554/live/ch00_0
            </code>
          </div>
        </div>
      </div>
    </Section>
  );
}
