/**
 * Reusable content section using DaisyUI card.
 */
export default function Section({ title, children, className = "", danger = false }) {
  return (
    <section
      className={`card bg-base-100 border p-5 mt-6 ${
        danger ? "border-error bg-error/5" : "border-base-300"
      } ${className}`}
    >
      {title && (
        <h2 className={`text-lg font-semibold mb-4 ${danger ? "text-error" : ""}`}>
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}
