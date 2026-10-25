"""SubscribeCenter API 路由声明与响应控制层。

约定（对齐本仓库既有插件与 V3 API 响应适配指南）：

- 路径前缀由宿主补全为 ``/api/v1/plugin/SubscribeCenter``，这里只写**裸路径**；
- 每个路由显式声明 ``response_model = schemas.Response[业务模型]``；
- 插件路由**不进入**宿主统一响应包装，因此必须自己声明一致的模型；
- 可预期业务失败返回 HTTP 400 + 友好 detail；未预期异常记日志后返回 500。
"""
from __future__ import annotations

from typing import Any, Dict, List

from app import schemas
from app.sdk.logging import logger
from fastapi import HTTPException, Response

from . import schemas as api_schemas


def _response_model(path: str):
    """返回指定路由的 V3 响应模型。"""
    return schemas.Response[api_schemas.API_RESPONSE_MODELS[path]]


def get_api(plugin) -> List[Dict[str, Any]]:
    """返回 MoviePilot V3 插件 API 路由声明。"""
    definitions = [
        ("/status", plugin.api_status, ["GET"], "获取插件运行状态与各源情况"),
        ("/history", plugin.api_history, ["GET"], "分页查询发现/写入流水"),
        ("/history/clear", plugin.api_history_clear, ["POST"], "清空发现流水"),
        (
            "/history/subscribe",
            plugin.api_history_subscribe,
            ["POST"],
            "从发现流水手动补订阅（重新订阅 / 加入订阅）",
        ),
        ("/calendar", plugin.api_calendar, ["GET"], "日历：整月视图"),
        ("/calendar/day", plugin.api_calendar_day, ["GET"], "日历：单日视图（默认今天）"),
        ("/auto_toggle", plugin.api_auto_toggle, ["GET"], "预览按播出日自动启停的判定"),
        (
            "/auto_toggle/apply",
            plugin.api_auto_toggle_apply,
            ["POST"],
            "立刻执行一次按播出日自动启停",
        ),
        ("/blacklist", plugin.api_blacklist, ["GET"], "读取排除规则（类型/题材）"),
        (
            "/blacklist/test",
            plugin.api_blacklist_test,
            ["POST"],
            "自测一条内容会不会被排除规则拦下",
        ),
        (
            "/blacklist/audit",
            plugin.api_blacklist_audit,
            ["POST"],
            "按排除规则体检已有订阅（后台跑，只读）",
        ),
        (
            "/blacklist/audit/result",
            plugin.api_blacklist_audit_result,
            ["GET"],
            "读取体检进度与结果",
        ),
        (
            "/blacklist/sweep",
            plugin.api_blacklist_sweep,
            ["POST"],
            "把体检选中的订阅批量暂停 / 恢复",
        ),
        ("/card_theme", plugin.api_card_theme, ["GET"], "读取订阅卡片配色"),
        ("/card_theme/save", plugin.api_card_theme_save, ["POST"], "保存订阅卡片配色"),
        ("/run_once", plugin.api_run_once, ["POST"], "启动一次发现任务（后台跑）"),
        (
            "/run_once/result",
            plugin.api_run_once_result,
            ["GET"],
            "读取发现任务的进度与结果",
        ),
        ("/preview", plugin.api_preview, ["POST"], "启动只读预览（后台跑，不写入）"),
        (
            "/preview/result",
            plugin.api_preview_result,
            ["GET"],
            "读取预览的进度与结果",
        ),
        ("/system_share", plugin.api_system_share, ["GET"], "读取订阅数据共享开关"),
        ("/system_share/save", plugin.api_system_share_save, ["POST"], "设置订阅数据共享开关"),
        ("/mapping_cache", plugin.api_mapping_cache, ["GET"], "查看身份映射缓存"),
        ("/mapping_cache/fix", plugin.api_mapping_fix, ["POST"], "人工修正一条身份映射"),
        ("/poster", plugin.api_poster, ["GET"], "代理 TMDB 海报图片（浏览器不可直连）"),
    ]
    return [
        {
            "path": path,
            "endpoint": endpoint,
            "methods": methods,
            "auth": "bear",
            "summary": summary,
            # /poster 直接返回图片字节，不能套 JSON envelope 模型
            "response_model": None if path == "/poster" else _response_model(path),
            # **只有 /poster 允许匿名**：<img> 标签发起的请求不会携带 Bearer token，
            # 走 auth 必然 401（真机 F12：/poster?... -> 401 Unauthorized）。
            # 安全性可接受：该路由只代理 TMDB 海报，且 _poster_path 会拒绝非
            # TMDB 域名的地址，不会被当成任意 URL 代理。
            "allow_anonymous": path == "/poster",
        }
        for path, endpoint, methods, summary in definitions
    ]


