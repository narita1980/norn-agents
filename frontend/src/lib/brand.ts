/** ユーザー向けプロダクト名（docs/CONVENTIONS.md と同期） */
export const PRODUCT_NAME_EN = 'Norns';
export const PRODUCT_NAME_JA = 'ノルンズ';

export function productTitle(): string {
  return `${PRODUCT_NAME_EN}（${PRODUCT_NAME_JA}）`;
}
