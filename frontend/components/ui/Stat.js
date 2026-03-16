import React from "react";

/**
 * Stat card component styled after ui-laravel/stat.blade.php
 * @param {object} props
 * @param {string} props.title
 * @param {string|number} props.value
 * @param {string} props.description
 * @param {React.ReactNode} props.icon
 * @param {"up"|"down"|"neutral"} props.trend
 * @param {string} props.trendValue
 * @param {string} props.className
 */
export default function Stat({
  title,
  value,
  description = null,
  icon = null,
  trend = null,
  trendValue = null,
  className = "",
  ...rest
}) {
  return (
    <div className={`stat ${className}`} {...rest}>
      {icon && <div className="stat-figure text-primary">{icon}</div>}
      <div className="stat-title">{title}</div>
      <div className="stat-value text-primary">{value}</div>
      {(description || trend) && (
        <div className="stat-desc flex items-center gap-1">
          {trend === "up" && (
            <svg
              className="w-4 h-4 text-success"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
              />
            </svg>
          )}
          {trend === "down" && (
            <svg
              className="w-4 h-4 text-error"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"
              />
            </svg>
          )}
          {trendValue && (
            <span
              className={
                trend === "up"
                  ? "text-success"
                  : trend === "down"
                    ? "text-error"
                    : ""
              }
            >
              {trendValue}
            </span>
          )}
          {description}
        </div>
      )}
    </div>
  );
}
