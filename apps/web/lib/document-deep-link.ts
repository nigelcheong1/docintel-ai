export function parseInitialPage(value?: string | string[]) {
  const rawValue = Array.isArray(value) ? value[0] : value;
  if (!rawValue) {
    return undefined;
  }
  const pageNumber = Number.parseInt(rawValue, 10);
  return Number.isFinite(pageNumber) && pageNumber > 0 ? pageNumber : undefined;
}

export function parseInitialChunk(value?: string | string[]) {
  const rawValue = Array.isArray(value) ? value[0] : value;
  return rawValue?.trim() || undefined;
}
