import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, F as FRONTEND_VERSION, u as unwrap, g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-D0KYhR5f.js';

const {resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createVNode:_createVNode,createElementVNode:_createElementVNode,unref:_unref,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,vModelText:_vModelText,withDirectives:_withDirectives,normalizeClass:_normalizeClass,withKeys:_withKeys} = await importShared('vue');


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
const _hoisted_16 = { class: "sc-theme-card" };
const _hoisted_17 = { class: "sc-theme-head" };
const _hoisted_18 = { class: "sc-theme-body" };
const _hoisted_19 = { class: "sc-theme-label" };
const _hoisted_20 = ["onUpdate:modelValue"];
const _hoisted_21 = { class: "sc-dim" };
const _hoisted_22 = { class: "sc-theme-actions" };
const _hoisted_23 = { class: "sc-maintabs" };
const _hoisted_24 = {
  key: 3,
  class: "sc-card sc-cal-card"
};
const _hoisted_25 = { class: "sc-cal-head" };
const _hoisted_26 = { class: "sc-cal-month" };
const _hoisted_27 = { class: "sc-dim sc-cal-total" };
const _hoisted_28 = {
  key: 0,
  class: "sc-today-scroll"
};
const _hoisted_29 = {
  key: 0,
  class: "sc-cal-empty"
};
const _hoisted_30 = {
  key: 1,
  class: "sc-today-grid"
};
const _hoisted_31 = { class: "sc-today-poster" };
const _hoisted_32 = ["src"];
const _hoisted_33 = ["title"];
const _hoisted_34 = { class: "sc-today-sub" };
const _hoisted_35 = {
  key: 0,
  class: "sc-today-sub sc-dim"
};
const _hoisted_36 = {
  key: 1,
  class: "sc-today-sub sc-cal-done",
  title: "按自动启停的判定，今天会被订阅刷新搜到"
};
const _hoisted_37 = ["title"];
const _hoisted_38 = { key: 0 };
const _hoisted_39 = {
  key: 1,
  class: "sc-cal-weekhead"
};
const _hoisted_40 = {
  key: 2,
  class: "sc-cal-scroll"
};
const _hoisted_41 = ["id"];
const _hoisted_42 = { class: "sc-cal-daynum" };
const _hoisted_43 = { class: "sc-cal-evposter" };
const _hoisted_44 = ["src"];
const _hoisted_45 = { class: "sc-cal-evbody" };
const _hoisted_46 = ["title"];
const _hoisted_47 = { class: "sc-cal-evline" };
const _hoisted_48 = { class: "sc-cal-evline sc-cal-time" };
const _hoisted_49 = ["onClick"];
const _hoisted_50 = ["onClick"];
const _hoisted_51 = {
  key: 4,
  class: "sc-card"
};
const _hoisted_52 = { class: "sc-card-head" };
const _hoisted_53 = { class: "sc-tabs sc-tabs-source" };
const _hoisted_54 = ["onClick"];
const _hoisted_55 = { class: "sc-tab-count" };
const _hoisted_56 = { class: "sc-search" };
const _hoisted_57 = { class: "sc-tabs" };
const _hoisted_58 = { class: "sc-tab-count" };
const _hoisted_59 = ["onClick"];
const _hoisted_60 = { class: "sc-tab-count" };
const _hoisted_61 = {
  key: 0,
  class: "sc-empty"
};
const _hoisted_62 = {
  key: 1,
  class: "sc-grid"
};
const _hoisted_63 = ["title", "onClick"];
const _hoisted_64 = ["src"];
const _hoisted_65 = { class: "sc-card-badge" };
const _hoisted_66 = { class: "sc-card-body" };
const _hoisted_67 = ["title"];
const _hoisted_68 = { class: "sc-card-meta" };
const _hoisted_69 = { key: 0 };
const _hoisted_70 = { key: 1 };
const _hoisted_71 = { key: 2 };
const _hoisted_72 = {
  key: 0,
  class: "sc-card-meta"
};
const _hoisted_73 = ["title"];
const _hoisted_74 = { class: "sc-card-actions" };
const _hoisted_75 = {
  key: 2,
  class: "sc-pager"
};
const _hoisted_76 = { class: "sc-hint" };

const {computed,nextTick,onMounted,onUnmounted,ref} = await importShared('vue');


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
/** 正在清空发现流水 */
const clearing = ref(false);
//: 正在手动补订阅的那条流水键（同一时间只允许一条，避免重复点）
const subscribing = ref('');
const tip = ref({ show: false, ok: true, text: '' });
const status = ref(null);
/** 详情页视图：日历（默认）/ 发现流水。 */
const viewTab = ref('calendar');
/** 日历模式：today（默认，今天列表）/ month（整月网格）。 */
const calMode = ref('today');
/** 今天视图数据（GET /calendar/day）。 */
const todayDate = ref('');
const todayView = ref(null);
const todayLoading = ref(false);

/** 今天视图的筛选：'' / updated / pending。 */
const todayFilter = ref('');

/** 切换今天视图筛选。 */
function switchTodayFilter(value) {
  todayFilter.value = todayFilter.value === value ? '' : value;
}

/** 筛选后的今天条目。 */
const todayItems = computed(() => {
  const items = todayView.value?.items || [];
  if (!todayFilter.value) return items
  return items.filter((item) => item.kind === todayFilter.value)
});

