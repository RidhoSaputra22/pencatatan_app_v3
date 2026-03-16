import React from "react";

/**
 * Avatar component styled after ui-laravel/avatar.blade.php
 * @param {object} props
 * @param {string} props.name
 * @param {string} props.src
 * @param {"xs"|"sm"|"md"|"lg"|"xl"|"2xl"} props.size
 * @param {boolean} props.online
 * @param {boolean} props.ring
 * @param {string} props.className
 */
export default function Avatar({
  name = "User",
  src = null,
  size = "md",
  online = false,
  ring = false,
  className = "",
  ...rest
}) {
  // Generate initials from name
  const initials =
    name
      .split(" ")
      .slice(0, 2)
      .map((w) => w[0]?.toUpperCase() || "")
      .join("") || name.slice(0, 2).toUpperCase();

  const sizeClasses = {
    xs: "w-6",
    sm: "w-8",
    lg: "w-10",
    lg: "w-12",
    xl: "w-16",
    "2xl": "w-20",
  };
  const textSizes = {
    xs: "text-xs",
    sm: "text-xs",
    lg: "text-sm",
    lg: "text-base",
    xl: "text-lg",
    "2xl": "text-2xl",
  };
  const sizeClass = sizeClasses[size] || sizeClasses.md;
  const textSize = textSizes[size] || textSizes.md;

  return (
    <div
      className={`avatar${online ? " online" : ""}${ring ? " ring ring-primary ring-offset-base-100 ring-offset-2" : ""} ${className}`}
      {...rest}
    >
      <div
        className={`${sizeClass} rounded-full ${src ? "" : "bg-primary text-primary-content placeholder"} flex justify-center items-center`}
      >
        {src ? (
          <img src={src} alt={name} />
        ) : (
          <span className={textSize}>{initials}</span>
        )}
      </div>
    </div>
  );
}
