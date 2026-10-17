"""胖虎订阅中心 - 配置、状态常量与业务常量。

本模块只放**无副作用**的纯常量与默认值，便于单元测试直接导入，
不触发任何宿主依赖或网络调用。
"""
from typing import Any, Dict

# --------------------------------------------------------------------- 插件元信息

PLUGIN_ID = "SubscribeCenter"
PLUGIN_NAME = "胖虎订阅中心"
PLUGIN_DESCRIPTION = "全自动开播 / 定档发现与订阅：从 TMDB、Bangumi、豆瓣 RSS、Simkl 发现即将开播与近期定档内容，三层去重后写入 MoviePilot 订阅。版本控制、洗版与下载优先级由宿主规则接管。"
PLUGIN_VERSION = "0.2.0"
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
MAX_DAILY_LIMIT = 50
DEFAULT_FUTURE_DAYS = 30
DEFAULT_MIN_RATING = 6.0

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
DECISION_SKIPPED_OUT_OF_WINDOW = "skipped_out_of_window"
DECISION_SKIPPED_NOT_FUTURE = "skipped_not_future"
DECISION_SKIPPED_DAILY_LIMIT = "skipped_daily_limit"
DECISION_PENDING_REVIEW = "pending_review"
DECISION_SKIPPED_SOURCE_DISABLED = "skipped_source_disabled"

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
SOURCE_BANGUMI = "bangumi"
SOURCE_DOUBAN_RSS = "douban_rss"
SOURCE_SIMKL = "simkl"
SOURCE_JUSTWATCH = "justwatch"

ALL_SOURCES = (
    SOURCE_TMDB,
    SOURCE_BANGUMI,
    SOURCE_DOUBAN_RSS,
    SOURCE_SIMKL,
    SOURCE_JUSTWATCH,
)

#: P1 已实现的数据源（其余源在配置页可开，但运行时会记录「未实现」并跳过）
IMPLEMENTED_SOURCES = frozenset({SOURCE_TMDB})


# --------------------------------------------------------------------- 配置

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
        "enable_bangumi": False,
        "enable_douban_rss": False,
        "enable_simkl": False,
        "enable_justwatch": False,
        # ---------------- 发现窗口与阈值
        "tmdb_future_days": DEFAULT_FUTURE_DAYS,
        "bangumi_future_days": DEFAULT_FUTURE_DAYS,
        "min_rating_tmdb": DEFAULT_MIN_RATING,
        "min_rating_bangumi": DEFAULT_MIN_RATING,
        "min_rating_douban": DEFAULT_MIN_RATING,
        "min_rating_simkl": DEFAULT_MIN_RATING,
        # ---------------- 豆瓣 RSS 源列表
        "douban_rss_sources": [],
        # ---------------- Simkl
        "simkl_client_id": "",
        # ---------------- 写入
        "daily_limit": DEFAULT_DAILY_LIMIT,
        "dry_run": False,
        # ---------------- 调度与通知
        "cron": DEFAULT_CRON,
        "timezone": DEFAULT_TIMEZONE,
        "notify": False,
        # ---------------- 界面
        "discovery_page_enabled": False,
        # ---------------- 一次性执行（不持久化语义，保存后由宿主清理）
        "onlyonce": False,
    }


#: 不进前端表单、仅后端自管的状态键（前端整份回写时必须排除）
BACKEND_OWNED_KEYS = frozenset({"onlyonce"})

#: 首次运行强制 dry-run 的持久化状态键（存插件数据，不放配置）
STATE_FIRST_RUN_DONE = "first_run_completed"
STATE_LAST_RUN = "last_run"
STATE_DAILY_COUNT = "daily_write_count"
STATE_TODAY = "daily_write_date"
