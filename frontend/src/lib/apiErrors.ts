/** API detail 文字列をユーザー向け日本語に変換。 */

export function formatApiErrorDetail(detail: string): string {
  const pendingMatch = /^session is not pending_approval \(current: (\w+)\)$/.exec(detail);
  if (pendingMatch) {
    const current = pendingMatch[1];
    switch (current) {
      case 'running':
        return 'すでに合議を開始しています。右パネルで進行を確認できます。';
      case 'completed':
        return 'このレビューは完了しています。';
      case 'failed':
        return 'このレビューは失敗しました。新しい PR で再度お試しください。';
      case 'skipped':
        return 'このレビューはスキップ済みです。';
      default:
        return `開始できません（状態: ${current}）`;
    }
  }
  if (detail === 'session not found') {
    return 'レビューセッションが見つかりません。';
  }
  if (detail === 'not authenticated') {
    return 'ログインが必要です。';
  }
  return detail;
}
