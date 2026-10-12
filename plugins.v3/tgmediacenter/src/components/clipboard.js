/** 复制文本到剪贴板：优先 Clipboard API，失败回退到临时 textarea。 */
export async function copyText(text) {
  const value = String(text ?? '')
  if (!value) return false

  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return true
    }
  } catch {
    // 非安全上下文（http）下 Clipboard API 不可用，走回退
  }

  try {
    const area = document.createElement('textarea')
    area.value = value
    area.setAttribute('readonly', 'readonly')
    area.style.position = 'fixed'
    area.style.top = '-1000px'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(area)
    return ok
  } catch {
    return false
  }
}