/** 拉某天的列表（留空=今天）。 */
async function loadToday() {
  todayLoading.value = true;
  try {
    const query = todayDate.value ? `calendar/day?date=${todayDate.value}` : 'calendar/day';
    const data = unwrap(await getPluginApi(props.api, props.pluginId, query));
    todayView.value = data;
    todayDate.value = data?.today || todayDate.value;
  } catch (error) {
    todayView.value = { today: '', total: 0, updated: 0, pending: 0, items: [] };
    setTip(error?.message || '读取今天日历失败', false);
  } finally {
    todayLoading.value = false;
  }
}

/** 回到今天。 */
function goToday() {
  todayDate.value = '';
  loadToday();
}

/** 切换 今天 / 月历。 */
function switchCalMode(mode) {
  calMode.value = mode;
  if (mode === 'today' && !todayView.value) loadToday();
  if (mode === 'month' && !calendar.value) loadCalendar();
}

/** 当前月份（YYYY-MM，默认本月）。 */
const calMonth = ref('');
/** 某天展开全部条目（key = YYYY-MM-DD）。 */
const expandedDays = ref({});
/** 整月日历数据（GET /calendar?month=）。 */
const calendar = ref(null);
const calendarLoading = ref(false);

/** 拉整月日历。 */
async function loadCalendar() {
  calendarLoading.value = true;
  try {
    const query = `calendar?month=${calMonth.value || ''}`;
    const data = unwrap(await getPluginApi(props.api, props.pluginId, query));
    calendar.value = data;
    calMonth.value = data?.month || calMonth.value;
  } catch (error) {
    calendar.value = { month: '', days: {}, total: 0, per_day_limit: 5 };
    setTip(error?.message || '读取日历失败', false);
    // 默认定位到今天（图 4 那种「一进来就看到今天」的体验）
    await nextTick();
    const today = document?.getElementById?.('sc-cal-today');
    if (today && typeof today.scrollIntoView === 'function') {
      today.scrollIntoView({ block: 'center' });
    }
  } finally {
    calendarLoading.value = false;
  }
}

/** 上/下个月。 */
function shiftMonth(delta) {
  const text = calMonth.value || new Date().toISOString().slice(0, 7);
  const [year, month] = text.split('-').map(Number);
  const base = new Date(year, month - 1 + delta, 1);
  calMonth.value = `${base.getFullYear()}-${String(base.getMonth() + 1).padStart(2, '0')}`;
  loadCalendar();
}

/** 月份标题：2026年10月。 */
const calMonthTitle = computed(() => {
  const text = calMonth.value || '';
  if (!/^\d{4}-\d{2}$/.test(text)) return '—'
  const [year, month] = text.split('-');
  return `${year}年${Number(month)}月`
});

/** 今天的 YYYY-MM-DD：优先用服务器返回的（避免浏览器 UTC 偏一天）。 */
const todayText = computed(
  () => calendar.value?.today || status.value?.today || new Date().toISOString().slice(0, 10),
);

/** 月历格子：周一开头，补齐前后空白。 */
const calWeeks = computed(() => {
  const text = calMonth.value;
  if (!/^\d{4}-\d{2}$/.test(text || '')) return []
  const [year, month] = text.split('-').map(Number);
  const first = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const lead = (first.getDay() + 6) % 7; // 周一=0
  const cells = [];
  for (let i = 0; i < lead; i += 1) cells.push({ empty: true, key: `lead-${i}` });
  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = `${text}-${String(day).padStart(2, '0')}`;
    cells.push({
      day,
      date,
      key: date,
      items: calendar.value?.days?.[date] || [],
    });
  }
  while (cells.length % 7 !== 0) cells.push({ empty: true, key: `tail-${cells.length}` });
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks
});

/** 切到本月。 */
function goThisMonth() {
  calMonth.value = '';
  loadCalendar();
}

/** 展开/收起某天。 */
function toggleDay(date) {
  expandedDays.value = { ...expandedDays.value, [date]: !expandedDays.value[date] };
}

/** 每格默认展示的条数。 */
const perDayLimit = computed(() => calendar.value?.per_day_limit || 5);

/** 某一格应该显示的条目。 */
function dayItems(cell) {
  const items = cell?.items || [];
  if (expandedDays.value[cell.date]) return items
  return items.slice(0, perDayLimit.value)
}

/** 某一格还有多少条被折叠。 */
function hiddenCount(cell) {
  const items = cell?.items || [];
  if (expandedDays.value[cell.date]) return 0
  return Math.max(items.length - perDayLimit.value, 0)
}

/** 条目上的「第 N 集」文案。 */
function episodeText(item) {
  const eps = item?.episodes || [];
  if (eps.length) return `第 ${eps.join('、')} 集`
  const start = Number(item?.start_episode || 1);
  const done = Number(item?.total_episode || 0) - Number(item?.lack_episode || 0);
  return `第 ${Math.max(start, done || start)} 集`
}

/** 电影发行基准日类型 -> 中文（与后端 RELEASE_KIND_LABELS 逐字对应）。 */
const RELEASE_KIND_LABELS = {
  digital: '数字发行',
  physical: '实体发行',
  theatrical: '影院上映',
  premiere: '首映',
  tv: '电视首播',
  general: '上映',
};

