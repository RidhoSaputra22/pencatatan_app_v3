import React from "react";

/**
 * Checkbox component styled after ui-laravel/checkbox.blade.php
 * @param {object} props
 * @param {string} props.name
 * @param {string} props.label
 * @param {Array<{value:string,label:string,disabled?:boolean}>} props.options
 * @param {Array<string>} props.checked
 * @param {boolean} props.required
 * @param {"horizontal"|"vertical"} props.layout
 * @param {string} props.helpText
 * @param {boolean} props.single
 * @param {function} props.onChange
 * @param {string} props.className
 * @param {string} props.error
 */
export default function Checkbox({
  name,
  label = null,
  options = [],
  checked = [],
  required = false,
  layout = "horizontal",
  helpText = null,
  single = false,
  onChange,
  className = "",
  error = null,
  ...rest
}) {
  // Handler for single or multiple
  const handleChange = (e) => {
    if (single) {
      onChange && onChange(e.target.checked ? ["1"] : []);
    } else {
      const value = e.target.value;
      if (e.target.checked) {
        onChange && onChange([...checked, value]);
      } else {
        onChange && onChange(checked.filter((v) => v !== value));
      }
    }
  };

  return (
    <div className={`form-control w-full ${className}`}>
      {label && (
        <label className="label">
          <span className="label-text">
            {label}
            {required && <span className="text-error ml-1">*</span>}
          </span>
        </label>
      )}
      {single ? (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            name={name}
            value="1"
            checked={checked.includes("1")}
            required={required}
            className="checkbox checkbox-primary"
            onChange={handleChange}
            {...rest}
          />
          <span className="label-text">{options[0]?.label || ""}</span>
        </label>
      ) : (
        <div
          className={`flex ${layout === "vertical" ? "flex-col" : "flex-wrap"} gap-4`}
        >
          {options.map((option) => (
            <label
              key={option.value}
              className={`flex items-center gap-2 cursor-pointer ${option.disabled ? "opacity-50" : ""}`}
            >
              <input
                type="checkbox"
                name={name}
                value={option.value}
                checked={checked.includes(option.value)}
                required={required}
                disabled={option.disabled}
                className="checkbox checkbox-primary"
                onChange={handleChange}
                {...rest}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      )}
      {helpText && (
        <label className="label">
          <span className="label-text-alt text-base-content/70">
            {helpText}
          </span>
        </label>
      )}
      {error && (
        <label className="label">
          <span className="label-text-alt text-error">{error}</span>
        </label>
      )}
    </div>
  );
}
