import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, u as unwrap, p as postPluginApi, R as RENDER_TIMEOUT_MS, a as getPluginApi } from './api-VNFYmuQY.js';

const {toDisplayString:_toDisplayString$1,createElementVNode:_createElementVNode$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,createBlock:_createBlock$1,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1$1 = {
  key: 0,
  class: "ec-slider"
};
const _hoisted_2$1 = { class: "ec-slider-head" };
const _hoisted_3$1 = {
  key: 4,
  class: "ec-color"
};
const _hoisted_4$1 = ["value"];


const _sfc_main$1 = {
  __name: 'CoverField',
  props: {
  item: { type: Object, required: true },
  config: { type: Object, required: true },
  fonts: { type: Array, default: () => [] },
},
  setup(__props) {

/**
 * 单个布局参数字段的渲染器：按 schema 的 type 生成控件。
 *
 * 直接修改传入的 `config` 对象（同一个 reactive 实例），避免为每个字段做 v-model 代理。
 */
const props = __props;

/** select 的 options 统一成 {title, value}，避免 Vuetify 渲染成 [object Object]。 */
function selectItems() {
  return (props.item.options || []).map(option => ({
    title: option.label !== undefined ? option.label : option.title,
    value: option.value,
  }))
}

return (_ctx, _cache) => {
  const _component_VSlider = _resolveComponent$1("VSlider");
  const _component_VSelect = _resolveComponent$1("VSelect");
  const _component_VSwitch = _resolveComponent$1("VSwitch");
  const _component_VTextField = _resolveComponent$1("VTextField");

  return (__props.item.type === 'range')
    ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
        _createElementVNode$1("div", _hoisted_2$1, [
          _createElementVNode$1("span", null, _toDisplayString$1(__props.item.label), 1),
          _createElementVNode$1("b", null, _toDisplayString$1(__props.config[__props.item.key]), 1)
        ]),
        _createVNode$1(_component_VSlider, {
          modelValue: __props.config[__props.item.key],
          "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((__props.config[__props.item.key]) = $event)),
          min: __props.item.min !== undefined && __props.item.min !== null ? __props.item.min : 0,
          max: __props.item.max !== undefined && __props.item.max !== null ? __props.item.max : 100,
          step: __props.item.step || 1,
          density: "compact",
          "hide-details": "",
          color: "primary",
          "thumb-label": ""
        }, null, 8, ["modelValue", "min", "max", "step"])
      ]))
    : (__props.item.type === 'select')
      ? (_openBlock$1(), _createBlock$1(_component_VSelect, {
          key: 1,
          modelValue: __props.config[__props.item.key],
          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((__props.config[__props.item.key]) = $event)),
          items: selectItems(),
          label: __props.item.label,
          density: "compact",
          variant: "outlined",
          "hide-details": ""
        }, null, 8, ["modelValue", "items", "label"]))
      : (__props.item.type === 'font')
        ? (_openBlock$1(), _createBlock$1(_component_VSelect, {
            key: 2,
            modelValue: __props.config[__props.item.key],
            "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((__props.config[__props.item.key]) = $event)),
            items: __props.fonts,
            label: __props.item.label,
            density: "compact",
            variant: "outlined",
            "hide-details": ""
          }, null, 8, ["modelValue", "items", "label"]))
        : (__props.item.type === 'boolean')
          ? (_openBlock$1(), _createBlock$1(_component_VSwitch, {
              key: 3,
              modelValue: __props.config[__props.item.key],
              "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((__props.config[__props.item.key]) = $event)),
              label: __props.item.label,
              color: "primary",
              "hide-details": "",
              inset: "",
              density: "compact"
            }, null, 8, ["modelValue", "label"]))
          : (__props.item.type === 'color')
            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_3$1, [
                _createElementVNode$1("label", {
                  class: "ec-color-swatch",
                  style: _normalizeStyle({ background: __props.config[__props.item.key] || '#000000' })
                }, [
                  _createElementVNode$1("input", {
                    type: "color",
                    class: "ec-color-input",
                    value: __props.config[__props.item.key] || '#000000',
                    onInput: _cache[4] || (_cache[4] = $event => (__props.config[__props.item.key] = $event.target.value))
                  }, null, 40, _hoisted_4$1)
                ], 4),
                _createVNode$1(_component_VTextField, {
                  modelValue: __props.config[__props.item.key],
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((__props.config[__props.item.key]) = $event)),
                  label: __props.item.label,
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "label"])
              ]))
            : (_openBlock$1(), _createBlock$1(_component_VTextField, {
                key: 5,
                modelValue: __props.config[__props.item.key],
                "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((__props.config[__props.item.key]) = $event)),
                label: __props.item.label,
                type: __props.item.type === 'number' ? 'number' : 'text',
                density: "compact",
                variant: "outlined",
                "hide-details": ""
              }, null, 8, ["modelValue", "label", "type"]))
}
}

};
const CoverField = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-a7f6afc8"]]);

