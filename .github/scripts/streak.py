"""Builds assets/streak.svg from the GitHub contribution calendar.

Runs inside GitHub Actions with the built-in GITHUB_TOKEN, so the profile
streak card no longer depends on an outside service.
"""
import datetime as dt
import json
import os
import urllib.request

USER = os.environ.get("GH_USER", "AnirudhKakarlaML")
TOKEN = os.environ["GITHUB_TOKEN"]
TZ = dt.timezone(dt.timedelta(hours=5, minutes=30))  # India time
OUT = "assets/streak.svg"


def graphql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_days():
    created = graphql(
        "query($u:String!){user(login:$u){createdAt}}", {"u": USER}
    )["user"]["createdAt"]
    start_year = int(created[:4])
    now = dt.datetime.now(dt.timezone.utc)
    days = {}
    q = """query($u:String!,$from:DateTime!,$to:DateTime!){user(login:$u){
      contributionsCollection(from:$from,to:$to){contributionCalendar{
      weeks{contributionDays{date contributionCount}}}}}}"""
    for year in range(start_year, now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = f"{year}-12-31T23:59:59Z" if year < now.year else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        cal = graphql(q, {"u": USER, "from": frm, "to": to})["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return days


def compute(days, today):
    dates = sorted(dt.date.fromisoformat(d) for d in days)
    dates = [d for d in dates if d <= today]
    total = sum(days[d.isoformat()] for d in dates)
    first = next((d for d in dates if days[d.isoformat()] > 0), today)

    # longest streak
    longest, longest_range, run, run_start = 0, (today, today), 0, None
    for d in dates:
        if days[d.isoformat()] > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > longest:
                longest, longest_range = run, (run_start, d)
        else:
            run = 0

    # current streak: today counts if done; if not done yet, start from yesterday
    cur, day = 0, today
    if days.get(day.isoformat(), 0) == 0:
        day -= dt.timedelta(days=1)
    cur_end = day
    while days.get(day.isoformat(), 0) > 0:
        cur += 1
        day -= dt.timedelta(days=1)
    cur_range = (day + dt.timedelta(days=1), cur_end) if cur else (today, today)
    return total, first, cur, cur_range, longest, longest_range


def fmt(d, with_year=False):
    s = d.strftime("%b %-d")
    return s + d.strftime(", %Y") if with_year else s


def rng(a, b, today):
    if a == b:
        return fmt(a, a.year != today.year)
    return f"{fmt(a, a.year != today.year)} - {fmt(b, b.year != today.year)}"


def svg(total, first, cur, cur_range, longest, longest_range, today):
    blue, text, sub, line = "#58a6ff", "#c9d1d9", "#8b949e", "#30363d"
    cur_txt = rng(*cur_range, today) if cur else "Start today"
    long_txt = rng(*longest_range, today) if longest else "-"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195">
  <style>
    .n {{ font: 700 28px 'Segoe UI', Ubuntu, sans-serif; fill: {blue}; }}
    .l {{ font: 600 14px 'Segoe UI', Ubuntu, sans-serif; fill: {text}; }}
    .s {{ font: 400 12px 'Segoe UI', Ubuntu, sans-serif; fill: {sub}; }}
  </style>
  <rect width="495" height="195" rx="4.5" fill="#0d1117"/>
  <line x1="165" y1="28" x2="165" y2="170" stroke="{line}"/>
  <line x1="330" y1="28" x2="330" y2="170" stroke="{line}"/>

  <text class="n" x="82.5" y="79" text-anchor="middle">{total}</text>
  <text class="l" x="82.5" y="114" text-anchor="middle">Total Contributions</text>
  <text class="s" x="82.5" y="140" text-anchor="middle">{fmt(first, True)} - Present</text>

  <circle cx="247.5" cy="71" r="40" fill="none" stroke="{blue}" stroke-width="5"/>
  <path d="M247.5 19 c-6 6 -9 11 -5 17 c-4 -1 -6 -4 -6 -7 c-4 5 -4 12 2 16 c5 3 13 2 15 -5 c2 -6 -2 -12 -6 -21 z"
        fill="{blue}" stroke="#0d1117" stroke-width="3"/>
  <text class="n" x="247.5" y="81" text-anchor="middle">{cur}</text>
  <text class="l" x="247.5" y="140" text-anchor="middle">Current Streak</text>
  <text class="s" x="247.5" y="162" text-anchor="middle">{cur_txt}</text>

  <text class="n" x="412.5" y="79" text-anchor="middle">{longest}</text>
  <text class="l" x="412.5" y="114" text-anchor="middle">Longest Streak</text>
  <text class="s" x="412.5" y="140" text-anchor="middle">{long_txt}</text>
</svg>
"""


def main():
    today = dt.datetime.now(TZ).date()
    stats = compute(fetch_days(), today)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(svg(*stats, today))
    print("total=%s current=%s longest=%s" % (stats[0], stats[2], stats[4]))


if __name__ == "__main__":
    main()
