"""胖虎订阅中心 - 配置、状态常量与业务常量。

本模块只放**无副作用**的纯常量与默认值，便于单元测试直接导入，
不触发任何宿主依赖或网络调用。
"""
import copy
from typing import Any, Dict, List

# --------------------------------------------------------------------- 插件元信息

PLUGIN_ID = "SubscribeCenter"
PLUGIN_NAME = "胖虎订阅中心"
PLUGIN_DESCRIPTION = (
    "全自动开播 / 定档发现与订阅：从 TMDB、AniList（番剧 + 国漫）、豆瓣 RSS "
    "发现即将开播与近期定档内容，三层去重后写入 MoviePilot 订阅。"
    "番剧支持两条通道：新番按开播日、连载按下一集播出时间（国漫靠这条才抓得到）。"
    "版本控制、洗版与下载优先级由宿主规则接管。"
)
PLUGIN_VERSION = "1.13.6"
PLUGIN_DESC = "全自动开播/定档发现与订阅：发现 → 去重 → 写订阅。"
PLUGIN_ICON = (
    "https://raw.githubusercontent.com/strongrexue/MoviePilot-Plugins/main/icons/subscribecenter.png"
)
PLUGIN_COLOR = "#F2A93B"
PLUGIN_AUTHOR = "strongrexue"
AUTHOR_URL = "https://github.com/strongrexue"
PLUGIN_CONFIG_PREFIX = "subscribecenter_"
PLUGIN_ORDER = 30
AUTH_LEVEL = 1

# --------------------------------------------------------------------- 常量

DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_CRON = "0 3 * * *"
DEFAULT_DAILY_LIMIT = 30
DEFAULT_FUTURE_DAYS = 3

#: 「按播出日自动启停」的定时。
#:
#: 为什么是 00:05 而不是 23:xx：判定基准是**服务器本地日期**，跨过零点就换了
#: 一天；早于零点跑必然把「明天播」的剧判成「今天播」。零点后 5 分钟足够让
#: 宿主的日期翻转、也留出 TMDB 查询时间，赶在当天第一轮订阅刷新之前生效。
DEFAULT_AUTO_TOGGLE_CRON = "5 0 * * *"

#: 洗版订阅的保留窗口（天）。
#:
#: 洗版订阅的语义不是「缺集」而是「等更好的版本」，而更好的版本（原盘 /
#: REMUX / 全季 BD）通常要完结后 3~6 个月才出种。套用剧集那 3 天窗口会把
#: 洗版订阅在季终后第 4 天就停掉，等于把它废掉。默认 90 天：季终三个月后
#: 还没等到更好的版本，要么站点没有、要么过滤规则卡住了，再空搜也没用。
DEFAULT_AUTO_TOGGLE_BEST_KEEP = 90
DEFAULT_MIN_RATING = 6.0
#: 最低关注度（TMDB popularity 分位参考：观众级大片 100+、院线片 10~50、
#: 冷门/影展片 <5）。未来档期的片子几乎都没评分，popularity 是唯一可用的
#: 质量信号 —— 实测同日上映的冷门片 popularity 普遍在个位数（0.2.2 真实事故：
#: 29 条写入里全是 Black Ink / Ghost Lake 这类 popularity<5 的片子）。
DEFAULT_MIN_POPULARITY = 15.0

#: 允许的原始语言（逗号分隔）。华语/日语/韩语/英语覆盖中文媒体库的主流需求；
#: 印度、土耳其、荷兰等小语种片通常不会被下载，进订阅只会白占额度
#: （0.2.4 实测里《12 12 12》印度片 popularity 10.8 拦不住，语言过滤能一次拦掉）。
DEFAULT_ORIGINAL_LANGUAGES = "zh,ja,ko,en"

#: 单条订阅写入的最大重试次数（失败即放弃并记录，不影响后续条目）
WRITE_MAX_ATTEMPTS = 1

#: 单个数据源的默认请求超时（秒）与重试次数
SOURCE_TIMEOUT_SECONDS = 15
SOURCE_MAX_RETRIES = 2

