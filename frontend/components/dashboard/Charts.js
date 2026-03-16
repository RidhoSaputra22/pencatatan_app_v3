import { Line, Doughnut } from "react-chartjs-2";
import { useEffect, useRef, useState } from "react";
import { fetchStatsPerSecond } from "@/services/stats.service";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Tooltip,
  Legend,
);

// Jika pollingInterval & day diberikan, LineChart akan polling data per second dari API
export function LineChart({ labels, data, label, pollingInterval, day }) {
  const [liveLabels, setLiveLabels] = useState(labels || []);
  const [liveData, setLiveData] = useState(data || []);
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

  const chartData = {
    labels: pollingInterval && day ? liveLabels : labels,
    datasets: [
      {
        label: label || "Statistik",
        data: pollingInterval && day ? liveData : data,
        fill: false,
        borderColor: "#6366f1",
        backgroundColor: "#6366f1",
        tension: 0.3,
      },
    ],
  };
  return <Line data={chartData} />;
}

export function DoughnutChart({
  labels,
  data,
  label,
  pollingInterval,
  day,
  type = "total",
}) {
  // type: "total" (default, pakai data prop), "event", "masuk", "keluar" (khusus polling per second)
  const [liveData, setLiveData] = useState(data || []);
  const timer = useRef(null);

  useEffect(() => {
    if (pollingInterval && day) {
      let stopped = false;
      async function poll() {
        try {
          const res = await fetchStatsPerSecond(day);
          // Akumulasi sesuai type
          let donutData = data || [];
          if (type === "event") {
            // Total event per detik
            donutData = [res.reduce((sum, r) => sum + r.count, 0)];
          }
          // Untuk pengembangan lebih lanjut: jika backend support masuk/keluar per second, bisa dipecah di sini
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
        borderWidth: 1,
      },
    ],
  };
  return <Doughnut data={chartData} />;
}
