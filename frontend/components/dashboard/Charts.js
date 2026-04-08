import { Line, Bar, Doughnut } from "react-chartjs-2";
import { useEffect, useRef, useState, useMemo } from "react";
import { fetchStatsPerSecond } from "@/services/stats.service";
import { formatNumber } from "@/lib/utils";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
);

// Gradient helper
function createGradient(ctx, chartArea, colorStart, colorEnd) {
  if (!chartArea) return colorStart;
  const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
  gradient.addColorStop(0, colorEnd);
  gradient.addColorStop(1, colorStart);
  return gradient;
}

export function LineChart({ labels, data, label, pollingInterval, day, color = "#6366f1" }) {
  const [liveLabels, setLiveLabels] = useState(labels || []);
  const [liveData, setLiveData] = useState(data || []);
  const chartRef = useRef(null);
  const timer = useRef(null);

  useEffect(() => {
    if (pollingInterval && day) {
      let stopped = false;
      async function poll() {
        try {
          const res = await fetchStatsPerSecond(day);
          if (!stopped) {
            setLiveLabels(res.map((r) => r.second.slice(11, 19)));
            setLiveData(res.map((r) => r.count));
          }
        } catch {}
        if (!stopped) {
          timer.current = setTimeout(poll, pollingInterval);
        }
      }
      poll();
      return () => {
        stopped = true;
        if (timer.current) clearTimeout(timer.current);
      };
    } else {
      setLiveLabels(labels || []);
      setLiveData(data || []);
    }
  }, [pollingInterval, day, labels, data]);

  const finalLabels = pollingInterval && day ? liveLabels : labels;
  const finalData = pollingInterval && day ? liveData : data;

  const chartData = {
    labels: finalLabels,
    datasets: [
      {
        label: label || "Statistik",
        data: finalData,
        fill: true,
        borderColor: color,
        backgroundColor: (context) => {
          const chart = context.chart;
          const { ctx, chartArea } = chart;
          if (!chartArea) return color + "1a";
          return createGradient(ctx, chartArea, color + "40", color + "05");
        },
        pointBackgroundColor: color,
        pointBorderColor: "#fff",
        pointBorderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointHoverBackgroundColor: color,
        pointHoverBorderColor: "#fff",
        pointHoverBorderWidth: 3,
        tension: 0.4,
        borderWidth: 2.5,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: true,
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "rgba(30, 30, 40, 0.9)",
        titleFont: { size: 12, weight: "bold" },
        bodyFont: { size: 11 },
        padding: 12,
        cornerRadius: 8,
        displayColors: false,
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${formatNumber(ctx.parsed.y)}`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: { size: 10 }, maxTicksLimit: 10, color: "#9ca3af" },
        border: { display: false },
      },
      y: {
        grid: { color: "rgba(229, 231, 235, 0.5)", drawBorder: false },
        beginAtZero: true,
        ticks: { font: { size: 10 }, color: "#9ca3af", padding: 8 },
        border: { display: false },
      },
    },
  };

  return (
    <div className="relative">
      <Line ref={chartRef} data={chartData} options={options} />
    </div>
  );
}

export function StackedBarChart({ labels, dataIn, dataOut }) {
  const chartData = {
    labels,
    datasets: [
      {
        label: "Pengunjung Masuk",
        data: dataIn,
        backgroundColor: "rgba(34, 197, 94, 0.85)",
        hoverBackgroundColor: "#22c55e",
        borderRadius: 4,
        borderSkipped: false,
      },
      {
        label: "Pengunjung Keluar",
        data: dataOut,
        backgroundColor: "rgba(239, 68, 68, 0.85)",
        hoverBackgroundColor: "#ef4444",
        borderRadius: 4,
        borderSkipped: false,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: true,
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          font: { size: 11, weight: "500" },
          padding: 16,
          usePointStyle: true,
          pointStyle: "roundRect",
        },
      },
      tooltip: {
        backgroundColor: "rgba(30, 30, 40, 0.9)",
        titleFont: { size: 12, weight: "bold" },
        bodyFont: { size: 11 },
        padding: 12,
        cornerRadius: 8,
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${formatNumber(ctx.parsed.y)}`,
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        grid: { display: false },
        ticks: { font: { size: 10 }, maxTicksLimit: 12, color: "#9ca3af" },
        border: { display: false },
      },
      y: {
        stacked: true,
        grid: { color: "rgba(229, 231, 235, 0.5)", drawBorder: false },
        beginAtZero: true,
        ticks: { font: { size: 10 }, color: "#9ca3af", padding: 8 },
        border: { display: false },
      },
    },
  };

  return <Bar data={chartData} options={options} />;
}

