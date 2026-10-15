/**
 * 封面设计器的前端状态与动作。
 *
 * 数据来自插件 API：`/layouts`（布局 + 参数字段）、`/libraries`（媒体库）、
 * `/fonts`、`/templates`；渲染与应用分别走 `/preview`、`/apply`。
 * 组件只负责渲染，不本地推测后端状态。
 */
import { computed, reactive, ref } from 'vue'
import { getPluginApi, postPluginApi, unwrap } from '../api'

/** 读取文件为 dataURL（上传字体 / 模板 / 成品图都用它）。 */
function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

export function useCoverDesigner({ api, pluginId, initialConfig, notify }) {
  const loading = ref(false)
  const previewing = ref(false)
  const applying = ref(false)
  const libraries = ref([])
  const layouts = ref([])
  const commonFields = ref([])
  const fonts = ref([])
  const templates = ref([])
  const previewImage = ref('')
  const previewInfo = ref({ count: 0, title: '' })
  const message = ref('')
  const messageOk = ref(true)

  const selectedServers = Array.isArray(initialConfig.selected_servers)
    ? initialConfig.selected_servers
    : []

  const form = reactive({
    server: selectedServers.length ? selectedServers[0] : '',
    library_id: '',
    layout: initialConfig.cover_layout || 'classic',
    mode: initialConfig.assets_mode || 'random',
    poster_count: Number(initialConfig.poster_count || 6),
    backdrop_count: Number(initialConfig.backdrop_count || 1),
    config: { ...(initialConfig.cover_config || {}) },
  })

  function report(text, ok = true) {
    message.value = text || ''
    messageOk.value = ok !== false
    if (typeof notify === 'function') notify(text, ok)
  }

  const layoutFields = computed(() => {
    const current = layouts.value.find(item => item.name === form.layout)
    return current && Array.isArray(current.fields) ? current.fields : []
  })

  const libraryItems = computed(() =>
    libraries.value.map(item => ({ title: item.name || item.id, value: item.id })),
  )
  const layoutItems = computed(() =>
    layouts.value.map(item => ({ title: item.label || item.name, value: item.name })),
  )
  const fontItems = computed(() => [
    { title: '默认（自动回退）', value: '' },
    ...fonts.value.map(name => ({ title: name, value: name })),
  ])

  /** 用 schema 默认值补齐缺失参数（force=true 时重置为默认）。 */
  function applyDefaults(fields, force = false) {
    for (const field of fields || []) {
      if (field.default === undefined || field.default === null) continue
      if (force || form.config[field.key] === undefined) {
        form.config[field.key] = field.default
      }
    }
  }

  /** 选中媒体库时用库名兜底主标题，避免空白标题。 */
  function syncTitleFromLibrary() {
    const target = libraries.value.find(item => item.id === form.library_id)
    if (target && !form.config.title) {
      form.config.title = target.name || target.id
    }
  }

  async function loadLayouts() {
    try {
      const data = unwrap(await getPluginApi(api(), pluginId(), 'layouts')) || {}
      commonFields.value = Array.isArray(data.common_fields) ? data.common_fields : []
      layouts.value = Array.isArray(data.layouts) ? data.layouts : []
      applyDefaults(commonFields.value)
      applyDefaults(layoutFields.value)
    } catch (error) {
      report(error?.message || '布局读取失败', false)
    }
  }

  async function loadFonts() {
    try {
      const data = unwrap(await getPluginApi(api(), pluginId(), 'fonts')) || {}
      fonts.value = Array.isArray(data.fonts) ? data.fonts : []
    } catch (error) {
      report(error?.message || '字体读取失败', false)
    }
  }

  async function loadTemplates() {
    try {
      const data = unwrap(await getPluginApi(api(), pluginId(), 'templates')) || {}
      templates.value = Array.isArray(data.templates) ? data.templates : []
    } catch (error) {
      report(error?.message || '模板读取失败', false)
    }
  }

  async function loadLibraries() {
    loading.value = true
    try {
      const query = form.server ? `?server=${encodeURIComponent(form.server)}` : ''
      const data = unwrap(await getPluginApi(api(), pluginId(), `libraries${query}`)) || {}
      libraries.value = Array.isArray(data.libraries) ? data.libraries : []
      if (!libraries.value.some(item => item.id === form.library_id)) {
        form.library_id = libraries.value.length ? libraries.value[0].id : ''
      }
      syncTitleFromLibrary()
    } catch (error) {
      libraries.value = []
      report(error?.message || '媒体库读取失败', false)
    } finally {
      loading.value = false
    }
  }

  function onServerChange() {
    form.library_id = ''
    return loadLibraries()
  }

  function onLayoutChange() {
    applyDefaults(layoutFields.value, true)
  }

  function requestBody() {
    return {
      server: form.server,
      library_id: form.library_id,
      layout: form.layout,
      config: { ...form.config },
      mode: form.mode,
      poster_count: Number(form.poster_count || 0),
      backdrop_count: Number(form.backdrop_count || 0),
    }
  }

  async function previewCover() {
    if (previewing.value) return
    previewing.value = true
    try {
      const data = unwrap(await postPluginApi(api(), pluginId(), 'preview', requestBody())) || {}
      previewImage.value = String(data.image || '')
      previewInfo.value = { count: Number(data.count || 0), title: String(data.title || '') }
      report('预览已生成')
    } catch (error) {
      report(error?.message || '预览生成失败', false)
    } finally {
      previewing.value = false
    }
  }

  /** 应用：不带 image_data → 后端现场渲染后上传。 */
  async function applyCover() {
    if (applying.value) return
    applying.value = true
    try {
      const data = unwrap(await postPluginApi(api(), pluginId(), 'apply', requestBody())) || {}
      report(data.uploaded ? '封面已应用' : '应用未生效', !!data.uploaded)
    } catch (error) {
      report(error?.message || '应用失败', false)
    } finally {
      applying.value = false
    }
  }

  /** 应用已生成的预览图（避免重复渲染）。 */
  async function applyPreviewImage() {
    if (!previewImage.value || applying.value) return
    applying.value = true
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'apply', {
          ...requestBody(),
          image_data: previewImage.value,
        }),
      ) || {}
      report(data.uploaded ? '预览图已设为封面' : '应用未生效', !!data.uploaded)
    } catch (error) {
      report(error?.message || '应用失败', false)
    } finally {
      applying.value = false
    }
  }

  /** 直接上传本地成品图替换封面（不经过生成器）。 */
  async function applyLocalImage(file) {
    if (!file || applying.value) return
    applying.value = true
    try {
      const imageData = await readFileAsDataUrl(file)
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'apply', {
          ...requestBody(),
          image_data: imageData,
        }),
      ) || {}
      report(data.uploaded ? '成品图已设为封面' : '应用未生效', !!data.uploaded)
    } catch (error) {
      report(error?.message || '上传失败', false)
    } finally {
      applying.value = false
    }
  }

  async function uploadFont(file) {
    if (!file) return
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'fonts/upload', {
          name: file.name,
          data: await readFileAsDataUrl(file),
        }),
      ) || {}
      fonts.value = Array.isArray(data.fonts) ? data.fonts : fonts.value
      report(`字体已上传：${file.name}`)
    } catch (error) {
      report(error?.message || '字体上传失败', false)
    }
  }

  async function deleteFont(name) {
    try {
      const data = unwrap(await postPluginApi(api(), pluginId(), 'fonts/delete', { name })) || {}
      fonts.value = Array.isArray(data.fonts) ? data.fonts : []
      report(`字体已删除：${name}`)
    } catch (error) {
      report(error?.message || '字体删除失败', false)
    }
  }

  async function saveTemplate(filename) {
    if (!filename) return
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'templates/save', {
          filename,
          name: filename.replace(/\.json$/i, ''),
          layout: form.layout,
          config: { ...form.config },
          preview: previewImage.value,
        }),
      ) || {}
      templates.value = Array.isArray(data.templates) ? data.templates : templates.value
      report(`模板已保存：${filename}`)
    } catch (error) {
      report(error?.message || '模板保存失败', false)
    }
  }

  async function uploadTemplate(file) {
    if (!file) return
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'templates/upload', {
          filename: file.name,
          data: await readFileAsDataUrl(file),
        }),
      ) || {}
      templates.value = Array.isArray(data.templates) ? data.templates : templates.value
      report(`模板已上传：${file.name}`)
    } catch (error) {
      report(error?.message || '模板上传失败', false)
    }
  }

  async function deleteTemplate(filename) {
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'templates/delete', { filename }),
      ) || {}
      templates.value = Array.isArray(data.templates) ? data.templates : []
      report(`模板已删除：${filename}`)
    } catch (error) {
      report(error?.message || '模板删除失败', false)
    }
  }

  function loadTemplate(template) {
    form.layout = template.layout || 'classic'
    form.config = { ...(template.config || {}) }
    applyDefaults(commonFields.value)
    applyDefaults(layoutFields.value)
    report(`已载入模板：${template.name || template.filename}`)
  }

  /** 模板预览图地址（原生资源端点，浏览器可直接 <img> 加载）。 */
  function templatePreviewUrl(template) {
    return `${window.location.origin}/api/v1/plugin/${pluginId()}/asset/template/${encodeURIComponent(template.filename)}`
  }

  async function loadAll() {
    await loadLayouts()
    await loadFonts()
    await loadTemplates()
    await loadLibraries()
  }

  return {
    form,
    loading,
    previewing,
    applying,
    libraries,
    layouts,
    commonFields,
    fonts,
    templates,
    previewImage,
    previewInfo,
    message,
    messageOk,
    layoutFields,
    libraryItems,
    layoutItems,
    fontItems,
    loadAll,
    loadLibraries,
    onServerChange,
    onLayoutChange,
    syncTitleFromLibrary,
    previewCover,
    applyCover,
    applyPreviewImage,
    applyLocalImage,
    uploadFont,
    deleteFont,
    saveTemplate,
    uploadTemplate,
    deleteTemplate,
    loadTemplate,
    templatePreviewUrl,
  }
}
