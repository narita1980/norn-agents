import { PRODUCT_NAME_EN } from '../lib/brand';

export function ChatOnboarding() {
  return (
    <li className="chat__onboarding" aria-label="はじめ方">
      <h2 className="chat__onboarding-title">{PRODUCT_NAME_EN} の試し方（3 ステップ）</h2>
      <ol className="chat__onboarding-steps">
        <li>
          <strong>ログイン</strong> — デモ用は <code>yuki</code> / パスワード <code>norn-demo</code>
          （ナビ右上で たけし・さくら に切替も可）
        </li>
        <li>
          <strong>PR を登録</strong> — 下の「手動 PR 登録」に{' '}
          <code>owner/repo#123</code> または PR URL を入力（Webhook なしでも OK）
        </li>
        <li>
          <strong>合議を開始</strong> — チャットに表示される <code>[開始する]</code> を押すと、右パネルに
          3 女神の合議が流れます
        </li>
      </ol>
      <p className="chat__onboarding-note">
        Draft PR を GitHub Webhook 連携済みリポジトリで open した場合も、同様に承認待ちが表示されます（若手
        <code>yuki</code> 向けセッション）。
      </p>
    </li>
  );
}
