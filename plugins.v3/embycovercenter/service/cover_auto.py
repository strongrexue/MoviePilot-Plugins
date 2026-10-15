"""自动封面任务：定时 / 入库事件触发，把选中媒体库的封面批量重生成并上传。

执行链路与手动「渲染并应用」一致（controller/api.py 的无 image_data 分支）：
resolve 服务器 → list_libraries 取库名 → 解析封面方案（模板预设或封面设计）
→ fetch_assets 拉素材 → PosterEngine.draw 渲染 → post_raw 上传 Primary。

- 定时：``__init__.get_service()`` 注册 CronTrigger（cover_cron）；
- 入库：宿主 ``EventType.WebhookMessage`` 事件（Emby webhook 转发），按
  (服务器, 媒体库) 防抖——Emby 扫库会逐条推送事件，一批入库只应渲染一次；
- 通知：走宿主 ``post_message``（notify_on_task_finish 门控），不自建通知通道。
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

from app.sdk.logging import logger

from . import assets_meta, emby_assets, emby_gateway
from .emby_gateway import GatewayError
from .render_engine import PosterEngine

# 库级并行度：每库 = 并行下载素材 + PIL 渲染 + 上传，多为 I/O，4 路并行
# 已能把 20+ 库的整轮时间压到串行的 1/3 左右，再高会挤压 Emby/带宽。
AUTO_COVER_WORKERS = 4

# 常见媒体库名的中英对照（副标题默认取英文名；与前端 useCoverDesigner 同源，键小写）。
LIBRARY_EN_NAMES = {
    "电影": "Movies",
    "电影库": "Movies",
    "欧美电影": "Western Movies",
    "华语电影": "Chinese Movies",
    "日韩电影": "Asian Movies",
    "4k电影": "4K Movies",
    "电视剧": "TV Shows",
    "剧集": "TV Shows",
    "电视节目": "TV Shows",
    "动漫": "Anime",
    "动画": "Anime",
    "番剧": "Anime",
    "综艺": "Variety Shows",
    "纪录片": "Documentaries",
    "儿童": "Kids",
    "少儿": "Kids",
    "亲子": "Kids",
    "音乐": "Music",
    "mv": "Music Videos",
    "体育": "Sports",
    "教育": "Education",
    "有声书": "Audiobooks",
}

# 同一 (服务器, 媒体库) 两次入库触发刷新的最小间隔（秒）。
WEBHOOK_DEBOUNCE_SECONDS = 600

# 全局互斥：定时、手动「立即运行」与入库触发不会并发渲染（渲染吃内存且逐库上传）。
_TASK_LOCK = threading.Lock()
# 入库防抖位图：{ (服务器名, 媒体库ID): 最近一次触发时间 }。
_WEBHOOK_LAST: Dict[Tuple[str, str], float] = {}


def english_name_for(name: Any) -> str:
    """按库名查内置英文名；未命中返回空串（键统一小写，兼容「4K电影/4k电影」）。"""
    key = str(name or "").strip().lower()
    return LIBRARY_EN_NAMES.get(key, "")


def _subtitle_for(config: Dict[str, Any], library_id: str, library_name: str) -> str:
    """副标题取值优先级：手填英文名（library_en_names）→ 内置词典 → 库名。"""
    override = config.get("library_en_names")
    if isinstance(override, dict):
        text = str(override.get(library_id) or "").strip()
        if text:
            return text
    return english_name_for(library_name) or library_name


def resolve_design(plugin, config: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """解析封面方案：选择了模板预设用模板（read_template），否则跟随封面设计。

    :raises ValueError: 模板预设不存在或内容不合法。
    """
    template_name = str(config.get("auto_cover_template") or "").strip()
    if template_name:
        data = assets_meta.read_template(plugin, template_name)
        return str(data.get("layout") or "classic"), dict(data.get("config") or {})
    return str(config.get("cover_layout") or "classic"), dict(config.get("cover_config") or {})


def selected_targets(plugin, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """解析目标媒体库：auto_cover_libraries 与 selected_servers 取交集。

    返回 ``[{server, ref, library_id, name}]``；服务器不可访问时记日志跳过，
    配置里已不存在的媒体库 ID 自然落选。
    """
    mapping = config.get("auto_cover_libraries")
    if not isinstance(mapping, dict):
        return []
    allowed_servers = {str(x) for x in (config.get("selected_servers") or [])}
    targets: List[Dict[str, Any]] = []
    for server_name, library_ids in mapping.items():
        server = str(server_name or "").strip()
        if not server or not isinstance(library_ids, list):
            continue
        wanted = {str(x).strip() for x in library_ids if str(x).strip()}
        if not wanted:
            continue
        if allowed_servers and server not in allowed_servers:
            continue
        try:
            ref = emby_gateway.resolve(server)
            libraries = emby_assets.list_libraries(ref)
        except GatewayError as error:
            logger.warning(f"[EmbyCoverCenter] 自动封面跳过服务器 {server}：{error}")
            continue
        for library in libraries:
            if not isinstance(library, dict):
                continue
            library_id = str(library.get("id") or "")
            if library_id in wanted:
                targets.append(
                    {
                        "server": server,
                        "ref": ref,
                        "library_id": library_id,
                        "name": str(library.get("name") or library_id),
                    }
                )
    return targets


def refresh_library(
    plugin,
    target: Dict[str, Any],
    layout: str,
    style: Dict[str, Any],
    config: Dict[str, Any],
) -> None:
    """渲染并上传单个媒体库封面；失败抛 GatewayError / ValueError。

    标题=库名、副标题按手填英文名 → 内置词典 → 库名；素材数量与手动应用同口径
    （封面方案 config 里的 poster_count/backdrop_count 优先，缺省回退插件配置）。
    """
    library_id = target["library_id"]
    ref = target["ref"]
    engine_config = dict(style)
    engine_config["engine"] = layout
    engine_config["title"] = target["name"] or library_id
    engine_config["subtitle"] = _subtitle_for(config, library_id, engine_config["title"])

    def _count(key: str, fallback: int) -> int:
        try:
            return int(engine_config.get(key) or fallback or 0)
        except (TypeError, ValueError):
            return int(fallback or 0)

    assets = emby_assets.fetch_assets(
        ref,
        library_id,
        mode=str(config.get("assets_mode") or "random"),
        poster_count=_count("poster_count", config.get("poster_count") or 6),
        backdrop_count=_count("backdrop_count", config.get("backdrop_count") or 1),
    )
    image = plugin.cover_engine().draw(engine_config, assets)
    emby_gateway.post_raw(
        ref,
        f"Items/{library_id}/Images/Primary",
        data=image,
        content_type=PosterEngine.base64_mime(image),
    )


def _post_message(plugin, title: str, text: str) -> None:
    """走宿主通知渠道（getattr 防旧宿主）；通知失败只记日志不影响主流程。"""
    func = getattr(plugin, "post_message", None)
    if not callable(func):
        return
    try:
        func(title=title, text=str(text or ""))
    except Exception as error:  # pragma: no cover - 通知失败不影响主流程
        logger.warning(f"[EmbyCoverCenter] 发送通知失败：{error}")


def _notify_run(plugin, summary: Dict[str, Any]) -> None:
    """整轮任务结束的通知（notify_on_task_finish 门控）。"""
    config = getattr(plugin, "config", None) or {}
    if not config.get("notify_on_task_finish"):
        return
    total = int(summary.get("total") or 0)
    ok_count = int(summary.get("ok") or 0)
    failed = int(summary.get("failed") or 0)
    if summary.get("error"):
        text = f"封面方案无效，本轮未执行：{summary['error']}"
    elif total <= 0:
        text = "未选择任何目标媒体库，请先在自动封面设置里勾选。"
    else:
        lines = [f"共 {total} 个媒体库：成功 {ok_count}，失败 {failed}。"]
        for item in summary.get("items") or []:
            if not item.get("ok"):
                lines.append(f"❌ {item.get('server')} / {item.get('library')}：{item.get('error') or '未知原因'}")
        text = "\n".join(lines)
    name = str(getattr(plugin, "plugin_name", "") or "胖虎封面中心")
    _post_message(plugin, f"{name} · 自动封面任务", text)


def run_auto_cover(plugin) -> Dict[str, Any]:
    """同步执行一轮自动封面；定时任务、手动接口与入库触发共用。

    全程持全局互斥锁（非阻塞获取，正在执行时直接跳过本轮）。

    :returns: 汇总 ``{total, ok, failed, items, error?}``。
    """
    config = getattr(plugin, "config", None) or {}
    if not _TASK_LOCK.acquire(blocking=False):
        logger.info("[EmbyCoverCenter] 自动封面任务已在执行，本轮跳过")
        return {"total": 0, "ok": 0, "failed": 0, "items": [], "error": "已有任务在执行，本轮跳过"}
    try:
        try:
            layout, style = resolve_design(plugin, config)
        except (ValueError, GatewayError) as error:
            logger.error(f"[EmbyCoverCenter] 自动封面封面方案无效：{error}")
            summary = {"total": 0, "ok": 0, "failed": 0, "items": [], "error": str(error)}
            _notify_run(plugin, summary)
            return summary
        targets = selected_targets(plugin, config)
        items: List[Dict[str, Any]] = [None] * len(targets)  # type: ignore[list-item]

        def _work(index: int) -> None:
            target = targets[index]
            label = f"{target['server']} / {target['name']}"
            try:
                refresh_library(plugin, target, layout, style, config)
                items[index] = {
                    "server": target["server"],
                    "library": target["name"],
                    "ok": True,
                    "error": "",
                }
                logger.info(f"[EmbyCoverCenter] 自动封面完成：{label}")
            except Exception as error:  # 单库失败不拖垮整轮，逐库隔离
                items[index] = {
                    "server": target["server"],
                    "library": target["name"],
                    "ok": False,
                    "error": str(error),
                }
                logger.warning(f"[EmbyCoverCenter] 自动封面失败 {label}：{error}")

        if targets:
            # 预热布局模块（首次加载非线程安全，避免并行首渲染时双重加载）。
            _ = getattr(plugin.cover_engine(), "layout_modules", None)
            workers = max(1, min(AUTO_COVER_WORKERS, len(targets)))
            if workers > 1:
                logger.info(f"[EmbyCoverCenter] 自动封面开始：{len(targets)} 个媒体库，{workers} 路并行")
                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="eccover") as pool:
                    list(pool.map(_work, range(len(targets))))
            else:
                _work(0)
        ok_count = sum(1 for item in items if item and item["ok"])
        summary = {
            "total": len(targets),
            "ok": ok_count,
            "failed": len(targets) - ok_count,
            "items": [item for item in items if item],
        }
        _notify_run(plugin, summary)
        return summary
    finally:
        _TASK_LOCK.release()


def _run_quietly(plugin) -> None:
    try:
        run_auto_cover(plugin)
    except Exception as error:  # pragma: no cover - 后台线程兜底
        logger.error(f"[EmbyCoverCenter] 自动封面任务异常：{error}")


def run_auto_cover_async(plugin) -> None:
    """后台线程执行一轮自动封面（手动「立即运行」入口，接口立即返回）。"""
    threading.Thread(target=_run_quietly, args=(plugin,), name="embycovercenter-auto-cover", daemon=True).start()


# --------------------------------------------------------------------------- 入库事件


def _library_of_item(ref, item_id: str) -> str:
    """经 Emby ancestors 找条目所属媒体库（Type=CollectionFolder 的祖先 ID）。"""
    try:
        ancestors = emby_gateway.get_json(ref, f"Items/{item_id}/Ancestors")
    except GatewayError as error:
        logger.warning(f"[EmbyCoverCenter] 读取条目层级失败 {item_id}：{error}")
        return ""
    for ancestor in ancestors or []:
        if isinstance(ancestor, dict) and str(ancestor.get("Type") or "") == "CollectionFolder":
            return str(ancestor.get("Id") or "")
    return ""


def handle_webhook(plugin, event) -> None:
    """宿主 WebhookMessage 事件入口：Emby 入库 → 刷新对应媒体库封面。

    防御式解析 event_data（字段名随宿主版本演进），只认事件名含 new / add 的
    入库事件；条目经 ancestors 定位到媒体库且在自动封面选择集内才刷新；同一
    (服务器, 媒体库) 在防抖窗口内只触发一次；auto_refresh_on_webhook 门控。
    """
    config = getattr(plugin, "config", None) or {}
    if not plugin.get_state() or not config.get("auto_refresh_on_webhook"):
        return
    data = getattr(event, "event_data", None)
    if not isinstance(data, dict):
        return
    event_name = str(
        data.get("event")
        or data.get("Event")
        or data.get("notification_type")
        or data.get("NotificationType")
        or ""
    ).lower()
    if not any(token in event_name for token in ("new", "add")):
        return
    # 条目 ID：Item.Id / item.id / ItemId / item_id / id
    item = data.get("Item") or data.get("item") or {}
    item_id = ""
    if isinstance(item, dict):
        item_id = str(item.get("Id") or item.get("id") or "")
    if not item_id:
        item_id = str(data.get("ItemId") or data.get("item_id") or data.get("id") or "")
    if not item_id:
        return
    # 服务器名：Server.Name / ServerName / server；目标只有一台时兜底采用它
    server_info = data.get("Server")
    server = ""
    if isinstance(server_info, dict):
        server = str(server_info.get("Name") or server_info.get("name") or "")
    if not server:
        server = str(data.get("ServerName") or data.get("server_name") or data.get("server") or "")
    mapping = config.get("auto_cover_libraries")
    if not isinstance(mapping, dict) or not mapping:
        return
    if server not in mapping:
        if not server and len(mapping) == 1:
            server = next(iter(mapping))
        else:
            return
    allowed_servers = {str(x) for x in (config.get("selected_servers") or [])}
    if allowed_servers and server not in allowed_servers:
        return
    try:
        ref = emby_gateway.resolve(server)
    except GatewayError as error:
        logger.warning(f"[EmbyCoverCenter] 入库刷新解析服务器失败 {server}：{error}")
        return
    library_id = _library_of_item(ref, item_id)
    wanted = {str(x).strip() for x in (mapping.get(server) or []) if str(x).strip()}
    if not library_id or library_id not in wanted:
        return
    now = time.monotonic()
    key = (server, library_id)
    last = _WEBHOOK_LAST.get(key)
    if last is not None and now - last < WEBHOOK_DEBOUNCE_SECONDS:
        logger.debug(f"[EmbyCoverCenter] 入库刷新防抖跳过：{server} / {library_id}")
        return
    _WEBHOOK_LAST[key] = now
    # 顺手清掉早已过期的防抖记录，避免长期驻留膨胀
    for stale in [k for k, ts in _WEBHOOK_LAST.items() if now - ts > WEBHOOK_DEBOUNCE_SECONDS * 2]:
        _WEBHOOK_LAST.pop(stale, None)
    # 网络与渲染放后台线程，不能阻塞宿主事件分发
    threading.Thread(
        target=_refresh_one_quietly,
        args=(plugin, ref, server, library_id),
        name="embycovercenter-webhook-refresh",
        daemon=True,
    ).start()


def _refresh_one_quietly(plugin, ref, server: str, library_id: str) -> None:
    """入库触发的单库刷新（后台线程）：失败只记日志并按通知设置告知。"""
    config = getattr(plugin, "config", None) or {}
    name = str(getattr(plugin, "plugin_name", "") or "胖虎封面中心")
    try:
        library_name = ""
        for library in emby_assets.list_libraries(ref):
            if isinstance(library, dict) and str(library.get("id")) == library_id:
                library_name = str(library.get("name") or library_id)
                break
        if not library_name:
            logger.info(f"[EmbyCoverCenter] 入库刷新跳过：媒体库 {library_id} 已不存在")
            return
        layout, style = resolve_design(plugin, config)
        refresh_library(
            plugin,
            {"server": server, "ref": ref, "library_id": library_id, "name": library_name},
            layout,
            style,
            config,
        )
        logger.info(f"[EmbyCoverCenter] 入库自动刷新完成：{server} / {library_name}")
        if config.get("notify_on_task_finish"):
            _post_message(plugin, f"{name} · 入库自动刷新", f"✅ {server} / {library_name} 封面已更新")
    except (GatewayError, ValueError, OSError) as error:
        logger.warning(f"[EmbyCoverCenter] 入库自动刷新失败 {server} / {library_id}：{error}")
        if config.get("notify_on_task_finish"):
            _post_message(plugin, f"{name} · 入库自动刷新", f"❌ {server} / {library_id}：{error}")
