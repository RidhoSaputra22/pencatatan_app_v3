/**
 * Button component styled after ui-laravel/button.blade.php
 * @param {object} props
 * @param {"primary"|"secondary"|"accent"|"ghost"|"link"|"info"|"success"|"warning"|"error"|"neutral"} props.variant
 * @param {"xs"|"sm"|"md"|"lg"} props.size
 * @param {boolean} props.outline
 * @param {boolean} props.loading
 * @param {string} props.href
 * @param {boolean} props.disabled
 * @param {boolean} props.isSubmit
 * @param {string} props.className
 */
export default function Button({
  children,
  variant = "primary",
  size = "md",
  outline = false,
  loading = false,
  href = null,
  disabled = false,
  isSubmit = true,
  className = "",
  ...rest
}) {
  // DaisyUI class mapping
  const variantClass =
    {
      primary: "btn-primary",
      secondary: "btn-secondary",
      accent: "btn-accent",
      ghost: "btn-ghost",
      link: "btn-link",
      info: "btn-info",
      success: "btn-success",
      warning: "btn-warning",
      error: "btn-error",
      neutral: "btn-neutral",
    }[variant] || "btn-primary";

  const sizeClass =
    {
      xs: "btn-xs",
      sm: "btn-sm",
      md: "",
      lg: "btn-lg",
    }[size] || "";

  let classes = `btn ${variantClass} ${sizeClass} gap-2`;
  if (outline) classes += " btn-outline";
  if (className) classes += ` ${className}`;

  const content = (
    <>
      {loading && <span className="loading loading-spinner loading-sm" />}
      {children}
    </>
  );

  if (href) {
    return (
      <a href={href} className={classes} aria-disabled={disabled} {...rest}>
        {content}
      </a>
    );
  }

  return (
    <button
      type={isSubmit ? "submit" : "button"}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading}
      {...rest}
    >
      {content}
    </button>
  );
}
