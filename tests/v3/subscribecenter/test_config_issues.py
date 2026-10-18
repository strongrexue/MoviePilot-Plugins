"""空转检测：启用但不可能产出内容的源要被自动关闭并给出提示。"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "plugins.v3"))


def _plugin(config: dict):
    """构造一个只带最小运行时状态的插件实例（不碰宿主、不读数据库）。"""
    from subscribecenter import SubscribeCenter

    obj = SubscribeCenter.__new__(SubscribeCenter)
    obj._config = dict(config)
    obj._runtime = {}
    obj._state = lambda: obj._runtime
    obj._save_state = lambda state: obj._runtime.update(state)
    obj.update_config = lambda cfg: obj._runtime.update({"written": dict(cfg)})
    return obj


BASE = {
    "enable_tmdb": False,
    "enable_anilist": False,
    "enable_douban_rss": False,
    "tmdb_future_days": 3,
    "anilist_future_days": 3,
    "douban_rss_sources": "",
}


def test_tmdb_disabled_by_zero_window():
    config = {**BASE, "enable_tmdb": True, "tmdb_future_days": 0}
    issues = _plugin(config)._empty_spectrum_check()
    assert issues and "TMDB" in issues[0]
    assert _plugin(config)._empty_spectrum_check()[0]


def test_anilist_disabled_by_zero_window():
    config = {**BASE, "enable_anilist": True, "anilist_future_days": -1}
    issues = _plugin(config)._empty_spectrum_check()
    assert issues and "AniList" in issues[0]


def test_douban_disabled_without_any_active_source():
    config = {**BASE, "enable_douban_rss": True, "douban_rss_sources": ""}
    issues = _plugin(config)._empty_spectrum_check()
    assert issues and "豆瓣" in issues[0]


def test_healthy_config_reports_no_issue():
    config = {
        **BASE,
        "enable_tmdb": True,
        "enable_anilist": True,
        "tmdb_future_days": 3,
        "anilist_future_days": 3,
    }
    obj = _plugin(config)
    assert obj._empty_spectrum_check() == []
    assert "config_issues" not in obj._runtime


def test_issue_is_persisted_for_frontend_and_config_corrected():
    config = {**BASE, "enable_tmdb": True, "tmdb_future_days": 0}
    obj = _plugin(config)
    obj._empty_spectrum_check()
    assert obj._runtime["config_issues"]
    assert obj._runtime["written"]["enable_tmdb"] is False, "纠正后的配置要写回"
    assert obj._config["enable_tmdb"] is False, "内存里的配置也要同步"
