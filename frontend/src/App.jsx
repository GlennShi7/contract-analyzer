import { useState } from 'react'
import Upload from './components/Upload'
import RiskReport from './components/RiskReport'
import ContractQuestions from './components/ContractQuestions'
import Icon from './components/Icon'
import { useLanguage } from './language'
import './DemoNotice.css'

const replayDemo = import.meta.env.VITE_REPLAY_DEMO === 'true'

function App() {
  const { language, setLanguage, t } = useLanguage()
  const [document, setDocument] = useState(null)

  return (
    <>
      <a className="skip-link" href="#workspace">{t("跳到工作区")}</a>
      <div className="app-shell">
        <aside className="sidebar" aria-label={t("工作台导航")}>
          <a className="brand" href="#workspace">
            <span className="brand-mark"><Icon name="document" size={23} /></span>
            <span><strong>{t("合同防踩坑")}</strong><small>CONTRACT WORKSPACE</small></span>
          </a>
          <div className="nav-caption">{t("工作空间")}</div>
          <nav>
            <a className="nav-link current" href="#workspace" aria-current="page"><Icon name="grid" />{t("合同工作台")}<span className="nav-dot" /></a>
            <a className="nav-link" href={document ? '#contract-questions-title' : '#reading-guide'}><Icon name={document ? 'chat' : 'book'} />{document ? t("原文问答") : t("阅读说明")}</a>
            <a className="nav-link" href="https://github.com/GlennShi7/contract-analyzer" target="_blank" rel="noreferrer"><Icon name="external" />{t("项目文档")}</a>
          </nav>
          <div className="sidebar-flow">
            <div className="nav-caption">{t("阅读路径")}</div>
            <div className={document ? 'flow-step complete' : 'flow-step active'}><span>{document ? <Icon name="check" size={14} /> : '01'}</span><div>{t("导入合同")}<small>{t("从一份 PDF 开始")}</small></div></div>
            <div className="flow-step"><span>02</span><div>{t("核对风险")}<small>{t("原文、解释与法条")}</small></div></div>
            <div className="flow-step"><span>03</span><div>{t("问清约定")}<small>{t("围绕当前合同提问")}</small></div></div>
          </div>
          {document && <div className="sidebar-document"><Icon name="document" /><div><small>{t("当前合同")}</small><span>{document.filename}</span></div></div>}
          <div className="sidebar-note"><Icon name="shield" size={18} /><p>{t("让阅读更有依据")}<small>{t("提示供理解参考，重要决定请核对原文与实际情况。")}</small></p></div>
        </aside>

        <div className="workspace-shell">
          <header className="topbar"><span>{t("工作空间")}<span className="breadcrumb-slash">/</span> <strong>{t("合同审阅")}</strong></span><div className="topbar-actions"><button type="button" className="language-toggle" data-language-toggle aria-label={t(language === 'en' ? '切换为中文' : '切换为英文')} onClick={() => setLanguage(language === 'en' ? 'zh' : 'en')}><span lang={language === 'en' ? 'zh-CN' : 'en'}>{language === 'en' ? '中文' : 'English'}</span></button><span className="mode-tag">{replayDemo ? t("演示回放") : t("阅读辅助")}</span></div></header>
          <main id="workspace" className="workspace">
            <div className="workspace-intro">
              <div><div className="eyebrow">READ WITH CLARITY</div><h1>{t("读懂合同，再做决定。")}</h1><p>{t("从原文定位到风险核对，把重要约定看清楚。")}</p></div>
              <span className="intro-icon"><Icon name="document" size={28} /></span>
            </div>
            {replayDemo && (
              <aside className="demo-notice" aria-label={t("回放演示说明")}>
                <Icon name="info" /><div>
                  <strong>{t("回放演示 · 不调用付费 API")}</strong>
                  <p>{t("风险分析回放2026年10月28日保存的结果，含已知解释偏差；问答为预设示例，不是新生成结果。")}</p>
                  <p><a href="/demo/lease_en.pdf" download>{t("下载合成演示 PDF")}<span aria-hidden="true">↗</span></a>{t("，上传后选择“美国 · Urbana, Illinois”。此模式仅接受该样例。")}</p>
                  <p>{t("可试问：“押金多久退还？”或“会自动续租吗？”")}</p>
                </div>
              </aside>
            )}
            <div className={`import-layout${document ? ' has-document' : ''}`}>
              <Upload onUploaded={setDocument} document={document} />
              <aside className="reading-guide panel" id="reading-guide" aria-labelledby="reading-guide-title">
                <div className="guide-heading"><span className="soft-icon"><Icon name="book" /></span><h2 id="reading-guide-title">{t("一份合同，三步读清")}</h2></div>
                <ol>
                  <li><span>1</span><div><strong>{t("导入可读取的 PDF")}</strong><p>{t("上传含文字的合同，先确认提取内容。")}</p></div></li>
                  <li><span>2</span><div><strong>{t("选择地区，核对风险")}</strong><p>{t("结合合同原文、解释与适用条件逐项阅读。")}</p></div></li>
                  <li><span>3</span><div><strong>{t("把不明白的地方问清楚")}</strong><p>{t("提问押金、付款或维修等约定，并展开原文核对。")}</p></div></li>
                </ol>
                <div className="guide-footnote"><Icon name="quote" size={16} /><span>{t("原文是起点，提示不是最终结论。")}</span></div>
              </aside>
            </div>
            {document ? (
              <>
                <div className="document-ready" role="status"><span className="ready-mark"><Icon name="check" size={16} /></span><span><strong>{document.filename}</strong><small>{t("已导入。现在可以核对风险，或直接向这份合同提问。")}</small></span></div>
                <RiskReport key={`risk-${document.doc_id}`} docId={document.doc_id} />
                <ContractQuestions key={`questions-${document.doc_id}`} docId={document.doc_id} />
              </>
            ) : (
              <div className="empty-workspace"><span className="soft-icon"><Icon name="search" size={22} /></span><div><h2>{t("重要的约定，值得多看一眼")}</h2><p>{t("导入后可查看风险提示、展开法条来源，也能围绕合同原文提问。")}</p></div></div>
            )}
            <footer className="workspace-footer"><span>{t("合同防踩坑 · 阅读辅助工具")}</span><span>{t("从原文出发，保留自己的判断。")}</span></footer>
          </main>
        </div>
      </div>
    </>
  )
}

export default App
