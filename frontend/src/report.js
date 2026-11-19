// Validate only the fields consumed by the report UI; preserve the response verbatim.
const text = value => typeof value === 'string' && value.trim().length > 0
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const categories = ['illegal', 'risk', 'verify', 'missing']
const tiers = ['universal', 'common', 'rare']

function sourceLink(value) {
  if (!text(value)) return false
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password
  } catch {
    return false
  }
}

export function isRenderableReport(report) {
  if (!object(report) || !Number.isInteger(report.risk_score) || report.risk_score < 1 || report.risk_score > 10 ||
      !['summary', 'legal_scope', 'disclaimer'].every(key => text(report[key])) ||
      !Array.isArray(report.cards) || !Array.isArray(report.legal_sources)) return false

  const ids = new Set()
  for (const law of report.legal_sources) {
    if (!object(law) || !['id', 'law', 'article', 'text', 'checked_on'].every(key => text(law[key])) ||
        !sourceLink(law.source_url) || ids.has(law.id) ||
        (law.authority_level !== undefined && !['national', 'municipal', 'state', 'federal'].includes(law.authority_level)) ||
        (law.applicability !== undefined && typeof law.applicability !== 'string')) return false
    ids.add(law.id)
  }
  return report.cards.every(card => object(card) &&
    ['title', 'explanation', 'suggestion'].every(key => text(card[key])) &&
    // A missing-term card has no quote; every other card must quote the contract.
    (card.category === 'missing' ? card.clause_text === '' : text(card.clause_text)) &&
    (card.category === undefined || categories.includes(card.category)) &&
    (card.tier === undefined || card.tier === null || tiers.includes(card.tier)) &&
    (card.checklist_item === undefined || card.checklist_item === null || Number.isInteger(card.checklist_item)) &&
    (card.checklist_name === undefined || card.checklist_name === null || typeof card.checklist_name === 'string') &&
    ['high', 'medium', 'low'].includes(card.risk_level) && typeof card.verified === 'boolean' &&
    Array.isArray(card.legal_basis) && card.legal_basis.every(id => text(id) && ids.has(id)))
}
