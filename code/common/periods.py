from datetime import date, datetime, timedelta, timezone

SHANGHAI = timezone(timedelta(hours=8))


def parse_date(value):
    if isinstance(value, datetime):
        return value.astimezone(SHANGHAI).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(value.replace("-", ""), "%Y%m%d").date()


def previous_week(today=None):
    today = today or datetime.now(SHANGHAI).date()
    end = today - timedelta(days=today.weekday() + 1)
    return end - timedelta(days=6), end


def periods(start, end):
    start, end = parse_date(start), parse_date(end)
    if end < start or ((end - start).days + 1) % 7:
        raise ValueError("日期区间必须为完整的7天倍数，且结束日期不早于开始日期")
    while start <= end:
        yield start, start + timedelta(days=6)
        start += timedelta(days=7)


def title_for(start, end):
    # 常规周一至周日，以及本次特定周日至周六区间，均按结束日的ISO周年编号。
    year, week, _ = end.isocalendar()
    return f"{year}第{week:02d}周简报"

