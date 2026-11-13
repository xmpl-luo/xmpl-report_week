from .summarizer import CATEGORIES, validate
from common.periods import title_for


def render(start, end, entries, coverage):
    title = title_for(start, end)
    lines = [f"# {title}", "", f"统计区间：{start:%Y%m%d}-{end:%Y%m%d}", "",
             "按文章首次发布日期归档；时间戳换算为北京时间。", ""]
    if start.weekday() != 0:
        lines += ["本期为指定历史区间（周日至周六），周编号按结束日所在 ISO 周计算。", ""]
    count = 0
    for category in CATEGORIES:
        selected = [e for e in entries if e["category"] == category]
        if not selected:
            continue
        lines += [f"## {category}", ""]
        for entry in selected:
            validate(entry)
            count += 1
            clean = lambda text: " ".join(text.splitlines()).strip()
            lines += [f"### {count}、{clean(entry['title'])}", ""]
            lines += [f"{i}. {clean(point)}\n" for i, point in enumerate(entry["points"], 1)]
            lines += [f"来源：{entry['source']}｜发布日期：{entry['published']}", "", entry["url"], ""]
    if not count:
        raise ValueError("没有可核实条目，拒绝生成空白简报")
    lines += ["## 采集说明", "", *[f"- {text}" for text in coverage], ""]
    return "\n".join(lines)

