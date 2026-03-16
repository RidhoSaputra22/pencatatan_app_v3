/**
 * Reusable labelled <textarea> using DaisyUI.
 */
/**
 * Textarea component styled after ui-laravel/textarea.blade.php
 * @param {object} props
 * @param {string} props.label
 * @param {string} props.placeholder
 * @param {string} props.value
 * @param {function} props.onChange
 * @param {string} props.error
 * @param {boolean} props.required
 * @param {number} props.rows
 * @param {string} props.className
 */
export default function Textarea({
  label,
  placeholder = "",
  value = "",
  onChange,
  error = null,
  required = false,
  rows = 4,
  className = "",
  name,
  ...rest
}) {
  return (
    <div className={`form-control w-full ${className}`}>
      {label && (
        <label className="label" htmlFor={name}>
          <span className="label-text">
            {label}
            {required && <span className="text-error ml-1">*</span>}
          </span>
        </label>
      )}
      <textarea
        id={name}
        name={name}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        required={required}
        rows={rows}
        className={`textarea textarea-bordered w-full font-mono${error ? " textarea-error" : ""}`}
        {...rest}
      />
      {error && (
        <label className="label">
          <span className="label-text-alt text-error">{error}</span>
        </label>
      )}
    </div>
  );
}
