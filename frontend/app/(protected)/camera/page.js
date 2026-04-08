"use client";

import { useAuth } from "@/context/AuthContext";
import { useCamera } from "@/hooks/useCamera";
import CameraForm from "@/components/camera/CameraForm";
import CountingAreaForm from "@/components/camera/CountingAreaForm";
import ConfigPreview from "@/components/camera/ConfigPreview";
import FootageUpload from "@/components/camera/FootageUpload";
import StreamingStatus from "@/components/camera/StreamingStatus";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";

export default function CameraPage() {
  const { user } = useAuth();
  const { camera, areas, error, reload } = useCamera(1);
  const isAdmin = user?.role === "ADMIN";

  return (
    <>
      <Heading level={1}>Konfigurasi Kamera</Heading>
      <div className="">

        {error && <Alert variant="error">{error}</Alert>}

        {isAdmin ? (
          <>
            <CountingAreaForm areas={areas} onSaved={reload} />
          </>
        ) : (
          /* Operator: read-only view of camera info */
          camera && (
            <Card className="mt-4 w-full">
              <Heading level={2} className="mb-3">
                Informasi Kamera
              </Heading>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="opacity-70">Nama:</span>{" "}
                  <strong>{camera.name}</strong>
                </div>
                <div>
                  <span className="opacity-70">Lokasi:</span>{" "}
                  <strong>{camera.location || "-"}</strong>
                </div>
                <div>
                  <span className="opacity-70">Stream URL:</span>{" "}
                  <strong className="break-all">
                    {camera.stream_url || "-"}
                  </strong>
                </div>
                <div>
                  <span className="opacity-70">Status:</span>{" "}
                  <Badge color={camera.is_active ? "success" : "error"}>
                    {camera.is_active ? "Aktif" : "Nonaktif"}
                  </Badge>
                </div>
              </div>
              {areas.length > 0 && (
                <div className="mt-4">
                  <Heading level={3} className="mb-2 text-sm">
                    Area Hitung:
                  </Heading>
                  {areas.map((a) => (
                    <div
                      key={a.area_id}
                      className="text-sm pl-3 border-l-2 border-success mb-2"
                    >
                      <strong>{a.name}</strong> — {a.direction_mode}{" "}
                      <Badge color={a.is_active ? "success" : "error"}>
                        {a.is_active ? "Aktif" : "Nonaktif"}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )
        )}
      </div>

      {/* Client Streaming Status */}
      <StreamingStatus />

      
    </>
  );
}
