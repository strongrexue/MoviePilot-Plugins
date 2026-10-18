"""离线仿真：新增订阅「首次全站搜索」到底能不能拦住。

用宿主真实代码（D:\\projects\\MoviePilot）+ 真实 SQLite 库跑一遍，不启动完整服务：

场景 1  复现真机：新增订阅 → 宿主入队首搜（source=new、59 秒后到期）
场景 2  只删队列任务够不够（含「N 扫描会不会重新入队」）
场景 3  在入队前拦截（把插件的 first_search_guard 挂到宿主入队方法上）
场景 4  走真实调用方 __post_subscribe_added 验证拦截点在调用链上生效
场景 5  状态 R 之后，宿主的两条周期扫描还会不会立刻搜它
场景 6  异步入队方法（async_queue_new_subscription_search）同样可拦

用法：D:\\projects\\MoviePilot\\.venv\\Scripts\\python.exe tools\\verify\\sim_first_search.py
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST = Path(os.environ.get("MOVIEPILOT_HOME") or r"D:\projects\MoviePilot")
SIM_CONFIG = REPO_ROOT / ".sim" / "config"

# 隔离宿主配置目录：必须在任何 app.* 导入之前设置
if SIM_CONFIG.exists():
    shutil.rmtree(SIM_CONFIG, ignore_errors=True)
SIM_CONFIG.mkdir(parents=True, exist_ok=True)
os.environ["CONFIG_DIR"] = str(SIM_CONFIG)
sys.path.insert(0, str(HOST))

from app.testing.bootstrap import prepare_backend  # noqa: E402

prepare_backend()

from sqlalchemy import delete, select, update  # noqa: E402

from app.application.subscription.query import subscription_search_due  # noqa: E402
from app.chain.subscribe import notify as notify_mod  # noqa: E402
from app.chain.subscribe.context import _SubscribePostCommitContext  # noqa: E402
from app.chain.subscribe.facade import SubscribeChain  # noqa: E402
from app.chain.subscribe.notify import SubscribeNotificationOwner  # noqa: E402
from app.chain.subscribe.search import SubscribeSearchOwner  # noqa: E402
from app.db.adapters.subscriptionsearch import (  # noqa: E402
    TransactionalSubscriptionSearchRepository,
)
from app.db.models.subscribe import Subscribe  # noqa: E402
from app.db.models.subscribeactivity import SubscribeActivity  # noqa: E402
from app.db.models.subscriptionsearch import SubscriptionSearchTask  # noqa: E402
from app.db.session import SessionFactory  # noqa: E402

# 插件自己的实现：直接拿真货来测，而不是另写一份
sys.path.insert(0, str(REPO_ROOT / "plugins.v3"))
from tgmediacenter.modules import first_search_guard as guard  # noqa: E402

QUEUE = TransactionalSubscriptionSearchRepository(SessionFactory)
MANGLE_SYNC = "_SubscribeChain__queue_new_subscription_search"
MANGLE_ASYNC = "_SubscribeChain__async_queue_new_subscription_search"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" —— {detail}" if detail else ""))


def banner(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


def new_subscribe(name: str = "小羊肖恩3：怪兽来袭", state: str = "N") -> int:
    with SessionFactory() as session:
        row = Subscribe(
            name=name,
            year="2026",
            type="电影",
            state=state,
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_search=None,
            search_interval=None,
        )
        session.add(row)
        session.commit()
        return int(row.id)


def state_of(sid: int) -> str:
    with SessionFactory() as session:
        row = session.get(Subscribe, sid)
        return str(row.state) if row is not None else "<missing>"


def tasks_of(sid: int) -> list[SubscriptionSearchTask]:
    with SessionFactory() as session:
        return list(
            session.execute(
                select(SubscriptionSearchTask).where(
                    SubscriptionSearchTask.subscription_id == sid
                )
            ).scalars()
        )


def clear_tasks() -> None:
    with SessionFactory() as session:
        session.execute(delete(SubscriptionSearchTask))
        session.execute(delete(SubscribeActivity))
        session.commit()


def activity_key_of(sid: int):
    with SessionFactory() as session:
        row = session.get(Subscribe, sid)
        return row.activity_key if row is not None else None


def snapshot_of(sid: int):
    with SessionFactory() as session:
        row = session.get(Subscribe, sid)
        if row is None:
            return None
        return types.SimpleNamespace(
            id=row.id,
            state=row.state,
            name=row.name,
            date=row.date,
            last_search=row.last_search,
            search_interval=row.search_interval,
        )


class FakeSubscriptionRepository:
    """宿主 subscription_repository 的最小替身（真实读库，接口够用）。"""

    def get(self, sid: int):
        return snapshot_of(sid)

    def list(self, state: str | None = None):
        wanted = {item for item in str(state or "").split(",") if item}
        with SessionFactory() as session:
            rows = list(session.execute(select(Subscribe)).scalars())
        return [
            types.SimpleNamespace(
                id=row.id,
                state=row.state,
                name=row.name,
                date=row.date,
                last_search=row.last_search,
                search_interval=row.search_interval,
            )
            for row in rows
            if not wanted or row.state in wanted
        ]


class FakeEventManager:
    """广播事件总线替身：只记录，不真正分发。"""

    def __init__(self) -> None:
        self.events: list[tuple[object, dict]] = []

    def send_event(self, event_type, payload=None, priority=None):
        self.events.append((event_type, payload or {}))

    async def async_send_event(self, event_type, payload=None, priority=None):
        self.events.append((event_type, payload or {}))


class FakeMediaInfo:
    """宿主 MediaInfo 替身：__post_subscribe_added 只用到 to_dict()。"""

    type = types.SimpleNamespace(value="电影")
    music_type = None
    vote_average = 0.0
    overview = ""
    title = "小羊肖恩3：怪兽来袭"
    year = "2026"

    def to_dict(self) -> dict:
        return {"title": self.title, "year": self.year}

    def get_poster_image(self):
        return None

    def get_backdrop_image(self):
        return None


def make_chain() -> SubscribeChain:
    """绕过 __init__ 造一个真实 SubscribeChain 实例，只接上队列与订阅仓库。"""
    chain = object.__new__(SubscribeChain)
    chain.subscription_search_repository = QUEUE
    chain.subscription_repository = FakeSubscriptionRepository()
    chain.eventmanager = FakeEventManager()
    return chain


def post_commit_context() -> _SubscribePostCommitContext:
    return _SubscribePostCommitContext(
        title="小羊肖恩3：怪兽来袭",
        year="2026",
        metainfo=None,  # 上报统计被替身接管，用不到
        mediainfo=FakeMediaInfo(),
        media_source=None,
        media_id=None,
        season=None,
        channel=None,
        source="仿真",
        userid=None,
        username=None,
        message=False,
        notification=None,
    )


PLUGIN_STUB = types.SimpleNamespace(
    config={"enabled": True, "skip_first_search_enabled": True}
)


def install_guard() -> bool:
    """用插件真实实现（first_search_guard.install）把守卫挂到宿主入队方法上。"""
    return guard.install(PLUGIN_STUB)


def uninstall_guard() -> None:
    """插件真实实现的还原入口（stop_service 里就是这么调的）。"""
    guard.uninstall()


# --------------------------------------------------------------------------
banner("0. 拦截点是否真的在调用链上")
print(f"宿主代码目录            ：{HOST}")
print(f"SubscribeChain 的 MRO   ：")
for klass in SubscribeChain.__mro__:
    print(f"    {klass.__module__}.{klass.__name__}")
resolved = getattr(SubscribeChain, MANGLE_SYNC)
print(f"\nchain 上解析到的入队方法：{resolved.__qualname__}")
check(
    "入队方法来自 SubscribeSearchOwner（可直接在混合类上打补丁）",
    resolved.__qualname__.startswith("SubscribeSearchOwner."),
    resolved.__qualname__,
)
check(
    "名字没有被 Python 改名隐藏（单下划线开头不参与 mangling）",
    MANGLE_SYNC in SubscribeSearchOwner.__dict__,
)
check(
    "守卫模块记录的入队方法名与宿主一致",
    guard.MANGLE_SYNC == MANGLE_SYNC and guard.MANGLE_ASYNC == MANGLE_ASYNC,
)

# --------------------------------------------------------------------------
banner("1. 复现真机：新增订阅 → 宿主立刻入队首搜")
clear_tasks()
sid = new_subscribe()
chain = make_chain()
chain._SubscribeChain__queue_new_subscription_search(sid)
rows = tasks_of(sid)
for row in rows:
    print(
        f"  任务：source={row.source} state={row.state} phase={row.phase} "
        f"priority={row.priority} available_at={row.available_at}"
    )
check("宿主入队了 1 条 source=new 的任务", len(rows) == 1 and rows[0].source == "new")
retry_at = rows[0].available_at if rows else ""
if retry_at:
    due = datetime.fromisoformat(retry_at)
    print(f"  距现在：{(due - datetime.now(timezone.utc)).total_seconds():.0f} 秒")
check(
    "任务被推迟到约 60 秒后（新订阅编辑期）",
    retry_at != "" and datetime.fromisoformat(retry_at) > datetime.now(timezone.utc),
)
print(f"  订阅状态：{state_of(sid)}（宿主：N=新建，R=订阅中，S=暂停）")

# --------------------------------------------------------------------------
banner("2. 只删队列任务够不够")
# 2a 到期后 worker 认领得到 —— 这一行就是 16:28 那次搜索的「调度」
with SessionFactory() as session:
    session.execute(
        update(SubscriptionSearchTask).values(
            available_at=(datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(
                timespec="seconds"
            )
        )
    )
    session.commit()
claimed = QUEUE.claim_next(owner="sim-worker")
check("到期后 worker 确实能认领到它（这就是 16:28 那次搜索）", claimed is not None)

# 2b 全新任务，不入队则已删 —— worker 认领不到
clear_tasks()
sid_del = new_subscribe("只删队列_未认领")
chain._SubscribeChain__queue_new_subscription_search(sid_del)
check("未删前队列里有它", len(tasks_of(sid_del)) == 1)
with SessionFactory() as session:
    removed = session.execute(
        delete(SubscriptionSearchTask).where(
            SubscriptionSearchTask.subscription_id == sid_del
        )
    ).rowcount
    session.commit()
print(f"  已删除任务行：{removed}")
check("删掉任务行后 worker 再也认领不到", QUEUE.claim_next(owner="sim-worker") is None)
check("队列里确实空了", tasks_of(sid_del) == [])

# 2c 但入队时写下的「已安排搜索」活动记录不会跟着消失（界面上会留一条孤儿记录）
with SessionFactory() as session:
    activity_rows = list(
        session.execute(
            select(SubscribeActivity).where(SubscribeActivity.activity_key == activity_key_of(sid_del))
        ).scalars()
    )
print(f"  该订阅残留的订阅活动记录：{[row.kind for row in activity_rows]}")
check(
    "删任务不会回收已写入的「已安排搜索」活动记录（界面留痕）",
    len(activity_rows) >= 1,
)

# 状态还是 N 时，宿主「新增订阅搜索」任务（每 5 分钟）会重新入队
pending_n = chain._load_search_subscriptions(sid=None, sids=None, state=None)
print(f"  状态 N 的订阅被 N 扫描捞到：{[item.id for item in pending_n]}")
check(
    "状态仍是 N 时，5 分钟一次的 N 扫描会重新捞出它（只删任务不够）",
    any(item.id == sid for item in pending_n),
)

# --------------------------------------------------------------------------
banner("3. 在入队前拦截（guard 挂在宿主入队方法上）")
original_sync = getattr(SubscribeSearchOwner, MANGLE_SYNC)
check("插件 install() 返回 True（接管成功）", install_guard() is True)
check("守卫模块报告已接管", guard.installed() is True)
clear_tasks()
sid_blocked = new_subscribe()
chain._SubscribeChain__queue_new_subscription_search(sid_blocked)
print(f"  状态：{state_of(sid_blocked)}；任务数：{len(tasks_of(sid_blocked))}")
check("没有入队任何任务", tasks_of(sid_blocked) == [])
check("订阅状态被推进到 R", state_of(sid_blocked) == "R")

# 幂等：再调一次不该出问题
chain._SubscribeChain__queue_new_subscription_search(sid_blocked)
check("重复调用仍然不入队", tasks_of(sid_blocked) == [])

# --------------------------------------------------------------------------
banner("4. 走真实调用方 __post_subscribe_added（和宿主入队同一条路径）")
notify_original_port = notify_mod._subscription_share_snapshot
notify_original_payload = getattr(SubscribeNotificationOwner, "_SubscribeChain__subscribe_report_payload")
notify_mod._subscription_share_snapshot = lambda: types.SimpleNamespace(
    report_added=lambda payload: True,
    async_report_added=None,
    list_shares=lambda: [],
    report_completed=lambda payload: True,
)
setattr(
    SubscribeNotificationOwner,
    "_SubscribeChain__subscribe_report_payload",
    staticmethod(lambda ctx: {}),
)
try:
    # 4a 未安装守卫：宿主原样入队
    uninstall_guard()
    clear_tasks()
    sid_real_blocked = new_subscribe()
    chain4 = make_chain()
    chain4._SubscribeChain__post_subscribe_added(sid_real_blocked, post_commit_context())
    print(f"  未装守卫：任务数={len(tasks_of(sid_real_blocked))} 状态={state_of(sid_real_blocked)}")
    check(
        "未装守卫时保持宿主原行为（入队首搜）",
        len(tasks_of(sid_real_blocked)) == 1,
    )

    # 4b 安装守卫：同一条调用链不再入队，且事件照发
    install_guard()
    clear_tasks()
    sid_real = new_subscribe()
    chain4 = make_chain()
    chain4._SubscribeChain__post_subscribe_added(sid_real, post_commit_context())
    print(
        f"  装守卫：任务数={len(tasks_of(sid_real))} 状态={state_of(sid_real)} "
        f"已发事件={len(chain4.eventmanager.events)}"
    )
    check("装守卫后不再入队", tasks_of(sid_real) == [])
    check("订阅状态 R", state_of(sid_real) == "R")
    check("SubscribeAdded 广播事件仍然照发（其它插件不受影响）", len(chain4.eventmanager.events) == 1)
finally:
    notify_mod._subscription_share_snapshot = notify_original_port
    setattr(
        SubscribeNotificationOwner,
        "_SubscribeChain__subscribe_report_payload",
        notify_original_payload,
    )

# --------------------------------------------------------------------------
banner("5. 状态 R 之后，宿主的两条周期扫描会不会立刻搜它")
chain5 = make_chain()
idle = chain5._load_search_subscriptions(sid=None, sids=None, state=None)
print(f"  N 扫描捞到：{[item.id for item in idle]}")
check("N 扫描（每 5 分钟）不再捞走它", all(item.id != sid_real for item in idle))

snap = snapshot_of(sid_real)
due_now = subscription_search_due(snap, 24, datetime.now(timezone.utc))
print(f"  R/P 扫描（每 5 分钟）本轮到期？{due_now}")
check("R/P 扫描按订阅间隔（默认 24h）算到期，不会立刻搜", due_now is False)

with SessionFactory() as session:
    session.execute(
        update(Subscribe)
        .where(Subscribe.id == sid_real)
        .values(last_search=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds"))
    )
    session.commit()
snap2 = snapshot_of(sid_real)
check(
    "间隔到点后 R/P 扫描恢复搜索（说明只是推迟，不是永久屏蔽）",
    subscription_search_due(snap2, 24, datetime.now(timezone.utc)) is True,
)

# --------------------------------------------------------------------------
banner("6. 异步入队方法同样可拦")
async def async_case() -> tuple[int, str]:
    clear_tasks()
    sid_async = new_subscribe()
    await chain5._SubscribeChain__async_queue_new_subscription_search(sid_async)
    return sid_async, state_of(sid_async)


sid_async, async_state = asyncio.run(async_case())
print(f"  任务数={len(tasks_of(sid_async))} 状态={async_state}")
check("异步路径也没有入队", tasks_of(sid_async) == [])
check("异步路径也把状态写成 R", async_state == "R")

uninstall_guard()
check(
    "uninstall() 后宿主方法对象复原（插件停用不留补丁）",
    getattr(SubscribeSearchOwner, MANGLE_SYNC) is original_sync and not guard.installed(),
)

# --------------------------------------------------------------------------
banner("结论")
failed = [item for item in results if not item[1]]
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
print(f"\n共 {len(results)} 项，失败 {len(failed)} 项")

# 先释放 SQLite 连接池再删隔离配置目录（Windows 上文件锁会让 rmtree 静默失败）
try:
    from app.db.engine import peek_sync_engine

    engine = peek_sync_engine()
    if engine is not None:
        engine.dispose()
except Exception:  # pragma: no cover - 清理失败不影响结论
    pass
shutil.rmtree(SIM_CONFIG, ignore_errors=True)
sys.exit(1 if failed else 0)
