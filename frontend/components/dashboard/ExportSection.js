"use client";

import { useState } from "react";
import { API_BASE } from "@/lib/constants";
import { getToken } from "@/lib/utils";
import Section from "@/components/ui/Section";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";

/**
 * Export & print section with actual download and print functionality.
 */
export default function ExportSection({ filterFrom, filterTo, day }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  const fromDay = filterFrom || day;
  const toDay = filterTo || day;

  /**
   * Download CSV file from backend.
   */
  async function handleDownloadCSV() {
    setDownloading(true);
    setError("");
    try {
      const token = getToken();
      const res = await fetch(
        `${API_BASE}/api/reports/csv?from_day=${fromDay}&to_day=${toDay}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) {
        throw new Error("Gagal download CSV");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `laporan_pengunjung_${fromDay}_${toDay}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message || "Gagal download");
    } finally {
      setDownloading(false);
    }
  }

  /**
   * Print the current dashboard stats.
   */
  function handlePrint() {
    // Create a printable version of the stats
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      setError("Pop-up diblokir browser. Izinkan pop-up untuk mencetak.");
      return;
    }

    // Get all stats data from the page
    const statsGrid = document.querySelector("section.grid");
    const statsTable = document.querySelector("table");

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Laporan Pengunjung Perpustakaan</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 20px; color: #333; }
          h1 { font-size: 18px; margin-bottom: 5px; }
          h2 { font-size: 14px; color: #666; margin-bottom: 20px; }
          .info { font-size: 12px; color: #888; margin-bottom: 15px; }
          .stats-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 20px; }
          .stat-card { border: 1px solid #ddd; padding: 10px; border-radius: 4px; text-align: center; }
          .stat-card .label { font-size: 11px; color: #666; }
          .stat-card .value { font-size: 20px; font-weight: bold; margin: 5px 0; }
          table { width: 100%; border-collapse: collapse; margin-top: 15px; }
          th, td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 12px; }
          th { background: #f5f5f5; font-weight: bold; }
          .footer { margin-top: 30px; font-size: 11px; color: #999; border-top: 1px solid #eee; padding-top: 10px; }
          @media print { body { padding: 0; } }
        </style>
      </head>
      <body>
        <h1>Laporan Monitoring Pengunjung Perpustakaan</h1>
        <h2>Periode: ${fromDay} s/d ${toDay}</h2>
        <div class="info">Dicetak pada: ${new Date().toLocaleString("id-ID")}</div>
        ${statsGrid ? `<div>${statsGrid.outerHTML}</div>` : ""}
        ${statsTable ? statsTable.outerHTML : "<p>Tidak ada data tabel.</p>"}
        <div class="footer">
          Dokumen ini dicetak dari Sistem Monitoring Pengunjung Perpustakaan
        </div>
      </body>
      </html>
    `);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
    }, 500);
  }

  return (
    <div className="card bg-gradient-to-r from-base-100 to-primary/5 shadow-lg p-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h3 className="font-bold text-base-content/80 flex items-center gap-2 mb-1">
            <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Export & Cetak Laporan
          </h3>
          <p className="text-xs text-base-content/40">
            Periode: <strong className="text-base-content/60">{fromDay}</strong> s/d <strong className="text-base-content/60">{toDay}</strong>
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" loading={downloading} onClick={handleDownloadCSV}>
            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
            Download CSV
          </Button>
          <Button variant="primary" onClick={handlePrint}>
            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" /></svg>
            Cetak Laporan
          </Button>
        </div>
      </div>

      {error && <div className="mt-3"><Alert variant="error">{error}</Alert></div>}
    </div>
  );
}