# --------------------------------------------------------------------- 端点实现


def _payload(request: Any, model: Any) -> Any:
    """把请求体归一成 pydantic 模型。

    FastAPI 是按**端点函数的类型注解**决定要不要解析 JSON body 的：注解写成
    ``Any`` 时，整个 body 会原样以 ``dict`` 传进来 —— ``request.title`` 立刻
    AttributeError，前端看到的就是 500（真机 1.14.0：「自测」报「黑名单自测失败」）。
    这里兜一层：无论注解写没写对、body 是模型还是 dict，都能拿到模型。
    """
    if isinstance(request, model):
        return request
    if isinstance(request, dict):
        return model(**request)
    if request is None:
        try:
            return model()
        except Exception as err:  # noqa: BLE001 - 必填字段缺失就是 400
            raise HTTPException(status_code=400, detail="缺少请求体") from err
    return request


async def api_status(plugin) -> Any:
    """返回插件运行状态。"""
    try:
        return schemas.Response(success=True, data=plugin.status_snapshot())
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 获取状态失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取插件状态失败") from err


async def api_history(
    plugin,
    page: int = 1,
    count: int = 20,
    decision: str = "",
    source: str = "",
    keyword: str = "",
) -> Any:
    """分页返回发现/写入流水。"""
    try:
        data = plugin.history_page(
            page=page,
            count=count,
            decision=decision,
            source=source,
            keyword=keyword,
        )
        return schemas.Response(success=True, data=data)
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 查询流水失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询流水失败") from err


async def api_history_clear(plugin) -> Any:
    """清空发现流水。

    清空之后「流水记录过就不再自动重订」这条规则会一起失效 —— 之前订过、
    后来被用户删掉的订阅，下一轮发现会重新订回来。这是刻意设计的解锁方式。
    """
    try:
        return schemas.Response(success=True, data=plugin.clear_history())
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 清空流水失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="清空流水失败") from err


async def api_history_subscribe(plugin, request: api_schemas.HistorySubscribeRequest) -> Any:
    """从发现流水手动补订阅（「重新订阅 / 加入订阅」按钮）。

    和每日自动发现走同一套写入口，但**故意绕开**窗口/评分/日限额/流水去重：
    用户点名要订的东西不该被插件的门槛拦住。订阅已存在时只回报状态，不改状态。
    """
    try:
        payload = _payload(request, api_schemas.HistorySubscribeRequest)
        result = await plugin.subscribe_from_history(key=payload.key)
        return schemas.Response(success=True, data=result)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except RuntimeError as err:
        logger.warning(f"[SubscribeCenter] 手动补订阅失败：{err}")
        raise HTTPException(status_code=500, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 手动补订阅异常：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="手动补订阅失败") from err


async def api_poster(plugin, path: str = "") -> Any:
    """代理 TMDB 海报。

    ``path`` 是 TMDB 返回的 ``poster_path``（形如 ``/abc.jpg``）。
    走插件后端抓取，浏览器只连 MoviePilot —— 否则国内网络下
    ``image.tmdb.org`` 往往连不上，流水封面会整片空白。
    """
    try:
        payload = await plugin.poster_bytes(path)
    except Exception as err:  # noqa: BLE001
        logger.warning(f"[SubscribeCenter] 抓取海报失败：{err}")
        payload = None
    if not payload:
        raise HTTPException(status_code=404, detail="海报不存在")
    content, content_type = payload
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


async def api_preview(plugin) -> Any:
    """只读预览（后台跑，立即返回）。

    真机：预览要跑完整流水线（拉四源 + 逐条解析），网关等不到就断成
    HTTP 502。改成本接口只「启动」，前端轮询 ``GET /preview/result``。
    与 ``/run_once`` 共用同一把互斥锁，但**不消耗每日写入额度**。
    """
    try:
        result = plugin.start_preview()
        return schemas.Response(success=True, data=api_schemas.TaskState(**result))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 启动预览失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="启动预览失败") from err


