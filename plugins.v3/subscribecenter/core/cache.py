"""身份映射缓存：``source + source_id`` / ``标题+年份+类型`` → 确定性身份。

存储层通过 :class:`CacheStore` 协议注入，因此本模块可离线单测；
真机上由插件主类用 ``save_data()`` / ``get_data()`` 提供落盘实现
（开发文档 §10：小型可序列化状态走 ``save_data``，不建表）。

.. note::
   只有**可写入的确定性身份**（L1/L2/L3）才允许进缓存；L4 模糊结果永不缓存，
   否则会污染后续运行的判定（开发文档 §6.2）。
"""
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Protocol

from .identity import MappingCache, source_id_key, title_key
from .model import ResolvedIdentity

#: 缓存最多保留的映射条数（超出按插入顺序淘汰最旧的）
MAX_ENTRIES = 2000


class CacheStore(Protocol):
    """缓存持久化能力（由插件主类实现）。"""

    def load(self) -> Any:
        """读取原始缓存载荷（不存在时返回 ``None``）。"""
        ...

    def save(self, payload: Any) -> None:
        """写入原始缓存载荷。"""
        ...


class MappingCacheStore(MappingCache):
    """两级键的映射缓存实现。

    - ``sid:<source>:<source_id>`` —— 来源内身份，最精确
    - ``t:<media_type>:<year>:<normalized_title>`` —— 标题近似，兜底
    """

    def __init__(self, store: Optional[CacheStore] = None) -> None:
        self._store = store
        self._batch_depth = 0
        self._dirty = False
        self._entries: Dict[str, Dict[str, Any]] = {}
        if store is not None:
            self._entries = self._decode(store.load())

    # ------------------------------------------------------------------ 读

    def get_by_source_id(self, source: str, source_id: str) -> Optional[ResolvedIdentity]:
        """按来源内身份查缓存。"""
        return self._to_identity(self._entries.get(source_id_key(source, source_id)))

    def get_by_title(
        self, normalized_title: str, year: Optional[str], media_type: str
    ) -> Optional[ResolvedIdentity]:
        """按标准化标题+年份+类型查缓存。"""
        if not normalized_title:
            return None
        return self._to_identity(
            self._entries.get(title_key(normalized_title, year, media_type))
        )

    def get(self, key: str) -> Optional[ResolvedIdentity]:
        """按原始键查缓存（供 API 展示/修正使用）。"""
        return self._to_identity(self._entries.get(key))

    # ------------------------------------------------------------------ 写

    def remember(self, key: str, identity: ResolvedIdentity) -> None:
        """写入一条映射；不可写入的身份（L4）直接忽略。

        .. note::
           在 `batch()` 上下文里只标脏、不落盘 —— 真机一次运行可解析
           200+ 条，逐条落盘等于 200+ 次数据库写入。
        """
        if not identity.writable:
            return
        self._entries[key] = {
            "media_source": identity.media_source,
            "media_id": identity.media_id,
            "confidence": identity.confidence,
            "reason": identity.reason,
        }
        self._evict()
        self._dirty = True
        if self._batch_depth == 0:
            self._flush()

    def fix(self, key: str, media_source: str, media_id: str) -> bool:
        """人工修正/新增一条映射。

        修正结果按 **L1 确定性身份** 记录（人工确认等价于确定性），
        因此一定会进缓存并被后续运行复用。

        :return: 是否写入成功（身份非法返回 ``False``）
        """
        try:
            identity = ResolvedIdentity(
                media_source=media_source,
                media_id=media_id,
                confidence="L1",
                reason="manual_fix",
            )
        except ValueError:
            return False
        self._entries[key] = {
            "media_source": identity.media_source,
            "media_id": identity.media_id,
            "confidence": identity.confidence,
            "reason": identity.reason,
        }
        self._flush()
        return True

    def forget(self, key: str) -> bool:
        """删除一条映射。"""
        if key not in self._entries:
            return False
        self._entries.pop(key, None)
        self._flush()
        return True

    def clear(self) -> None:
        """清空全部映射。"""
        self._entries = {}
        self._flush()

    # ------------------------------------------------------------------ 视图

    def keys(self) -> List[str]:
        """返回全部缓存键（已排序，便于稳定展示）。"""
        return sorted(self._entries)

    def snapshot(self) -> List[Dict[str, Any]]:
        """返回可回传给前端的映射列表。"""
        result: List[Dict[str, Any]] = []
        for key in self.keys():
            value = self._entries[key]
            result.append({"key": key, **value})
        return result

    @property
    def size(self) -> int:
        """当前缓存条数。"""
        return len(self._entries)

    # ------------------------------------------------------------------ 内部

    @staticmethod
    def _decode(payload: Any) -> Dict[str, Dict[str, Any]]:
        """把持久化载荷解码为内部结构；任何异常都回落到空缓存。"""
        if not isinstance(payload, dict):
            return {}
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            return {}
        result: Dict[str, Dict[str, Any]] = {}
        for key, value in entries.items():
            if isinstance(value, dict) and value.get("media_source") and value.get("media_id"):
                result[str(key)] = value
        return result

    @staticmethod
    def _to_identity(value: Any) -> Optional[ResolvedIdentity]:
        """把缓存值还原为 :class:`ResolvedIdentity`；非法值当作未命中。"""
        if not isinstance(value, dict):
            return None
        try:
            return ResolvedIdentity(
                media_source=str(value.get("media_source") or ""),
                media_id=str(value.get("media_id") or ""),
                confidence=str(value.get("confidence") or "L2"),
                reason=str(value.get("reason") or "cache"),
            )
        except ValueError:
            return None

    def _evict(self) -> None:
        """超出上限时按插入顺序淘汰最旧的条目。"""
        overflow = len(self._entries) - MAX_ENTRIES
        if overflow <= 0:
            return
        for key in list(self._entries)[:overflow]:
            self._entries.pop(key, None)

    @contextmanager
    def batch(self) -> Any:
        """批量写入上下文：期间只标脏，退出时统一落盘一次。"""
        self._batch_depth += 1
        try:
            yield self
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0 and self._dirty:
                self._flush()
                self._dirty = False

    def _flush(self) -> None:
        """落盘；失败不抛（缓存只是加速层，不能影响主流程）。"""
        if self._store is None:
            return
        try:
            self._store.save({"entries": self._entries})
            self._dirty = False
        except Exception:  # noqa: BLE001
            pass


__all__ = ["MAX_ENTRIES", "CacheStore", "MappingCacheStore"]