/**
 * 封面设计器的前端状态与动作。
 *
 * 数据来自插件 API：`/layouts`（布局 + 参数字段）、`/libraries`（媒体库）、
 * `/fonts`、`/templates`；渲染与应用分别走 `/preview`、`/apply`。
 * 组件只负责渲染，不本地推测后端状态。
 */
const {computed: computed$1,reactive,ref: ref$1} = await importShared('vue');

/** 读取文件为 dataURL（上传字体 / 模板 / 成品图都用它）。 */
function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('文件读取失败'));
    reader.readAsDataURL(file);
  })
}

/** 内容字段：跟随「目标对象」（媒体库 / 用户输入），不随风格模板改动。 */
const CONTENT_KEYS = ['title', 'subtitle'];

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
};

/** 按库名查英文名；未命中返回空串。 */
function englishNameFor(name) {
  const key = String(name || '').trim().toLowerCase();
  return LIBRARY_EN_NAMES[key] || ''
}

/** 按 schema 字段类型归一化配置值。
 *
 * ChillPoster 的模板预设把不少数字存成了字符串（如 `"fan_radius": "850"`），
 * 直接塞给滑块会渲染异常，这里按 `type` 统一转成数值 / 布尔 / 字符串。 */
function coerceValues(groups, raw) {
  const result = { ...(raw || {}) };
  for (const group of groups || []) {
    for (const item of group.items || []) {
      const key = item && item.key;
      if (!key || result[key] === undefined || result[key] === null) continue
      const value = result[key];
      if (item.type === 'range' || item.type === 'number') {
        const num = Number(value);
        result[key] = Number.isFinite(num) ? num : (item.default !== undefined ? item.default : 0);
      } else if (item.type === 'boolean') {
        result[key] = value === true || value === 'true' || value === 1 || value === '1';
      } else if (['text', 'color', 'select', 'font'].includes(item.type)) {
        result[key] = String(value);
      }
    }
  }
  return result
}

