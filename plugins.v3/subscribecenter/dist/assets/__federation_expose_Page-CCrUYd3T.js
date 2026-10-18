import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, F as FRONTEND_VERSION, u as unwrap, a as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-nS8jbhE_.js';

const {resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createVNode:_createVNode,createElementVNode:_createElementVNode,unref:_unref,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,normalizeClass:_normalizeClass,normalizeStyle:_normalizeStyle,vModelText:_vModelText,withKeys:_withKeys,withDirectives:_withDirectives} = await importShared('vue');


const _hoisted_1 = { class: "sc-top" };
const _hoisted_2 = { class: "sc-top-left" };
const _hoisted_3 = { class: "sc-logo" };
const _hoisted_4 = { class: "sc-top-text" };
const _hoisted_5 = { class: "sc-title" };
const _hoisted_6 = { class: "sc-top-actions" };
const _hoisted_7 = { class: "sc-stat-grid" };
const _hoisted_8 = { class: "sc-stat-top" };
const _hoisted_9 = { class: "sc-stat-label" };
const _hoisted_10 = { class: "sc-stat-value" };
const _hoisted_11 = { class: "sc-stat-sub" };
const _hoisted_12 = { class: "sc-sources" };
const _hoisted_13 = { class: "sc-source-head" };
const _hoisted_14 = { class: "sc-source-sub" };
const _hoisted_15 = {
  key: 0,
  class: "sc-error"
};
const _hoisted_16 = { class: "sc-overview" };
const _hoisted_17 = { class: "sc-dim" };
const _hoisted_18 = { class: "sc-overview-toggle" };
const _hoisted_19 = {
  key: 0,
  class: "sc-overview-body"
};
const _hoisted_20 = {
  key: 0,
  class: "sc-hint"
};
const _hoisted_21 = { class: "sc-state-row" };
const _hoisted_22 = { class: "sc-dim" };
const _hoisted_23 = ["onClick"];
const _hoisted_24 = { class: "sc-dim" };
const _hoisted_25 = { class: "sc-overview-count" };
const _hoisted_26 = { key: 0 };
const _hoisted_27 = { class: "sc-poster-grid" };
const _hoisted_28 = { class: "sc-poster-wrap" };
const _hoisted_29 = ["src", "onError"];
const _hoisted_30 = {
  key: 1,
  class: "sc-poster-empty"
};
const _hoisted_31 = {
  key: 2,
  class: "sc-poster-best"
};
const _hoisted_32 = ["title"];
const _hoisted_33 = { key: 0 };
const _hoisted_34 = { class: "sc-poster-meta" };
const _hoisted_35 = { key: 0 };
const _hoisted_36 = { class: "sc-card" };
const _hoisted_37 = { class: "sc-card-head" };
const _hoisted_38 = { class: "sc-tabs sc-tabs-source" };
const _hoisted_39 = ["onClick"];
const _hoisted_40 = { class: "sc-tab-count" };
const _hoisted_41 = { class: "sc-search" };
const _hoisted_42 = { class: "sc-tabs" };
const _hoisted_43 = { class: "sc-tab-count" };
const _hoisted_44 = ["onClick"];
const _hoisted_45 = { class: "sc-tab-count" };
const _hoisted_46 = {
  key: 0,
  class: "sc-empty"
};
const _hoisted_47 = {
  key: 1,
  class: "sc-grid"
};
const _hoisted_48 = { class: "sc-card-poster" };
const _hoisted_49 = ["src"];
const _hoisted_50 = { class: "sc-card-badge" };
const _hoisted_51 = { class: "sc-card-body" };
const _hoisted_52 = ["title"];
const _hoisted_53 = { class: "sc-card-meta" };
const _hoisted_54 = { key: 0 };
const _hoisted_55 = { key: 1 };
const _hoisted_56 = { key: 2 };
const _hoisted_57 = {
  key: 0,
  class: "sc-card-meta"
};
const _hoisted_58 = ["title"];
const _hoisted_59 = { class: "sc-card-actions" };
const _hoisted_60 = {
  key: 2,
  class: "sc-pager"
};
const _hoisted_61 = { class: "sc-hint" };

const {computed,nextTick,onMounted,onUnmounted,ref,watch} = await importShared('vue');

const OVERVIEW_KEY = 'subscribecenter:overview-open';
const OVERVIEW_PAGE = 20;