/** 电影条目：哪一种发行日（普通=数字、洗版=实体）。 */
function releaseKindText(kind) {
  return RELEASE_KIND_LABELS[kind] || '上映'
}

/** 日历筛选：全部 / 今日已入库 / 待入库 / 洗版。 */
const calFilter = ref('');

/** 过滤后的日历条目。 */
computed(() => {
  const items = calendar.value?.items || [];
  if (!calFilter.value) return items
  return items.filter((item) => item.kind === calFilter.value)
});

/** 切换视图 tab。 */
function switchView(tab) {
  viewTab.value = tab;
  if (tab === 'calendar' && !calendar.value) loadCalendar();
}

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
  skipped_recorded: '流水已记录（不再自动订）',
  skipped_blacklist: '命中排除规则',
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
  // 豆瓣 / Bangumi 等非 TMDB 海报是绝对 URL：原样交给后端代理
  if (/^https?:\/\//i.test(text)) return text
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

/** 清空发现流水。
 *
 * 这是「流水记过就不再自动重订」的解锁方式：清空之后，之前订过又被删掉的
 * 订阅会在下一轮重新被发现。所以必须二次确认，且把后果写清。
 */
async function clearHistory() {
  if (!window.confirm(
    '清空发现流水？\n\n' +
    '清空后，之前订阅过（后来被你删掉）的作品会重新被自动订阅。',
  )) return
  clearing.value = true;
  try {
    const result = unwrap(await postPluginApi(props.api, props.pluginId, 'history/clear', {}));
    setTip(`已清空 ${result?.removed ?? 0} 条流水`);
    history.value.page = 1;
    await loadHistory();
    await loadStatus();
  } catch (error) {
    setTip(error?.message || '清空流水失败', false);
  } finally {
    clearing.value = false;
  }
}

/**
 * 拼宿主详情页地址（新标签打开）。
 *
 * 宿主前端用 hash 路由：`#/media?media_source=…&media_id=…&type=…&title=…&year=…`。
 * `media_source` 必须是宿主的枚举值（`themoviedb` / `douban` / …），`type` 是**中文**
 * 的媒体类型（`电视剧` / `电影`）—— 这两点错了详情页会打不开或认错媒体。
 */
function detailUrl(item) {
  const mediaSource = String(item?.media_source || '');
  const mediaId = String(item?.media_id || '');
  if (!mediaSource || !mediaId) return ''
  const params = new URLSearchParams();
  params.set('media_source', mediaSource);
  params.set('media_id', mediaId);
  params.set('type', String(item?.media_type || '') === 'tv' ? '电视剧' : '电影');
  if (item?.title) params.set('title', String(item.title));
  if (item?.year) params.set('year', String(item.year));
  // 去掉当前 hash，避免拼成 `#/subscribe#/media?...`
  const base = window.location.href.split('#')[0];
  return `${base}#/media?${params.toString()}`
}

function openDetail(item) {
  const url = detailUrl(item);
  if (!url) return
  window.open(url, '_blank', 'noopener');
}

/** 只有拿到了确定性身份（来源 + ID）的流水才能一键订阅。 */
function canSubscribe(item) {
  return Boolean(item?.key) && Boolean(item?.media_source) && Boolean(item?.media_id)
}

/** 「已订阅过」的给「重新订阅」，其余给「加入订阅」。 */
function subscribeLabel(item) {
  const decision = String(item?.decision || '');
  return decision === 'added' || decision === 'skipped_already_subscribed'
    ? '重新订阅'
    : '加入订阅'
}

/**
 * 从流水手动补订阅。
 *
 * 后端刻意绕开窗口/评分/日限额/流水去重 —— 用户点名要订的东西不该被门槛拦住。
 * 订阅已存在时不改状态，只回报宿主里的当前状态。
 */
async function subscribeFromHistory(item) {
  const key = String(item?.key || '');
  if (!key || subscribing.value) return
  if (!canSubscribe(item)) {
    setTip('这条流水没有确定性身份，无法直接订阅', false);
    return
  }
  subscribing.value = key;
  try {
    const result = unwrap(
      await postPluginApi(
        props.api,
        props.pluginId,
        'history/subscribe',
        { key },
        { timeoutMs: 120000 },
      ),
    );
    if (result?.action === 'added') {
      setTip(result?.message || '已加入订阅');
      await loadHistory();
      await loadStatus();
    } else {
      // 「订阅中」不是错误，用普通提示，别刷红
      setTip(result?.message || '没有写入订阅', true);
    }
  } catch (error) {
    setTip(error?.message || '订阅失败', false);
  } finally {
    subscribing.value = '';
  }
}

async function refreshAll() {
  if (viewTab.value === 'calendar' && calMode.value === 'today') loadToday();
  await Promise.all([loadStatus(), loadHistory()]);
}

async function runOnce() {
  if (busy.value) return
  busy.value = 'run';
  try {
    const start = unwrap(
      await postPluginApi(props.api, props.pluginId, 'run_once', {}, { timeoutMs: 60000 }),
    );
    if (!start?.started) {
      setTip(start?.message || '已有发现任务正在运行，本次跳过');
      return
    }
    setTip('已在后台开始执行，正在等结果（可能要一两分钟）…');
    // 整条流水线跑得比网关超时久，只能轮询结果（真机 502 的修法）
    let state = null;
    for (let i = 0; i < 450; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 4000));
      state = unwrap(
        await getPluginApi(props.api, props.pluginId, 'run_once/result', { timeoutMs: 60000 }),
      );
      if (state?.error) throw new Error(state.error)
      if (!state?.running) break
    }
    const s = state?.result?.summary || {};
    setTip(
      `本次完成：拉取 ${s.fetched ?? 0} 条 / 新增 ${s.added ?? 0} 条 / `
        + `跳过 ${s.skipped ?? 0} 条 / 待确认 ${s.pending_review ?? 0} 条`,
    );
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

/** 订阅卡片配色（写进宿主 UserCustomCSS，MP 订阅页跟着变色）。 */
const themeSaving = ref(false);
const theme = ref({
  colors: { subscribing: '#FFC107', pending: '#F97316', paused: '#9CA3AF' },
});

const themeRows = [
  { key: 'subscribing', label: '订阅中' },
  { key: 'pending', label: '待定' },
  { key: 'paused', label: '暂停' },
];

async function loadTheme() {
  try {
    const data = unwrap(await getPluginApi(props.api, props.pluginId, 'card_theme'));
    if (data) {
      theme.value = { colors: { ...theme.value.colors, ...(data.colors || {}) } };
    }
  } catch (error) {
    /* 配色读取失败不影响主功能 */
  }
}

async function saveTheme() {
  themeSaving.value = true;
  try {
    unwrap(
      await postPluginApi(props.api, props.pluginId, 'card_theme/save', {
        colors: theme.value.colors,
      }),
    );
    setTip('配色已保存：刷新 MoviePilot 页面后生效');
  } catch (error) {
    setTip(error?.message || '配色保存失败', false);
  } finally {
    themeSaving.value = false;
  }
}

async function resetTheme() {
  themeSaving.value = true;
  try {
    unwrap(await postPluginApi(props.api, props.pluginId, 'card_theme/save', { reset: true }));
    setTip('已恢复默认：若颜色仍在，请重启 MoviePilot（设置服务有内存缓存）');
  } catch (error) {
    setTip(error?.message || '恢复默认失败', false);
  } finally {
    themeSaving.value = false;
  }
}

/** 数据源显示名。 */
function sourceLabel(key) {
  const map = {
    tmdb: 'TMDB',
    anilist: 'AniList',
    douban_rss: '豆瓣榜单',
    hot_media: '热门媒体',
    qq_video: '腾讯视频',
    bilibili: 'B 站番剧',
  };
  return map[key] || key
}


onMounted(async () => {
  await loadTheme();
});


/** 「按源」tab：TMDB / AniList / 豆瓣，带条数。 */
const sourceTabs = computed(() => {
  const counts = history.value?.source_counts || {};
  const labelOf = {
    tmdb: 'TMDB',
    anilist: 'AniList',
    douban_rss: '豆瓣',
    hot_media: '热门媒体',
    qq_video: '腾讯',
    bilibili: 'B 站',
  };
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
  loadToday();
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
    ((status.value?.config_issues || []).length)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3",
          title: `已自动关闭 ${status.value.config_issues.length} 个不会产出内容的数据源`,
          text: status.value.config_issues.join('；')
        }, null, 8, ["title", "text"]))
      : _createCommentVNode("", true),
    (versionMismatch.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3",
          text: `${versionMismatch.value}：浏览器仍在用缓存的旧联邦组件。请按 Ctrl+Shift+R 硬刷新页面。`
        }, null, 8, ["text"]))
      : _createCommentVNode("", true),
    (tip.value.show)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 2,
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
            _cache[20] || (_cache[20] = _createTextVNode(" 胖虎订阅中心 ", -1)),
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
          _cache[21] || (_cache[21] = _createElementVNode("div", { class: "sc-subtitle" }, "发现片源 → 解析身份 → 去重 → 写订阅", -1))
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
          default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
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
          default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
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
          default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
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
                  default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
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
      _createElementVNode("div", _hoisted_17, [
        _createVNode(_component_VIcon, {
          icon: "mdi-palette-outline",
          size: "16"
        }),
        _cache[26] || (_cache[26] = _createElementVNode("span", { class: "sc-theme-title" }, "订阅卡片配色", -1)),
        _cache[27] || (_cache[27] = _createElementVNode("span", { class: "sc-dim" }, "保存后刷新 MoviePilot 页面生效；只影响卡片外观，不改订阅", -1))
      ]),
      _createElementVNode("div", _hoisted_18, [
        (_openBlock(), _createElementBlock(_Fragment, null, _renderList(themeRows, (row) => {
          return _createElementVNode("div", {
            class: "sc-theme-row",
            key: row.key
          }, [
            _createElementVNode("span", _hoisted_19, _toDisplayString(row.label), 1),
            _withDirectives(_createElementVNode("input", {
              type: "color",
              "onUpdate:modelValue": $event => ((theme.value.colors[row.key]) = $event),
              class: "sc-theme-color"
            }, null, 8, _hoisted_20), [
              [_vModelText, theme.value.colors[row.key]]
            ]),
            _createElementVNode("code", _hoisted_21, _toDisplayString(theme.value.colors[row.key]), 1)
          ])
        }), 64)),
        _createElementVNode("div", _hoisted_22, [
          _createVNode(_component_VBtn, {
            size: "x-small",
            color: "primary",
            loading: themeSaving.value,
            onClick: saveTheme
          }, {
            default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
              _createTextVNode("保存", -1)
            ]))]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_VBtn, {
            size: "x-small",
            variant: "text",
            disabled: themeSaving.value,
            onClick: resetTheme
          }, {
            default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
              _createTextVNode(" 恢复默认 ", -1)
            ]))]),
            _: 1
          }, 8, ["disabled"])
        ])
      ])
    ]),
    _createElementVNode("div", _hoisted_23, [
      _createElementVNode("button", {
        type: "button",
        class: _normalizeClass(["sc-maintab", { 'sc-maintab-active': viewTab.value === 'calendar' }]),
        onClick: _cache[2] || (_cache[2] = $event => (switchView('calendar')))
      }, [
        _createVNode(_component_VIcon, {
          icon: "mdi-calendar-month-outline",
          size: "16"
        }),
        _cache[30] || (_cache[30] = _createTextVNode(" 日历 ", -1))
      ], 2),
      _createElementVNode("button", {
        type: "button",
        class: _normalizeClass(["sc-maintab", { 'sc-maintab-active': viewTab.value === 'history' }]),
        onClick: _cache[3] || (_cache[3] = $event => (switchView('history')))
      }, [
        _createVNode(_component_VIcon, {
          icon: "mdi-history",
          size: "16"
        }),
        _cache[31] || (_cache[31] = _createTextVNode(" 发现流水 ", -1))
      ], 2),
      _cache[32] || (_cache[32] = _createElementVNode("span", { class: "sc-dim sc-maintabs-hint" }, "可选日期 · 默认今天 · 与 MoviePilot 日历同源", -1))
    ]),
    (viewTab.value === 'calendar')
      ? (_openBlock(), _createElementBlock("div", _hoisted_24, [
          _createElementVNode("div", _hoisted_25, [
            _createElementVNode("button", {
              type: "button",
              class: _normalizeClass(["sc-calmode", { 'sc-calmode-active': calMode.value === 'today' }]),
              onClick: _cache[4] || (_cache[4] = $event => (switchCalMode('today')))
            }, " 今天 ", 2),
            _createElementVNode("button", {
              type: "button",
              class: _normalizeClass(["sc-calmode", { 'sc-calmode-active': calMode.value === 'month' }]),
              onClick: _cache[5] || (_cache[5] = $event => (switchCalMode('month')))
            }, " 月历 ", 2),
            (calMode.value === 'today')
              ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                  _withDirectives(_createElementVNode("input", {
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((todayDate).value = $event)),
                    type: "date",
                    class: "sc-cal-date-input",
                    onChange: _cache[7] || (_cache[7] = $event => (loadToday()))
                  }, null, 544), [
                    [_vModelText, todayDate.value]
                  ]),
                  (todayView.value?.today !== status.value?.today)
                    ? (_openBlock(), _createBlock(_component_VBtn, {
                        key: 0,
                        size: "x-small",
                        variant: "text",
                        onClick: goToday
                      }, {
                        default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                          _createTextVNode(" 今天 ", -1)
                        ]))]),
                        _: 1
                      }))
                    : _createCommentVNode("", true),
                  _createElementVNode("button", {
                    type: "button",
                    class: _normalizeClass(["sc-calmode", { 'sc-calmode-active': todayFilter.value === '' }]),
                    onClick: _cache[8] || (_cache[8] = $event => (switchTodayFilter('')))
                  }, " 全部 " + _toDisplayString(todayView.value?.total || 0), 3),
                  _createElementVNode("button", {
                    type: "button",
                    class: _normalizeClass(["sc-calmode", { 'sc-calmode-active': todayFilter.value === 'updated' }]),
                    onClick: _cache[9] || (_cache[9] = $event => (switchTodayFilter('updated')))
                  }, " 已入库 " + _toDisplayString(todayView.value?.updated || 0), 3),
                  _createElementVNode("button", {
                    type: "button",
                    class: _normalizeClass(["sc-calmode", { 'sc-calmode-active': todayFilter.value === 'pending' }]),
                    onClick: _cache[10] || (_cache[10] = $event => (switchTodayFilter('pending')))
                  }, " 待入库 " + _toDisplayString(todayView.value?.pending || 0), 3),
                  _createVNode(_component_VBtn, {
                    size: "x-small",
                    variant: "text",
                    class: "sc-cal-refresh",
                    loading: todayLoading.value,
                    onClick: loadToday
                  }, {
                    default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                      _createTextVNode(" 刷新 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"])
                ], 64))
              : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                  _createVNode(_component_VBtn, {
                    size: "x-small",
                    variant: "text",
                    icon: "mdi-chevron-left",
                    onClick: _cache[11] || (_cache[11] = $event => (shiftMonth(-1)))
                  }),
                  _createElementVNode("span", _hoisted_26, _toDisplayString(calMonthTitle.value), 1),
                  _createVNode(_component_VBtn, {
                    size: "x-small",
                    variant: "text",
                    icon: "mdi-chevron-right",
                    onClick: _cache[12] || (_cache[12] = $event => (shiftMonth(1)))
                  }),
                  _createVNode(_component_VBtn, {
                    size: "x-small",
                    variant: "text",
                    onClick: goThisMonth
                  }, {
                    default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                      _createTextVNode("本月", -1)
                    ]))]),
                    _: 1
                  }),
                  _createElementVNode("span", _hoisted_27, "本月 " + _toDisplayString(calendar.value?.total || 0) + " 条", 1),
                  _createVNode(_component_VBtn, {
                    size: "x-small",
                    variant: "text",
                    class: "sc-cal-refresh",
                    loading: calendarLoading.value,
                    onClick: loadCalendar
                  }, {
                    default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                      _createTextVNode(" 刷新 ", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"])
                ], 64))
          ]),
          (calMode.value === 'today')
            ? (_openBlock(), _createElementBlock("div", _hoisted_28, [
                (!todayItems.value.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_29, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-calendar-blank-outline",
                        size: "34"
                      }),
                      _createElementVNode("div", null, _toDisplayString(todayFilter.value ? '当前筛选下没有条目' : '这一天没有需要处理的更新'), 1),
                      _cache[37] || (_cache[37] = _createElementVNode("div", { class: "sc-dim" }, "切到「月历」可以看整月安排", -1))
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_30, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(todayItems.value, (item) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.id + '-' + item.kind,
                          class: "sc-today-item"
                        }, [
                          _createElementVNode("div", _hoisted_31, [
                            (item.poster)
                              ? (_openBlock(), _createElementBlock("img", {
                                  key: 0,
                                  src: posterUrl(item),
                                  alt: "",
                                  loading: "lazy",
                                  onError: _cache[13] || (_cache[13] = $event => (markPosterFailed($event)))
                                }, null, 40, _hoisted_32))
                              : (_openBlock(), _createBlock(_component_VIcon, {
                                  key: 1,
                                  icon: "mdi-filmstrip-box-multiple",
                                  size: "22"
                                })),
                            _createElementVNode("span", {
                              class: _normalizeClass(["sc-today-badge", item.kind === 'updated' ? 'sc-today-badge-ok' : 'sc-today-badge-wait'])
                            }, _toDisplayString(item.kind === 'updated' ? '今日更新' : '今日待播'), 3)
                          ]),
                          _createElementVNode("div", {
                            class: "sc-today-title",
                            title: item.name
                          }, _toDisplayString(item.name), 9, _hoisted_33),
                          _createElementVNode("div", _hoisted_34, _toDisplayString(episodeText(item)), 1),
                          _createElementVNode("div", {
                            class: _normalizeClass(["sc-today-sub", item.kind === 'updated' ? 'sc-cal-done' : 'sc-cal-wait'])
                          }, _toDisplayString(item.kind === 'updated' ? '已入库' : '未入库') + " (" + _toDisplayString(item.total_episode - item.lack_episode) + "/" + _toDisplayString(item.total_episode) + ") ", 3),
                          (item.release_kind)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_35, _toDisplayString(releaseKindText(item.release_kind)), 1))
                            : _createCommentVNode("", true),
                          (item.searched === true)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_36, [
                                _createVNode(_component_VIcon, {
                                  icon: "mdi-radar",
                                  size: "11"
                                }),
                                _cache[38] || (_cache[38] = _createTextVNode(" 今天会搜 ", -1))
                              ]))
                            : (item.searched === false)
                              ? (_openBlock(), _createElementBlock("div", {
                                  key: 2,
                                  class: "sc-today-sub sc-cal-wait",
                                  title: item.search_note || '按自动启停的判定，今天不会被搜'
                                }, [
                                  _createVNode(_component_VIcon, {
                                    icon: "mdi-pause-circle-outline",
                                    size: "11"
                                  }),
                                  _cache[39] || (_cache[39] = _createTextVNode(" 今天不搜", -1)),
                                  (item.search_note)
                                    ? (_openBlock(), _createElementBlock("span", _hoisted_38, "（" + _toDisplayString(item.search_note) + "）", 1))
                                    : _createCommentVNode("", true)
                                ], 8, _hoisted_37))
                              : _createCommentVNode("", true)
                        ]))
                      }), 128))
                    ]))
              ]))
            : _createCommentVNode("", true),
          (calMode.value === 'month')
            ? (_openBlock(), _createElementBlock("div", _hoisted_39, [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(['周一', '周二', '周三', '周四', '周五', '周六', '周日'], (w) => {
                  return _createElementVNode("span", { key: w }, _toDisplayString(w), 1)
                }), 64))
              ]))
            : _createCommentVNode("", true),
          (calMode.value === 'month')
            ? (_openBlock(), _createElementBlock("div", _hoisted_40, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(calWeeks.value, (week, wi) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: wi,
                    class: "sc-cal-week"
                  }, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(week, (cell) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: cell.key,
                        id: cell.date === todayText.value ? 'sc-cal-today' : undefined,
                        class: _normalizeClass(["sc-cal-day", {
              'sc-cal-day-empty': cell.empty,
              'sc-cal-day-today': cell.date === todayText.value,
            }])
                      }, [
                        (!cell.empty)
                          ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                              _createElementVNode("div", _hoisted_42, _toDisplayString(cell.day), 1),
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(dayItems(cell), (item) => {
                                return (_openBlock(), _createElementBlock("div", {
                                  key: cell.date + '-' + item.id + '-' + item.kind,
                                  class: "sc-cal-ev"
                                }, [
                                  _createElementVNode("div", _hoisted_43, [
                                    (item.poster)
                                      ? (_openBlock(), _createElementBlock("img", {
                                          key: 0,
                                          src: posterUrl(item),
                                          alt: "",
                                          loading: "lazy",
                                          onError: _cache[14] || (_cache[14] = $event => (markPosterFailed($event)))
                                        }, null, 40, _hoisted_44))
                                      : (_openBlock(), _createBlock(_component_VIcon, {
                                          key: 1,
                                          icon: "mdi-filmstrip-box-multiple",
                                          size: "16"
                                        }))
                                  ]),
                                  _createElementVNode("div", _hoisted_45, [
                                    _createElementVNode("div", {
                                      class: "sc-cal-evtitle",
                                      title: item.name
                                    }, _toDisplayString(item.name), 9, _hoisted_46),
                                    _createElementVNode("div", _hoisted_47, [
                                      _createVNode(_component_VIcon, {
                                        icon: "mdi-card-text-outline",
                                        size: "11"
                                      }),
                                      _createTextVNode(_toDisplayString(episodeText(item)), 1)
                                    ]),
                                    _createElementVNode("div", {
                                      class: _normalizeClass(["sc-cal-evline", item.kind === 'updated' ? 'sc-cal-done' : 'sc-cal-wait'])
                                    }, [
                                      _createVNode(_component_VIcon, {
                                        icon: item.kind === 'updated' ? 'mdi-check' : 'mdi-close',
                                        size: "11"
                                      }, null, 8, ["icon"]),
                                      _createTextVNode(" " + _toDisplayString(item.kind === 'updated' ? '已入库' : '未入库') + " (" + _toDisplayString(item.total_episode - item.lack_episode) + "/" + _toDisplayString(item.total_episode) + ") ", 1)
                                    ], 2),
                                    _createElementVNode("div", _hoisted_48, [
                                      _createVNode(_component_VIcon, {
                                        icon: "mdi-clock-outline",
                                        size: "11"
                                      }),
                                      _createTextVNode(_toDisplayString(item.air_time || item.air_date), 1)
                                    ])
                                  ])
                                ]))
                              }), 128)),
                              (hiddenCount(cell))
                                ? (_openBlock(), _createElementBlock("button", {
                                    key: 0,
                                    type: "button",
                                    class: "sc-cal-more",
                                    onClick: $event => (toggleDay(cell.date))
                                  }, [
                                    _createVNode(_component_VIcon, {
                                      icon: "mdi-unfold-more-horizontal",
                                      size: "12"
                                    }),
                                    _createTextVNode(" +" + _toDisplayString(hiddenCount(cell)), 1)
                                  ], 8, _hoisted_49))
                                : (expandedDays.value[cell.date])
                                  ? (_openBlock(), _createElementBlock("button", {
                                      key: 1,
                                      type: "button",
                                      class: "sc-cal-more",
                                      onClick: $event => (toggleDay(cell.date))
                                    }, [
                                      _createVNode(_component_VIcon, {
                                        icon: "mdi-unfold-less-horizontal",
                                        size: "12"
                                      }),
                                      _cache[40] || (_cache[40] = _createTextVNode(" 收起 ", -1))
                                    ], 8, _hoisted_50))
                                  : _createCommentVNode("", true)
                            ], 64))
                          : _createCommentVNode("", true)
                      ], 10, _hoisted_41))
                    }), 128))
                  ]))
                }), 128))
              ]))
            : _createCommentVNode("", true)
        ]))
      : _createCommentVNode("", true),
    (viewTab.value === 'history')
      ? (_openBlock(), _createElementBlock("div", _hoisted_51, [
          _createElementVNode("div", _hoisted_52, [
            _cache[45] || (_cache[45] = _createElementVNode("span", { class: "sc-card-title" }, "发现流水", -1)),
            _createElementVNode("div", _hoisted_53, [
              _cache[41] || (_cache[41] = _createElementVNode("span", { class: "sc-tabs-label" }, "数据源", -1)),
              _createElementVNode("button", {
                type: "button",
                class: _normalizeClass(["sc-tab", { 'sc-tab-active': !sourceFilter.value }]),
                onClick: _cache[15] || (_cache[15] = $event => (switchSource('')))
              }, " 全部 ", 2),
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sourceTabs.value, (tab) => {
                return (_openBlock(), _createElementBlock("button", {
                  key: tab.value,
                  type: "button",
                  class: _normalizeClass(["sc-tab", { 'sc-tab-active': sourceFilter.value === tab.value }]),
                  onClick: $event => (switchSource(tab.value))
                }, [
                  _createTextVNode(_toDisplayString(tab.label) + " ", 1),
                  _createElementVNode("span", _hoisted_55, _toDisplayString(tab.count), 1)
                ], 10, _hoisted_54))
              }), 128))
            ]),
            _createElementVNode("div", _hoisted_56, [
              _createVNode(_component_VIcon, {
                icon: "mdi-magnify",
                size: "16",
                class: "sc-dim"
              }),
              _withDirectives(_createElementVNode("input", {
                "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((keyword).value = $event)),
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
                    onClick: _cache[17] || (_cache[17] = $event => {keyword.value = ''; searchKeyword();})
                  }))
                : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_57, [
              _createElementVNode("button", {
                type: "button",
                class: _normalizeClass(["sc-tab", { 'sc-tab-active': !filter.value }]),
                onClick: _cache[18] || (_cache[18] = $event => (switchFilter('')))
              }, [
                _cache[42] || (_cache[42] = _createTextVNode(" 全部 ", -1)),
                _createElementVNode("span", _hoisted_58, _toDisplayString(history.value.total || 0), 1)
              ], 2),
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(decisionTabs.value, (tab) => {
                return (_openBlock(), _createElementBlock("button", {
                  key: tab.value,
                  type: "button",
                  class: _normalizeClass(["sc-tab", { 'sc-tab-active': filter.value === tab.value }]),
                  onClick: $event => (switchFilter(tab.value))
                }, [
                  _createTextVNode(_toDisplayString(tab.label) + " ", 1),
                  _createElementVNode("span", _hoisted_60, _toDisplayString(tab.count), 1)
                ], 10, _hoisted_59))
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
              default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                _createTextVNode("每部只显示最新状态", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              size: "x-small",
              variant: "text",
              color: "warning",
              "prepend-icon": "mdi-delete-sweep-outline",
              loading: clearing.value,
              disabled: clearing.value || loading.value || !history.value.total,
              onClick: clearHistory
            }, {
              default: _withCtx(() => [...(_cache[44] || (_cache[44] = [
                _createTextVNode(" 清空流水 ", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "disabled"])
          ]),
          (!history.value.items.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_61, " 还没有流水。点「立即运行一次」即可看到发现结果。 "))
            : (_openBlock(), _createElementBlock("div", _hoisted_62, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(history.value.items, (item, index) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: index,
                    class: "sc-card-item"
                  }, [
                    _createElementVNode("div", {
                      class: _normalizeClass(["sc-card-poster", { 'sc-poster-link': Boolean(detailUrl(item)) }]),
                      title: detailUrl(item) ? '在宿主里打开详情页' : '',
                      onClick: $event => (openDetail(item))
                    }, [
                      (posterUrl(item))
                        ? (_openBlock(), _createElementBlock("img", {
                            key: 0,
                            src: posterUrl(item),
                            alt: "",
                            loading: "lazy",
                            onError: _cache[19] || (_cache[19] = $event => (markPosterFailed($event)))
                          }, null, 40, _hoisted_64))
                        : (_openBlock(), _createBlock(_component_VIcon, {
                            key: 1,
                            icon: "mdi-filmstrip-box-multiple",
                            size: "30",
                            class: "sc-poster-ph"
                          })),
                      _createElementVNode("span", _hoisted_65, [
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
                    ], 10, _hoisted_63),
                    _createElementVNode("div", _hoisted_66, [
                      _createElementVNode("div", {
                        class: "sc-card-title",
                        title: item.title
                      }, [
                        _createElementVNode("b", null, _toDisplayString(item.title), 1)
                      ], 8, _hoisted_67),
                      _createElementVNode("div", _hoisted_68, [
                        (item.year)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_69, _toDisplayString(item.year), 1))
                          : _createCommentVNode("", true),
                        (item.media_type)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_70, _toDisplayString(item.media_type), 1))
                          : _createCommentVNode("", true),
                        _createElementVNode("span", null, _toDisplayString(item.source), 1),
                        (item.confidence)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_71, _toDisplayString(item.confidence), 1))
                          : _createCommentVNode("", true)
                      ]),
                      (item.release_date)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_72, " 放送 " + _toDisplayString(item.release_date), 1))
                        : _createCommentVNode("", true),
                      (item.reason)
                        ? (_openBlock(), _createElementBlock("div", {
                            key: 1,
                            class: "sc-card-reason",
                            title: item.reason
                          }, _toDisplayString(item.reason), 9, _hoisted_73))
                        : _createCommentVNode("", true),
                      _createElementVNode("div", _hoisted_74, [
                        (canSubscribe(item))
                          ? (_openBlock(), _createBlock(_component_VBtn, {
                              key: 0,
                              size: "x-small",
                              variant: "text",
                              loading: subscribing.value === item.key,
                              disabled: Boolean(subscribing.value),
                              "prepend-icon": "mdi-plus-circle-outline",
                              onClick: $event => (subscribeFromHistory(item))
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(subscribeLabel(item)), 1)
                              ]),
                              _: 2
                            }, 1032, ["loading", "disabled", "onClick"]))
                          : _createCommentVNode("", true),
                        _createVNode(_component_VBtn, {
                          size: "x-small",
                          variant: "text",
                          "prepend-icon": "mdi-pencil-outline",
                          onClick: $event => (fixMapping(item))
                        }, {
                          default: _withCtx(() => [...(_cache[46] || (_cache[46] = [
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
            ? (_openBlock(), _createElementBlock("div", _hoisted_75, [
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  disabled: history.value.page <= 1,
                  onClick: prevPage
                }, {
                  default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                    _createTextVNode("上一页", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createElementVNode("span", _hoisted_76, "第 " + _toDisplayString(history.value.page) + " 页 · 共 " + _toDisplayString(history.value.total) + " 部作品", 1),
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  disabled: history.value.page * history.value.count >= history.value.total,
                  onClick: nextPage
                }, {
                  default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                    _createTextVNode(" 下一页 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"])
              ]))
            : _createCommentVNode("", true)
        ]))
      : _createCommentVNode("", true)
  ], 2))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-645ec567"]]);

export { Page as default };
