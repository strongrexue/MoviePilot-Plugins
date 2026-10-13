/**
 * 流水「决策」字段的展示辅助（详情页与仪表盘共用）。
 *
 * 决策值是入库的英文常量（model/hit_log.py），直接展示对人不友好；
 * 这里做一层中文映射，未认识的值原样返回（前向兼容新决策）。
 */

const DECISION_LABELS = {
  hit: '命中推送',
  failed: '处理失败',
  skipped_not_missing: '媒体库已存在',
  skipped_not_subscribed: '未订阅',
  skipped_unrecognized: '无法识别',
  skipped_keyword: '关键词未命中',
  skipped_no_link: '无可推链接',
  skipped_unknown: '无法判断',
  skipped_extension: '扩展名未命中',
}

/** 决策中文文案（未知值原样返回）。 */
export function decisionLabel(value) {
  const key = String(value || '').trim()
  return DECISION_LABELS[key] || key || '—'
}

/** 决策徽章颜色。 */
export function decisionColor(value) {
  if (value === 'hit') return 'success'
  if (value === 'failed') return 'error'
  if (String(value || '').startsWith('skipped')) return 'default'
  return 'primary'
}
