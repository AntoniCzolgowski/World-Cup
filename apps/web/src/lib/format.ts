export function formatCompact(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: value >= 1000 ? 1 : 0,
  }).format(value);
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function parseWallClockDate(isoValue: string): Date {
  const match = isoValue.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) {
    return new Date(isoValue);
  }

  const [, year, month, day, hour, minute] = match;
  return new Date(Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute)));
}

export function formatMatchDate(isoValue: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    month: "short",
    day: "numeric",
  }).format(parseWallClockDate(isoValue));
}

export function formatMatchTime(isoValue: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    hour: "numeric",
    minute: "2-digit",
  }).format(parseWallClockDate(isoValue));
}

export function formatMatchDateTime(isoValue: string, options?: { includeWeekday?: boolean }): string {
  const includeWeekday = options?.includeWeekday ?? false;
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    ...(includeWeekday ? { weekday: "short" as const } : {}),
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parseWallClockDate(isoValue));
}
