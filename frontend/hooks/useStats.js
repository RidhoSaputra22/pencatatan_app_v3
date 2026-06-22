"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { fetchSummary, fetchDaily, fetchStatsPerSecond } from "@/services/stats.service";
import { todayISO, formatDate } from "@/lib/utils";
import { POLL_INTERVAL } from "@/lib/constants";
import { useClientRuntimeConfig } from "@/hooks/useClientRuntimeConfig";

function getMonthStart(monthValue) {
  return `${monthValue}-01`;
}

function getMonthEnd(monthValue) {
  const [year, month] = monthValue.split("-").map(Number);
  const lastDay = new Date(year, month, 0).getDate();
  return `${monthValue}-${String(lastDay).padStart(2, "0")}`;
}

function buildAppliedPeriod({
  periodType,
  selectedDay,
  fromTime,
  toTime,
  fromMonth,
  toMonth,
  fromYear,
  toYear,
  today,
}) {
  if (periodType === "daily") {
    return {
      periodType,
      fromDate: selectedDay,
      toDate: selectedDay,
      fromTime,
      toTime,
      fromDateTime: `${selectedDay}T${fromTime}:00`,
      toDateTime: `${selectedDay}T${toTime}:59`,
      startAt: `${selectedDay}T${fromTime}:00`,
      endAt: `${selectedDay}T${toTime}:59`,
      displayLabel: `${selectedDay} ${fromTime} s/d ${toTime}`,
      summaryLabel: `Tanggal ${selectedDay}, jam ${fromTime} - ${toTime}`,
    };
  }

  if (periodType === "monthly") {
    const fromDate = getMonthStart(fromMonth);
    const rawToDate = getMonthEnd(toMonth);
    const toDate = rawToDate > today ? today : rawToDate;
    return {
      periodType,
      fromDate,
      toDate,
      fromTime: null,
      toTime: null,
      fromDateTime: null,
      toDateTime: null,
      startAt: `${fromDate}T00:00:00`,
      endAt: `${toDate}T23:59:59`,
      displayLabel: `${fromDate} s/d ${toDate}`,
      summaryLabel: `Bulan ${fromMonth} s/d ${toMonth}`,
    };
  }

  const fromDate = `${fromYear}-01-01`;
  const rawToDate = `${toYear}-12-31`;
  const toDate = rawToDate > today ? today : rawToDate;
  return {
    periodType,
    fromDate,
    toDate,
    fromTime: null,
    toTime: null,
    fromDateTime: null,
    toDateTime: null,
    startAt: `${fromDate}T00:00:00`,
    endAt: `${toDate}T23:59:59`,
    displayLabel: `${fromDate} s/d ${toDate}`,
    summaryLabel: `Tahun ${fromYear} s/d ${toYear}`,
  };
}

function shiftDate(dateValue, deltaDays) {
  const shifted = new Date(`${dateValue}T00:00:00`);
  shifted.setDate(shifted.getDate() + deltaDays);
  return formatDate(shifted);
}

function shiftDateTime(dateTimeValue, deltaDays) {
  const shifted = new Date(dateTimeValue);
  shifted.setDate(shifted.getDate() + deltaDays);
  const isoDate = formatDate(shifted);
  const hours = String(shifted.getHours()).padStart(2, "0");
  const minutes = String(shifted.getMinutes()).padStart(2, "0");
  const seconds = String(shifted.getSeconds()).padStart(2, "0");
  return `${isoDate}T${hours}:${minutes}:${seconds}`;
}

function getComparisonPeriod(period) {
  if (period.periodType === "daily") {
    const fromDateTime = shiftDateTime(period.fromDateTime, -1);
    const toDateTime = shiftDateTime(period.toDateTime, -1);
    return {
      fromDate: fromDateTime.slice(0, 10),
      toDate: toDateTime.slice(0, 10),
      fromDateTime,
      toDateTime,
    };
  }

  const from = new Date(`${period.fromDate}T00:00:00`);
  const to = new Date(`${period.toDate}T00:00:00`);
  const dayCount = Math.max(
    1,
    Math.round((to.getTime() - from.getTime()) / 86400000) + 1,
  );
  const comparisonTo = shiftDate(period.fromDate, -1);
  const comparisonFrom = shiftDate(comparisonTo, -(dayCount - 1));

  return {
    fromDate: comparisonFrom,
    toDate: comparisonTo,
    fromDateTime: null,
    toDateTime: null,
  };
}

