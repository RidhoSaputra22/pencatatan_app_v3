/**
 * Reusable table using DaisyUI.
 * @param {string[]} columns   — header labels
 * @param {Array}    rows      — data arrays (each row = array of cells)
 * @param {string}   emptyText — shown when rows is empty
 */
export default function Table({
  columns = [],
  rows = [],
  emptyText = "Tidak ada data.",
}) {
  return (
    <div className="w-[80dvw] lg:w-full overflow-x-auto">
      <table className="table table-zebra w-full">
        <thead>
          <tr>
            <th>No.</th>
            {columns.map((col, i) => (
              <th key={i}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length + 1} className="text-center opacity-60">
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((row, ri) => (
              <tr key={ri} className="hover">
                <td> {ri + 1} </td>
                {row.map((cell, ci) => (
                  <td key={ci}>{cell}</td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
