import type { Transaction } from "@/lib/api";

const ROWS_KEY = "webhook-console-rows";
const THEME_KEY = "webhook-console-theme";
const MAX_ROWS = 50;

export type Theme = "light" | "dark";

export type TrackedRow = {
  id: string;
  sentAt: number;
  transaction: Transaction | null;
  missing: boolean;
};

export function loadRows(): TrackedRow[] {
  try {
    const stored = localStorage.getItem(ROWS_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

export function saveRows(rows: TrackedRow[]): void {
  try {
    localStorage.setItem(ROWS_KEY, JSON.stringify(rows.slice(0, MAX_ROWS)));
  } catch {
    // The list still works for this page view without storage.
  }
}

export function loadTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return stored === "light" || stored === "dark" ? stored : null;
  } catch {
    return null;
  }
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // The theme still applies for this page view without storage.
  }
}