async def api_preview_result(plugin) -> Any:
    """读取预览进度 / 结果（跑完才有 ``result``）。"""
    try:
        result = plugin.preview_state()
        return schemas.Response(success=True, data=api_schemas.TaskState(**result))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 读取预览状态失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="读取预览状态失败") from err


async def api_mapping_cache(plugin) -> Any:
    """返回映射缓存内容。"""
    try:
        return schemas.Response(success=True, data=plugin.mapping_cache_view())
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 读取映射缓存失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="读取映射缓存失败") from err


async def api_mapping_fix(plugin, request: api_schemas.MappingFixRequest) -> Any:
    """人工修正一条身份映射。"""
    try:
        key = request.key
        if not key and request.title:
            # 前端只让用户填 TMDB ID；键由后端按「归一化标题 + 年份 + 类型」生成，
            # 与身份解析用的键完全一致，所以下一次运行必定命中。
            from ..core.identity import normalize_title, strip_season_suffix, title_key

            key = title_key(
                normalize_title(strip_season_suffix(request.title)),
                request.year,
                request.media_type or "tv",
            )
        data = plugin.mapping_fix(
            key=key,
            media_source=request.media_source,
            media_id=request.media_id,
        )
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 修正映射失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="修正映射失败") from err
    if not data.get("success"):
        raise HTTPException(status_code=400, detail="媒体身份非法，未写入映射")
    return schemas.Response(success=True, data=data)


__all__ = [
    "api_history",
    "api_history_clear",
    "api_history_subscribe",
    "api_blacklist_audit",
    "api_blacklist_audit_result",
    "api_blacklist_sweep",
    "api_mapping_cache",
    "api_preview",
    "api_preview_result",
    "api_mapping_fix",
    "api_run_once",
    "api_run_once_result",
    "api_status",
    "get_api",
]


async def api_calendar_day(plugin, date: str = "") -> Any:
    """单日日历（默认今天）：给「今天」列表视图用。"""
    try:
        data = await plugin.calendar_today(date_text=date)
        return schemas.Response(success=True, data=api_schemas.CalendarView(**data))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 读取单日日历失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="读取单日日历失败") from err


async def api_calendar(plugin, month: str = "") -> Any:
    """日历（整月）：``month=YYYY-MM``，留空=本月。

    .. note::
       这里**只返回一种模型**（CalendarMonth）。之前同一路径既能返回单日
       又能返回整月，宿主按 ``API_RESPONSE_MODELS`` 校验时对不上，前端只拿到
       「未知错误」，月历全是空格子。
    """
    try:
        data = await plugin.calendar_month(month_text=month)
        return schemas.Response(success=True, data=api_schemas.CalendarMonth(**data))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 读取日历失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="读取日历失败") from err


async def api_auto_toggle(plugin) -> Any:
    """预览「按播出日自动启停」：算出今天该启用/暂停哪些订阅，**不写库**。

    用户点「执行」前必须先能看到这份清单 —— 这个功能会改订阅状态，
    不该是"点了才知道"。
    """
    try:
        data = await plugin.auto_toggle_plan()
        return schemas.Response(success=True, data=api_schemas.AutoToggleView(**data))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 计算自动启停计划失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="计算自动启停计划失败") from err


async def api_auto_toggle_apply(plugin) -> Any:
    """在后台跑一次自动启停（会写订阅状态），立刻返回。

    .. note::
       真正的执行要串行核对媒体库，几分钟起步 —— 放在 HTTP 请求里会被网关
       502 掐断（真机踩过）。所以这里只挂后台线程，前端轮询 ``/auto_toggle``
       的 ``last_run.running`` 看进度。
    """
    try:
        result = await plugin.auto_toggle_apply()
    except RuntimeError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 执行自动启停失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="执行自动启停失败") from err
    return schemas.Response(success=True, data=api_schemas.AutoToggleStart(**result))


async def api_blacklist(plugin) -> Any:
    """读取排除规则元数据（内置题材预设 + TMDB 类型名）。"""
    try:
        data = plugin.blacklist_meta()
        return schemas.Response(success=True, data=api_schemas.BlacklistMeta(**data))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 读取排除规则失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="读取排除规则失败") from err


