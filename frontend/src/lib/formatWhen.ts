export function formatWhen(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('ja-JP', { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return iso;
  }
}
