"use client";

import { useState, useEffect, useCallback } from "react";
import {
  startCapture,
  stopCapture,
  fetchCaptureStatus,
  testVideoSource,
} from "@/services/camera.service";
import Section from "@/components/ui/Section";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Badge from "@/components/ui/Badge";
import Alert from "@/components/ui/Alert";

/**
 * Manage server-side video capture (RTSP/webcam/file).
 * Replaces the need to run a separate Python client script.
 * Admin can start/stop capture and configure parameters from this panel.
 */
export default function StreamManager({ camera, onSourceChanged, externalSource }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [testResult, setTestResult] = useState(null);

  // Form state
  const [source, setSource] = useState("");
  const [quality, setQuality] = useState(80);
  const [maxFps, setMaxFps] = useState(15);
  const [maxWidth, setMaxWidth] = useState(960);

  // Poll capture status
  const refreshStatus = useCallback(async () => {
    try {
      const data = await fetchCaptureStatus();
      setStatus(data);
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    const interval = setInterval(refreshStatus, 3000);
    return () => clearInterval(interval);
  }, [refreshStatus]);

  // Prefill source from camera stream_url
  useEffect(() => {
    if (camera?.stream_url && !source) {
      setSource(camera.stream_url);
    }
  }, [camera, source]);

  // Accept external source from RTSP scanner
  useEffect(() => {
    if (externalSource) {
      setSource(externalSource);
    }
  }, [externalSource]);

  async function handleStart() {
    if (!source.trim()) {
      setError("Masukkan sumber video (RTSP URL, webcam index, atau file path)");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      await startCapture({
        source: source.trim(),
        quality,
        max_fps: maxFps,
        max_width: maxWidth,
      });
      setSuccess("Capture berhasil dimulai");
      await refreshStatus();
    } catch (e) {
      setError(e.message || "Gagal memulai capture");
    } finally {
      setLoading(false);
    }
  }

  async function handleStop() {
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      await stopCapture();
      setSuccess("Capture dihentikan");
      await refreshStatus();
    } catch (e) {
      setError(e.message || "Gagal menghentikan capture");
    } finally {
      setLoading(false);
    }
  }

  async function handleTest() {
    if (!source.trim()) {
      setError("Masukkan sumber video untuk ditest");
      return;
    }
    setTesting(true);
    setError("");
    setTestResult(null);
    try {
      const result = await testVideoSource(source.trim());
      setTestResult(result);
    } catch (e) {
      setError(e.message || "Gagal test sumber video");
    } finally {
      setTesting(false);
    }
  }

  const isRunning = status?.running === true;
  const hasFrame = status?.has_frame === true;

  return (
    <Section title="Stream Capture Manager">
      <p className="text-sm opacity-70 mb-4">
        Mulai capture video RTSP/webcam/file langsung dari server ini tanpa perlu menjalankan script terpisah.
        Frame yang di-capture akan tersedia di{" "}
        <code className="bg-base-200 px-1 rounded text-xs">/stream/capture</code>{" "}
        untuk diproses oleh edge worker (YOLOv5).
      </p>

      {/* Status Panel */}
      {status && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <div className="bg-base-200 rounded-lg p-3">
            <div className="text-xs opacity-60 mb-1">Status</div>
            <Badge
              type={isRunning ? (hasFrame ? "success" : "warning") : "neutral"}
            >
              {isRunning
                ? hasFrame
                  ? "Capturing"
                  : "Menunggu Frame..."
                : "Tidak Aktif"}
            </Badge>
          </div>
          <div className="bg-base-200 rounded-lg p-3">
            <div className="text-xs opacity-60 mb-1">FPS</div>
            <div className="font-mono font-semibold">
              {isRunning ? status.fps || 0 : "-"}
            </div>
          </div>
          <div className="bg-base-200 rounded-lg p-3">
            <div className="text-xs opacity-60 mb-1">Resolusi</div>
            <div className="font-mono font-semibold text-sm">
              {isRunning && status.resolution?.[0]
                ? `${status.resolution[0]}×${status.resolution[1]}`
                : "-"}
            </div>
          </div>
          <div className="bg-base-200 rounded-lg p-3">
            <div className="text-xs opacity-60 mb-1">Frame Count</div>
            <div className="font-mono font-semibold">
              {status.frame_version || 0}
            </div>
          </div>
        </div>
      )}

      {/* Error from running capture */}
      {status?.error && (
        <Alert type="warning" className="mb-3">
          {status.error}
        </Alert>
      )}

      {/* Active source indicator */}
      {isRunning && status.source && (
        <div className="flex items-center gap-2 mb-4 p-2 bg-success/10 rounded-lg border border-success/30">
          <span className="loading loading-ring loading-xs text-success"></span>
          <span className="text-sm">
            <strong>Sumber aktif:</strong>{" "}
            <code className="bg-base-200 px-1 rounded text-xs break-all">
              {status.source}
            </code>
          </span>
        </div>
      )}

      {/* Source Input */}
      <div className="grid gap-3">
        <div>
          <label className="block text-sm font-medium mb-1">
            Sumber Video
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              className="input input-bordered flex-1 text-sm"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="rtsp://ip:554/live  atau  0 (webcam)  atau  /path/video.mp4"
            />
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={handleTest}
              disabled={testing || !source.trim()}
            >
              {testing ? (
                <span className="loading loading-spinner loading-xs"></span>
              ) : (
                "🔍 Test"
              )}
            </button>
          </div>
        </div>

        {/* Test Result */}
        {testResult && (
          <div
            className={`text-sm p-2 rounded-lg border ${
              testResult.ok
                ? "bg-success/10 border-success/30 text-success"
                : "bg-error/10 border-error/30 text-error"
            }`}
          >
            {testResult.ok ? (
              <>
                ✅ Sumber video berhasil dibuka —{" "}
                {testResult.resolution && (
                  <span>
                    {testResult.resolution[0]}×{testResult.resolution[1]}
                  </span>
                )}
                {testResult.fps && <span> @ {testResult.fps} FPS</span>}
              </>
            ) : (
              <>❌ {testResult.error}</>
            )}
          </div>
        )}

        {/* Config */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-medium mb-1 opacity-70">
              Kualitas JPEG
            </label>
            <input
              type="number"
              className="input input-bordered input-sm w-full"
              value={quality}
              onChange={(e) => setQuality(Number(e.target.value))}
              min={1}
              max={100}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 opacity-70">
              Max FPS
            </label>
            <input
              type="number"
              className="input input-bordered input-sm w-full"
              value={maxFps}
              onChange={(e) => setMaxFps(Number(e.target.value))}
              min={1}
              max={60}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 opacity-70">
              Max Lebar (px)
            </label>
            <input
              type="number"
              className="input input-bordered input-sm w-full"
              value={maxWidth}
              onChange={(e) => setMaxWidth(Number(e.target.value))}
              min={320}
              max={1920}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          {!isRunning ? (
            <Button
              variant="success"
              size="sm"
              loading={loading}
              onClick={handleStart}
            >
              ▶ Mulai Capture
            </Button>
          ) : (
            <Button
              variant="error"
              size="sm"
              loading={loading}
              onClick={handleStop}
            >
              ⏹ Stop Capture
            </Button>
          )}
        </div>

        {error && <p className="text-error text-sm">{error}</p>}
        {success && <p className="text-success text-sm">{success}</p>}
      </div>

      {/* Info */}
      <div className="mt-4 p-3 bg-base-200 rounded-lg">
        <h4 className="text-sm font-semibold mb-2">Cara Penggunaan</h4>
        <ol className="text-xs space-y-1.5 list-decimal list-inside opacity-80">
          <li>
            Masukkan sumber video (RTSP URL, index webcam, atau path file)
          </li>
          <li>
            Klik <strong>&quot;Test&quot;</strong> untuk memverifikasi koneksi
          </li>
          <li>
            Klik <strong>&quot;Mulai Capture&quot;</strong> untuk memulai
          </li>
          <li>
            Set <code className="bg-base-300 px-1 rounded">EDGE_STREAM_URL</code> ke{" "}
            <code className="bg-base-300 px-1 rounded">
              http://localhost:8000/stream/capture
            </code>{" "}
            agar edge worker membaca dari capture ini
          </li>
        </ol>
      </div>
    </Section>
  );
}