async def api_blacklist_test(plugin, request: api_schemas.BlacklistTestRequest) -> Any:
    """自测：给一段片名/题材串，立刻返回会不会被拦下、命中哪条规则。

    这个接口的意义：黑名单是「静默生效」的规则，用户配完必须能当场验证
    —— 否则第一次发现某个题材没订上，根本不知道是被谁拦的。
    """
    try:
        payload = _payload(request, api_schemas.BlacklistTestRequest)
        data = plugin.blacklist_test(
            title=payload.title,
            original_title=payload.original_title,
            media_type=payload.media_type,
            tags=payload.tags,
            genre_ids=payload.genre_ids,
            keywords=payload.keywords,
            rules_config=payload.rules,
        )
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 黑名单自测失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="黑名单自测失败") from err
    return schemas.Response(success=True, data=api_schemas.BlacklistTestResult(**data))


async def api_blacklist_audit(plugin) -> Any:
    """启动「已有订阅体检」（后台跑，立刻返回状态）。

    为什么又用后台任务：体检要给每条订阅查一次 TMDB 详情，200 条订阅就是
    200 次请求 —— 在一次 HTTP 请求里同步跑一定被网关掐成 502（1.14.3 的教训）。
    """
    try:
        data = plugin.start_blacklist_audit()
        return schemas.Response(success=True, data=api_schemas.TaskState(**data))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 启动体检失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="启动体检失败") from err


async def api_blacklist_audit_result(plugin) -> Any:
    """读体检进度 / 结果（``result`` 是 ``BlacklistAuditView`` 的结构）。"""
    try:
        data = plugin.blacklist_audit_state()
        return schemas.Response(success=True, data=api_schemas.TaskState(**data))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 读取体检结果失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="读取体检结果失败") from err


async def api_blacklist_sweep(
    plugin, request: api_schemas.BlacklistSweepRequest
) -> Any:
    """把体检选中的订阅批量暂停 / 恢复。

    只改状态不删订阅：删订阅会进订阅历史且不可逆，「暂停」随时能改回来。
    """
    try:
        payload = _payload(request, api_schemas.BlacklistSweepRequest)
        data = await plugin.blacklist_sweep(ids=payload.ids, action=payload.action)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 批量暂停失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="批量暂停失败") from err
    return schemas.Response(
        success=True, data=api_schemas.BlacklistSweepResult(**data)
    )


async def api_card_theme(plugin) -> Any:
    """读取订阅卡片配色。"""
    return schemas.Response(success=True, data=api_schemas.CardTheme(**plugin.card_theme_config()))


async def api_card_theme_save(plugin, request: api_schemas.CardThemeRequest) -> Any:
    """保存订阅卡片配色并写入宿主自定义 CSS。"""
    colors = None if request.reset else (request.colors or None)
    data = await plugin.apply_card_theme(colors=colors)
    return schemas.Response(
        success=bool(data.get("success")),
        message=str(data.get("error") or ""),
        data=api_schemas.CardThemeResult(
            success=bool(data.get("success")), error=str(data.get("error") or "")
        ),
    )


async def api_run_once(plugin, source: str = "") -> Any:
    """手动触发一次发现任务（后台跑，立即返回）。

    真机：整条流水线要一两分钟，网关几十秒就断成 HTTP 502。所以这里只
    「启动」并返回任务状态，进度与结果用 ``GET /run_once/result`` 轮询。
    与定时任务共用同一把互斥锁：已有运行在跑时不启动（``started=False``）。
    """
    try:
        result = plugin.start_run_once(source)
        return schemas.Response(success=True, data=api_schemas.TaskState(**result))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 手动运行失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="手动运行失败") from err


async def api_run_once_result(plugin) -> Any:
    """读取「立即运行一次」的进度 / 结果。"""
    try:
        result = plugin.run_once_state()
        return schemas.Response(success=True, data=api_schemas.TaskState(**result))
    except Exception as err:  # noqa: BLE001
        logger.error(f"[SubscribeCenter] 读取运行状态失败：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail="读取运行状态失败") from err


async def api_system_share(plugin) -> Any:
    """读取宿主的「订阅数据共享」开关。"""
    data = await plugin.system_share()
    return schemas.Response(success=True, data=api_schemas.SystemShareState(**data))


async def api_system_share_save(
    plugin, request: api_schemas.SystemShareRequest
) -> Any:
    """设置「订阅数据共享」开关（热门媒体依赖它）。"""
    payload = _payload(request, api_schemas.SystemShareRequest)
    data = await plugin.set_system_share(payload.enabled)
    return schemas.Response(success=True, data=api_schemas.SystemShareState(**data))



