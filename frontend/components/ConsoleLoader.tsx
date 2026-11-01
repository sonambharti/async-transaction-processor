"use client";

import dynamic from "next/dynamic";

// The console reads localStorage and generates random IDs, so it renders only in the browser.
export const ConsoleLoader = dynamic(
  () => import("@/components/Console").then((module) => module.Console),
  {
    ssr: false,
    loading: () => (
      <main className="page" aria-busy="true">
        <div className="skeleton" />
      </main>
    ),
  },
);
