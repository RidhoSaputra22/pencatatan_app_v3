/**
 * Card component styled after ui-laravel/card.blade.php
 * @param {object} props
 * @param {string} props.title
 * @param {boolean} props.compact
 * @param {string} props.href
 * @param {React.ReactNode} props.actions
 * @param {string} props.className
 * @param {React.ReactNode} props.children
 */
export default function Card({
  title,
  compact = false,
  href = null,
  actions = null,
  className = "",
  children,
  highlight = false,
  ...rest
}) {
  const hoverClass = href
    ? "cursor-pointer transition-shadow duration-200 hover:shadow-2xl hover:-translate-y-0.5 active:scale-[0.99]"
    : "";
  const highlightClass = highlight ? "ring-2 ring-primary" : "";
  const cardClass = `card bg-base-100 shadow-xl ${highlightClass} ${className} ${hoverClass}`;
  const bodyClass = `card-body${compact ? " p-4" : ""}`;

  const cardContent = (
    <div className={bodyClass}>
      {title && <h2 className="card-title">{title}</h2>}
      {children}
      {actions && (
        <div className="card-actions justify-end mt-4">{actions}</div>
      )}
    </div>
  );

  if (href) {
    return (
      <div className={cardClass} {...rest}>
        <a href={href} className="block">
          {cardContent}
        </a>
      </div>
    );
  }
  return (
    <div className={cardClass} {...rest}>
      {cardContent}
    </div>
  );
}
