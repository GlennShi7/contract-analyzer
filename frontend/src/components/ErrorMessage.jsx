import { useLanguage } from '../language'
import { english } from '../messages'

export default function ErrorMessage({ message, fallback }) {
  const { language, t } = useLanguage()
  const unknownDetail = language === 'en' && !Object.hasOwn(english, message) && /[\u3400-\u9fff]/u.test(message)
  return <div className="error-message" role="alert">
    <p>{unknownDetail ? t(fallback) : t(message)}</p>
    {unknownDetail && <details><summary>{t('原始服务提示')}</summary><p>{message}</p></details>}
  </div>
}