const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'SubscribeCenter' },
  // 作为 MP 左侧「发现」分区的整页入口渲染时置 true：整页没有"关闭"语义，隐藏关闭按钮。
  appPage: { type: Boolean, default: false },
},
  emits: ['close', 'switch'],
  setup(__props, { emit: __emit }) {

/**
 * 详情页（插件管理里的弹窗 / 侧栏整页共用）。
 *
 * 展示运行状态、各数据源情况、最近流水，并提供「立即运行一次」。
 * 与仪表盘共用 /status 与 /history 接口。
 */
const props = __props;
const emit = __emit;

const loading = ref(false);
const busy = ref('');
const tip = ref({ show: false, ok: true, text: '' });
const status = ref(null);
const history = ref({ items: [], total: 0, page: 1, count: 20 });
const filter = ref('');
const sourceFilter = ref('');
const keyword = ref('');

let refreshTimer = null;

const backendVersion = computed(() => String(status.value?.plugin_version || ''));
const versionMismatch = computed(() => {
  if (!backendVersion.value) return ''
  return backendVersion.value === FRONTEND_VERSION
    ? ''
    : `前端组件 v${FRONTEND_VERSION} ≠ 后端 v${backendVersion.value}`
});

const DECISION_LABELS = {
  added: '新增订阅',
  skipped_dry_run: 'dry-run 跳过',
  skipped_first_run_dry: '首次试运行',
  skipped_already_subscribed: '已订阅',
  skipped_already_completed: '已完成过',
  skipped_duplicate: '跨源重复',
  skipped_rating: '评分不足',
  skipped_popularity: '关注度不足',
  skipped_out_of_window: '超出窗口',
  skipped_not_future: '定档已过',
  skipped_daily_limit: '触达上限',
  pending_review: '待确认',
  skipped_special: '特别篇（不处理）',
  skipped_finished: '已播完（跳过）',
  skipped_no_date: '无日期（跳过）',
  skipped_want: '想看不足（跳过）',
  skipped_source_disabled: '源未启用',
};

/**
 * 拼封面地址：**走插件后端代理**，不直连 image.tmdb.org。
 *
 * 原因：TMDB API 是服务器带代理访问的，但图片是浏览器直连 ——
 * 国内网络下 image.tmdb.org 常常连不上，封面会整片空白（真机反馈）。
 * 走 /poster 代理后浏览器只连 MoviePilot，图片由服务器绕代理取回。
 */
/**
 * 把数据库里的 poster 值归一化成 TMDB **图片路径**（`/abc.jpg`）。
 *
 * 宿主识别有时返回完整 URL（`https://image.tmdb.org/t/p/original/xxx.jpg`），
 * 存进流水后如果直接当 src 用，浏览器会去直连 image.tmdb.org ——
 * 国内网络下必然失败，表现为「只有少数卡片有图」。
 */
function posterPath(item) {
  const raw = item?.poster;
  if (!raw) return ''
  const text = String(raw);
  const match = text.match(/\/t\/p\/[^/]+(\/.+)$/);
  if (match) return match[1]
  return text.startsWith('/') ? text : ''
}

function posterUrl(item) {
  const path = posterPath(item);
  if (!path) return ''
  const id = String(props.pluginId || 'SubscribeCenter');
  // 插件路由固定挂在 /api/v1/plugin/<id> 下；<img> 用绝对路径，与 axios 的 baseURL 无关。
  return `/api/v1/plugin/${id}/poster?path=${encodeURIComponent(path)}`
}

function decisionLabel(value) {
  return DECISION_LABELS[value] || value || '—'
}

function decisionColor(value) {
  if (value === 'added') return 'success'
  if (value === 'pending_review') return 'warning'
  if (String(value || '').startsWith('skipped')) return 'default'
  return 'default'
}

function setTip(text, ok = true) {
  tip.value = { show: true, ok, text };
}

async function loadStatus() {
  try {
    status.value = unwrap(await getPluginApi(props.api, props.pluginId, 'status'));
  } catch (error) {
    setTip(error?.message || '状态加载失败', false);
  }
}

async function loadHistory() {
  loading.value = true;
  try {
    const params = new URLSearchParams({
      page: String(history.value.page || 1),
      count: String(history.value.count || 20),
    });
    if (filter.value) params.set('decision', filter.value);
    if (sourceFilter.value) params.set('source', sourceFilter.value);
    if (keyword.value.trim()) params.set('keyword', keyword.value.trim());
    history.value = unwrap(
      await getPluginApi(props.api, props.pluginId, `history?${params.toString()}`),
    );
  } catch (error) {
    setTip(error?.message || '流水加载失败', false);
  } finally {
    loading.value = false;
  }
}

async function refreshAll() {
  await Promise.all([loadStatus(), loadHistory()]);
}

async function runOnce() {
  if (busy.value) return
  busy.value = 'run';
  try {
    const result = unwrap(
      await postPluginApi(props.api, props.pluginId, 'run_once', {}, { timeoutMs: 600000 }),
    );
    if (result?.skipped) {
      setTip('已有发现任务正在运行，本次跳过');
    } else {
      const s = result?.summary || {};
      setTip(
        `本次完成：拉取 ${s.fetched ?? 0} 条 / 新增 ${s.added ?? 0} 条 / `
          + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`,
      );
    }
    await refreshAll();
  } catch (error) {
    setTip(error?.message || '运行失败', false);
  } finally {
    busy.value = '';
  }
}

function prevPage() {
  if (history.value.page <= 1) return
  history.value.page -= 1;
  loadHistory();
}

function nextPage() {
  const total = Number(history.value.total) || 0;
  const count = Number(history.value.count) || 20;
  if (history.value.page * count >= total) return
  history.value.page += 1;
  loadHistory();
}

/** 顶部状态 tab：只列出确实有数据的决策，按条数倒序。 */
const decisionTabs = computed(() => {
  const counts = history.value?.counts || {};
  return Object.entries(counts)
    .filter(([, value]) => Number(value) > 0)
    .map(([value, count]) => ({ value, count, label: decisionLabel(value) }))
    .sort((a, b) => b.count - a.count)
});

/** 切换状态筛选（tab）。 */
function switchFilter(value) {
  if (filter.value === value) return
  filter.value = value;
  history.value.page = 1;
  loadHistory();
}

/** 订阅总览：宿主订阅按状态分组（着色的卡片）。 */
const overview = ref({ total: 0, counts: {}, items: [] });
const overviewLoaded = ref(false);
const overviewOpen = ref(overviewOpenSaved());
const overviewState = ref('');

/** 数据源显示名。 */
function sourceLabel(key) {
  const map = { tmdb: 'TMDB', anilist: 'AniList', douban_rss: '豆瓣榜单' };
  return map[key] || key
}

/** 订阅总览展开状态：记住上次选择（默认展开）。 */
function overviewOpenSaved() {
  try {
    const raw = window.localStorage.getItem(OVERVIEW_KEY);
    return raw === null ? true : raw === '1'
  } catch (error) {
    return true
  }
}

/** 状态码 → 中文 + 颜色（与 MP 订阅页一致：未开始/订阅中/待定/暂停/完成）。 */
const STATE_META = {
  N: { label: '未开始', color: '#FFC107' },
  R: { label: '订阅中', color: '#3B82F6' },
  P: { label: '待定', color: '#F97316' },
  S: { label: '暂停', color: '#9CA3AF' },
  D: { label: '订阅完成', color: '#22C55E' },
};

/** 一条订阅的状态元信息（完成后优先显示「订阅完成」）。 */
function stateMeta(item) {
  const total = Number(item.total_episode || 0);
  const lack = Number(item.lack_episode || 0);
  const code = String(item.state || 'N');
  if (code === 'S') return { ...STATE_META.S, code: 'S' }
  if (total > 0 && lack === 0) return { ...STATE_META.D, code: 'D' }
  return { ...(STATE_META[code] || { label: code, color: '#6B7280' }), code }
}

/** 状态排序权重：暂停 → 待定 → 订阅中 → 未开始 → 完成。 */
const STATE_ORDER = { R: 0, S: 1, P: 2, N: 3, D: 4 };

/** 订阅列表（筛选 + 排序后的**全部**，未截断）。 */
const overviewSorted = computed(() => {
  let items = overview.value.items || [];
  if (overviewState.value) {
    items = items.filter((item) => stateMeta(item).code === overviewState.value);
  }
  return [...items].sort((a, b) => {
    const wa = STATE_ORDER[stateMeta(a).code] ?? 9;
    const wb = STATE_ORDER[stateMeta(b).code] ?? 9;
    if (wa !== wb) return wa - wb
    return String(b.last_update || '').localeCompare(String(a.last_update || ''))
  })
});

/** 实际渲染的条数（滚动加载，跟随页面滚动）。 */
const overviewItems = computed(() => overviewSorted.value.slice(0, overviewLimit.value));

/** 还有多少没显示。 */
const overviewRemain = computed(() =>
  Math.max(overviewSorted.value.length - overviewItems.value.length, 0),
);

/** 一次显示多少张（滚动加载）。 */
const overviewLimit = ref(OVERVIEW_PAGE);

/** 到底自动加载更多。

 用 **IntersectionObserver 观察网格底部哨兵**，而不是监听 window scroll ——
 插件页的滚动容器是宿主内部的 div，`window` 的 scroll 事件根本不触发
 （真机：插件页滚不动，MP 自己的页面一滚就出）。
 观察器不关心谁在滚，只要哨兵进入视口就追加。
 */
const overviewSentinel = ref(null);
let overviewObserver = null;

/** 网格的滚动容器（订阅总览内部滚动，不是窗口）。 */
function overviewScroller() {
  return overviewSentinel.value?.closest('.sc-poster-grid') || null
}

/** 哨兵是否已滚动到容器可视区附近。

 以前拿 `window.innerHeight` 判断 —— 网格改成内部滚动后，哨兵在裁剪区外
 但坐标仍在窗口内，于是循环一路加到 206 条（真机：展开直接全部加载）。
 */
/** 网格当前是否真的在内部滚动（窄屏会取消高度上限，改成跟随页面滚）。 */
function overviewScrollsInternally() {
  const box = overviewScroller();
  if (!box) return false
  const style = window.getComputedStyle(box);
  return style.overflowY === 'auto' || style.overflowY === 'scroll'
}

function sentinelVisible() {
  const el = overviewSentinel.value;
  const box = overviewScroller();
  if (!el) return false
  const rect = el.getBoundingClientRect();
  if (!box || !overviewScrollsInternally()) {
    // 跟随页面滚动（含手机端）：按视口判断
    return rect.top <= window.innerHeight + 120
  }
  const view = box.getBoundingClientRect();
  return rect.top <= view.bottom + 120
}

/** 追加一批，直到不再可见或没剩的（宽屏时一次 +20 可能仍停在原地）。 */
async function growOverview() {
  if (!overviewOpen.value) return
  let guard = 0;
  while (overviewRemain.value > 0 && sentinelVisible() && guard < 20) {
    overviewLimit.value += OVERVIEW_PAGE;
    guard += 1;
    await nextTick();
  }
}

function ensureOverviewObserver() {
  if (overviewObserver || !overviewSentinel.value) return
  overviewObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) growOverview();
    },
    // 有内部滚动时 root 必须是滚动容器本身（视口不会重新判定）；
    // 窄屏取消高度上限后没有内部滚动，root 要回到视口。
    {
      root: overviewScrollsInternally() ? overviewScroller() : null,
      rootMargin: '0px 0px 120px 0px',
    },
  );
  overviewObserver.observe(overviewSentinel.value);
}

/** 收起时销毁观察器：v-if 会重建哨兵节点，旧观察器会绑在已销毁的节点上。 */
function dropOverviewObserver() {
  if (overviewObserver) {
    overviewObserver.disconnect();
    overviewObserver = null;
  }
}

watch(overviewOpen, async (open) => {
  if (!open) {
    dropOverviewObserver();
    return
  }
  await nextTick();
  ensureOverviewObserver();
  await growOverview();
});

onMounted(async () => {
  if (overviewOpen.value) await loadOverview();
  await nextTick();
  ensureOverviewObserver();
});

onUnmounted(() => dropOverviewObserver());

/** 是否开启洗版（best_version / best_version_full）。 */
function isBestVersion(item) {
  return Boolean(Number(item.best_version || 0) || Number(item.best_version_full || 0))
}

/** 集数进度文本。 */
function episodeText(item) {
  const total = Number(item.total_episode || 0);
  if (!total) return ''
  const lack = Number(item.lack_episode || 0);
  return `${Math.max(total - lack, 0)}/${total}`
}

/** 拉一次订阅总览（已拉过就跳过）。 */
async function loadOverview(force = false) {
  if (overviewLoaded.value && !force) return
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'subscriptions'));
    overview.value = data || { total: 0, counts: {}, items: [] };
    overviewLoaded.value = true;
    await nextTick();
    await growOverview();
  } catch (error) {
    setTip(error?.message || '读取订阅总览失败', false);
  }
}

/** 展开/收起；展开时按需拉数据。 */
async function toggleOverview() {
  overviewOpen.value = !overviewOpen.value;
  try {
    window.localStorage.setItem(OVERVIEW_KEY, overviewOpen.value ? '1' : '0');
  } catch (error) {
    /* 隐私模式下忽略 */
  }
  if (overviewOpen.value) await loadOverview();
}

/** 「按源」tab：TMDB / AniList / 豆瓣，带条数。 */
const sourceTabs = computed(() => {
  const counts = history.value?.source_counts || {};
  const labelOf = { tmdb: 'TMDB', anilist: 'AniList', douban_rss: '豆瓣' };
  return Object.entries(counts)
    .filter(([, value]) => Number(value) > 0)
    .map(([value, count]) => ({ value, count, label: labelOf[value] || value }))
    .sort((a, b) => b.count - a.count)
});

/** 切换数据源筛选。 */
/** 手动修正映射：输入 TMDB ID，写入映射缓存（下次运行必定命中）。 */
async function fixMapping(item) {
  const input = window.prompt(
    `手动指定「${item.title}」的 TMDB 条目 ID（从 TMDB 网址里取数字，如 /tv/12345）：`,
    item.media_id || '',
  );
  if (!input) return
  const id = String(input).trim().replace(/\D/g, '');
  if (!id) {
    setTip('请输入纯数字的 TMDB ID', false);
    return
  }
  try {
    const mediaType = item.media_type === 'movie' ? 'movie' : 'tv';
    unwrap(
      await postPluginApi(props.api, props.pluginId, 'mapping_cache/fix', {
        key: '',
        title: item.title,
        year: item.year || '',
        media_type: mediaType,
        media_source: 'themoviedb',
        media_id: id,
      }),
    );
    setTip(`已修正：${item.title} -> themoviedb/${id}（下次运行生效）`);
    await refreshAll();
  } catch (error) {
    setTip(error?.message || '修正失败', false);
  }
}

function searchKeyword() {
  history.value.page = 1;
  loadHistory();
}

function switchSource(value) {
  if (sourceFilter.value === value) return
  sourceFilter.value = value;
  history.value.page = 1;
  loadHistory();
}

/** 海报加载失败：隐藏 <img>，露出底下的占位图标（否则浏览器会画出 alt 文本）。 */
function markPosterFailed(event) {
  const img = event?.target;
  if (img) img.style.display = 'none';
}

/** 上次运行的详细数字（通知里只报新增，细节放这里看）。 */
const lastSummary = computed(() => status.value?.last_summary || null);

/** 顶部统计卡：状态一览。 */
const statCards = computed(() => {
  const s = status.value || {};
  const summary = lastSummary.value || {};
  const sources = s.sources || [];
  const enabledSources = sources.filter((row) => row.enabled);
  return [
    {
      icon: 'mdi-download-network-outline',
      label: '今日写入',
      value: `${s.written_today ?? 0}`,
      sub:
        s.daily_limit == null
          ? '上限未知'
          : Number(s.daily_limit) <= 0
            ? '不限条数'
            : `上限 ${s.daily_limit} 条`,
      color: 'primary',
    },
    {
      icon: 'mdi-radar',
      label: '数据源',
      value: `${enabledSources.length}/${sources.length}`,
      sub: s.enabled ? '插件已启用' : '插件未启用',
      color: s.enabled ? 'success' : 'warning',
    },
    {
      icon: 'mdi-plus-circle-outline',
      label: '上次新增',
      value: `${summary.added ?? 0}`,
      sub: summary.fetched != null ? `拉取 ${summary.fetched} 条` : '尚无运行记录',
      color: 'success',
    },
    {
      icon: 'mdi-clock-outline',
      label: '最近运行',
      value: s.last_run ? String(s.last_run).slice(11) : '—',
      sub: s.last_run ? String(s.last_run).slice(0, 10) : '从未运行',
      color: 'info',
    },
  ]
});

onMounted(() => {
  refreshAll();
  refreshTimer = setInterval(refreshAll, 30000);
});

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
});

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VBtn = _resolveComponent("VBtn");

  return (_openBlock(), _createElementBlock("div", {
    class: _normalizeClass(["sc-root", { 'sc-root-page': __props.appPage }])
  }, [
    (versionMismatch.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3",
          text: `${versionMismatch.value}：浏览器仍在用缓存的旧联邦组件。请按 Ctrl+Shift+R 硬刷新页面。`
        }, null, 8, ["text"]))
      : _createCommentVNode("", true),
    (tip.value.show)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: tip.value.ok ? 'success' : 'error',
          variant: "tonal",
          density: "compact",
          class: "mb-3",
          closable: "",
          text: tip.value.text,
          "onClick:close": _cache[0] || (_cache[0] = $event => (tip.value.show = false))
        }, null, 8, ["type", "text"]))
      : _createCommentVNode("", true),
    _createElementVNode("div", _hoisted_1, [
      _createElementVNode("div", _hoisted_2, [
        _createElementVNode("div", _hoisted_3, [
          _createVNode(_component_VIcon, {
            icon: "mdi-movie-open-star-outline",
            size: "20"
          })
        ]),
        _createElementVNode("div", _hoisted_4, [
          _createElementVNode("div", _hoisted_5, [
            _cache[8] || (_cache[8] = _createTextVNode(" 胖虎订阅中心 ", -1)),
            _createVNode(_component_VChip, {
              size: "x-small",
              variant: "flat",
              color: "primary",
              class: "ml-2"
            }, {
              default: _withCtx(() => [
                _createTextVNode(" v" + _toDisplayString(_unref(FRONTEND_VERSION)), 1)
              ]),
              _: 1
            })
          ]),
          _cache[9] || (_cache[9] = _createElementVNode("div", { class: "sc-subtitle" }, "发现片源 → 解析身份 → 去重 → 写订阅", -1))
        ])
      ]),
      _createElementVNode("div", _hoisted_6, [
        _createVNode(_component_VBtn, {
          color: "primary",
          size: "small",
          variant: "flat",
          "prepend-icon": "mdi-radar",
          loading: busy.value === 'run',
          onClick: runOnce
        }, {
          default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
            _createTextVNode(" 立即运行一次 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-refresh",
          loading: loading.value,
          onClick: refreshAll
        }, {
          default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
            _createTextVNode(" 刷新 ", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          size: "small",
          variant: "text",
          "prepend-icon": "mdi-cog",
          onClick: _cache[1] || (_cache[1] = $event => (emit('switch')))
        }, {
          default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
            _createTextVNode("设置", -1)
          ]))]),
          _: 1
        })
      ])
    ]),
    _createElementVNode("div", _hoisted_7, [
      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(statCards.value, (card) => {
        return (_openBlock(), _createElementBlock("div", {
          key: card.label,
          class: "sc-stat"
        }, [
          _createElementVNode("div", _hoisted_8, [
            _createVNode(_component_VIcon, {
              icon: card.icon,
              size: "17",
              color: card.color
            }, null, 8, ["icon", "color"]),
            _createElementVNode("span", _hoisted_9, _toDisplayString(card.label), 1)
          ]),
          _createElementVNode("div", _hoisted_10, _toDisplayString(card.value), 1),
          _createElementVNode("div", _hoisted_11, _toDisplayString(card.sub), 1)
        ]))
      }), 128))
    ]),
    _createElementVNode("div", _hoisted_12, [
      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((status.value?.sources || []), (s) => {
        return (_openBlock(), _createElementBlock("div", {
          key: s.source,
          class: "sc-source-chip"
        }, [
          _createElementVNode("div", _hoisted_13, [
            _createElementVNode("b", null, _toDisplayString(sourceLabel(s.source)), 1),
            _createVNode(_component_VChip, {
              size: "x-small",
              variant: "flat",
              color: s.enabled ? 'success' : 'default'
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(s.enabled ? '已启用' : '未启用'), 1)
              ]),
              _: 2
            }, 1032, ["color"]),
            (!s.implemented)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 0,
                  size: "x-small",
                  variant: "flat",
                  color: "warning"
                }, {
                  default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                    _createTextVNode(" 未实现 ", -1)
                  ]))]),
                  _: 1
                }))
              : _createCommentVNode("", true)
          ]),
          _createElementVNode("div", _hoisted_14, " 最近 " + _toDisplayString(s.last_count) + " 条 · " + _toDisplayString(s.last_run || '从未运行'), 1),
          (s.last_error)
            ? (_openBlock(), _createElementBlock("div", _hoisted_15, "失败：" + _toDisplayString(s.last_error), 1))
            : _createCommentVNode("", true)
        ]))
      }), 128))
    ]),
    _createElementVNode("div", _hoisted_16, [
      _createElementVNode("div", {
        class: "sc-overview-head",
        onClick: toggleOverview
      }, [
        _createVNode(_component_VIcon, {
          icon: overviewOpen.value ? 'mdi-chevron-down' : 'mdi-chevron-right',
          size: "18"
        }, null, 8, ["icon"]),
        _cache[14] || (_cache[14] = _createElementVNode("span", { class: "sc-overview-title" }, "订阅总览", -1)),
        _createElementVNode("span", _hoisted_17, [
          (overviewLoaded.value)
            ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                _createTextVNode(" 共 " + _toDisplayString(overview.value.total) + " 条订阅 · 已完成 " + _toDisplayString(overview.value.counts.D || 0) + " · 待定 " + _toDisplayString(overview.value.counts.P || 0), 1)
              ], 64))
            : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                _createTextVNode("（尚未加载）")
              ], 64))
        ]),
        _cache[15] || (_cache[15] = _createElementVNode("span", { class: "sc-overview-spacer" }, null, -1)),
        _createElementVNode("span", _hoisted_18, _toDisplayString(overviewOpen.value ? '收起 ⌃' : '展开 ⌄'), 1)
      ]),
      (overviewOpen.value)
        ? (_openBlock(), _createElementBlock("div", _hoisted_19, [
            (!overview.value.total)
              ? (_openBlock(), _createElementBlock("div", _hoisted_20, "暂无订阅"))
              : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                  _createElementVNode("div", _hoisted_21, [
                    _createElementVNode("button", {
                      type: "button",
                      class: _normalizeClass(["sc-state-chip", { 'sc-state-active': !overviewState.value }]),
                      onClick: _cache[2] || (_cache[2] = $event => (overviewState.value = ''))
                    }, [
                      _cache[16] || (_cache[16] = _createTextVNode(" 全部 ", -1)),
                      _createElementVNode("span", _hoisted_22, _toDisplayString(overview.value.total), 1)
                    ], 2),
                    (_openBlock(), _createElementBlock(_Fragment, null, _renderList(STATE_META, (meta, code) => {
                      return _createElementVNode("button", {
                        key: code,
                        type: "button",
                        class: _normalizeClass(["sc-state-chip", { 'sc-state-active': overviewState.value === code }]),
                        style: _normalizeStyle({ borderColor: meta.color }),
                        onClick: $event => (overviewState.value = overviewState.value === code ? '' : code)
                      }, [
                        _createElementVNode("span", {
                          class: "sc-state-dot",
                          style: _normalizeStyle({ background: meta.color })
                        }, null, 4),
                        _createTextVNode(" " + _toDisplayString(meta.label) + " ", 1),
                        _createElementVNode("span", _hoisted_24, _toDisplayString(overview.value.counts[code] || 0), 1)
                      ], 14, _hoisted_23)
                    }), 64))
                  ]),
                  _createElementVNode("div", _hoisted_25, [
                    _createTextVNode(" 已显示 " + _toDisplayString(overviewItems.value.length) + " / " + _toDisplayString(overviewSorted.value.length) + " ", 1),
                    (overviewRemain.value > 0)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_26, " · 继续向下滚动自动加载"))
                      : _createCommentVNode("", true)
                  ]),
                  _createElementVNode("div", _hoisted_27, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(overviewItems.value, (item) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: item.id,
                        class: "sc-poster-card",
                        style: _normalizeStyle({ borderColor: stateMeta(item).color })
                      }, [
                        _createElementVNode("div", _hoisted_28, [
                          (posterUrl(item))
                            ? (_openBlock(), _createElementBlock("img", {
                                key: 0,
                                src: posterUrl(item),
                                alt: "",
                                loading: "lazy",
                                class: "sc-poster-img",
                                onError: $event => (markPosterFailed(item))
                              }, null, 40, _hoisted_29))
                            : (_openBlock(), _createElementBlock("div", _hoisted_30, [
                                _createVNode(_component_VIcon, {
                                  icon: "mdi-television-classic",
                                  size: "26"
                                })
                              ])),
                          _createElementVNode("span", {
                            class: "sc-poster-state",
                            style: _normalizeStyle({ background: stateMeta(item).color })
                          }, _toDisplayString(stateMeta(item).label), 5),
                          (isBestVersion(item))
                            ? (_openBlock(), _createElementBlock("span", _hoisted_31, "洗版"))
                            : _createCommentVNode("", true)
                        ]),
                        _createElementVNode("div", {
                          class: "sc-poster-name",
                          title: item.name
                        }, [
                          _createTextVNode(_toDisplayString(item.name), 1),
                          (item.season)
                            ? (_openBlock(), _createElementBlock("span", _hoisted_33, " S" + _toDisplayString(String(item.season).padStart(2, '0')), 1))
                            : _createCommentVNode("", true)
                        ], 8, _hoisted_32),
                        _createElementVNode("div", _hoisted_34, [
                          _createElementVNode("span", null, _toDisplayString(item.year || ''), 1),
                          (episodeText(item))
                            ? (_openBlock(), _createElementBlock("span", _hoisted_35, _toDisplayString(episodeText(item)), 1))
                            : _createCommentVNode("", true)
                        ])
                      ], 4))
                    }), 128)),
                    _createElementVNode("div", {
                      ref_key: "overviewSentinel",
                      ref: overviewSentinel,
                      class: "sc-overview-sentinel"
                    }, null, 512)
                  ])
                ], 64))
          ]))
        : _createCommentVNode("", true)
    ]),
    _createElementVNode("div", _hoisted_36, [
      _createElementVNode("div", _hoisted_37, [
        _cache[20] || (_cache[20] = _createElementVNode("span", { class: "sc-card-title" }, "发现流水", -1)),
        _createElementVNode("div", _hoisted_38, [
          _cache[17] || (_cache[17] = _createElementVNode("span", { class: "sc-tabs-label" }, "数据源", -1)),
          _createElementVNode("button", {
            type: "button",
            class: _normalizeClass(["sc-tab", { 'sc-tab-active': !sourceFilter.value }]),
            onClick: _cache[3] || (_cache[3] = $event => (switchSource('')))
          }, " 全部 ", 2),
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sourceTabs.value, (tab) => {
            return (_openBlock(), _createElementBlock("button", {
              key: tab.value,
              type: "button",
              class: _normalizeClass(["sc-tab", { 'sc-tab-active': sourceFilter.value === tab.value }]),
              onClick: $event => (switchSource(tab.value))
            }, [
              _createTextVNode(_toDisplayString(tab.label) + " ", 1),
              _createElementVNode("span", _hoisted_40, _toDisplayString(tab.count), 1)
            ], 10, _hoisted_39))
          }), 128))
        ]),
        _createElementVNode("div", _hoisted_41, [
          _createVNode(_component_VIcon, {
            icon: "mdi-magnify",
            size: "16",
            class: "sc-dim"
          }),
          _withDirectives(_createElementVNode("input", {
            "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((keyword).value = $event)),
            class: "sc-search-input",
            type: "text",
            placeholder: "搜索片名 / 原因（回车）",
            onKeyup: _withKeys(searchKeyword, ["enter"])
          }, null, 544), [
            [_vModelText, keyword.value]
          ]),
          (keyword.value)
            ? (_openBlock(), _createBlock(_component_VBtn, {
                key: 0,
                size: "x-small",
                variant: "text",
                icon: "mdi-close",
                onClick: _cache[5] || (_cache[5] = $event => {keyword.value = ''; searchKeyword();})
              }))
            : _createCommentVNode("", true)
        ]),
        _createElementVNode("div", _hoisted_42, [
          _createElementVNode("button", {
            type: "button",
            class: _normalizeClass(["sc-tab", { 'sc-tab-active': !filter.value }]),
            onClick: _cache[6] || (_cache[6] = $event => (switchFilter('')))
          }, [
            _cache[18] || (_cache[18] = _createTextVNode(" 全部 ", -1)),
            _createElementVNode("span", _hoisted_43, _toDisplayString(history.value.total || 0), 1)
          ], 2),
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(decisionTabs.value, (tab) => {
            return (_openBlock(), _createElementBlock("button", {
              key: tab.value,
              type: "button",
              class: _normalizeClass(["sc-tab", { 'sc-tab-active': filter.value === tab.value }]),
              onClick: $event => (switchFilter(tab.value))
            }, [
              _createTextVNode(_toDisplayString(tab.label) + " ", 1),
              _createElementVNode("span", _hoisted_45, _toDisplayString(tab.count), 1)
            ], 10, _hoisted_44))
          }), 128))
        ]),
        _createVNode(_component_VChip, {
          size: "x-small",
          variant: "tonal"
        }, {
          default: _withCtx(() => [
            _createTextVNode("共 " + _toDisplayString(history.value.total) + " 部作品", 1)
          ]),
          _: 1
        }),
        _createVNode(_component_VChip, {
          size: "x-small",
          variant: "text"
        }, {
          default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
            _createTextVNode("每部只显示最新状态", -1)
          ]))]),
          _: 1
        })
      ]),
      (!history.value.items.length)
        ? (_openBlock(), _createElementBlock("div", _hoisted_46, " 还没有流水。点「立即运行一次」即可看到发现结果。 "))
        : (_openBlock(), _createElementBlock("div", _hoisted_47, [
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value.items, (item, index) => {
              return (_openBlock(), _createElementBlock("div", {
                key: index,
                class: "sc-card-item"
              }, [
                _createElementVNode("div", _hoisted_48, [
                  (posterUrl(item))
                    ? (_openBlock(), _createElementBlock("img", {
                        key: 0,
                        src: posterUrl(item),
                        alt: "",
                        loading: "lazy",
                        onError: _cache[7] || (_cache[7] = $event => (markPosterFailed($event)))
                      }, null, 40, _hoisted_49))
                    : (_openBlock(), _createBlock(_component_VIcon, {
                        key: 1,
                        icon: "mdi-filmstrip-box-multiple",
                        size: "30",
                        class: "sc-poster-ph"
                      })),
                  _createElementVNode("span", _hoisted_50, [
                    _createVNode(_component_VChip, {
                      size: "x-small",
                      variant: "flat",
                      color: decisionColor(item.decision)
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(decisionLabel(item.decision)), 1)
                      ]),
                      _: 2
                    }, 1032, ["color"])
                  ])
                ]),
                _createElementVNode("div", _hoisted_51, [
                  _createElementVNode("div", {
                    class: "sc-card-title",
                    title: item.title
                  }, [
                    _createElementVNode("b", null, _toDisplayString(item.title), 1)
                  ], 8, _hoisted_52),
                  _createElementVNode("div", _hoisted_53, [
                    (item.year)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_54, _toDisplayString(item.year), 1))
                      : _createCommentVNode("", true),
                    (item.media_type)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_55, _toDisplayString(item.media_type), 1))
                      : _createCommentVNode("", true),
                    _createElementVNode("span", null, _toDisplayString(item.source), 1),
                    (item.confidence)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_56, _toDisplayString(item.confidence), 1))
                      : _createCommentVNode("", true)
                  ]),
                  (item.release_date)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_57, " 放送 " + _toDisplayString(item.release_date), 1))
                    : _createCommentVNode("", true),
                  (item.reason)
                    ? (_openBlock(), _createElementBlock("div", {
                        key: 1,
                        class: "sc-card-reason",
                        title: item.reason
                      }, _toDisplayString(item.reason), 9, _hoisted_58))
                    : _createCommentVNode("", true),
                  _createElementVNode("div", _hoisted_59, [
                    _createVNode(_component_VBtn, {
                      size: "x-small",
                      variant: "text",
                      "prepend-icon": "mdi-pencil-outline",
                      onClick: $event => (fixMapping(item))
                    }, {
                      default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                        _createTextVNode(" 修正映射 ", -1)
                      ]))]),
                      _: 1
                    }, 8, ["onClick"])
                  ])
                ])
              ]))
            }), 128))
          ])),
      (history.value.total > history.value.count)
        ? (_openBlock(), _createElementBlock("div", _hoisted_60, [
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "text",
              disabled: history.value.page <= 1,
              onClick: prevPage
            }, {
              default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                _createTextVNode("上一页", -1)
              ]))]),
              _: 1
            }, 8, ["disabled"]),
            _createElementVNode("span", _hoisted_61, "第 " + _toDisplayString(history.value.page) + " 页 · 共 " + _toDisplayString(history.value.total) + " 部作品", 1),
            _createVNode(_component_VBtn, {
              size: "small",
              variant: "text",
              disabled: history.value.page * history.value.count >= history.value.total,
              onClick: nextPage
            }, {
              default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                _createTextVNode(" 下一页 ", -1)
              ]))]),
              _: 1
            }, 8, ["disabled"])
          ]))
        : _createCommentVNode("", true)
    ])
  ], 2))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-805d3122"]]);

export { Page as default };