#: 发现决策（后端常量必须与前端 label 映射逐字一致）
DECISION_ADDED = "added"
DECISION_SKIPPED_DRY_RUN = "skipped_dry_run"
DECISION_SKIPPED_FIRST_RUN = "skipped_first_run_dry"
DECISION_SKIPPED_ALREADY_SUBSCRIBED = "skipped_already_subscribed"
DECISION_SKIPPED_ALREADY_COMPLETED = "skipped_already_completed"
DECISION_SKIPPED_DUPLICATE = "skipped_duplicate"
DECISION_SKIPPED_RATING = "skipped_rating"
DECISION_SKIPPED_POPULARITY = "skipped_popularity"
DECISION_SKIPPED_OUT_OF_WINDOW = "skipped_out_of_window"
DECISION_SKIPPED_NOT_FUTURE = "skipped_not_future"
DECISION_SKIPPED_DAILY_LIMIT = "skipped_daily_limit"
DECISION_PENDING_REVIEW = "pending_review"
#: 特别篇 / OVA / 番外 / 学前篇等衍生内容 —— 不是「匹配失败」，是设计上不处理
DECISION_SKIPPED_SPECIAL = "skipped_special"
#: 匹配到的 TMDB 剧集已全部播完 —— 订了也搜不到未播资源
DECISION_SKIPPED_FINISHED = "skipped_finished"
#: 来源没有定档日期，且是电影 —— 无从判断是否即将上映
DECISION_SKIPPED_NO_DATE = "skipped_no_date"
#: 豆瓣想看人数不足
DECISION_SKIPPED_WANT = "skipped_want"
DECISION_SKIPPED_SOURCE_DISABLED = "skipped_source_disabled"
#: 发现流水里已经记着「订阅过」这一部 —— 用户把订阅删了也不再自动订回来
#:
#: 与 ``skipped_already_subscribed`` 的区别：那条是「宿主当前就有这条订阅」，
#: 删掉订阅后就会消失；这条记的是**历史**，只有清空流水才会忘掉。
DECISION_SKIPPED_RECORDED = "skipped_recorded"

#: 身份解析级别
CONFIDENCE_L1 = "L1"  # 确定性 ID 直通
CONFIDENCE_L2 = "L2"  # 已确认映射缓存
CONFIDENCE_L3 = "L3"  # 精确搜索 + 年份硬校验
CONFIDENCE_L4 = "L4"  # 模糊评分 —— 永不写入



#: 允许写入订阅的置信度级别白名单（L4 严格排除，见开发文档 §6.2）
WRITABLE_CONFIDENCE = frozenset({CONFIDENCE_L1, CONFIDENCE_L2, CONFIDENCE_L3})

#: 媒体类型（字符串常量，避免导入宿主枚举）
MEDIA_TYPE_MOVIE = "movie"
MEDIA_TYPE_TV = "tv"

#: 数据源标识
SOURCE_TMDB = "tmdb"
SOURCE_ANILIST = "anilist"
SOURCE_BANGUMI = "bangumi"
SOURCE_DOUBAN_RSS = "douban_rss"

#: 热门媒体：MoviePilot 官方热门订阅统计（需开启订阅数据共享）
SOURCE_HOT_MEDIA = "hot_media"
SOURCE_SIMKL = "simkl"
SOURCE_JUSTWATCH = "justwatch"

#: 前端展示的数据源集合。
#:
#: **不含 Bangumi** —— 自 1.0.0 起它降级为内部「日文 → 中文」标题翻译层，
#: 不是发现源，不该出现在数据源列表里（真机反馈：界面上还挂着一个
#: 「Bangumi 已启用·未实现」，误导性很强）。
ALL_SOURCES = (
    SOURCE_TMDB,
    SOURCE_ANILIST,
    SOURCE_DOUBAN_RSS,
    SOURCE_HOT_MEDIA,
)

#: 已实现的数据源（其余源在配置页可开，但运行时会记录「未实现」并跳过）
IMPLEMENTED_SOURCES = frozenset(
    {SOURCE_TMDB, SOURCE_ANILIST, SOURCE_DOUBAN_RSS, SOURCE_HOT_MEDIA}
)


# --------------------------------------------------------------------- 配置

