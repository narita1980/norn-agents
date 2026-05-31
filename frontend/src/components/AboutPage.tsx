export function AboutPage() {
  return (
    <section className="about">
      <header className="about__hero">
        <p className="about__kicker">Project Norn</p>
        <h1 className="about__title">Norn（ノルン）とは</h1>
        <p className="about__lead">
          若手エンジニアの<strong>コードレビューと成長の伴走</strong>を、AI の複数視点で支えるサービスです。
          GitHub の Draft PR やチャットから、レビューとメンタリングを受け取れます。
        </p>
      </header>

      <article className="about__card">
        <h2 className="about__heading">名前の読み方</h2>
        <dl className="about__dl">
          <div>
            <dt>英語表記</dt>
            <dd>
              <strong>Norn</strong> — 英語では「ノーン」に近い発音です。
            </dd>
          </div>
          <div>
            <dt>日本語での呼び方</dt>
            <dd>
              <strong>ノルン</strong> と読むのが一般的です（本サービスでもこの読みを使います）。
            </dd>
          </div>
          <div>
            <dt>由来</dt>
            <dd>
              北欧神話の運命を司る三女神 <strong>Norns</strong>（ノルンズ）の名前に由来しています。
              過去・現在・未来を見通すイメージから、レビュー担当の
              <strong>ウルド・スクルド・ヴェルダンディ</strong>（メンター・キャリア・伴走）の 3 視点を組み合わせています。
            </dd>
          </div>
        </dl>
      </article>

      <article className="about__card">
        <h2 className="about__heading">どんなサービスか</h2>
        <p>
          Norn は、<strong>若手エンジニア向けのマルチエージェント・コードレビュー伴走ツール</strong>です。
          シニアの定型的なレビュー負荷を下げつつ、若手が安心して PR を出し、学びながら直せる環境をつくることを目指しています。
        </p>
        <ul className="about__list">
          <li>
            <strong>GitHub Draft PR</strong> を開くと、Norn がレビュー待ちのセッションを用意します（自動で合議は始まりません）。
          </li>
          <li>
            チャット UI で<strong>「開始する」</strong>を押したタイミングで、AI がコードを読み合議します（Human-in-the-loop）。
          </li>
          <li>
            結果は<strong>チャット</strong>と<strong>GitHub の PR コメント</strong>の両方に届きます。
          </li>
          <li>
            PR 以外の開発相談も、チャットから質問できます（内容に応じて応答の仕方が変わります）。
          </li>
        </ul>
      </article>

      <article className="about__card">
        <h2 className="about__heading">「3 女神」とは（3 つのレビュー視点）</h2>
        <p className="about__note">
          UI 上では北欧神話にちなんだ名前を使っていますが、実体は<strong>役割の違う 3 つの AI エージェント</strong>です。
          最後にモデレーター（司会）がまとめ、1 本のレビューとして届けます。
        </p>
        <div className="about__agents">
          <div className="about__agent about__agent--urd">
            <h3>ウルド（メンター）</h3>
            <p>
              過去・確立された知恵の番人として、セキュリティ、設計、Lint、ベストプラクティスなど
              <strong>コードとして正しいか</strong>を事実ベースで教え導きます。
            </p>
          </div>
          <div className="about__agent about__agent--skuld">
            <h3>スクルド（キャリア）</h3>
            <p>
              未来を見通すキャリアメンターとして、学習リソースや次の挑戦テーマ、
              <strong>成長と市場価値</strong>につながる視点を提案します。
            </p>
          </div>
          <div className="about__agent about__agent--verdandi">
            <h3>ヴェルダンディ（伴走）</h3>
            <p>
              現在に寄り添う伴走コーチとして、努力を認め<strong>心理的安全性</strong>を保ちながら、
              いま直せる改善を一緒に整理して合議を締めます。
            </p>
          </div>
        </div>
      </article>

      <article className="about__card">
        <h2 className="about__heading">使い方の流れ</h2>
        <ol className="about__steps">
          <li>
            <span className="about__step-num">1</span>
            <div>
              <strong>Draft PR を作成</strong>
              <p>GitHub 上でドラフトのプルリクエストを開くと、Norn が承認待ち状態でセッションを登録します。</p>
            </div>
          </li>
          <li>
            <span className="about__step-num">2</span>
            <div>
              <strong>チャットで確認・開始</strong>
              <p>
                この画面（チャット）または PR コメントのリンクから開き、内容を確認して「開始する」を押します。
              </p>
            </div>
          </li>
          <li>
            <span className="about__step-num">3</span>
            <div>
              <strong>合議を見る</strong>
              <p>
                右パネルにウルド・スクルド・ヴェルダンディの発言が順に流れ、まとめがチャットと GitHub に投稿されます。
              </p>
            </div>
          </li>
          <li>
            <span className="about__step-num">4</span>
            <div>
              <strong>直して、また相談</strong>
              <p>指摘を反映したあとも、同じスレッドで質問や次の PR の相談ができます。</p>
            </div>
          </li>
        </ol>
        <p className="about__note">
          Webhook を使わない場合は、チャット内の<strong>手動 PR 登録</strong>から同じ流れでレビューを始められます。
        </p>
      </article>

      <article className="about__card">
        <h2 className="about__heading">大切にしていること</h2>
        <ul className="about__list">
          <li>
            <strong>心理的安全性</strong> — 人格否定ではなく、学びと次の一歩に焦点を当てたフィードバック。
          </li>
          <li>
            <strong>あなたが決める</strong> — 合議は承認後に開始。スキップも選べます。
          </li>
          <li>
            <strong>バランスの取れた出力</strong> — メンター・キャリア・伴走の 3 視点を 1 回の合議でまとめ、読みやすいレビューにします。
          </li>
        </ul>
      </article>
    </section>
  );
}