function isAppliedPeriodLive(period, today) {
  if (period.toDate !== today) {
    return false;
  }

  return new Date(period.endAt).getTime() >= Date.now();
}

/**
 * Aggregate per-second data into hourly buckets.
 */
function aggregateHourly(perSecondData) {
  const buckets = {};
  for (let h = 0; h < 24; h++) {
    const label = String(h).padStart(2, "0") + ":00";
    buckets[label] = 0;
  }
  for (const r of perSecondData) {
    const hour = r.second.slice(11, 13) + ":00";
    if (buckets[hour] !== undefined) {
      buckets[hour] += r.count;
    }
  }
  const labels = Object.keys(buckets);
  const data = Object.values(buckets);
  return { labels, data };
}

function normalizeEntryStats(row) {
  if (!row) return row;
  const uniqueVisitors = Number(row.unique_visitors ?? row.total_in ?? 0);
  const totalOut = Number(row.total_out ?? 0);
  return {
    ...row,
    total_events: uniqueVisitors + totalOut,
    total_in: uniqueVisitors,
  };
}

function normalizeDailyStats(rows = []) {
  return rows.map(normalizeEntryStats);
}

function summarizeStatsRows(rows = [], date, currentInside = 0) {
  const normalizedRows = normalizeDailyStats(rows);

  return {
    date,
    total_events: normalizedRows.reduce(
      (sum, row) => sum + Number(row.total_events || 0),
      0,
    ),
    unique_visitors: normalizedRows.reduce(
      (sum, row) => sum + Number(row.unique_visitors ?? row.total_in ?? 0),
      0,
    ),
    total_in: normalizedRows.reduce(
      (sum, row) => sum + Number(row.total_in || 0),
      0,
    ),
    total_out: normalizedRows.reduce(
      (sum, row) => sum + Number(row.total_out || 0),
      0,
    ),
    current_inside: currentInside,
  };
}

/**
 * Compute insight data from stats.
 */
function computeInsights(totalEvents, comparisonEvents, hourlyData, totalIn, totalOut) {
  // Busier / quieter
  let busyLabel = null;
  let busyPercent = null;
  if (comparisonEvents > 0) {
    const diff = ((totalEvents - comparisonEvents) / comparisonEvents) * 100;
    busyPercent = Math.round(diff);
    busyLabel = diff >= 0 ? "ramai" : "sepi";
  }

  // Peak hour
  let peakHour = null;
  if (hourlyData && hourlyData.labels.length > 0) {
    let maxVal = 0;
    let maxIdx = 0;
    hourlyData.data.forEach((v, i) => {
      if (v > maxVal) { maxVal = v; maxIdx = i; }
    });
    if (maxVal > 0) {
      peakHour = hourlyData.labels[maxIdx];
    }
  }

  // In/Out ratio
  let ratio = null;
  if (totalOut > 0) {
    ratio = (totalIn / totalOut).toFixed(1);
  } else if (totalIn > 0) {
    ratio = totalIn.toString();
  }

  return { busyLabel, busyPercent, peakHour, ratio };
}

/**
 * Hook that polls stats every POLL_INTERVAL ms and exposes
 * summary + daily data with comparable-period deltas, hourly aggregation,
 * insights, and visits-like period filters.
 */