#: 当前配置结构版本。每次改了默认值且希望老用户跟着变，就 +1 并在 config_migrations 登记。
#: 豆瓣 RSS 的内置榜单预设。
#:
#: 每一条都是**实测可用**的 RSSHub 路线（404 的 ustop250 / movie/new 未列入）。
#: 每条独立可控：开关 / 每榜条数 / 窗口天数 / 最低想看人数 —— 用 dict 而不是
#: 裸 URL 列表，是因为「即将上映」带精确日期（窗口可放宽到 30 天）、
#: 而榜单类没有日期（靠 TMDB 未播集判断），两者理想参数本来就不同。
DEFAULT_DOUBAN_LISTS = [
    {
        "name": "电影即将上映",
        "url": "/douban/movie/coming",
        "enabled": True,
        "max_items": 0,
        "future_days": 30,
        "min_want": 0,
    },
    {
        "name": "剧集即将播出",
        "url": "/douban/tv/coming",
        "enabled": True,
        "max_items": 0,
        "future_days": 30,
        "min_want": 0,
    },
    {
        "name": "近期热门剧集",
        "url": "/douban/list/tv_real_time_hotest",
        "enabled": True,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "近期热门国产剧",
        "url": "/douban/list/tv_domestic",
        "enabled": True,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "近期热门综艺",
        "url": "/douban/list/tv_variety",
        "enabled": True,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "近期热门动画",
        "url": "/douban/list/tv_animation",
        "enabled": True,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "豆瓣推荐剧集",
        "url": "/douban/recommended/tv",
        "enabled": True,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "近期热门电影",
        "url": "/douban/list/movie_real_time_hotest",
        "enabled": False,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "华语口碑剧集",
        "url": "/douban/list/tv_chinese_best_weekly",
        "enabled": False,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "全球口碑剧集",
        "url": "/douban/list/tv_global_best_weekly",
        "enabled": False,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "电影口碑榜",
        "url": "/douban/list/movie_weekly_best",
        "enabled": False,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "日剧",
        "url": "/douban/list/tv_japanese",
        "enabled": False,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "韩剧",
        "url": "/douban/list/tv_korean",
        "enabled": False,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
    {
        "name": "美剧",
        "url": "/douban/list/tv_american",
        "enabled": False,
        "max_items": 0,
        "future_days": 3,
        "min_want": 0,
    },
]


CONFIG_VERSION = 9


def default_config() -> Dict[str, Any]:
    """返回插件默认配置。

    .. important::
       本函数的键集合必须与前端 ``src/components/configDefaults.js`` **严格一致**。
       宿主 ``update_config()`` 是整份覆盖，配置项任一侧缺失都会被静默清掉。
       ``tests/v3/subscribecenter/test_config_parity.py`` 对此设了回归锁。
       前端对应文件：``plugins.v3/subscribecenter/src/components/configDefaults.js``。
    """
    return {
        "enabled": False,
        # ---------------- 数据源开关
        "enable_tmdb": True,
        "enable_anilist": True,
        "enable_bangumi": False,
        "enable_douban_rss": False,
        # ---------------- 发现窗口与阈值
        "tmdb_future_days": DEFAULT_FUTURE_DAYS,
        "bangumi_future_days": DEFAULT_FUTURE_DAYS,
        "min_rating_tmdb": DEFAULT_MIN_RATING,
        "min_rating_bangumi": DEFAULT_MIN_RATING,
        "min_rating_douban": DEFAULT_MIN_RATING,
        "min_popularity": DEFAULT_MIN_POPULARITY,
        # ---------------- AniList（番剧 / 国漫）
        #: 番剧发现窗口（天）。番剧定档密集，窗口不必太长。
        "anilist_future_days": DEFAULT_FUTURE_DAYS,
        #: 最低热度（AniList 的 popularity 量纲与 TMDB 完全不同：
        #: 冷门番约 500~2000，主流番 2 万~5 万，所以不能复用 TMDB 的 15）。
        #: 最低评分（AniList averageScore/10：70≈7.0 分）。与 TMDB 量纲不同：
        #: AniList 用的是站内加权分，普遍比 TMDB 低一档，所以单独设。
        "min_rating_anilist": DEFAULT_MIN_RATING,
        "anilist_min_popularity": 1000.0,
        #: 是否包含国产动画（countryOfOrigin=CN）。
        #: **默认开** —— 国漫只有 AniList 能覆盖（Bangumi 的日历实测漏掉大半）。
        "anilist_include_donghua": True,
        #: Bangumi 是否「按季拆分」订阅。
        #:
        #: **默认关**。国产动画在 TMDB 通常被建模成「单季多集」
        #: （实测《牧神记》= 第 1 季 110 集，第 105 集 = 2026-10-18，
        #: 正好对应 Bangumi「牧神记5」的开播日）。此时 Bangumi 的
        #: 「第 5 期」不是 TMDB 的第 5 季 —— 传 season=5 会让宿主去找
        #: 一个不存在的季，什么都订不到。
        #: 关掉后按 TMDB 默认季订阅，靠宿主按集追踪，才是正确行为。
        "bangumi_split_season": False,
        #: 是否只保留指定原始语言的条目
        "filter_original_language": True,
        "tmdb_original_languages": DEFAULT_ORIGINAL_LANGUAGES,
        # ---------------- 豆瓣 RSS 源列表
        #: 豆瓣 RSS 榜单列表：内置预设 + 自定义，每条独立控制
        #: （name / url / enabled / max_items / future_days / min_want）
        #: RSSHub 域名（总控）：榜单里只存路由（/douban/movie/coming），
        #: 拼接时用「域名 + 路由」。换 RSSHub 地址只改这一处，不用逐条改。
        "rsshub_domain": "https://rsshub.ddsrem.com",
        "douban_rss_sources": copy.deepcopy(DEFAULT_DOUBAN_LISTS),
        #: 每个榜单最多取前 N 条（榜单按名次排列，取前 N 即取最热的）。
        #: 实测 /douban/list/tv_hot 有 241 条，不限量会把额度全吃掉。
        "douban_max_items_per_feed": 30,
        #: 豆瓣的发现窗口（天）—— **独立于 TMDB**。
        #:
        #: 豆瓣「即将上映」是按档期排的策展列表，可以比 TMDB 宽一些；
        #: 而榜单类路线本身没有日期，窗口对它不起作用。
        "douban_future_days": DEFAULT_FUTURE_DAYS,
        #: 豆瓣「想看人数」门槛（0 = 不过滤）。
        #:
        #: 只有 coming 类路线带想看数（如「想看：27357」），榜单类没有。
        #: 缺失时放行（按接入契约，缺失值不拦）。量纲是「人数」，
        #: 与 TMDB popularity 无关，因此单独设一个门槛。
        "douban_min_want": 0,
        #: 身份解析并发数。
        #:
        #: 榜单类来源一次能给 200+ 条候选，串行约 0.7s/条（3 分钟）。
        #: 并发 8 路实测降到 20~30 秒；再高收益有限且容易触发 TMDB 限流。
        "resolve_concurrency": 8,
        #: 是否用 TMDB episode group 精确订阅「被压成单季」的番剧。
        #:
        #: 真机：《药屋少女的呢喃》TMDB 是 1 季 60 集连续编号（第 49~60 集才是
        #: 第 3 季），但 episode group 里 Season 3 = 12 集。带 group 订阅后
        #: 宿主只追这 12 集，不会去补前 48 集旧番。关掉则按单季整体订阅。
        "prefer_episode_group": True,
        #: 已完成过的订阅是否允许重新订阅（忽略订阅历史）。
        #:
        #: 默认**开启**：宿主把订阅标成完成时会移入 subscribehistory，
        #: 但用户可能已经从媒体库删掉文件、想重新下。
        #: 注意：真正「已经播完」的剧会先被 finished 判定拦住
        #: （TMDB 无未播集），所以不会每轮都重复建订阅。
        "resubscribe_completed": True,
        #: 「发现流水里记录过订阅过的，就不再自动订回来」。
        #:
        #: 默认**开启**：流水是本插件自己的账本，记着「这部我订过」。用户主动
        #: 把订阅删掉通常就是不想再要它 —— 宿主那边的 ``subscription_exists``
        #: 已经查不到了，只有流水还记得。想让它重新订，就清空流水（或删掉对应
        #: 的那几条记录）：流水里没有记录，才会重新订阅。
        "dedupe_by_history": True,
        # ---------------- Simkl
        # ---------------- 写入
        "daily_limit": DEFAULT_DAILY_LIMIT,
        # ---------------- 按播出日自动启停（治「订阅刷新」的空转）
        #: 总开关。**默认关**：它会改用户订阅的状态，属于「有副作用」的能力，
        #: 必须由用户显式打开（打开前可以先点「预览」看清会动哪几条）。
        #:
        #: 背景：宿主的「订阅刷新」按 ``subscribe_rss_interval``（默认 30 分钟）
        #: 把**全部** R/P 订阅拉进匹配循环。订阅到两百条时，绝大多数条目当天
        #: 并没有新集，纯属空转。本功能按 TMDB ``episodes[].air_date`` 把
        #: 「今天没该搜的集」的订阅暂停为 ``S``，有集的恢复为 ``R``。
        "auto_toggle_enabled": False,
        #: 每天几点判定一次。默认零点后 5 分钟（见 ``DEFAULT_AUTO_TOGGLE_CRON``）。
        "auto_toggle_cron": DEFAULT_AUTO_TOGGLE_CRON,
        #: 提前几天把「即将播出」的订阅也算上（0 = 只看今天）。
        #:
        #: 默认 0，严格对齐「当天播出的才启用」。调成 1 就是「今天和明天要播的
        #: 都启用」，适合站点出种慢、需要提前搜的情况。
        "auto_toggle_lookahead_days": 0,
        #: 某一集已播出但还没入库时，再多留几天 ``R``。
        #:
        #: 这是「已播但 PT 还没资源」的兜底：播出日当天没出种是常态（生肉要
        #: 压、字幕组要翻），当天就暂停会导致这一集永远收不到。默认 3 天。
        #: 超过窗口还没入库的，按「等资源等太久」暂停（下载器里已有任务时
        #: 宿主自己会继续追，不依赖订阅状态）。
        "auto_toggle_keep_days": 3,
        #: 洗版订阅（``best_version=1``）的保留窗口，默认 90 天。
        #:
        #: 见 ``DEFAULT_AUTO_TOGGLE_BEST_KEEP``：洗版等的是「更好的版本」，
        #: 不是「缺集」，用 3 天窗口会在季终后立刻把它停掉。设 0 表示跟随上面
        #: 的 ``auto_toggle_keep_days``。
        "auto_toggle_best_version_keep_days": DEFAULT_AUTO_TOGGLE_BEST_KEEP,
        #: 洗版判定模式：什么时候把「没洗到顶」当成「还要继续搜」。
        #:
        #: - ``after_finale``（默认）：只在**本季已完结**后才按洗版算。播出期
        #:   宿主只下「首个可用版本」，真正的洗版（原盘/REMUX）是季终之后才
        #:   陆续有资源；播出期就按洗版判，等于所有洗版订阅长期 ``R``。
        #: - ``always``：播出期也算（想全程蹲洗版的人用，代价是这些订阅基本
        #:   不会被暂停）。
        "auto_toggle_best_version_mode": "after_finale",
        #: 是否连电影订阅一起管（默认开）。
        #:
        #: 电影没有「集」，基准日取 TMDB 发行日：普通订阅看数字发行（type=4，
        #: WEB-DL 出种），洗版订阅看实体发行（type=5，原盘/REMUX 出种）。
        #: 想等枪版的人把它关掉即可 —— 影院期一律暂停会挡住枪版。
        "auto_toggle_movie_enabled": True,
        #: 单次最多改多少条（0 = 不限）。防止第一次打开时一口气暂停两百条把
        #: 人吓到；超出时**先保恢复、后保暂停**（少暂停只是多搜一次，漏恢复
        #: 会让该搜的订阅一整天不搜）。
        "auto_toggle_max_changes": 0,
        #: 每次自动启停后是否发通知（消息里带暂停/恢复条数）。
        "auto_toggle_notify": False,
        # ---------------- 调度与通知
        #: 每源独立定时（五位 cron，留空 = 跟随上面的全局 cron）
        "cron_tmdb": "",
        "cron_anilist": "",
        "cron_douban_rss": "",
        "cron_hot_media": "",
        "cron": DEFAULT_CRON,
        "timezone": DEFAULT_TIMEZONE,
        "notify": False,
        # ---------------- 界面
        # ---------------- 测试辅助
        #: 一次性开关：保存配置时把「今日已写入条数」清零，便于同一天反复测试。
        #: 用完自动置回 False（否则每日额度会永远失效）。
        "reset_daily_counter": False,
        # ---------------- 配置结构版本（用于把默认值变更推给存量配置）
        "config_version": CONFIG_VERSION,
        # ---------------- 一次性执行（不持久化语义，保存后由宿主清理）
        "onlyonce": False,
    }


#: 一次性开关：读取后必须立刻置回默认值（避免长期生效）
ONE_SHOT_FLAGS = frozenset({"reset_daily_counter", "onlyonce"})


# --------------------------------------------------------------------- 配置迁移

#: 当前配置结构版本。**每次改了默认值且希望老用户跟着变，就 +1 并在下面登记。**
def config_migrations() -> Dict[int, Dict[str, Any]]:
    """返回「从某版本升到下一版本时要覆盖的键值」。

    背景：宿主 ``update_config()`` 保存的是**完整快照**，``init_plugin``
    也是「默认值 merge 存量配置」。所以只改 `default_config()` 的默认值，
    **老用户的存量配置不会跟着变** —— 他们库里存着旧值，merge 后旧值胜出。

    真机踩过：把窗口默认值从 30 改成 8 后，用户的库里仍是
    ``tmdb_future_days=30``，白等了一轮。

    .. note::
       这里只登记「改了默认值、且希望存量跟随」的键。
       **凡是用户可能主动改过的键都要谨慎** —— 例如把开关从 True 改成 False
       再覆盖，会把用户手动打开的开关关掉。
       当前登记的都是「数值默认值调整」，覆盖是安全的（老用户几乎不可能
       正好把它们设成旧默认值）。
    """
    return {
        # v1 -> v2：窗口收紧 30 -> 8 天
        2: {"tmdb_future_days": 8},
        # v2 -> v3：窗口再收到 3 天 —— PT 资源普遍上映后才有，提前订只是空转。
        # 3 天窗口 = 上映前 3 天进窗口，共 4 次运行机会（进窗口当天 + 上映日及前后），
        # 足以吸收单次运行失败；真机实测一周实际新增约 4 条，部分天为 0。
        3: {"tmdb_future_days": DEFAULT_FUTURE_DAYS},
        # v3 -> v4：启用 AniList 源（番剧 + 国漫），Bangumi 降级为标题翻译层。
        # 这是**新增**源，不是改用户既有选择：老用户库里没有这三个键，
        # merge 默认值后就是这里写的值，因此只登记「窗口」与「国漫开关」
        # 这类会随版本演进调整的项；两个开关（enable_anilist）不覆盖，
        # 避免把用户手动关掉的源又打开。
        4: {
            "anilist_future_days": DEFAULT_FUTURE_DAYS,
            "anilist_include_donghua": True,
        },
        # v4 -> v5：豆瓣 RSS 从「裸 URL 列表」升级为「每榜独立配置」。
        # 迁移只做格式转换，不改用户的选择（老的 URL 全部保留、默认启用），
        # 名字从 URL 末段推导；已是 dict 列表则原样保留。
        5: {"douban_rss_sources": "migrate_lists"},
    }


def _migrate_douban_lists(value: Any) -> List[Dict[str, Any]]:
    """把老的豆瓣 RSS 配置迁移成「每榜独立配置」列表。

    老形态是字符串列表（每行一个 URL）；新形态是 dict 列表。
    迁移**不改用户的选择**：老的 URL 全部保留并默认启用，名字从 URL 末段推导
    （``/douban/movie/coming`` -> ``电影即将上映`` 这类推导不出来时就用末段原文）。
    """
    from ..sources.douban_rss import list_name_of, normalize_list_entry

    if not isinstance(value, (list, tuple)):
        return []
    result: List[Dict[str, Any]] = []
    for entry in value:
        if isinstance(entry, dict):
            normalized = normalize_list_entry(entry)
            if normalized["url"]:
                result.append(normalized)
            continue
        url = str(entry or "").strip()
        if not url:
            continue
        result.append(normalize_list_entry({"url": url, "name": list_name_of(url)}))
    return result


def migrate_config(config: Dict[str, Any]) -> tuple:
    """按 ``config_migrations`` 升级存量配置。

    :param config: 已与默认值合并的配置字典
    :return: ``(配置, 是否发生变更, 变更说明列表)``
    """
    stored = config.get("config_version")
    try:
        current = int(stored)
    except (TypeError, ValueError):
        # 老配置没有该键：视为版本 1（即「窗口 30 天」那一代）
        current = 1

    migrations = config_migrations()
    changes: list = []
    while current < CONFIG_VERSION:
        next_version = current + 1
        patch = migrations.get(next_version) or {}
        for key, value in patch.items():
            if value == "migrate_lists":
                # 特殊迁移：豆瓣 RSS 从裸 URL 列表升级为每榜独立配置
                converted = _migrate_douban_lists(config.get(key))
                if config.get(key) != converted:
                    config[key] = converted
                    changes.append(f"{key}: -> {len(converted)} 条榜单")
                continue
            if config.get(key) != value:
                config[key] = value
                changes.append(f"{key}: -> {value}")
        current = next_version

    if stored != CONFIG_VERSION:
        config["config_version"] = CONFIG_VERSION
        if not changes:
            changes.append(f"config_version -> {CONFIG_VERSION}")
    return config, bool(changes), changes


#: 不进前端表单、仅后端自管的状态键（前端整份回写时必须排除）
BACKEND_OWNED_KEYS = frozenset({"onlyonce"})

#: 首次运行强制 dry-run 的持久化状态键（存插件数据，不放配置）
STATE_FIRST_RUN_DONE = "first_run_completed"
STATE_LAST_RUN = "last_run"
STATE_DAILY_COUNT = "daily_write_count"
STATE_TODAY = "daily_write_date"
