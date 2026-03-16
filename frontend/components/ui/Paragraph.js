export default function Paragraph({ children, className = "" }) {
  return <p className={`text-sm opacity-70 ${className}`}>{children}</p>;
}
