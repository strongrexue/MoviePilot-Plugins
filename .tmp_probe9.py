"""一次性诊断：0.2.3 的 popularity 门槛会选出哪些条目。

在容器内：docker exec -w /app moviepilot-v3 python /probe9.py
"""
import json
import urllib.parse
from datetime import date, timedelta

from app.testing.bootstrap import prepare_backend

prepare_backend()

from app.runtime.settings import get_runtime_setting  # noqa: E402
from app.sdk.network import RequestUtils  # noqa: E402

KEY = get_runtime_setting("TMDB_API_KEY") or ""
PROXY = get_runtime_setting("PROXY")
REQ = RequestUtils(proxies=PROXY) if PROXY else RequestUtils()

TODAY = date.today()
END = TODAY + timedelta(days=30)
S, E = TODAY.isoformat(), END.isoformat()
COMMON = {"language": "zh-CN", "include_adult": "false"}

MOVIE = "https://api.themoviedb.org/3/discover/movie"
TV = "https://api.themoviedb.org/3/discover/tv"


def fetch(url_base, params):
    """取一页。"""
    full = {**COMMON, **params, "api_key": KEY}
    resp = REQ.get_res(url_base + "?" + urllib.parse.urlencode(full))
    if not resp:
        return []
    data = resp.json() if callable(getattr(resp, "json", None)) else json.loads(resp.text)
    return data.get("results") or []


def collect(url_base, date_params, pages=3):
    """按插件当前策略收集候选（popularity.desc + 日期升序）。"""
    seen = {}
    for sort_by in ("popularity.desc", "primary_release_date.asc" if "movie" in url_base else "first_air_date.asc"):
        for page in range(1, pages + 1):
            for item in fetch(url_base, {**date_params, "sort_by": sort_by, "page": page}):
                d = item.get("release_date") or item.get("first_air_date")
                if not d or not item.get("id"):
                    continue
                seen[item["id"]] = {
                    "title": item.get("title") or item.get("name"),
                    "date": d,
                    "pop": item.get("popularity") or 0,
                    "vote": item.get("vote_average") or 0,
                }
    return seen


all_items = {}
all_items.update(collect(MOVIE, {
    "primary_release_date.gte": S, "primary_release_date.lte": E,
    "with_release_type": "2|3",
}))
all_items.update(collect(TV, {
    "first_air_date.gte": S, "first_air_date.lte": E,
}))

print(f"候选池共 {len(all_items)} 条（插件当前策略实际抓取的范围）")

for threshold in (0, 5, 10, 15, 20):
    hits = [v for v in all_items.values() if v["pop"] >= threshold]
    print(f"  min_popularity={threshold:<3} -> 通过 {len(hits)} 条")

print("\n===== min_popularity=10 会写入的（按关注度降序前 20）=====")
hits = sorted([v for v in all_items.values() if v["pop"] >= 10],
              key=lambda x: -x["pop"])
for v in hits[:20]:
    print("   pop=%-7.1f vote=%-5s %-11s %s" % (v["pop"], v["vote"], v["date"], (v["title"] or "")[:26]))
print(f"\n共 {len(hits)} 条会通过门槛")
