"use client";

import { useState, useEffect } from "react";
import { fetchStreamRelayHealth } from "@/services/camera.service";
import Section from "@/components/ui/Section";
import Badge from "@/components/ui/Badge";
import Alert from "@/components/ui/Alert";

/**
 * Shows the status of the UDP stream relay.
 * Indicates whether a client is streaming CCTV footage to the server.
 */
export default function StreamingStatus() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function check() {
      try {
        const data = await fetchStreamRelayHealth();
        if (active) {
          setStatus(data);
          setError("");
        }
      } catch {
        if (active) {
          setStatus(null);
          setError("Tidak dapat terhubung ke stream relay.");
        }
      }
    }

    check();
    const interval = setInterval(check, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const isReceiving = status?.has_frame === true;
  const isWaiting = status && !status.has_frame;

  return (
    <Section title="Status Streaming Client (UDP)">
      <p className="text-sm opacity-70 mb-3">
        Menampilkan status penerimaan stream CCTV dari client melalui UDP.
        Client menjalankan <code className="bg-base-200 px-1 rounded text-xs">streamer.py</code> untuk mengirim
        footage ke server ini.
      </p>

      {error && <Alert variant="secondary" className="mb-3">{error}</Alert>}

      {status && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="bg-base-200 rounded-lg p-3">
            <div className="text-xs opacity-60 mb-1">Status</div>
            <Badge color={isReceiving ? "success" : isWaiting ? "warning" : "error"}>
              {isReceiving ? "Menerima Stream" : isWaiting ? "Menunggu Client" : "Tidak Aktif"}
            </Badge>
          </div>

          <div className="bg-base-200 rounded-lg p-3">
            <div className="text-xs opacity-60 mb-1">UDP Port</div>
            <div className="font-mono font-semibold">{status.udp_port}</div>
          </div>

          <div className="bg-base-200 rounded-lg p-3">
            <div className="text-xs opacity-60 mb-1">Frame Age</div>
            <div className="font-mono font-semibold">
              {status.frame_age_ms != null ? `${status.frame_age_ms} ms` : "-"}
            </div>
          </div>

          <div className="bg-base-200 rounded-lg p-3">
            <div className="text-xs opacity-60 mb-1">Frame Count</div>
            <div className="font-mono font-semibold">{status.frame_version || 0}</div>
          </div>
        </div>
      )}

      <div className="mt-4 p-3 bg-base-200 rounded-lg">
        <h4 className="text-sm font-semibold mb-2">Cara Streaming dari Client</h4>
        <ol className="text-xs space-y-1.5 list-decimal list-inside opacity-80">
          <li>
            Install Python & OpenCV di PC client:
            <code className="bg-base-300 px-1 rounded ml-1">pip install opencv-python numpy</code>
          </li>
          <li>
            Copy folder <code className="bg-base-300 px-1 rounded">client/</code> ke PC client
          </li>
          <li>
            Jalankan streamer:
            <div className="bg-base-300 rounded px-2 py-1 mt-1 font-mono break-all">
              python streamer.py --source 0 --server-ip {"<IP_SERVER>"} --server-port {status?.udp_port || 9999}
            </div>
          </li>
          <li>
            Opsi sumber video:
            <ul className="list-disc list-inside ml-3 mt-1 space-y-0.5">
              <li><code className="bg-base-300 px-1 rounded">--source 0</code> — Webcam</li>
              <li><code className="bg-base-300 px-1 rounded">--source rtsp://ip:554/live</code> — CCTV RTSP</li>
              <li><code className="bg-base-300 px-1 rounded">--source /path/video.mp4</code> — File rekaman</li>
            </ul>
          </li>
        </ol>
      </div>
    </Section>
  );
}
