import { useEffect, useState } from 'react'
import { translate } from './messages'
import { LanguageContext } from './language'

const preferenceKey = 'contract-review-ui-language'

export function LanguageProvider({ children }) {
  const [language, setLanguage] = useState(() => {
    try { return localStorage.getItem(preferenceKey) === 'zh' ? 'zh' : 'en' }
    catch { return 'en' }
  })

  useEffect(() => {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'
    document.title = language === 'zh' ? '合同防踩坑工具 | Contract Risk Analyzer' : 'Contract Risk Analyzer | Contract Workspace'
    try { localStorage.setItem(preferenceKey, language) } catch { /* The switch also works without storage. */ }
  }, [language])

  return <LanguageContext.Provider value={{ language, setLanguage, t: (text, values) => translate(text, language, values) }}>{children}</LanguageContext.Provider>
}
