/**
 * 封面设计器的前端状态与动作。
 *
 * 数据来自插件 API：`/layouts`（布局 + 参数字段）、`/libraries`（媒体库）、
 * `/fonts`、`/templates`；渲染与应用分别走 `/preview`、`/apply`。
 * 组件只负责渲染，不本地推测后端状态。
 */
import { computed, reactive, ref } from 'vue'
import { getPluginApi, postPluginApi, savePluginConfig, unwrap, RENDER_TIMEOUT_MS } from '../api'

/** 读取文件为 dataURL（上传字体 / 模板 / 成品图都用它）。 */
function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

/** 内容字段：跟随「目标对象」（媒体库 / 用户输入），不随风格模板改动。 */
const CONTENT_KEYS = ['title', 'subtitle']

/** 常见媒体库名的中英对照（副标题默认取英文名）。
 *
 * 命中则用英文，未命中回退库名本身；键统一小写以兼容「4K电影 / 4k电影」这类写法。
 * 用户在副标题里手填的英文名优先于本词典（见 `libraryEnNames`）。 */
const LIBRARY_EN_NAMES = {
  '电影': 'Movies',
  '电影库': 'Movies',
  '欧美电影': 'Western Movies',
  '华语电影': 'Chinese Movies',
  '日韩电影': 'Asian Movies',
  '4k电影': '4K Movies',
  '电视剧': 'TV Shows',
  '剧集': 'TV Shows',
  '电视节目': 'TV Shows',
  '动漫': 'Anime',
  '动画': 'Anime',
  '番剧': 'Anime',
  '综艺': 'Variety Shows',
  '纪录片': 'Documentaries',
  '儿童': 'Kids',
  '少儿': 'Kids',
  '亲子': 'Kids',
  '音乐': 'Music',
  'mv': 'Music Videos',
  '体育': 'Sports',
  '教育': 'Education',
  '有声书': 'Audiobooks',
}

/** 按库名查英文名；未命中返回空串。 */
function englishNameFor(name) {
  const key = String(name || '').trim().toLowerCase()
  return LIBRARY_EN_NAMES[key] || ''
}

/** 按 schema 字段类型归一化配置值。
 *
 * ChillPoster 的模板预设把不少数字存成了字符串（如 `"fan_radius": "850"`），
 * 直接塞给滑块会渲染异常，这里按 `type` 统一转成数值 / 布尔 / 字符串。 */
function coerceValues(groups, raw) {
  const result = { ...(raw || {}) }
  for (const group of groups || []) {
    for (const item of group.items || []) {
      const key = item && item.key
      if (!key || result[key] === undefined || result[key] === null) continue
      const value = result[key]
      if (item.type === 'range' || item.type === 'number') {
        const num = Number(value)
        result[key] = Number.isFinite(num) ? num : (item.default !== undefined ? item.default : 0)
      } else if (item.type === 'boolean') {
        result[key] = value === true || value === 'true' || value === 1 || value === '1'
      } else if (['text', 'color', 'select', 'font', 'file'].includes(item.type)) {
        result[key] = String(value)
      }
    }
  }
  return result
}

