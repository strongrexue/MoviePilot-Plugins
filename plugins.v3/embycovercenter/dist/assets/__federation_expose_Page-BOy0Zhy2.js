import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, u as unwrap, p as postPluginApi, R as RENDER_TIMEOUT_MS, a as getPluginApi, s as savePluginConfig, g as getPluginConfig } from './_plugin-vue_export-helper-BGiM_AXo.js';
import { F as FRONTEND_VERSION } from './version-CtiXbcsG.js';

const {toDisplayString:_toDisplayString$3,createElementVNode:_createElementVNode$3,resolveComponent:_resolveComponent$3,createVNode:_createVNode$3,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,createCommentVNode:_createCommentVNode$3,createBlock:_createBlock$3,normalizeStyle:_normalizeStyle,createTextVNode:_createTextVNode$3,withCtx:_withCtx$3} = await importShared('vue');


const _hoisted_1$3 = {
  key: 0,
  class: "ec-slider"
};
const _hoisted_2$3 = { class: "ec-slider-head" };
const _hoisted_3$2 = {
  key: 4,
  class: "ec-color"
};
const _hoisted_4$2 = ["value"];
const _hoisted_5$2 = {
  key: 5,
  class: "ec-file"
};


const _sfc_main$3 = {
  __name: 'CoverField',
  props: {
  item: { type: Object, required: true },
  config: { type: Object, required: true },
  fonts: { type: Array, default: () => [] },
  /** 文件类字段（如主视觉）可选的已上传文件清单。 */
  files: { type: Array, default: () => [] },
},
  emits: ['upload', 'delete'],
  setup(__props, { emit: __emit }) {

/**
 * 单个布局参数字段的渲染器：按 schema 的 type 生成控件。
 *
 * 直接修改传入的 `config` 对象（同一个 reactive 实例），避免为每个字段做 v-model 代理。
 */
const props = __props;

const emit = __emit;

/** select 的 options 统一成 {title, value}，避免 Vuetify 渲染成 [object Object]。 */
function selectItems() {
  return (props.item.options || []).map(option => ({
    title: option.label !== undefined ? option.label : option.title,
    value: option.value,
  }))
}

/** 文件字段：已上传文件清单 + 「不使用」空选项。 */
function fileItems() {
  return [
    { title: '（不使用）', value: '' },
    ...(props.files || []).map(name => ({ title: name, value: name })),
  ]
}

function onFilePicked(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (file) emit('upload', file);
}

/** 删除当前选中的底图文件（由上层弹确认框后执行）。 */
function onFileDelete() {
  const name = config[item.key];
  if (name) emit('delete', name);
}

return (_ctx, _cache) => {
  const _component_VSlider = _resolveComponent$3("VSlider");
  const _component_VSelect = _resolveComponent$3("VSelect");
  const _component_VSwitch = _resolveComponent$3("VSwitch");
  const _component_VTextField = _resolveComponent$3("VTextField");
  const _component_VBtn = _resolveComponent$3("VBtn");

  return (__props.item.type === 'range')
    ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_1$3, [
        _createElementVNode$3("div", _hoisted_2$3, [
          _createElementVNode$3("span", null, _toDisplayString$3(__props.item.label), 1),
          _createElementVNode$3("b", null, _toDisplayString$3(__props.config[__props.item.key]), 1)
        ]),
        _createVNode$3(_component_VSlider, {
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
      ? (_openBlock$3(), _createBlock$3(_component_VSelect, {
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
        ? (_openBlock$3(), _createBlock$3(_component_VSelect, {
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
          ? (_openBlock$3(), _createBlock$3(_component_VSwitch, {
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
            ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_3$2, [
                _createElementVNode$3("label", {
                  class: "ec-color-swatch",
                  style: _normalizeStyle({ background: __props.config[__props.item.key] || '#000000' })
                }, [
                  _createElementVNode$3("input", {
                    type: "color",
                    class: "ec-color-input",
                    value: __props.config[__props.item.key] || '#000000',
                    onInput: _cache[4] || (_cache[4] = $event => (__props.config[__props.item.key] = $event.target.value))
                  }, null, 40, _hoisted_4$2)
                ], 4),
                _createVNode$3(_component_VTextField, {
                  modelValue: __props.config[__props.item.key],
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((__props.config[__props.item.key]) = $event)),
                  label: __props.item.label,
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "label"])
              ]))
            : (__props.item.type === 'file')
              ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_5$2, [
                  _createVNode$3(_component_VSelect, {
                    modelValue: __props.config[__props.item.key],
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((__props.config[__props.item.key]) = $event)),
                    items: fileItems(),
                    label: __props.item.label,
                    density: "compact",
                    variant: "outlined",
                    "hide-details": ""
                  }, null, 8, ["modelValue", "items", "label"]),
                  _createVNode$3(_component_VBtn, {
                    tag: "label",
                    size: "small",
                    variant: "tonal",
                    "prepend-icon": "mdi-upload",
                    class: "ec-file-btn"
                  }, {
                    default: _withCtx$3(() => [
                      _cache[8] || (_cache[8] = _createTextVNode$3(" 上传 ", -1)),
                      _createElementVNode$3("input", {
                        type: "file",
                        accept: ".jpg,.jpeg,.png,.webp",
                        class: "ec-file-input",
                        onChange: onFilePicked
                      }, null, 32)
                    ]),
                    _: 1
                  }),
                  _createVNode$3(_component_VBtn, {
                    size: "small",
                    variant: "tonal",
                    color: "error",
                    "prepend-icon": "mdi-delete",
                    class: "ec-file-btn",
                    disabled: !__props.config[__props.item.key],
                    title: "删除选中的底图文件",
                    onClick: onFileDelete
                  }, {
                    default: _withCtx$3(() => [...(_cache[9] || (_cache[9] = [
                      _createTextVNode$3(" 删除 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled"])
                ]))
              : (_openBlock$3(), _createBlock$3(_component_VTextField, {
                  key: 6,
                  modelValue: __props.config[__props.item.key],
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((__props.config[__props.item.key]) = $event)),
                  label: __props.item.label,
                  type: __props.item.type === 'number' ? 'number' : 'text',
                  density: "compact",
                  variant: "outlined",
                  "hide-details": ""
                }, null, 8, ["modelValue", "label", "type"]))
}
}

};
const CoverField = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-21a4b415"]]);

/**
 * 封面设计器的前端状态与动作。
 *
 * 数据来自插件 API：`/layouts`（布局 + 参数字段）、`/libraries`（媒体库）、
 * `/fonts`、`/templates`；渲染与应用分别走 `/preview`、`/apply`。
 * 组件只负责渲染，不本地推测后端状态。
 */
const {computed: computed$3,reactive: reactive$2,ref: ref$2} = await importShared('vue');

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
      } else if (['text', 'color', 'select', 'font', 'file'].includes(item.type)) {
        result[key] = String(value);
      }
    }
  }
  return result
}

function useCoverDesigner({ api, pluginId, initialConfig, notify }) {
  const loading = ref$2(false);
  const previewing = ref$2(false);
  const applying = ref$2(false);
  const libraries = ref$2([]);
  const layouts = ref$2([]);
  const commonGroup = ref$2('引擎通用');
  const commonFields = ref$2([]);
  const fonts = ref$2([]);
  const keyartFiles = ref$2([]);
  const templates = ref$2([]);
  const previewImage = ref$2('');
  const previewInfo = ref$2({ count: 0, title: '' });
  const message = ref$2('');
  const messageOk = ref$2(true);

  const selectedServers = Array.isArray(initialConfig.selected_servers)
    ? initialConfig.selected_servers
    : [];

  const form = reactive$2({
    server: selectedServers.length ? selectedServers[0] : '',
    library_id: '',
    layout: initialConfig.cover_layout || 'classic',
    mode: initialConfig.assets_mode || 'random',
    poster_count: Number(initialConfig.poster_count || 6),
    backdrop_count: Number(initialConfig.backdrop_count || 1),
    config: { ...(initialConfig.cover_config || {}) },
  });

  // 各媒体库手填的英文名（副标题覆盖值），随配置持久化到插件配置。
  const libraryEnNames = reactive$2(
    initialConfig.library_en_names && typeof initialConfig.library_en_names === 'object'
      ? { ...initialConfig.library_en_names }
      : {},
  );

  function report(text, ok = true) {
    message.value = text || '';
    messageOk.value = ok !== false;
    if (typeof notify === 'function') notify(text, ok);
  }

  const layoutGroups = computed$3(() => {
    const current = layouts.value.find(item => item.name === form.layout);
    return current && Array.isArray(current.groups) ? current.groups : []
  });

  /** 风格参数分组（不含内容字段）；「引擎通用」单独一块，便于放到右列。 */
  const styleGroups = computed$3(() =>
    layoutGroups.value.map(group => ({
      group: group.group || '参数',
      items: (Array.isArray(group.items) ? group.items : []).filter(
        item => item && !CONTENT_KEYS.includes(item.key),
      ),
    })),
  );

  const engineGroup = computed$3(() =>
    commonFields.value.length
      ? { group: commonGroup.value || '引擎通用', items: commonFields.value }
      : null,
  );

  const allGroups = computed$3(() => {
    const groups = [...styleGroups.value];
    if (engineGroup.value) groups.push(engineGroup.value);
    return groups
  });

  const libraryItems = computed$3(() =>
    libraries.value.map(item => ({ title: item.name || item.id, value: item.id })),
  );
  const layoutItems = computed$3(() =>
    layouts.value.map(item => ({ title: item.label || item.name, value: item.name })),
  );
  const fontItems = computed$3(() => [
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

  async function loadKeyart() {
    try {
      const data = unwrap(await getPluginApi(api(), pluginId(), 'keyart')) || {};
      keyartFiles.value = Array.isArray(data.files) ? data.files : [];
    } catch (error) {
      keyartFiles.value = [];
      report(error?.message || '主视觉列表读取失败', false);
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
      ) || {};
      keyartFiles.value = Array.isArray(data.files) ? data.files : keyartFiles.value;
      report(`主视觉已上传：${file.name}`);
      return file.name
    } catch (error) {
      report(error?.message || '主视觉上传失败', false);
      return ''
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
      });
    } catch {
      /* 方案保存失败时保持静默：封面本身已应用成功 */
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
      if (data.uploaded) saveScheme();
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
      if (data.uploaded) saveScheme();
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
      if (data.uploaded) saveScheme();
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

  /** 删除已上传的主视觉；引用该文件名的字段一并清空，避免留下失效引用。 */
  async function deleteKeyart(name) {
    if (!name) return
    try {
      const data = unwrap(await postPluginApi(api(), pluginId(), 'keyart/delete', { name })) || {};
      keyartFiles.value = Array.isArray(data.files) ? data.files : [];
      if (form.config.keyart_file === name) form.config.keyart_file = '';
      report(`主视觉已删除：${name}`);
    } catch (error) {
      report(error?.message || '主视觉删除失败', false);
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
    await loadKeyart();
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
    deleteKeyart,
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

const {createElementVNode:_createElementVNode$2,unref:_unref$2,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,createVNode:_createVNode$2,toDisplayString:_toDisplayString$2,openBlock:_openBlock$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2,createElementBlock:_createElementBlock$2,renderList:_renderList$1,Fragment:_Fragment$1,withModifiers:_withModifiers,normalizeClass:_normalizeClass$2} = await importShared('vue');


const _hoisted_1$2 = { class: "ec-cover" };
const _hoisted_2$2 = { class: "ec-toolbar" };
const _hoisted_3$1 = { class: "ec-toolbar-actions" };
const _hoisted_4$1 = { class: "ec-preview-stage" };
const _hoisted_5$1 = ["src"];
const _hoisted_6$1 = {
  key: 1,
  class: "ec-placeholder"
};
const _hoisted_7$1 = { class: "ec-meta" };
const _hoisted_8$1 = { class: "ec-templates" };
const _hoisted_9$1 = ["title", "onClick"];
const _hoisted_10$1 = ["src"];
const _hoisted_11$1 = {
  key: 1,
  class: "ec-template-noimg"
};
const _hoisted_12$1 = { class: "ec-template-name" };
const _hoisted_13 = { class: "ec-row-wrap mt-2" };
const _hoisted_14 = { class: "ec-acc-title" };
const _hoisted_15 = { class: "ec-acc-sum ms-auto" };
const _hoisted_16 = {
  key: 0,
  class: "ec-fields"
};
const _hoisted_17 = {
  key: 1,
  class: "ec-fields"
};
const _hoisted_18 = {
  key: 2,
  class: "ec-fields"
};
const _hoisted_19 = {
  key: 3,
  class: "ec-row-wrap"
};
const _hoisted_20 = {
  key: 4,
  class: "ec-chips"
};
const _hoisted_21 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};

const {computed: computed$2,onMounted: onMounted$2,reactive: reactive$1,ref: ref$1} = await importShared('vue');

/**
 * 封面设计面板（单列 / 对齐 ChillPoster）。
 *
 * 自上而下全部占满宽度：
 * - 顶部工具条：刷新 / 生成预览 / 渲染并应用；
 * - 预览横版：合成结果占满整行，关键参数摘要压成图下一行小字；
 * - 模板预设横版：点卡片即载入；
 * - 可折叠分组（点击展开/收起，头部右侧带一行关键值摘要）：
 *   目标对象 → 布局分组 → 文字内容 → 其余布局分组 → 引擎通用 → 封面上传 → 字体。
 *
 * 主/副标题属于「文字内容」（跟随媒体库 / 用户输入），载入模板只套用风格参数。
 */

const _sfc_main$2 = {
  __name: 'CoverDesignPane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  initialConfig: { type: Object, default: () => ({}) },
  servers: { type: Array, default: () => [] },
},
  setup(__props) {

const props = __props;

const designer = useCoverDesigner({
  api: () => props.api,
  pluginId: () => props.pluginId,
  initialConfig: props.initialConfig,
});
const { form, previewImage, previewInfo, message, messageOk, styleGroups, engineGroup } = designer;

/** 删除确认弹窗：模板 / 字体的删除入口太容易误点，统一先确认再执行。 */
const confirm = reactive$1({ show: false, title: '', text: '', action: null });
function askDelete(title, text, action) {
  confirm.title = title;
  confirm.text = text;
  confirm.action = action;
  confirm.show = true;
}
const askDeleteTemplate = template =>
  askDelete(
    '删除模板预设',
    `确定删除「${template.name || template.filename}」吗？内置模板重启插件后会自动补回，自行上传的不会。`,
    () => designer.deleteTemplate(template.filename),
  );
const askDeleteFont = name =>
  askDelete(
    '删除字体',
    `确定删除字体「${name}」吗？正在使用该字体的封面会回退为内置字体。`,
    () => designer.deleteFont(name),
  );
function confirmOk() {
  const action = confirm.action;
  confirm.show = false;
  confirm.action = null;
  if (action) action();
}

const serverItems = computed$2(() =>
  props.servers.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
);

const modeItems = [
  { title: '随机抽取', value: 'random' },
  { title: '最新入库', value: 'latest' },
];

const templateName = ref$1('');

/** 默认只展开 1-2 组：目标对象 + 第一个布局分组（无布局分组时只展开目标对象）。 */
const openSections = ref$1(['target', 'style-0']);

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

/** 字段内的文件上传（主视觉）：上传成功后把文件名写回该字段。 */
async function onFieldUpload(item, file) {
  const name = await designer.uploadKeyart(file);
  if (name) form.config[item.key] = name;
}

/** 字段内的文件删除（主视觉）：先确认，再删文件并清空字段引用。 */
function onFieldDelete(item, name) {
  askDelete(
    '删除底图',
    `确定删除底图「${name}」吗？引用它的模板会回退到媒体库背景图。`,
    () => designer.deleteKeyart(name),
  );
}

const currentLayoutLabel = computed$2(() => {
  const hit = designer.layoutItems.value.find(item => item.value === form.layout);
  return hit ? hit.title : form.layout
});

const currentLibraryName = computed$2(() => {
  const hit = designer.libraries.value.find(item => item.id === form.library_id);
  return hit ? (hit.name || hit.id) : '未选媒体库'
});

const canvasLabel = computed$2(() => {
  const width = Number(form.config.canvas_width || 0);
  const height = Number(form.config.canvas_height || 0);
  return width && height ? `${width} × ${height}` : '—'
});

/** 头部摘要：取前两个有值的可读参数，收起时也能一眼看到关键设置。 */
function summarize(items) {
  const readable = ['range', 'number', 'select', 'font', 'color'];
  const parts = [];
  for (const item of items || []) {
    if (parts.length >= 2) break
    if (!item || !readable.includes(item.type)) continue
    const value = form.config[item.key];
    if (value === undefined || value === null || value === '') continue
    let text = String(value);
    if (item.type === 'select' && Array.isArray(item.options)) {
      const hit = item.options.find(option => String(option.value) === text);
      if (hit) text = String(hit.label || text);
    }
    parts.push(`${item.label} ${text}`);
  }
  return parts.join(' · ') || '—'
}

/** 折叠分组清单：目标对象 → 布局分组 → 文字内容 → 其余布局分组 → 引擎通用 → 封面上传 → 字体。 */
const blocks = computed$2(() => {
  const list = [];
  list.push({
    id: 'target',
    kind: 'target',
    icon: 'mdi-crosshairs-gps',
    title: '目标对象',
    summary: `${form.server || '未选服务器'} · ${currentLibraryName.value} · ${currentLayoutLabel.value}`,
  });
  const styles = styleGroups.value.filter(group => group.items.length);
  if (styles.length) {
    list.push({
      id: 'style-0',
      kind: 'style',
      icon: 'mdi-image-multiple-outline',
      title: styles[0].group,
      summary: summarize(styles[0].items),
      items: styles[0].items,
    });
  }
  list.push({
    id: 'content',
    kind: 'content',
    icon: 'mdi-format-text',
    title: '文字内容',
    summary: `${form.config.title || '—'} / ${form.config.subtitle || '—'}`,
  });
  styles.slice(1).forEach((group, index) => {
    list.push({
      id: `style-${index + 1}`,
      kind: 'style',
      icon: 'mdi-tune-variant',
      title: group.group,
      summary: summarize(group.items),
      items: group.items,
    });
  });
  if (engineGroup.value) {
    list.push({
      id: 'engine',
      kind: 'engine',
      icon: 'mdi-cog-outline',
      title: engineGroup.value.group,
      summary: summarize(engineGroup.value.items),
      items: engineGroup.value.items,
    });
  }
  list.push({ id: 'upload', kind: 'upload', icon: 'mdi-image-plus', title: '封面上传', summary: '成品图替换 / 应用当前预览' });
  list.push({
    id: 'fonts',
    kind: 'fonts',
    icon: 'mdi-format-font',
    title: `字体（${designer.fonts.value.length}）`,
    summary: '点击已装字体右侧 × 可删除',
  });
  return list
});

onMounted$2(designer.loadAll);

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VAlert = _resolveComponent$2("VAlert");
  const _component_VCardTitle = _resolveComponent$2("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$2("VCardSubtitle");
  const _component_VCardItem = _resolveComponent$2("VCardItem");
  const _component_VProgressLinear = _resolveComponent$2("VProgressLinear");
  const _component_VCardText = _resolveComponent$2("VCardText");
  const _component_VCard = _resolveComponent$2("VCard");
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VTextField = _resolveComponent$2("VTextField");
  const _component_VSelect = _resolveComponent$2("VSelect");
  const _component_VChip = _resolveComponent$2("VChip");
  const _component_VExpansionPanel = _resolveComponent$2("VExpansionPanel");
  const _component_VExpansionPanels = _resolveComponent$2("VExpansionPanels");
  const _component_VSpacer = _resolveComponent$2("VSpacer");
  const _component_VCardActions = _resolveComponent$2("VCardActions");
  const _component_VDialog = _resolveComponent$2("VDialog");

  return (_openBlock$2(), _createElementBlock$2("div", _hoisted_1$2, [
    _createElementVNode$2("div", _hoisted_2$2, [
      _cache[14] || (_cache[14] = _createElementVNode$2("div", { class: "ec-toolbar-head" }, [
        _createElementVNode$2("div", { class: "ec-h" }, "封面设计"),
        _createElementVNode$2("div", { class: "ec-sub" }, "选媒体库 → 调风格 → 生成预览 → 应用到媒体库封面")
      ], -1)),
      _createElementVNode$2("div", _hoisted_3$1, [
        _createVNode$2(_component_VBtn, {
          size: "small",
          variant: "text",
          loading: _unref$2(designer).loading.value,
          onClick: _unref$2(designer).loadAll
        }, {
          default: _withCtx$2(() => [...(_cache[11] || (_cache[11] = [
            _createTextVNode$2("刷新", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "onClick"]),
        _createVNode$2(_component_VBtn, {
          size: "small",
          variant: "tonal",
          "prepend-icon": "mdi-image-refresh",
          loading: _unref$2(designer).previewing.value,
          onClick: _unref$2(designer).previewCover
        }, {
          default: _withCtx$2(() => [...(_cache[12] || (_cache[12] = [
            _createTextVNode$2(" 生成预览 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "onClick"]),
        _createVNode$2(_component_VBtn, {
          color: "primary",
          size: "small",
          variant: "flat",
          "prepend-icon": "mdi-check",
          loading: _unref$2(designer).applying.value,
          onClick: _unref$2(designer).applyCover
        }, {
          default: _withCtx$2(() => [...(_cache[13] || (_cache[13] = [
            _createTextVNode$2(" 渲染并应用 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading", "onClick"])
      ])
    ]),
    (_unref$2(message))
      ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
          key: 0,
          type: _unref$2(messageOk) ? 'success' : 'error',
          variant: "tonal",
          density: "compact"
        }, {
          default: _withCtx$2(() => [
            _createTextVNode$2(_toDisplayString$2(_unref$2(message)), 1)
          ]),
          _: 1
        }, 8, ["type"]))
      : _createCommentVNode$2("", true),
    _createVNode$2(_component_VCard, {
      variant: "tonal",
      class: "ec-band"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCardItem, { class: "py-2" }, {
          append: _withCtx$2(() => [
            _createVNode$2(_component_VBtn, {
              size: "small",
              variant: "text",
              "prepend-icon": "mdi-image-refresh",
              loading: _unref$2(designer).previewing.value,
              onClick: _unref$2(designer).previewCover
            }, {
              default: _withCtx$2(() => [...(_cache[17] || (_cache[17] = [
                _createTextVNode$2(" 生成 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "onClick"])
          ]),
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-subtitle-1" }, {
              default: _withCtx$2(() => [...(_cache[15] || (_cache[15] = [
                _createTextVNode$2("预览", -1)
              ]))]),
              _: 1
            }),
            _createVNode$2(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx$2(() => [...(_cache[16] || (_cache[16] = [
                _createTextVNode$2("横版占满 · 生成后可一键应用为当前媒体库封面", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$2(_component_VCardText, null, {
          default: _withCtx$2(() => [
            (_unref$2(designer).previewing.value)
              ? (_openBlock$2(), _createBlock$2(_component_VProgressLinear, {
                  key: 0,
                  indeterminate: "",
                  color: "primary",
                  height: "2",
                  class: "mb-2"
                }))
              : _createCommentVNode$2("", true),
            _createElementVNode$2("div", _hoisted_4$1, [
              (_unref$2(previewImage))
                ? (_openBlock$2(), _createElementBlock$2("img", {
                    key: 0,
                    src: _unref$2(previewImage),
                    class: "ec-preview",
                    alt: "封面预览"
                  }, null, 8, _hoisted_5$1))
                : (_openBlock$2(), _createElementBlock$2("div", _hoisted_6$1, "点击「生成」查看封面效果"))
            ]),
            _createElementVNode$2("div", _hoisted_7$1, [
              _createElementVNode$2("span", null, "布局 " + _toDisplayString$2(currentLayoutLabel.value), 1),
              _createElementVNode$2("span", null, "媒体库 " + _toDisplayString$2(currentLibraryName.value), 1),
              _createElementVNode$2("span", null, "条目 " + _toDisplayString$2(_unref$2(previewInfo).count || 0), 1),
              _createElementVNode$2("span", null, "画布 " + _toDisplayString$2(canvasLabel.value), 1)
            ])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode$2(_component_VCard, {
      variant: "tonal",
      class: "ec-band"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCardItem, { class: "py-2" }, {
          append: _withCtx$2(() => [
            _createVNode$2(_component_VBtn, {
              tag: "label",
              for: "ec-upload-template",
              size: "small",
              variant: "text",
              "prepend-icon": "mdi-upload"
            }, {
              default: _withCtx$2(() => [...(_cache[19] || (_cache[19] = [
                _createTextVNode$2(" 上传 ", -1)
              ]))]),
              _: 1
            })
          ]),
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardTitle, { class: "text-subtitle-1" }, {
              default: _withCtx$2(() => [
                _createTextVNode$2("模板预设（" + _toDisplayString$2(_unref$2(designer).templates.value.length) + "）", 1)
              ]),
              _: 1
            }),
            _createVNode$2(_component_VCardSubtitle, { class: "text-caption" }, {
              default: _withCtx$2(() => [...(_cache[18] || (_cache[18] = [
                _createTextVNode$2("横版占满 · 点击卡片即载入（仅套用风格参数，不改标题/副标题）", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode$2(_component_VCardText, null, {
          default: _withCtx$2(() => [
            _createElementVNode$2("div", _hoisted_8$1, [
              (_openBlock$2(true), _createElementBlock$2(_Fragment$1, null, _renderList$1(_unref$2(designer).templates.value, (template) => {
                return (_openBlock$2(), _createElementBlock$2("div", {
                  key: template.filename,
                  class: _normalizeClass$2(["ec-template", { 'ec-template--active': template.layout === _unref$2(form).layout }]),
                  role: "button",
                  title: `点击载入：${template.name || template.filename}`,
                  onClick: $event => (_unref$2(designer).loadTemplate(template))
                }, [
                  (template.has_preview)
                    ? (_openBlock$2(), _createElementBlock$2("img", {
                        key: 0,
                        src: _unref$2(designer).templatePreviewUrl(template),
                        class: "ec-template-thumb",
                        alt: ""
                      }, null, 8, _hoisted_10$1))
                    : (_openBlock$2(), _createElementBlock$2("div", _hoisted_11$1, _toDisplayString$2(template.layout), 1)),
                  _createVNode$2(_component_VBtn, {
                    class: "ec-template-del",
                    size: "x-small",
                    icon: "",
                    variant: "text",
                    title: "删除模板",
                    onClick: _withModifiers($event => (askDeleteTemplate(template)), ["stop"])
                  }, {
                    default: _withCtx$2(() => [
                      _createVNode$2(_component_VIcon, {
                        icon: "mdi-close",
                        size: "14"
                      })
                    ]),
                    _: 1
                  }, 8, ["onClick"]),
                  _createElementVNode$2("div", _hoisted_12$1, _toDisplayString$2(template.name || template.filename), 1)
                ], 10, _hoisted_9$1))
              }), 128))
            ]),
            _createElementVNode$2("div", _hoisted_13, [
              _createVNode$2(_component_VTextField, {
                modelValue: templateName.value,
                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((templateName).value = $event)),
                label: "模板文件名",
                placeholder: "如 我的封面.json",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                class: "ec-template-input"
              }, null, 8, ["modelValue"]),
              _createVNode$2(_component_VBtn, {
                size: "small",
                variant: "tonal",
                disabled: !templateName.value,
                onClick: _cache[1] || (_cache[1] = $event => (_unref$2(designer).saveTemplate(templateName.value)))
              }, {
                default: _withCtx$2(() => [...(_cache[20] || (_cache[20] = [
                  _createTextVNode$2(" 保存当前 ", -1)
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
    _createVNode$2(_component_VExpansionPanels, {
      modelValue: openSections.value,
      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((openSections).value = $event)),
      variant: "accordion",
      flat: "",
      multiple: "",
      class: "ec-acc"
    }, {
      default: _withCtx$2(() => [
        (_openBlock$2(true), _createElementBlock$2(_Fragment$1, null, _renderList$1(blocks.value, (block) => {
          return (_openBlock$2(), _createBlock$2(_component_VExpansionPanel, {
            key: block.id,
            value: block.id
          }, {
            title: _withCtx$2(() => [
              _createVNode$2(_component_VIcon, {
                icon: block.icon,
                size: "18",
                class: "ec-acc-icon me-2"
              }, null, 8, ["icon"]),
              _createElementVNode$2("span", _hoisted_14, _toDisplayString$2(block.title), 1),
              _createElementVNode$2("span", _hoisted_15, _toDisplayString$2(block.summary), 1)
            ]),
            text: _withCtx$2(() => [
              (block.kind === 'target')
                ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_16, [
                    _createVNode$2(_component_VSelect, {
                      modelValue: _unref$2(form).server,
                      "onUpdate:modelValue": [
                        _cache[2] || (_cache[2] = $event => ((_unref$2(form).server) = $event)),
                        _unref$2(designer).onServerChange
                      ],
                      items: serverItems.value,
                      label: "媒体服务器",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "items", "onUpdate:modelValue"]),
                    _createVNode$2(_component_VSelect, {
                      modelValue: _unref$2(form).library_id,
                      "onUpdate:modelValue": [
                        _cache[3] || (_cache[3] = $event => ((_unref$2(form).library_id) = $event)),
                        _unref$2(designer).syncFromLibrary
                      ],
                      items: _unref$2(designer).libraryItems.value,
                      label: "媒体库",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "items", "onUpdate:modelValue"]),
                    _createVNode$2(_component_VSelect, {
                      modelValue: _unref$2(form).layout,
                      "onUpdate:modelValue": [
                        _cache[4] || (_cache[4] = $event => ((_unref$2(form).layout) = $event)),
                        _unref$2(designer).onLayoutChange
                      ],
                      items: _unref$2(designer).layoutItems.value,
                      label: "风格（布局）",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "items", "onUpdate:modelValue"]),
                    _createVNode$2(_component_VSelect, {
                      modelValue: _unref$2(form).mode,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((_unref$2(form).mode) = $event)),
                      items: modeItems,
                      label: "素材模式",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]))
                : (block.kind === 'content')
                  ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_17, [
                      _createVNode$2(_component_VTextField, {
                        modelValue: _unref$2(form).config.title,
                        "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((_unref$2(form).config.title) = $event)),
                        label: "主标题内容",
                        density: "compact",
                        variant: "outlined",
                        "hide-details": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode$2(_component_VTextField, {
                        modelValue: _unref$2(form).config.subtitle,
                        "onUpdate:modelValue": [
                          _cache[7] || (_cache[7] = $event => ((_unref$2(form).config.subtitle) = $event)),
                          _unref$2(designer).onSubtitleEdited
                        ],
                        label: "副标题内容（英文名）",
                        density: "compact",
                        variant: "outlined",
                        "hide-details": ""
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _cache[21] || (_cache[21] = _createElementVNode$2("div", { class: "text-caption text-medium-emphasis ec-span" }, " 主标题跟随所选媒体库，副标题自动取英文名（手填即记住该库），载入模板不会改它们。 ", -1))
                    ]))
                  : (block.kind === 'style' || block.kind === 'engine')
                    ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_18, [
                        (_openBlock$2(true), _createElementBlock$2(_Fragment$1, null, _renderList$1(block.items, (item) => {
                          return (_openBlock$2(), _createBlock$2(CoverField, {
                            key: item.key,
                            item: item,
                            config: _unref$2(form).config,
                            fonts: _unref$2(designer).fontItems.value,
                            files: _unref$2(designer).keyartFiles.value,
                            onUpload: $event => (onFieldUpload(item, $event)),
                            onDelete: $event => (onFieldDelete(item, $event))
                          }, null, 8, ["item", "config", "fonts", "files", "onUpload", "onDelete"]))
                        }), 128))
                      ]))
                    : (block.kind === 'upload')
                      ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_19, [
                          _createVNode$2(_component_VBtn, {
                            tag: "label",
                            for: "ec-upload-local-image",
                            size: "small",
                            variant: "tonal",
                            "prepend-icon": "mdi-image",
                            loading: _unref$2(designer).applying.value
                          }, {
                            default: _withCtx$2(() => [...(_cache[22] || (_cache[22] = [
                              _createTextVNode$2(" 选择本地封面（直接替换） ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["loading"]),
                          _createVNode$2(_component_VBtn, {
                            size: "small",
                            variant: "tonal",
                            "prepend-icon": "mdi-content-save-check",
                            disabled: !_unref$2(previewImage),
                            loading: _unref$2(designer).applying.value,
                            onClick: _unref$2(designer).applyPreviewImage
                          }, {
                            default: _withCtx$2(() => [...(_cache[23] || (_cache[23] = [
                              _createTextVNode$2(" 应用当前预览图 ", -1)
                            ]))]),
                            _: 1
                          }, 8, ["disabled", "loading", "onClick"])
                        ]))
                      : (block.kind === 'fonts')
                        ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_20, [
                            (_openBlock$2(true), _createElementBlock$2(_Fragment$1, null, _renderList$1(_unref$2(designer).fonts.value, (name) => {
                              return (_openBlock$2(), _createBlock$2(_component_VChip, {
                                key: name,
                                size: "small",
                                variant: "tonal",
                                closable: "",
                                "onClick:close": $event => (askDeleteFont(name))
                              }, {
                                default: _withCtx$2(() => [
                                  _createTextVNode$2(_toDisplayString$2(name), 1)
                                ]),
                                _: 2
                              }, 1032, ["onClick:close"]))
                            }), 128)),
                            (!_unref$2(designer).fonts.value.length)
                              ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_21, " 未上传字体（中文会回退为方块），请先上传 .ttf/.otf "))
                              : _createCommentVNode$2("", true),
                            _createVNode$2(_component_VBtn, {
                              tag: "label",
                              for: "ec-upload-font",
                              size: "small",
                              variant: "text",
                              "prepend-icon": "mdi-upload"
                            }, {
                              default: _withCtx$2(() => [...(_cache[24] || (_cache[24] = [
                                _createTextVNode$2(" 上传字体 ", -1)
                              ]))]),
                              _: 1
                            })
                          ]))
                        : _createCommentVNode$2("", true)
            ]),
            _: 2
          }, 1032, ["value"]))
        }), 128))
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createElementVNode$2("input", {
      id: "ec-upload-font",
      type: "file",
      accept: ".ttf,.otf,.ttc",
      class: "ec-file-input",
      onChange: onFontPicked
    }, null, 32),
    _createElementVNode$2("input", {
      id: "ec-upload-template",
      type: "file",
      accept: ".json",
      class: "ec-file-input",
      onChange: onTemplatePicked
    }, null, 32),
    _createElementVNode$2("input", {
      id: "ec-upload-local-image",
      type: "file",
      accept: "image/*",
      class: "ec-file-input",
      onChange: onLocalImagePicked
    }, null, 32),
    _createVNode$2(_component_VDialog, {
      modelValue: confirm.show,
      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((confirm.show) = $event)),
      "max-width": "400"
    }, {
      default: _withCtx$2(() => [
        _createVNode$2(_component_VCard, null, {
          default: _withCtx$2(() => [
            _createVNode$2(_component_VCardItem, { class: "py-3" }, {
              default: _withCtx$2(() => [
                _createVNode$2(_component_VCardTitle, { class: "text-subtitle-1" }, {
                  default: _withCtx$2(() => [
                    _createTextVNode$2(_toDisplayString$2(confirm.title), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode$2(_component_VCardText, { class: "text-body-2" }, {
              default: _withCtx$2(() => [
                _createTextVNode$2(_toDisplayString$2(confirm.text), 1)
              ]),
              _: 1
            }),
            _createVNode$2(_component_VCardActions, null, {
              default: _withCtx$2(() => [
                _createVNode$2(_component_VSpacer),
                _createVNode$2(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[9] || (_cache[9] = $event => (confirm.show = false))
                }, {
                  default: _withCtx$2(() => [...(_cache[25] || (_cache[25] = [
                    _createTextVNode$2("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode$2(_component_VBtn, {
                  color: "error",
                  variant: "flat",
                  onClick: confirmOk
                }, {
                  default: _withCtx$2(() => [...(_cache[26] || (_cache[26] = [
                    _createTextVNode$2("删除", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const CoverDesignPane = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-1162b088"]]);

/**
 * Emby 计划任务中心的前端状态与动作。
 *
 * 数据来自插件 API `/emby_tasks`（已归一化：中文标签、触发器摘要、运行状态），
 * 本模块只负责轮询、操作与触发器草稿管理，不做本地推测。
 */
const {reactive} = await importShared('vue');

const TRIGGER_TYPE_OPTIONS = [
  { value: 'DailyTrigger', label: '每天' },
  { value: 'WeeklyTrigger', label: '每周' },
  { value: 'IntervalTrigger', label: '按间隔' },
  { value: 'StartupTrigger', label: '服务器启动时' },
];

const WEEK_DAY_OPTIONS = [
  { value: 'Monday', label: '周一' },
  { value: 'Tuesday', label: '周二' },
  { value: 'Wednesday', label: '周三' },
  { value: 'Thursday', label: '周四' },
  { value: 'Friday', label: '周五' },
  { value: 'Saturday', label: '周六' },
  { value: 'Sunday', label: '周日' },
];

function defaultDraft() {
  return {
    type: 'DailyTrigger',
    time: '00:00',
    day_of_week: 'Monday',
    interval_hours: 24,
    max_runtime_hours: '',
  }
}

function draftFromTrigger(trigger) {
  return {
    type: trigger?.type || 'DailyTrigger',
    time: trigger?.time || '00:00',
    day_of_week: trigger?.day_of_week || 'Monday',
    interval_hours: trigger?.interval_hours || 24,
    max_runtime_hours: trigger?.max_runtime_hours || '',
  }
}

function useEmbyTasks({ api, pluginId, notify }) {
  const state = reactive({
    loading: false,
    actionId: '',
    server: '',
    categories: [],
    runningCount: 0,
    updatedAt: '',
    error: '',
  });

  const dialog = reactive({
    visible: false,
    loading: false,
    saving: false,
    taskId: '',
    taskName: '',
    triggers: [],
  });

  function report(message, ok = true) {
    if (typeof notify === 'function') notify(message, ok);
  }

  async function load() {
    if (state.loading) return
    state.loading = true;
    state.error = '';
    try {
      const target = String(pluginId() || '');
      const query = state.server ? `?server=${encodeURIComponent(state.server)}` : '';
      const data = unwrap(await getPluginApi(api(), target, `emby_tasks${query}`)) || {};
      state.categories = Array.isArray(data.categories) ? data.categories : [];
      state.runningCount = Number(data.running_count || 0);
      state.updatedAt = String(data.updated_at || '');
    } catch (error) {
      state.categories = [];
      state.error = error?.message || 'Emby 任务读取失败';
    } finally {
      state.loading = false;
    }
  }

  async function action(taskId, verb, okMessage) {
    if (state.actionId) return
    state.actionId = taskId;
    try {
      const body = { server: state.server };
      await postPluginApi(api(), pluginId(), `emby_tasks/${encodeURIComponent(taskId)}/${verb}`, body);
      report(okMessage);
      await load();
    } catch (error) {
      report(error?.message || '操作失败', false);
    } finally {
      state.actionId = '';
    }
  }

  function run(taskId) {
    return action(taskId, 'run', '任务已启动')
  }

  function stop(taskId) {
    return action(taskId, 'stop', '停止命令已发送')
  }

  async function openTriggers(task) {
    if (dialog.loading) return
    dialog.loading = true;
    dialog.taskId = task.id;
    dialog.taskName = task.name;
    dialog.triggers = [];
    dialog.visible = true;
    try {
      const query = state.server ? `?server=${encodeURIComponent(state.server)}` : '';
      const data = unwrap(
        await getPluginApi(api(), pluginId(), `emby_tasks/${encodeURIComponent(task.id)}${query}`),
      ) || {};
      const triggers = Array.isArray(data.triggers) ? data.triggers : [];
      dialog.triggers = triggers.map(draftFromTrigger);
      if (!dialog.triggers.length) dialog.triggers = [defaultDraft()];
    } catch (error) {
      dialog.triggers = [defaultDraft()];
      report(error?.message || '触发器读取失败', false);
    } finally {
      dialog.loading = false;
    }
  }

  function addDraft() {
    dialog.triggers.push(defaultDraft());
  }

  function removeDraft(index) {
    dialog.triggers.splice(index, 1);
    if (!dialog.triggers.length) dialog.triggers.push(defaultDraft());
  }

  function closeDialog() {
    dialog.visible = false;
    dialog.triggers = [];
  }

  async function saveTriggers() {
    if (dialog.saving) return
    dialog.saving = true;
    try {
      const body = {
        server: state.server,
        triggers: dialog.triggers.map(item => ({
          type: item.type,
          time: item.time,
          day_of_week: item.day_of_week,
          interval_hours: Number(item.interval_hours || 0),
          max_runtime_hours: Number(item.max_runtime_hours || 0),
        })),
      };
      await postPluginApi(
        api(),
        pluginId(),
        `emby_tasks/${encodeURIComponent(dialog.taskId)}/triggers`,
        body,
      );
      report('触发器已保存');
      closeDialog();
      await load();
    } catch (error) {
      report(error?.message || '触发器保存失败', false);
    } finally {
      dialog.saving = false;
    }
  }

  return { state, dialog, load, run, stop, openTriggers, addDraft, removeDraft, closeDialog, saveTriggers }
}

const {unref:_unref$1,toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,createVNode:_createVNode$1,createElementVNode:_createElementVNode$1,createElementBlock:_createElementBlock$1,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass$1} = await importShared('vue');


const _hoisted_1$1 = { class: "ec-actions" };
const _hoisted_2$1 = {
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_3 = { class: "ec-cats" };
const _hoisted_4 = { class: "ec-cat-head" };
const _hoisted_5 = { class: "ec-cat-name" };
const _hoisted_6 = { class: "ec-task-list" };
const _hoisted_7 = { class: "ec-task-main" };
const _hoisted_8 = { class: "ec-task-title" };
const _hoisted_9 = { class: "ec-task-meta" };
const _hoisted_10 = { key: 0 };
const _hoisted_11 = { class: "ec-task-side" };
const _hoisted_12 = {
  key: 0,
  class: "ec-progress"
};

const {computed: computed$1,onMounted: onMounted$1} = await importShared('vue');

/**
 * Emby 计划任务中心面板。
 *
 * 分类卡片双列瀑布流（全部展开、CSS 多列自动填充，窄屏自动回退单列）；
 * 任务行卡片化，支持编辑触发器、立即运行、停止。
 */

const _sfc_main$1 = {
  __name: 'EmbyTasksPanel',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  servers: { type: Array, default: () => [] },
},
  emits: ['notify'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const tasks = useEmbyTasks({
  api: () => props.api,
  pluginId: () => props.pluginId,
  notify: (message, ok) => emit('notify', message, ok),
});

const { state, dialog } = tasks;
const { load, run, stop, openTriggers, addDraft, removeDraft, closeDialog, saveTriggers } = tasks;

const serverItems = computed$1(() =>
  props.servers.map(server => ({
    title: server.active ? server.name : `${server.name}（未连接）`,
    value: server.name,
  })),
);

function runningCountIn(category) {
  return (category.tasks || []).filter(task => task.is_running).length
}

function statusColor(task) {
  if (task.status_type === 'running') return 'primary'
  if (task.status_type === 'success') return 'success'
  if (task.status_type === 'error') return 'error'
  if (task.status_type === 'cancelled') return 'warning'
  return 'grey'
}

onMounted$1(load);

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VCardTitle = _resolveComponent$1("VCardTitle");
  const _component_VCardSubtitle = _resolveComponent$1("VCardSubtitle");
  const _component_VSelect = _resolveComponent$1("VSelect");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VCardItem = _resolveComponent$1("VCardItem");
  const _component_VProgressLinear = _resolveComponent$1("VProgressLinear");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VDivider = _resolveComponent$1("VDivider");
  const _component_VTextField = _resolveComponent$1("VTextField");
  const _component_VSpacer = _resolveComponent$1("VSpacer");
  const _component_VCardActions = _resolveComponent$1("VCardActions");
  const _component_VCard = _resolveComponent$1("VCard");
  const _component_VDialog = _resolveComponent$1("VDialog");

  return (_openBlock$1(), _createBlock$1(_component_VCard, {
    variant: "tonal",
    class: "ec-tasks"
  }, {
    default: _withCtx$1(() => [
      _createVNode$1(_component_VCardItem, { class: "ec-tasks-head" }, {
        append: _withCtx$1(() => [
          _createElementVNode$1("div", _hoisted_1$1, [
            (serverItems.value.length > 1)
              ? (_openBlock$1(), _createBlock$1(_component_VSelect, {
                  key: 0,
                  modelValue: _unref$1(state).server,
                  "onUpdate:modelValue": [
                    _cache[0] || (_cache[0] = $event => ((_unref$1(state).server) = $event)),
                    _unref$1(load)
                  ],
                  items: serverItems.value,
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  class: "ec-server"
                }, null, 8, ["modelValue", "items", "onUpdate:modelValue"]))
              : _createCommentVNode$1("", true),
            _createVNode$1(_component_VBtn, {
              size: "small",
              variant: "text",
              loading: _unref$1(state).loading,
              onClick: _unref$1(load)
            }, {
              default: _withCtx$1(() => [...(_cache[3] || (_cache[3] = [
                _createTextVNode$1("刷新", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "onClick"])
          ])
        ]),
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCardTitle, { class: "text-subtitle-1" }, {
            default: _withCtx$1(() => [
              _cache[2] || (_cache[2] = _createTextVNode$1(" Emby 任务中心 ", -1)),
              (_unref$1(state).runningCount)
                ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                    key: 0,
                    color: "primary",
                    variant: "tonal",
                    size: "small",
                    label: "",
                    class: "ms-2"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(_unref$1(state).runningCount) + " 运行中 ", 1)
                    ]),
                    _: 1
                  }))
                : _createCommentVNode$1("", true)
            ]),
            _: 1
          }),
          (_unref$1(state).updatedAt)
            ? (_openBlock$1(), _createBlock$1(_component_VCardSubtitle, {
                key: 0,
                class: "text-caption"
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(" 更新于 " + _toDisplayString$1(_unref$1(state).updatedAt), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode$1("", true)
        ]),
        _: 1
      }),
      (_unref$1(state).loading)
        ? (_openBlock$1(), _createBlock$1(_component_VProgressLinear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            height: "2"
          }))
        : _createCommentVNode$1("", true),
      _createVNode$1(_component_VCardText, null, {
        default: _withCtx$1(() => [
          (_unref$1(state).error)
            ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "mb-2"
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(_toDisplayString$1(_unref$1(state).error), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode$1("", true),
          (!_unref$1(state).categories.length && !_unref$1(state).error)
            ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_2$1, " 暂无任务数据。 "))
            : _createCommentVNode$1("", true),
          _createElementVNode$1("div", _hoisted_3, [
            (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(_unref$1(state).categories, (category) => {
              return (_openBlock$1(), _createElementBlock$1("div", {
                key: category.name,
                class: "ec-cat"
              }, [
                _createElementVNode$1("div", _hoisted_4, [
                  _createVNode$1(_component_VIcon, {
                    icon: "mdi-view-list-outline",
                    size: "16",
                    class: "ec-cat-icon"
                  }),
                  _createElementVNode$1("span", _hoisted_5, _toDisplayString$1(category.name), 1),
                  _createVNode$1(_component_VChip, {
                    size: "x-small",
                    variant: "tonal",
                    color: "grey",
                    label: ""
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(category.count), 1)
                    ]),
                    _: 2
                  }, 1024),
                  (runningCountIn(category))
                    ? (_openBlock$1(), _createBlock$1(_component_VChip, {
                        key: 0,
                        size: "x-small",
                        variant: "tonal",
                        color: "primary",
                        label: ""
                      }, {
                        default: _withCtx$1(() => [
                          _createTextVNode$1(_toDisplayString$1(runningCountIn(category)) + " 运行中 ", 1)
                        ]),
                        _: 2
                      }, 1024))
                    : _createCommentVNode$1("", true)
                ]),
                _createElementVNode$1("div", _hoisted_6, [
                  (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(category.tasks, (task) => {
                    return (_openBlock$1(), _createElementBlock$1("div", {
                      key: task.id,
                      class: _normalizeClass$1(["ec-task", { 'ec-task--running': task.is_running }])
                    }, [
                      _createVNode$1(_component_VChip, {
                        color: statusColor(task),
                        variant: "tonal",
                        size: "small",
                        label: "",
                        class: "ec-task-chip"
                      }, {
                        default: _withCtx$1(() => [
                          _createTextVNode$1(_toDisplayString$1(task.status_label), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"]),
                      _createElementVNode$1("div", _hoisted_7, [
                        _createElementVNode$1("div", _hoisted_8, _toDisplayString$1(task.name), 1),
                        _createElementVNode$1("div", _hoisted_9, [
                          _createTextVNode$1(_toDisplayString$1(task.trigger_summary) + " ", 1),
                          (task.last_run_time)
                            ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_10, " · 上次 " + _toDisplayString$1(task.last_run_time), 1))
                            : _createCommentVNode$1("", true)
                        ])
                      ]),
                      _createElementVNode$1("div", _hoisted_11, [
                        (task.is_running)
                          ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_12, _toDisplayString$1(task.progress) + "%", 1))
                          : _createCommentVNode$1("", true),
                        _createVNode$1(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          "prepend-icon": "mdi-play",
                          title: "立即运行",
                          disabled: !!_unref$1(state).actionId && _unref$1(state).actionId !== task.id,
                          loading: _unref$1(state).actionId === task.id,
                          onClick: $event => (_unref$1(run)(task.id))
                        }, {
                          default: _withCtx$1(() => [...(_cache[4] || (_cache[4] = [
                            _createTextVNode$1(" 运行 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled", "loading", "onClick"]),
                        (task.is_running)
                          ? (_openBlock$1(), _createBlock$1(_component_VBtn, {
                              key: 1,
                              size: "small",
                              color: "error",
                              variant: "text",
                              "prepend-icon": "mdi-stop",
                              title: "停止",
                              disabled: !!_unref$1(state).actionId && _unref$1(state).actionId !== task.id,
                              loading: _unref$1(state).actionId === task.id,
                              onClick: $event => (_unref$1(stop)(task.id))
                            }, {
                              default: _withCtx$1(() => [...(_cache[5] || (_cache[5] = [
                                _createTextVNode$1(" 停止 ", -1)
                              ]))]),
                              _: 1
                            }, 8, ["disabled", "loading", "onClick"]))
                          : _createCommentVNode$1("", true),
                        _createVNode$1(_component_VBtn, {
                          size: "small",
                          variant: "text",
                          "prepend-icon": "mdi-clock-edit-outline",
                          title: "编辑触发器",
                          disabled: !!_unref$1(state).actionId,
                          onClick: $event => (_unref$1(openTriggers)(task))
                        }, {
                          default: _withCtx$1(() => [...(_cache[6] || (_cache[6] = [
                            _createTextVNode$1(" 触发器 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["disabled", "onClick"])
                      ]),
                      (task.is_running)
                        ? (_openBlock$1(), _createBlock$1(_component_VProgressLinear, {
                            key: 0,
                            "model-value": task.progress,
                            height: "3",
                            color: "primary",
                            rounded: "",
                            class: "ec-task-bar"
                          }, null, 8, ["model-value"]))
                        : _createCommentVNode$1("", true)
                    ], 2))
                  }), 128))
                ])
              ]))
            }), 128))
          ])
        ]),
        _: 1
      }),
      _createVNode$1(_component_VDialog, {
        modelValue: _unref$1(dialog).visible,
        "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((_unref$1(dialog).visible) = $event)),
        "max-width": "760",
        persistent: _unref$1(dialog).saving
      }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCard, null, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VCardItem, null, {
                append: _withCtx$1(() => [
                  _createVNode$1(_component_VBtn, {
                    size: "small",
                    icon: "",
                    variant: "text",
                    disabled: _unref$1(dialog).saving,
                    onClick: _unref$1(closeDialog)
                  }, {
                    default: _withCtx$1(() => [
                      _createVNode$1(_component_VIcon, {
                        icon: "mdi-close",
                        size: "18"
                      })
                    ]),
                    _: 1
                  }, 8, ["disabled", "onClick"])
                ]),
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VCardTitle, { class: "text-subtitle-1" }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1("触发器 · " + _toDisplayString$1(_unref$1(dialog).taskName), 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode$1(_component_VDivider),
              _createVNode$1(_component_VCardText, { class: "ec-trigger-body" }, {
                default: _withCtx$1(() => [
                  (_unref$1(dialog).loading)
                    ? (_openBlock$1(), _createBlock$1(_component_VProgressLinear, {
                        key: 0,
                        indeterminate: "",
                        color: "primary",
                        height: "2"
                      }))
                    : _createCommentVNode$1("", true),
                  (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(_unref$1(dialog).triggers, (draft, index) => {
                    return (_openBlock$1(), _createElementBlock$1("div", {
                      key: index,
                      class: "ec-trigger-row"
                    }, [
                      _createVNode$1(_component_VSelect, {
                        modelValue: draft.type,
                        "onUpdate:modelValue": $event => ((draft.type) = $event),
                        items: _unref$1(TRIGGER_TYPE_OPTIONS),
                        "item-title": "label",
                        "item-value": "value",
                        label: "类型",
                        density: "compact",
                        variant: "outlined",
                        "hide-details": ""
                      }, null, 8, ["modelValue", "onUpdate:modelValue", "items"]),
                      (draft.type === 'DailyTrigger' || draft.type === 'WeeklyTrigger')
                        ? (_openBlock$1(), _createBlock$1(_component_VTextField, {
                            key: 0,
                            modelValue: draft.time,
                            "onUpdate:modelValue": $event => ((draft.time) = $event),
                            label: "时间 HH:MM",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                        : _createCommentVNode$1("", true),
                      (draft.type === 'WeeklyTrigger')
                        ? (_openBlock$1(), _createBlock$1(_component_VSelect, {
                            key: 1,
                            modelValue: draft.day_of_week,
                            "onUpdate:modelValue": $event => ((draft.day_of_week) = $event),
                            items: _unref$1(WEEK_DAY_OPTIONS),
                            "item-title": "label",
                            "item-value": "value",
                            label: "星期",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue", "items"]))
                        : _createCommentVNode$1("", true),
                      (draft.type === 'IntervalTrigger')
                        ? (_openBlock$1(), _createBlock$1(_component_VTextField, {
                            key: 2,
                            modelValue: draft.interval_hours,
                            "onUpdate:modelValue": $event => ((draft.interval_hours) = $event),
                            type: "number",
                            label: "间隔（小时）",
                            density: "compact",
                            variant: "outlined",
                            "hide-details": ""
                          }, null, 8, ["modelValue", "onUpdate:modelValue"]))
                        : _createCommentVNode$1("", true),
                      _createVNode$1(_component_VTextField, {
                        modelValue: draft.max_runtime_hours,
                        "onUpdate:modelValue": $event => ((draft.max_runtime_hours) = $event),
                        type: "number",
                        label: "最长运行（小时，可空）",
                        density: "compact",
                        variant: "outlined",
                        "hide-details": ""
                      }, null, 8, ["modelValue", "onUpdate:modelValue"]),
                      _createVNode$1(_component_VBtn, {
                        size: "small",
                        icon: "",
                        variant: "text",
                        disabled: _unref$1(dialog).saving,
                        onClick: $event => (_unref$1(removeDraft)(index))
                      }, {
                        default: _withCtx$1(() => [
                          _createVNode$1(_component_VIcon, {
                            icon: "mdi-delete-outline",
                            size: "18"
                          })
                        ]),
                        _: 1
                      }, 8, ["disabled", "onClick"])
                    ]))
                  }), 128)),
                  _createVNode$1(_component_VBtn, {
                    size: "small",
                    variant: "text",
                    "prepend-icon": "mdi-plus",
                    disabled: _unref$1(dialog).saving,
                    onClick: _unref$1(addDraft)
                  }, {
                    default: _withCtx$1(() => [...(_cache[7] || (_cache[7] = [
                      _createTextVNode$1(" 添加计划 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "onClick"])
                ]),
                _: 1
              }),
              _createVNode$1(_component_VDivider),
              _createVNode$1(_component_VCardActions, null, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VSpacer),
                  _createVNode$1(_component_VBtn, {
                    variant: "text",
                    disabled: _unref$1(dialog).saving,
                    onClick: _unref$1(closeDialog)
                  }, {
                    default: _withCtx$1(() => [...(_cache[8] || (_cache[8] = [
                      _createTextVNode$1("取消", -1)
                    ]))]),
                    _: 1
                  }, 8, ["disabled", "onClick"]),
                  _createVNode$1(_component_VBtn, {
                    color: "primary",
                    variant: "flat",
                    loading: _unref$1(dialog).saving,
                    disabled: _unref$1(dialog).saving,
                    onClick: _unref$1(saveTriggers)
                  }, {
                    default: _withCtx$1(() => [...(_cache[9] || (_cache[9] = [
                      _createTextVNode$1(" 保存触发器 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading", "disabled", "onClick"])
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue", "persistent"])
    ]),
    _: 1
  }))
}
}

};
const EmbyTasksPanel = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-18525921"]]);

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,unref:_unref,normalizeClass:_normalizeClass,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "ec-status" };
const _hoisted_2 = { class: "ec-chips" };

const {computed,onMounted,ref} = await importShared('vue');

/**
 * 插件详情页 / 侧栏整页内容。
 *
 * 主区分成两个可切换的 Tab：「封面设计」与「Emby 任务中心」；顶部工具条保留
 * 刷新 / 连通测试 / 设置入口，配置弹窗仍复用 Config.vue。
 */

const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'EmbyCoverCenter' },
  appPage: { type: Boolean, default: false },
},
  emits: ['switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const tab = ref('cover');
const loading = ref(false);
const status = ref({});
const config = ref(null);
const loadError = ref('');
const actionMessage = ref('');
const actionOk = ref(true);

const backendVersion = computed(() => String(status.value.plugin_version || ''));
const versionMismatched = computed(
  () => !!backendVersion.value && backendVersion.value !== FRONTEND_VERSION,
);
const servers = computed(() => (Array.isArray(status.value.servers) ? status.value.servers : []));
const activeCount = computed(() => servers.value.filter(server => server.active).length);

async function load() {
  if (loading.value) return
  loading.value = true;
  loadError.value = '';
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status')) || {};
  } catch (error) {
    loadError.value = error?.message || '状态读取失败';
  } finally {
    loading.value = false;
  }
  // 封面设计从已保存配置起步（取不到就用内置默认，不影响使用）。
  try {
    config.value = (await getPluginConfig(props.api, props.pluginId)) || {};
  } catch (error) {
    config.value = {};
  }
}

async function ping() {
  actionMessage.value = '';
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'ping')) || {};
    actionOk.value = true;
    actionMessage.value = `连通正常 · 后端 v${data.plugin_version || backendVersion.value || '?'}`;
  } catch (error) {
    actionOk.value = false;
    actionMessage.value = error?.message || '连通性测试失败';
  }
}

function onNotify(message, ok = true) {
  actionOk.value = ok !== false;
  actionMessage.value = message || '';
}

onMounted(load);

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VToolbar = _resolveComponent("VToolbar");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
  const _component_VWindow = _resolveComponent("VWindow");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    flat: "",
    class: _normalizeClass(["ec-page", { 'ec-page--app': props.appPage }])
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VToolbar, {
        density: "comfortable",
        class: "ec-toolbar"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal",
            rounded: "lg",
            size: "32",
            class: "ms-3 me-2"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-image-multiple-outline" })
            ]),
            _: 1
          }),
          _cache[7] || (_cache[7] = _createElementVNode("div", { class: "ec-heading" }, [
            _createElementVNode("div", { class: "text-h6" }, "胖虎封面中心"),
            _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "Emby 媒体库封面生成与任务中心")
          ], -1)),
          _createVNode(_component_VSpacer),
          _createVNode(_component_VBtn, {
            size: "small",
            variant: "text",
            loading: loading.value,
            onClick: load
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: "mdi-refresh",
                size: "18"
              }),
              _cache[4] || (_cache[4] = _createElementVNode("span", { class: "ec-label" }, "刷新", -1))
            ]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_VBtn, {
            size: "small",
            variant: "text",
            onClick: ping
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: "mdi-lan-connect",
                size: "18"
              }),
              _cache[5] || (_cache[5] = _createElementVNode("span", { class: "ec-label" }, "连通测试", -1))
            ]),
            _: 1
          }),
          _createVNode(_component_VBtn, {
            size: "small",
            variant: "text",
            onClick: _cache[0] || (_cache[0] = $event => (emit('switch')))
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, {
                icon: "mdi-cog-outline",
                size: "18"
              }),
              _cache[6] || (_cache[6] = _createElementVNode("span", { class: "ec-label" }, "设置", -1))
            ]),
            _: 1
          }),
          (!props.appPage)
            ? (_openBlock(), _createBlock(_component_VBtn, {
                key: 0,
                size: "small",
                icon: "",
                variant: "text",
                onClick: _cache[1] || (_cache[1] = $event => (emit('close')))
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VIcon, {
                    icon: "mdi-close",
                    size: "18"
                  })
                ]),
                _: 1
              }))
            : _createCommentVNode("", true)
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      (loading.value)
        ? (_openBlock(), _createBlock(_component_VProgressLinear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            height: "2"
          }))
        : _createCommentVNode("", true),
      _createElementVNode("div", _hoisted_1, [
        _createElementVNode("div", _hoisted_2, [
          _createVNode(_component_VChip, {
            color: status.value.enabled ? 'success' : 'grey',
            variant: "tonal",
            size: "small",
            label: ""
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(status.value.enabled ? '已启用' : '已停用'), 1)
            ]),
            _: 1
          }, 8, ["color"]),
          _createVNode(_component_VChip, {
            color: "primary",
            variant: "tonal",
            size: "small",
            label: ""
          }, {
            default: _withCtx(() => [
              _createTextVNode("v" + _toDisplayString(backendVersion.value || '—'), 1)
            ]),
            _: 1
          }),
          _createVNode(_component_VChip, {
            color: "info",
            variant: "tonal",
            size: "small",
            label: ""
          }, {
            default: _withCtx(() => [
              _createTextVNode(" 服务器 " + _toDisplayString(activeCount.value) + "/" + _toDisplayString(servers.value.length), 1)
            ]),
            _: 1
          })
        ]),
        (loadError.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 0,
              type: "warning",
              variant: "tonal",
              density: "compact",
              class: "ec-full"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(loadError.value) + " ", 1),
                _createVNode(_component_VBtn, {
                  size: "x-small",
                  variant: "text",
                  class: "text-none",
                  onClick: load
                }, {
                  default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                    _createTextVNode("重试", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        (versionMismatched.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 1,
              type: "info",
              variant: "tonal",
              density: "compact",
              class: "ec-full"
            }, {
              default: _withCtx(() => [
                _createTextVNode(" 前端组件 v" + _toDisplayString(_unref(FRONTEND_VERSION)) + " ≠ 后端 v" + _toDisplayString(backendVersion.value) + "：浏览器仍在使用旧联邦组件， 请按 Ctrl + Shift + R 硬刷新；若仍不一致，说明插件未真正更新。 ", 1)
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        (actionMessage.value)
          ? (_openBlock(), _createElementBlock("div", {
              key: 2,
              class: _normalizeClass(["ec-full", actionOk.value ? 'text-success' : 'text-error'])
            }, _toDisplayString(actionMessage.value), 3))
          : _createCommentVNode("", true)
      ]),
      _createVNode(_component_VTabs, {
        modelValue: tab.value,
        "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((tab).value = $event)),
        density: "comfortable",
        color: "primary",
        class: "ec-tabs"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VTab, {
            value: "cover",
            "prepend-icon": "mdi-image-edit-outline"
          }, {
            default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
              _createTextVNode("封面设计", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VTab, {
            value: "tasks",
            "prepend-icon": "mdi-calendar-clock-outline"
          }, {
            default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
              _createTextVNode("Emby 任务中心", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue"]),
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardText, { class: "ec-body" }, {
        default: _withCtx(() => [
          _createVNode(_component_VWindow, {
            modelValue: tab.value,
            "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((tab).value = $event)),
            touch: false
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VWindowItem, {
                value: "cover",
                class: "ec-pane"
              }, {
                default: _withCtx(() => [
                  (config.value)
                    ? (_openBlock(), _createBlock(CoverDesignPane, {
                        key: 0,
                        api: props.api,
                        "plugin-id": props.pluginId,
                        "initial-config": config.value,
                        servers: servers.value
                      }, null, 8, ["api", "plugin-id", "initial-config", "servers"]))
                    : _createCommentVNode("", true)
                ]),
                _: 1
              }),
              _createVNode(_component_VWindowItem, {
                value: "tasks",
                class: "ec-pane"
              }, {
                default: _withCtx(() => [
                  _createVNode(EmbyTasksPanel, {
                    api: props.api,
                    "plugin-id": props.pluginId,
                    servers: servers.value,
                    onNotify: onNotify
                  }, null, 8, ["api", "plugin-id", "servers"])
                ]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        _: 1
      })
    ]),
    _: 1
  }, 8, ["class"]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-8624a41f"]]);

export { Page as default };