export function InOutDoughnutChart({ totalIn, totalOut }) {
  const total = totalIn + totalOut;
  const inPercent = total > 0 ? Math.round((totalIn / total) * 100) : 0;
  const outPercent = total > 0 ? 100 - inPercent : 0;

  const chartData = {
    labels: ["Masuk", "Keluar"],
    datasets: [
      {
        data: [totalIn, totalOut],
        backgroundColor: ["#22c55e", "#ef4444"],
        hoverBackgroundColor: ["#16a34a", "#dc2626"],
        borderWidth: 0,
        cutout: "72%",
        borderRadius: 6,
        spacing: 3,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "rgba(30, 30, 40, 0.9)",
        titleFont: { size: 12, weight: "bold" },
        bodyFont: { size: 11 },
        padding: 12,
        cornerRadius: 8,
        callbacks: {
          label: (ctx) => {
            const pct = total > 0 ? Math.round((ctx.parsed / total) * 100) : 0;
            return `${ctx.label}: ${formatNumber(ctx.parsed)} (${pct}%)`;
          },
        },
      },
    },
  };

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative w-44 h-44">
        <Doughnut data={chartData} options={options} />
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-extrabold text-base-content">{inPercent}%</span>
          <span className="text-xs text-base-content/50 font-medium">Masuk</span>
        </div>
      </div>
      <div className="flex gap-6 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-success"></span>
          <span className="font-semibold text-success">{inPercent}%</span>
          <span className="text-base-content/50">Masuk</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-error"></span>
          <span className="font-semibold text-error">{outPercent}%</span>
          <span className="text-base-content/50">Keluar</span>
        </div>
      </div>
    </div>
  );
}

export function DoughnutChart({
  labels,
  data,
  label,
  pollingInterval,
  day,
  type = "total",
}) {
  const [liveData, setLiveData] = useState(data || []);
  const timer = useRef(null);

  useEffect(() => {
    if (pollingInterval && day) {
      let stopped = false;
      async function poll() {
        try {
          const res = await fetchStatsPerSecond(day);
          let donutData = data || [];
          if (type === "event") {
            donutData = [res.reduce((sum, r) => sum + r.count, 0)];
          }
          if (!stopped) setLiveData(donutData);
        } catch {}
        if (!stopped) {
          timer.current = setTimeout(poll, pollingInterval);
        }
      }
      poll();
      return () => {
        stopped = true;
        if (timer.current) clearTimeout(timer.current);
      };
    } else {
      setLiveData(data || []);
    }
  }, [pollingInterval, day, data, type]);

  const chartData = {
    labels,
    datasets: [
      {
        label: label || "Distribusi",
        data: pollingInterval && day ? liveData : data,
        backgroundColor: [
          "#6366f1",
          "#06b6d4",
          "#f59e42",
          "#ef4444",
          "#22c55e",
        ],
        borderWidth: 0,
        cutout: "65%",
        borderRadius: 4,
        spacing: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          font: { size: 11, weight: "500" },
          padding: 12,
          usePointStyle: true,
          pointStyle: "circle",
        },
      },
      tooltip: {
        backgroundColor: "rgba(30, 30, 40, 0.9)",
        padding: 12,
        cornerRadius: 8,
      },
    },
  };

  return <Doughnut data={chartData} options={options} />;
}