export function useCoverDesigner({ api, pluginId, initialConfig, notify }) {
  const loading = ref(false)
  const previewing = ref(false)
  const applying = ref(false)
  const libraries = ref([])
  const layouts = ref([])
  const commonGroup = ref('引擎通用')
  const commonFields = ref([])
  const fonts = ref([])
  const keyartFiles = ref([])
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

  // 各媒体库手填的英文名（副标题覆盖值），随配置持久化到插件配置。
  const libraryEnNames = reactive(
    initialConfig.library_en_names && typeof initialConfig.library_en_names === 'object'
      ? { ...initialConfig.library_en_names }
      : {},
  )

  function report(text, ok = true) {
    message.value = text || ''
    messageOk.value = ok !== false
    if (typeof notify === 'function') notify(text, ok)
  }

  const layoutGroups = computed(() => {
    const current = layouts.value.find(item => item.name === form.layout)
    return current && Array.isArray(current.groups) ? current.groups : []
  })

  /** 风格参数分组（不含内容字段）；「引擎通用」单独一块，便于放到右列。 */
  const styleGroups = computed(() =>
    layoutGroups.value.map(group => ({
      group: group.group || '参数',
      items: (Array.isArray(group.items) ? group.items : []).filter(
        item => item && !CONTENT_KEYS.includes(item.key),
      ),
    })),
  )

  const engineGroup = computed(() =>
    commonFields.value.length
      ? { group: commonGroup.value || '引擎通用', items: commonFields.value }
      : null,
  )

  const allGroups = computed(() => {
    const groups = [...styleGroups.value]
    if (engineGroup.value) groups.push(engineGroup.value)
    return groups
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

  /** 用 schema 默认值补齐缺失参数（force=true 时重置为默认）。
   *  内容字段（标题 / 副标题）跳过：它们由「目标对象」与用户输入决定。 */
  function applyDefaults(groups, force = false) {
    for (const group of groups || []) {
      for (const item of group.items || []) {
        if (!item || !item.key || CONTENT_KEYS.includes(item.key)) continue
        if (item.default === undefined || item.default === null) continue
        if (force || form.config[item.key] === undefined) {
          form.config[item.key] = item.default
        }
      }
    }
  }

  /** 目标对象跟随所选媒体库：主标题=库名，副标题=英文名。
   *  英文名优先取「该库手填值」，其次内置中英词典，最后回退库名本身。 */
  function syncFromLibrary() {
    const target = libraries.value.find(item => item.id === form.library_id)
    if (!target) return
    form.config.title = target.name || target.id
    form.config.subtitle =
      libraryEnNames[form.library_id] || englishNameFor(target.name) || target.name || ''
  }

  /** 用户手填副标题时记为当前媒体库的英文名覆盖值（清空则移除覆盖）。 */
  function onSubtitleEdited(value) {
    if (!form.library_id) return
    const text = String(value == null ? '' : value).trim()
    if (text) libraryEnNames[form.library_id] = text
    else delete libraryEnNames[form.library_id]
  }

  async function loadLayouts() {
    try {
      const data = unwrap(await getPluginApi(api(), pluginId(), 'layouts')) || {}
      commonGroup.value = String(data.common_group || '引擎通用')
      commonFields.value = Array.isArray(data.common_fields) ? data.common_fields : []
      layouts.value = Array.isArray(data.layouts) ? data.layouts : []
      if (!layouts.value.some(item => item.name === form.layout)) {
        form.layout = layouts.value.length ? layouts.value[0].name : form.layout
      }
      form.config = coerceValues(allGroups.value, form.config)
      applyDefaults(allGroups.value)
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

  async function loadKeyart() {
    try {
      const data = unwrap(await getPluginApi(api(), pluginId(), 'keyart')) || {}
      keyartFiles.value = Array.isArray(data.files) ? data.files : []
    } catch (error) {
      keyartFiles.value = []
      report(error?.message || '主视觉列表读取失败', false)
    }
  }

  /** 上传主视觉到插件数据目录，成功后自动选中（布局直接引用文件名）。 */
  async function uploadKeyart(file) {
    if (!file) return ''
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'keyart/upload', {
          name: file.name,
          data: await readFileAsDataUrl(file),
        }),
      ) || {}
      keyartFiles.value = Array.isArray(data.files) ? data.files : keyartFiles.value
      report(`主视觉已上传：${file.name}`)
      return file.name
    } catch (error) {
      report(error?.message || '主视觉上传失败', false)
      return ''
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
      syncFromLibrary()
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
    applyDefaults(layoutGroups.value, true)
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

  /** 把当前封面方案持久化到插件配置（下次进入页面与自动封面「跟随封面设计」
   *  都读它）。只写设计字段，基础字段由设置弹窗负责；失败不影响应用结果。 */
  async function saveScheme() {
    try {
      await savePluginConfig(api(), pluginId(), {
        cover_layout: form.layout,
        cover_config: { ...form.config },
        assets_mode: form.mode,
        poster_count: Number(form.poster_count || 0),
        backdrop_count: Number(form.backdrop_count || 0),
        library_en_names: { ...libraryEnNames },
      })
    } catch {
      /* 方案保存失败时保持静默：封面本身已应用成功 */
    }
  }

  async function previewCover() {
    if (previewing.value) return
    previewing.value = true
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'preview', requestBody(), { timeoutMs: RENDER_TIMEOUT_MS }),
      ) || {}
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
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'apply', requestBody(), { timeoutMs: RENDER_TIMEOUT_MS }),
      ) || {}
      if (data.uploaded) saveScheme()
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
      if (data.uploaded) saveScheme()
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
      if (data.uploaded) saveScheme()
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

  /** 载入模板：**只套用风格参数**，主/副标题属于「目标对象」，不随模板改动。 */
  function loadTemplate(template) {
    const incoming = { ...(template.config || {}) }
    for (const key of CONTENT_KEYS) delete incoming[key]
    form.layout = template.layout || form.layout
    form.config = coerceValues(allGroups.value, {
      ...incoming,
      title: form.config.title,
      subtitle: form.config.subtitle,
    })
    applyDefaults(allGroups.value)
    syncFromLibrary()
    report(`已载入模板：${template.name || template.filename}（仅套用风格参数）`)
  }

  /** 模板预览图地址（原生资源端点，浏览器可直接 <img> 加载）。 */
  function templatePreviewUrl(template) {
    return `${window.location.origin}/api/v1/plugin/${pluginId()}/asset/template/${encodeURIComponent(template.filename)}`
  }

  async function loadAll() {
    await loadLayouts()
    await loadFonts()
    await loadKeyart()
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
    keyartFiles,
    templates,
    previewImage,
    previewInfo,
    message,
    messageOk,
    commonGroup,
    commonFields,
    layoutGroups,
    styleGroups,
    engineGroup,
    allGroups,
    libraryItems,
    layoutItems,
    fontItems,
    loadAll,
    loadLibraries,
    loadKeyart,
    uploadKeyart,
    onServerChange,
    onLayoutChange,
    libraryEnNames,
    syncFromLibrary,
    onSubtitleEdited,
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
