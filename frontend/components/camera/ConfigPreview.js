"use client";

import Section from "@/components/ui/Section";

/**
 * Read-only JSON dump of camera + areas config.
 */
export default function ConfigPreview({ camera, areas }) {
  return (
    <Section title="Current Configuration">
      {camera ? (
        <pre className="bg-base-200 p-3 rounded-sm overflow-x-auto text-xs">
          {`Camera:\n${JSON.stringify(camera, null, 2)}\n\nCounting Areas:\n${JSON.stringify(areas, null, 2)}`}
        </pre>
      ) : (
        <p>Loading...</p>
      )}
    </Section>
  );
}