function useCoverDesigner({ api, pluginId, initialConfig, notify }) {
  const loading = ref$1(false);
  const previewing = ref$1(false);
  const applying = ref$1(false);
  const libraries = ref$1([]);
  const layouts = ref$1([]);
  const commonGroup = ref$1('引擎通用');
  const commonFields = ref$1([]);
  const fonts = ref$1([]);
  const templates = ref$1([]);
  const previewImage = ref$1('');
  const previewInfo = ref$1({ count: 0, title: '' });
  const message = ref$1('');
  const messageOk = ref$1(true);

  const selectedServers = Array.isArray(initialConfig.selected_servers)
    ? initialConfig.selected_servers
    : [];

  const form = reactive({
    server: selectedServers.length ? selectedServers[0] : '',
    library_id: '',
    layout: initialConfig.cover_layout || 'classic',
    mode: initialConfig.assets_mode || 'random',
    poster_count: Number(initialConfig.poster_count || 6),
    backdrop_count: Number(initialConfig.backdrop_count || 1),
    config: { ...(initialConfig.cover_config || {}) },
  });

  // 各媒体库手填的英文名（副标题覆盖值），随配置持久化到插件配置。
  const libraryEnNames = reactive(
    initialConfig.library_en_names && typeof initialConfig.library_en_names === 'object'
      ? { ...initialConfig.library_en_names }
      : {},
  );

  function report(text, ok = true) {
    message.value = text || '';
    messageOk.value = ok !== false;
    if (typeof notify === 'function') notify(text, ok);
  }

  const layoutGroups = computed$1(() => {
    const current = layouts.value.find(item => item.name === form.layout);
    return current && Array.isArray(current.groups) ? current.groups : []
  });

  /** 风格参数分组（不含内容字段）；「引擎通用」单独一块，便于放到右列。 */
  const styleGroups = computed$1(() =>
    layoutGroups.value.map(group => ({
      group: group.group || '参数',
      items: (Array.isArray(group.items) ? group.items : []).filter(
        item => item && !CONTENT_KEYS.includes(item.key),
      ),
    })),
  );

  const engineGroup = computed$1(() =>
    commonFields.value.length
      ? { group: commonGroup.value || '引擎通用', items: commonFields.value }
      : null,
  );

  const allGroups = computed$1(() => {
    const groups = [...styleGroups.value];
    if (engineGroup.value) groups.push(engineGroup.value);
    return groups
  });

  const libraryItems = computed$1(() =>
    libraries.value.map(item => ({ title: item.name || item.id, value: item.id })),
  );
  const layoutItems = computed$1(() =>
    layouts.value.map(item => ({ title: item.label || item.name, value: item.name })),
  );
  const fontItems = computed$1(() => [
    { title: '默认（自动回退）', value: '' },
    ...fonts.value.map(name => ({ title: name, value: name })),
  ]);

  /** 用 schema 默认值补齐缺失参数（force=true 时重置为默认）。
   *  内容字段（标题 / 副标题）跳过：它们由「目标对象」与用户输入决定。 */
  function applyDefaults(groups, force = false) {
    for (const group of groups || []) {
      for (const item of group.items || []) {
        if (!item || !item.key || CONTENT_KEYS.includes(item.key)) continue
        if (item.default === undefined || item.default === null) continue
        if (force || form.config[item.key] === undefined) {
          form.config[item.key] = item.default;
        }
      }
    }
  }

  /** 目标对象跟随所选媒体库：主标题=库名，副标题=英文名。
   *  英文名优先取「该库手填值」，其次内置中英词典，最后回退库名本身。 */
  function syncFromLibrary() {
    const target = libraries.value.find(item => item.id === form.library_id);
    if (!target) return
    form.config.title = target.name || target.id;
    form.config.subtitle =
      libraryEnNames[form.library_id] || englishNameFor(target.name) || target.name || '';
  }

  /** 用户手填副标题时记为当前媒体库的英文名覆盖值（清空则移除覆盖）。 */
  function onSubtitleEdited(value) {
    if (!form.library_id) return
    const text = String(value == null ? '' : value).trim();
    if (text) libraryEnNames[form.library_id] = text;
    else delete libraryEnNames[form.library_id];
  }

  async function loadLayouts() {
    try {
      const data = unwrap(await getPluginApi(api(), pluginId(), 'layouts')) || {};
      commonGroup.value = String(data.common_group || '引擎通用');
      commonFields.value = Array.isArray(data.common_fields) ? data.common_fields : [];
      layouts.value = Array.isArray(data.layouts) ? data.layouts : [];
      if (!layouts.value.some(item => item.name === form.layout)) {
        form.layout = layouts.value.length ? layouts.value[0].name : form.layout;
      }
      form.config = coerceValues(allGroups.value, form.config);
      applyDefaults(allGroups.value);
    } catch (error) {
      report(error?.message || '布局读取失败', false);
    }
  }

  async function loadFonts() {
    try {
      const data = unwrap(await getPluginApi(api(), pluginId(), 'fonts')) || {};
      fonts.value = Array.isArray(data.fonts) ? data.fonts : [];
    } catch (error) {
      report(error?.message || '字体读取失败', false);
    }
  }

  async function loadTemplates() {
    try {
      const data = unwrap(await getPluginApi(api(), pluginId(), 'templates')) || {};
      templates.value = Array.isArray(data.templates) ? data.templates : [];
    } catch (error) {
      report(error?.message || '模板读取失败', false);
    }
  }

  async function loadLibraries() {
    loading.value = true;
    try {
      const query = form.server ? `?server=${encodeURIComponent(form.server)}` : '';
      const data = unwrap(await getPluginApi(api(), pluginId(), `libraries${query}`)) || {};
      libraries.value = Array.isArray(data.libraries) ? data.libraries : [];
      if (!libraries.value.some(item => item.id === form.library_id)) {
        form.library_id = libraries.value.length ? libraries.value[0].id : '';
      }
      syncFromLibrary();
    } catch (error) {
      libraries.value = [];
      report(error?.message || '媒体库读取失败', false);
    } finally {
      loading.value = false;
    }
  }

  function onServerChange() {
    form.library_id = '';
    return loadLibraries()
  }

  function onLayoutChange() {
    applyDefaults(layoutGroups.value, true);
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
    previewing.value = true;
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'preview', requestBody(), { timeoutMs: RENDER_TIMEOUT_MS }),
      ) || {};
      previewImage.value = String(data.image || '');
      previewInfo.value = { count: Number(data.count || 0), title: String(data.title || '') };
      report('预览已生成');
    } catch (error) {
      report(error?.message || '预览生成失败', false);
    } finally {
      previewing.value = false;
    }
  }

  /** 应用：不带 image_data → 后端现场渲染后上传。 */
  async function applyCover() {
    if (applying.value) return
    applying.value = true;
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'apply', requestBody(), { timeoutMs: RENDER_TIMEOUT_MS }),
      ) || {};
      report(data.uploaded ? '封面已应用' : '应用未生效', !!data.uploaded);
    } catch (error) {
      report(error?.message || '应用失败', false);
    } finally {
      applying.value = false;
    }
  }

  /** 应用已生成的预览图（避免重复渲染）。 */
  async function applyPreviewImage() {
    if (!previewImage.value || applying.value) return
    applying.value = true;
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'apply', {
          ...requestBody(),
          image_data: previewImage.value,
        }),
      ) || {};
      report(data.uploaded ? '预览图已设为封面' : '应用未生效', !!data.uploaded);
    } catch (error) {
      report(error?.message || '应用失败', false);
    } finally {
      applying.value = false;
    }
  }

  /** 直接上传本地成品图替换封面（不经过生成器）。 */
  async function applyLocalImage(file) {
    if (!file || applying.value) return
    applying.value = true;
    try {
      const imageData = await readFileAsDataUrl(file);
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'apply', {
          ...requestBody(),
          image_data: imageData,
        }),
      ) || {};
      report(data.uploaded ? '成品图已设为封面' : '应用未生效', !!data.uploaded);
    } catch (error) {
      report(error?.message || '上传失败', false);
    } finally {
      applying.value = false;
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
      ) || {};
      fonts.value = Array.isArray(data.fonts) ? data.fonts : fonts.value;
      report(`字体已上传：${file.name}`);
    } catch (error) {
      report(error?.message || '字体上传失败', false);
    }
  }

  async function deleteFont(name) {
    try {
      const data = unwrap(await postPluginApi(api(), pluginId(), 'fonts/delete', { name })) || {};
      fonts.value = Array.isArray(data.fonts) ? data.fonts : [];
      report(`字体已删除：${name}`);
    } catch (error) {
      report(error?.message || '字体删除失败', false);
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
      ) || {};
      templates.value = Array.isArray(data.templates) ? data.templates : templates.value;
      report(`模板已保存：${filename}`);
    } catch (error) {
      report(error?.message || '模板保存失败', false);
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
      ) || {};
      templates.value = Array.isArray(data.templates) ? data.templates : templates.value;
      report(`模板已上传：${file.name}`);
    } catch (error) {
      report(error?.message || '模板上传失败', false);
    }
  }

  async function deleteTemplate(filename) {
    try {
      const data = unwrap(
        await postPluginApi(api(), pluginId(), 'templates/delete', { filename }),
      ) || {};
      templates.value = Array.isArray(data.templates) ? data.templates : [];
      report(`模板已删除：${filename}`);
    } catch (error) {
      report(error?.message || '模板删除失败', false);
    }
  }

  /** 载入模板：**只套用风格参数**，主/副标题属于「目标对象」，不随模板改动。 */
  function loadTemplate(template) {
    const incoming = { ...(template.config || {}) };
    for (const key of CONTENT_KEYS) delete incoming[key];
    form.layout = template.layout || form.layout;
    form.config = coerceValues(allGroups.value, {
      ...incoming,
      title: form.config.title,
      subtitle: form.config.subtitle,
    });
    applyDefaults(allGroups.value);
    syncFromLibrary();
    report(`已载入模板：${template.name || template.filename}（仅套用风格参数）`);
  }

  /** 模板预览图地址（原生资源端点，浏览器可直接 <img> 加载）。 */
  function templatePreviewUrl(template) {
    return `${window.location.origin}/api/v1/plugin/${pluginId()}/asset/template/${encodeURIComponent(template.filename)}`
  }

  async function loadAll() {
    await loadLayouts();
    await loadFonts();
    await loadTemplates();
    await loadLibraries();
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

const {createElementVNode:_createElementVNode,unref:_unref,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,withModifiers:_withModifiers,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "ec-cover" };
const _hoisted_2 = { class: "ec-toolbar" };
const _hoisted_3 = { class: "ec-toolbar-actions" };
const _hoisted_4 = { class: "ec-cols" };
const _hoisted_5 = { class: "ec-controls" };
const _hoisted_6 = { class: "ec-preview-side" };
const _hoisted_7 = ["src"];
const _hoisted_8 = {
  key: 2,
  class: "ec-placeholder"
};
const _hoisted_9 = {
  key: 3,
  class: "text-caption"
};
const _hoisted_10 = { key: 0 };
const _hoisted_11 = { class: "ec-templates" };
const _hoisted_12 = ["title", "onClick"];
const _hoisted_13 = ["src"];
const _hoisted_14 = {
  key: 1,
  class: "ec-template-noimg"
};
const _hoisted_15 = { class: "ec-template-name" };
const _hoisted_16 = { class: "ec-row-wrap mt-2" };
const _hoisted_17 = { class: "ec-chips" };
const _hoisted_18 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};

