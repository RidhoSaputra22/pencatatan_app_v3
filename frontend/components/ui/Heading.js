export default function Heading({ level = 1, children, className = "" }) {
  const Tag = `h${level}`;
  const base =
    level === 1
      ? "text-2xl font-bold mb-2"
      : level === 2
        ? "text-xl font-semibold mb-2"
        : level === 3
          ? "text-lg font-semibold mb-2"
          : "text-base font-bold mb-2";
  return <Tag className={`${base} ${className}`}>{children}</Tag>;
}