export function useStats() {
  const { clientPollingEnabled } = useClientRuntimeConfig();
  const [summary, setSummary] = useState(null);
  const [comparisonSummary, setComparisonSummary] = useState(null);
  const [daily, setDaily] = useState([]);
  const [perSecond, setPerSecond] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const today = useMemo(() => todayISO(), []);
  const currentMonth = today.slice(0, 7);
  const currentYear = today.slice(0, 4);

  const [periodType, setPeriodType] = useState("daily");
  const [selectedDay, setSelectedDay] = useState(today);
  const [fromTime, setFromTime] = useState("00:00");
  const [toTime, setToTime] = useState("23:59");
  const [fromMonth, setFromMonth] = useState(currentMonth);
  const [toMonth, setToMonth] = useState(currentMonth);
  const [fromYear, setFromYear] = useState(currentYear);
  const [toYear, setToYear] = useState(currentYear);
  const [appliedPeriod, setAppliedPeriod] = useState(() =>
    buildAppliedPeriod({
      periodType: "daily",
      selectedDay: today,
      fromTime: "00:00",
      toTime: "23:59",
      fromMonth: currentMonth,
      toMonth: currentMonth,
      fromYear: currentYear,
      toYear: currentYear,
      today,
    }),
  );

  const handleFromTimeChange = useCallback((value) => {
    setFromTime(value);
    setToTime((currentValue) => (value > currentValue ? value : currentValue));
  }, []);

  const handleToTimeChange = useCallback((value) => {
    setToTime(value);
    setFromTime((currentValue) => (value < currentValue ? value : currentValue));
  }, []);

  const handleFromMonthChange = useCallback((value) => {
    setFromMonth(value);
    setToMonth((currentValue) => (value > currentValue ? value : currentValue));
  }, []);

  const handleToMonthChange = useCallback((value) => {
    setToMonth(value);
    setFromMonth((currentValue) => (value < currentValue ? value : currentValue));
  }, []);

  const handleFromYearChange = useCallback((value) => {
    setFromYear(value);
    setToYear((currentValue) => (value > currentValue ? value : currentValue));
  }, []);

  const handleToYearChange = useCallback((value) => {
    setToYear(value);
    setFromYear((currentValue) => (value < currentValue ? value : currentValue));
  }, []);

  const applyPeriod = useCallback(() => {
    setAppliedPeriod(
      buildAppliedPeriod({
        periodType,
        selectedDay,
        fromTime,
        toTime,
        fromMonth,
        toMonth,
        fromYear,
        toYear,
        today,
      }),
    );
  }, [periodType, selectedDay, fromTime, toTime, fromMonth, toMonth, fromYear, toYear, today]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const isSingleDay = appliedPeriod.periodType === "daily";
      const targetDay = appliedPeriod.fromDate;
      const comparisonPeriod = getComparisonPeriod(appliedPeriod);

      const [dailyData, comparisonDailyData, summaryData] = await Promise.all([
        isSingleDay
          ? fetchDaily(targetDay, null, null, {
              fromDateTime: appliedPeriod.fromDateTime,
              toDateTime: appliedPeriod.toDateTime,
            })
          : fetchDaily(null, appliedPeriod.fromDate, appliedPeriod.toDate),
        fetchDaily(
          comparisonPeriod.fromDate,
          comparisonPeriod.fromDate,
          comparisonPeriod.toDate,
          {
            fromDateTime: comparisonPeriod.fromDateTime,
            toDateTime: comparisonPeriod.toDateTime,
          },
        ).catch(() => []),
        isSingleDay
          ? fetchSummary(targetDay, {
              fromDateTime: appliedPeriod.fromDateTime,
              toDateTime: appliedPeriod.toDateTime,
            }).catch(() => null)
          : Promise.resolve(null),
      ]);

      const normalizedDailyData = normalizeDailyStats(dailyData);
      setDaily(normalizedDailyData);
      setComparisonSummary(
        summarizeStatsRows(comparisonDailyData, comparisonPeriod.fromDate),
      );

      if (isSingleDay) {
        setSummary(
          summaryData
            ? normalizeEntryStats(summaryData)
            : summarizeStatsRows(normalizedDailyData, targetDay),
        );

        try {
          const ps = await fetchStatsPerSecond(targetDay, null, {
            fromDateTime: appliedPeriod.fromDateTime,
            toDateTime: appliedPeriod.toDateTime,
          });
          setPerSecond(ps || []);
        } catch {
          setPerSecond([]);
        }
      } else {
        setSummary(
          summarizeStatsRows(normalizedDailyData, appliedPeriod.fromDate),
        );
        setPerSecond([]);
      }

      setLastUpdatedAt(new Date());
    } catch (e) {
      setError(e.message || "Failed to load stats");
    } finally {
      setLoading(false);
    }
  }, [appliedPeriod]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (clientPollingEnabled !== true || !POLL_INTERVAL) {
      return undefined;
    }

    if (!isAppliedPeriodLive(appliedPeriod, today)) {
      return undefined;
    }

    const timerId = window.setInterval(load, POLL_INTERVAL);
    return () => window.clearInterval(timerId);
  }, [clientPollingEnabled, load, appliedPeriod, today]);

  const totalEvents = summary?.total_events ?? daily.reduce((s, r) => s + r.total_events, 0);
  const uniqueVisitors = summary?.unique_visitors ?? daily.reduce((s, r) => s + r.unique_visitors, 0);
  const totalIn = summary?.total_in ?? daily.reduce((s, r) => s + r.total_in, 0);
  const totalOut = summary?.total_out ?? daily.reduce((s, r) => s + r.total_out, 0);
  const currentInside = summary?.current_inside ?? 0;

  const comparisonTotalEvents = comparisonSummary?.total_events || 0;
  const comparisonUniqueVisitors = comparisonSummary?.unique_visitors || 0;
  const comparisonTotalIn = comparisonSummary?.total_in || 0;
  const comparisonTotalOut = comparisonSummary?.total_out || 0;

  // Compute change percentages
  const calcChange = (current, prev) => {
    if (!prev || prev === 0) return null;
    return Math.round(((current - prev) / prev) * 100);
  };
  const changePercents = {
    totalEvents: calcChange(totalEvents, comparisonTotalEvents),
    uniqueVisitors: calcChange(uniqueVisitors, comparisonUniqueVisitors),
    totalIn: calcChange(totalIn, comparisonTotalIn),
    totalOut: calcChange(totalOut, comparisonTotalOut),
    currentInside: null,
  };

  // Hourly aggregation from per-second data
  const hourlyData = useMemo(() => aggregateHourly(perSecond), [perSecond]);

  // Insights
  const insights = useMemo(
    () => computeInsights(totalEvents, comparisonTotalEvents, hourlyData, totalIn, totalOut),
    [totalEvents, comparisonTotalEvents, hourlyData, totalIn, totalOut]
  );

  const filterFrom = appliedPeriod.fromDate;
  const filterTo = appliedPeriod.toDate;
  const filterFromDateTime = appliedPeriod.fromDateTime;
  const filterToDateTime = appliedPeriod.toDateTime;
  const day = appliedPeriod.displayLabel;
  const isSingleDayView = appliedPeriod.periodType === "daily";
  const isCurrentDayView = isSingleDayView && appliedPeriod.fromDate === today;
  const isLivePeriod = isAppliedPeriodLive(appliedPeriod, today);

  return {
    day,
    today,
    summary,
    daily,
    perSecond,
    hourlyData,
    totalEvents,
    uniqueVisitors,
    totalIn,
    totalOut,
    currentInside,
    loading,
    changePercents,
    insights,
    lastUpdatedAt,
    clientPollingEnabled,
    error,
    reload: load,
    filterFrom,
    filterTo,
    filterFromDateTime,
    filterToDateTime,
    periodType,
    setPeriodType,
    selectedDay,
    setSelectedDay,
    fromTime,
    handleFromTimeChange,
    toTime,
    handleToTimeChange,
    fromMonth,
    handleFromMonthChange,
    toMonth,
    handleToMonthChange,
    fromYear,
    handleFromYearChange,
    toYear,
    handleToYearChange,
    appliedSummaryLabel: appliedPeriod.summaryLabel,
    applyPeriod,
    isSingleDayView,
    isCurrentDayView,
    isLivePeriod,
  };
}