const {computed,onMounted,ref} = await importShared('vue');

/**
 * 封面设计面板。
 *
 * 结构：
 * - 左列（目标对象 + 风格参数）：选服务器/媒体库/风格，以及该风格的 schema 驱动参数；
 * - 右列（预览 + 模板 + 引擎通用 + 封面上传 + 字体）：视觉与资源相关的都放右侧，列更宽。
 *
 * 主/副标题属于「目标对象」（跟随媒体库 / 用户输入），载入模板只套用风格参数。
 */

const _sfc_main = {
  __name: 'CoverDesignPane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  initialConfig: { type: Object, default: () => ({}) },
  servers: { type: Array, default: () => [] },
},
  setup(__props, { expose: __expose }) {

const props = __props;

const designer = useCoverDesigner({
  api: () => props.api,
  pluginId: () => props.pluginId,
  initialConfig: props.initialConfig,
});
const { form, previewImage, previewInfo, message, messageOk, styleGroups, engineGroup } = designer;

const serverItems = computed(() =>
  props.servers.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
);

const modeItems = [
  { title: '随机抽取', value: 'random' },
  { title: '最新入库', value: 'latest' },
];

const fontInput = ref(null);
const templateInput = ref(null);
const localImageInput = ref(null);
const templateName = ref('');

function pick(reference) {
  const element = reference.value;
  if (element) element.click();
}

function onFontPicked(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (file) designer.uploadFont(file);
}

function onTemplatePicked(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (file) designer.uploadTemplate(file);
}

function onLocalImagePicked(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (file) designer.applyLocalImage(file);
}

onMounted(designer.loadAll);

/** 供父组件保存配置时取当前封面设置（这些字段会持久化到插件配置）。 */
function snapshot() {
  return {
    cover_layout: form.layout,
    cover_config: { ...form.config },
    assets_mode: form.mode,
    poster_count: Number(form.poster_count || 0),
    backdrop_count: Number(form.backdrop_count || 0),
    library_en_names: { ...designer.libraryEnNames },
  }
}

__expose({ snapshot });

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent("VCardSubtitle");
  const _component_VCardItem = _resolveComponent("VCardItem");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VChip = _resolveComponent("VChip");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("div", _hoisted_2, [
      _cache[14] || (_cache[14] = _createElementVNode("div", { class: "ec-toolbar-head" }, [
        _createElementVNode("div", { class: "ec-h" }, "封面设计"),
        _createElementVNode("div", { class: "ec-sub" }, "选媒体库 → 调风格 → 生成预览 → 应用到媒体库封面")
      ], -1)),
      _createElementVNode("div", _hoisted_3, [
        _createVNode(_component_VBtn, {
          size: "small",
          variant: "text",
          loading: _unref(designer).loading.value,
          onClick: _unref(designer).loadAll
        }, {
          default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
            _createTextVNode("刷新", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "onClick"]),
        _createVNode(_component_VBtn, {
          size: "small",
          variant: "tonal",
          "prepend-icon": "mdi-image-refresh",
          loading: _unref(designer).previewing.value,
          onClick: _unref(designer).previewCover
        }, {
          default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
            _createTextVNode(" 生成预览 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "onClick"]),
        _createVNode(_component_VBtn, {
          color: "primary",
          size: "small",
          variant: "flat",
          "prepend-icon": "mdi-check",
          loading: _unref(designer).applying.value,
          onClick: _unref(designer).applyCover
        }, {
          default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
            _createTextVNode(" 渲染并应用 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "onClick"])
      ])
    ]),
    (_unref(message))
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: _unref(messageOk) ? 'success' : 'error',
          variant: "tonal",
          density: "compact",
          class: "mb-2"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(_unref(message)), 1)
          ]),
          _: 1
        }, 8, ["type"]))
      : _createCommentVNode("", true),
    _createElementVNode("div", _hoisted_4, [
      _createElementVNode("div", _hoisted_5, [
        _createVNode(_component_VCard, {
          variant: "tonal",
          class: "ec-block"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, { class: "py-2" }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                  default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                    _createTextVNode("目标对象", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
                  default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                    _createTextVNode("主标题跟随库名、副标题自动用英文名（手填即记住该库），载入模板不会改它们", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, { class: "ec-fields" }, {
              default: _withCtx(() => [
                _createVNode(_component_VSelect, {
                  modelValue: _unref(form).server,
                  "onUpdate:modelValue": [
                    _cache[0] || (_cache[0] = $event => ((_unref(form).server) = $event)),
                    _unref(designer).onServerChange
                  ],
                  items: serverItems.value,
                  label: "媒体服务器",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "items", "onUpdate:modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: _unref(form).library_id,
                  "onUpdate:modelValue": [
                    _cache[1] || (_cache[1] = $event => ((_unref(form).library_id) = $event)),
                    _unref(designer).syncFromLibrary
                  ],
                  items: _unref(designer).libraryItems.value,
                  label: "媒体库",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "items", "onUpdate:modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: _unref(form).layout,
                  "onUpdate:modelValue": [
                    _cache[2] || (_cache[2] = $event => ((_unref(form).layout) = $event)),
                    _unref(designer).onLayoutChange
                  ],
                  items: _unref(designer).layoutItems.value,
                  label: "风格（布局）",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "items", "onUpdate:modelValue"]),
                _createVNode(_component_VSelect, {
                  modelValue: _unref(form).mode,
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((_unref(form).mode) = $event)),
                  items: modeItems,
                  label: "素材模式",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: _unref(form).config.title,
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((_unref(form).config.title) = $event)),
                  label: "主标题内容",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue"]),
                _createVNode(_component_VTextField, {
                  modelValue: _unref(form).config.subtitle,
                  "onUpdate:modelValue": [
                    _cache[5] || (_cache[5] = $event => ((_unref(form).config.subtitle) = $event)),
                    _unref(designer).onSubtitleEdited
                  ],
                  label: "副标题内容（英文名）",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "onUpdate:modelValue"])
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(styleGroups), (group, index) => {
          return (_openBlock(), _createBlock(_component_VCard, {
            key: index,
            variant: "tonal",
            class: "ec-block"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VCardItem, { class: "py-2" }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(group.group), 1)
                    ]),
                    _: 2
                  }, 1024)
                ]),
                _: 2
              }, 1024),
              _createVNode(_component_VCardText, { class: "ec-fields" }, {
                default: _withCtx(() => [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.items, (item) => {
                    return (_openBlock(), _createBlock(CoverField, {
                      key: item.key,
                      item: item,
                      config: _unref(form).config,
                      fonts: _unref(designer).fontItems.value
                    }, null, 8, ["item", "config", "fonts"]))
                  }), 128))
                ]),
                _: 2
              }, 1024)
            ]),
            _: 2
          }, 1024))
        }), 128))
      ]),
      _createElementVNode("div", _hoisted_6, [
        _createVNode(_component_VCard, {
          variant: "tonal",
          class: "ec-preview-card"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, { class: "py-2" }, {
              append: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  "prepend-icon": "mdi-image-refresh",
                  loading: _unref(designer).previewing.value,
                  onClick: _unref(designer).previewCover
                }, {
                  default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
                    _createTextVNode(" 生成 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading", "onClick"])
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                  default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
                    _createTextVNode("预览", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, { class: "ec-preview-body" }, {
              default: _withCtx(() => [
                (_unref(designer).previewing.value)
                  ? (_openBlock(), _createBlock(_component_VProgressLinear, {
                      key: 0,
                      indeterminate: "",
                      color: "primary",
                      height: "2"
                    }))
                  : _createCommentVNode("", true),
                (_unref(previewImage))
                  ? (_openBlock(), _createElementBlock("img", {
                      key: 1,
                      src: _unref(previewImage),
                      class: "ec-preview",
                      alt: "封面预览"
                    }, null, 8, _hoisted_7))
                  : (_openBlock(), _createElementBlock("div", _hoisted_8, "点击「生成」查看封面效果")),
                (_unref(previewInfo).title)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_9, [
                      _createTextVNode(_toDisplayString(_unref(previewInfo).title), 1),
                      (_unref(previewInfo).count)
                        ? (_openBlock(), _createElementBlock("span", _hoisted_10, " · " + _toDisplayString(_unref(previewInfo).count) + " 部", 1))
                        : _createCommentVNode("", true)
                    ]))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VCard, {
          variant: "tonal",
          class: "ec-block mt-2"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, { class: "py-2" }, {
              append: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  "prepend-icon": "mdi-upload",
                  onClick: _cache[6] || (_cache[6] = $event => (pick(templateInput.value)))
                }, {
                  default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                    _createTextVNode("上传", -1)
                  ]))]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                  default: _withCtx(() => [
                    _createTextVNode("模板预设（" + _toDisplayString(_unref(designer).templates.value.length) + "）", 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardSubtitle, { class: "text-caption" }, {
                  default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                    _createTextVNode("点击卡片即载入（仅套用风格参数，不改标题/副标题）", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_11, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(designer).templates.value, (template) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: template.filename,
                      class: _normalizeClass(["ec-template", { 'ec-template--active': template.layout === _unref(form).layout }]),
                      role: "button",
                      title: `点击载入：${template.name || template.filename}`,
                      onClick: $event => (_unref(designer).loadTemplate(template))
                    }, [
                      (template.has_preview)
                        ? (_openBlock(), _createElementBlock("img", {
                            key: 0,
                            src: _unref(designer).templatePreviewUrl(template),
                            class: "ec-template-thumb",
                            alt: ""
                          }, null, 8, _hoisted_13))
                        : (_openBlock(), _createElementBlock("div", _hoisted_14, _toDisplayString(template.layout), 1)),
                      _createVNode(_component_VBtn, {
                        class: "ec-template-del",
                        size: "x-small",
                        icon: "",
                        variant: "text",
                        title: "删除模板",
                        onClick: _withModifiers($event => (_unref(designer).deleteTemplate(template.filename)), ["stop"])
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VIcon, {
                            icon: "mdi-close",
                            size: "14"
                          })
                        ]),
                        _: 1
                      }, 8, ["onClick"]),
                      _createElementVNode("div", _hoisted_15, _toDisplayString(template.name || template.filename), 1)
                    ], 10, _hoisted_12))
                  }), 128))
                ]),
                _createElementVNode("div", _hoisted_16, [
                  _createVNode(_component_VTextField, {
                    modelValue: templateName.value,
                    "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((templateName).value = $event)),
                    label: "模板文件名",
                    placeholder: "如 我的封面.json",
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    class: "ec-template-input"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VBtn, {
                    size: "small",
                    variant: "tonal",
                    disabled: !templateName.value,
                    onClick: _cache[8] || (_cache[8] = $event => (_unref(designer).saveTemplate(templateName.value)))
                  }, {
                    default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                      _createTextVNode(" 保存当前 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled"])
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        (_unref(engineGroup))
          ? (_openBlock(), _createBlock(_component_VCard, {
              key: 0,
              variant: "tonal",
              class: "ec-block mt-2"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardItem, { class: "py-2" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(_unref(engineGroup).group), 1)
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCardText, { class: "ec-fields" }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(engineGroup).items, (item) => {
                      return (_openBlock(), _createBlock(CoverField, {
                        key: item.key,
                        item: item,
                        config: _unref(form).config,
                        fonts: _unref(designer).fontItems.value
                      }, null, 8, ["item", "config", "fonts"]))
                    }), 128))
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        _createVNode(_component_VCard, {
          variant: "tonal",
          class: "ec-block mt-2"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, { class: "py-2" }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                  default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                    _createTextVNode("封面上传", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, { class: "ec-row-wrap" }, {
              default: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "tonal",
                  "prepend-icon": "mdi-image",
                  loading: _unref(designer).applying.value,
                  onClick: _cache[9] || (_cache[9] = $event => (pick(localImageInput.value)))
                }, {
                  default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                    _createTextVNode(" 选择本地封面（直接替换） ", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "tonal",
                  "prepend-icon": "mdi-content-save-check",
                  disabled: !_unref(previewImage),
                  loading: _unref(designer).applying.value,
                  onClick: _unref(designer).applyPreviewImage
                }, {
                  default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                    _createTextVNode(" 应用当前预览图 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading", "onClick"])
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VCard, {
          variant: "tonal",
          class: "ec-block mt-2"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardItem, { class: "py-2" }, {
              append: _withCtx(() => [
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  "prepend-icon": "mdi-upload",
                  onClick: _cache[10] || (_cache[10] = $event => (pick(fontInput.value)))
                }, {
                  default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                    _createTextVNode("上传", -1)
                  ]))]),
                  _: 1
                })
              ]),
              default: _withCtx(() => [
                _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
                  default: _withCtx(() => [
                    _createTextVNode("字体（" + _toDisplayString(_unref(designer).fonts.value.length) + "）", 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_17, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(designer).fonts.value, (name) => {
                    return (_openBlock(), _createBlock(_component_VChip, {
                      key: name,
                      size: "small",
                      variant: "tonal",
                      closable: "",
                      "onClick:close": $event => (_unref(designer).deleteFont(name))
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(name), 1)
                      ]),
                      _: 2
                    }, 1032, ["onClick:close"]))
                  }), 128)),
                  (!_unref(designer).fonts.value.length)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_18, " 未上传字体（中文会回退为方块），请先上传 .ttf/.otf "))
                    : _createCommentVNode("", true)
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ])
    ]),
    _createElementVNode("input", {
      ref_key: "fontInput",
      ref: fontInput,
      type: "file",
      accept: ".ttf,.otf,.ttc",
      class: "ec-hidden",
      onChange: onFontPicked
    }, null, 544),
    _createElementVNode("input", {
      ref_key: "templateInput",
      ref: templateInput,
      type: "file",
      accept: ".json",
      class: "ec-hidden",
      onChange: onTemplatePicked
    }, null, 544),
    _createElementVNode("input", {
      ref_key: "localImageInput",
      ref: localImageInput,
      type: "file",
      accept: "image/*",
      class: "ec-hidden",
      onChange: onLocalImagePicked
    }, null, 544)
  ]))
}
}

};
const CoverDesignPane = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-8ffbb0b6"]]);

export { CoverDesignPane as C };
