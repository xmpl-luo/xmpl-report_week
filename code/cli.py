"""Run from any working directory: python <project>/code/cli.py --help."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from collection.collector import collect
from common.periods import parse_date, periods, previous_week, title_for
from common.settings import ROOT, RUNTIME, load_env, read_json, write_json
from generation.render import render
from generation.summarizer import summarize, validate


def main(argv=None):
    load_env()
    parser = argparse.ArgumentParser(description="游戏产品设计周报：采集、生成、云文档及推送独立运行")
    parser.add_argument("action", choices=["doctor", "collect", "generate", "run", "sync-wiki", "push-bot"])
    parser.add_argument("--start", help="YYYYMMDD，默认上一周周一")
    parser.add_argument("--end", help="YYYYMMDD，默认上一周周日")
    parser.add_argument("--sources", help="逗号分隔来源ID")
    parser.add_argument("--max-pages", type=int, default=180)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--curated", type=Path, help="人工核实摘要JSON文件")
    parser.add_argument("--file", type=Path, help="需要同步或发送的Markdown文件")
    args = parser.parse_args(argv)
    if args.action == "doctor":
        print(json.dumps({"project": str(ROOT), "python":sys.version.split()[0], "configuration":{
            key: "已配置（********）" if os.getenv(key) else "未配置" for key in (
                "OPENAI_API_KEY", "OPENAI_MODEL", "LARK_APP_ID", "LARK_APP_SECRET", "LARK_WEBHOOK_URL")}}, ensure_ascii=False, indent=2))
        return
    if args.action in ("sync-wiki", "push-bot"):
        if not args.file or not args.file.is_file():
            parser.error("需要 --file 指向已生成的Markdown文件")
        from publishing.lark import Lark, send_webhook
        if args.action == "sync-wiki":
            result = Lark().sync(args.file)
            print("云文档同步完成，节点：" + result["node_token"])
        else:
            send_webhook(args.file)
            print("机器人发送完成")
        return
    if bool(args.start) != bool(args.end):
        parser.error("--start 与 --end 必须同时指定")
    start, end = (parse_date(args.start), parse_date(args.end)) if args.start else previous_week()
    windows = list(periods(start, end))
    if args.max_pages < 1:
        parser.error("--max-pages 必须大于0")
    selected = args.sources.split(",") if args.sources else None
    bundle_path = RUNTIME / "collection" / f"{start:%Y%m%d}-{end:%Y%m%d}.json"
    if args.action in ("collect", "run"):
        articles, audit = collect(start, end, selected=selected, max_pages=args.max_pages, refresh=args.refresh)
        write_json(bundle_path, {"start":str(start), "end":str(end), "articles":articles, "audit":audit})
        print(f"采集完成：{len(articles)}篇；审计记录：{bundle_path}")
    if args.action == "collect":
        return
    if args.curated:
        curated = read_json(args.curated)
        if not isinstance(curated, dict) or "entries" not in curated or not curated.get("coverage"):
            raise ValueError("人工摘要JSON必须包含 entries 与 coverage")
        entries = curated["entries"]
        coverage = curated["coverage"]
    else:
        bundle = read_json(bundle_path)
        if not bundle:
            raise ValueError("尚未采集，请先 collect 或使用 --curated")
        entries = []
        summary_cache = RUNTIME / "summaries"
        import hashlib
        for article in bundle["articles"]:
            fingerprint = hashlib.sha256(json.dumps(article, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            cache = summary_cache / (fingerprint + ".json")
            saved = read_json(cache)
            entry = saved["entry"] if saved is not None else summarize(article)
            write_json(cache, {"entry":entry})
            if entry:
                entries.append(entry)
        coverage = [f"{r['source']}：采集{r['included']}篇；状态{r['status']}，不表示完整覆盖。" for r in bundle["audit"]]
    seen = set()
    for entry in entries:
        validate(entry)
        if urlsplit(entry.get("url", "")).scheme != "https" or not entry.get("source"):
            raise ValueError("摘要缺少HTTPS原文链接或来源")
        day = parse_date(entry["published"])
        if not start <= day <= end:
            raise ValueError("人工摘要中存在区间外的发布日期")
        if entry["url"] in seen:
            raise ValueError("摘要存在重复链接")
        seen.add(entry["url"])
    # Render every period before writing any output: do not quietly publish empty weeks.
    rendered = []
    for first, last in windows:
        matching = sorted([e for e in entries if first <= parse_date(e["published"]) <= last], key=lambda e:(e["published"],e["url"]))
        text = render(first, last, matching, coverage)
        path = ROOT / "report_add/week" / (title_for(first, last) + ".md")
        if path.exists() and path.read_text(encoding="utf-8") != text:
            raise ValueError(f"已有不同内容的同名简报，拒绝覆盖：{path.name}")
        rendered.append((path, text))
    for path, text in rendered:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".md.tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
        print(f"已生成：{path}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(f"执行失败：{error}", file=sys.stderr)
        sys.exit(1)

