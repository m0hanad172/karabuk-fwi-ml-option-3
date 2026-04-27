/** All display times use Istanbul timezone for Karabuk, Turkey scope. */
const TZ = "Europe/Istanbul";

export function formatIstanbulTime(isoString: string | null | undefined): string {
  if (!isoString) return "N/A";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "N/A";
    return d.toLocaleString("en-GB", { timeZone: TZ, hour12: false });
  } catch {
    return "N/A";
  }
}

export function formatIstanbulDate(isoString: string | null | undefined): string {
  if (!isoString) return "N/A";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "N/A";
    return d.toLocaleDateString("en-GB", { timeZone: TZ });
  } catch {
    return "N/A";
  }
}

export function formatIstanbulTimeOnly(isoString: string | null | undefined): string {
  if (!isoString) return "N/A";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "N/A";
    return d.toLocaleTimeString("en-GB", { timeZone: TZ, hour12: false });
  } catch {
    return "N/A";
  }
}

export function nowIstanbul(): string {
  return new Date().toLocaleString("en-GB", { timeZone: TZ, hour12: false });
}
