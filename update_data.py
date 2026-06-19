#!/usr/bin/env python3
"""
世界杯数据更新 + 每日战报推送
每小时执行：更新网站数据(data.json + news.json)
每日21点额外输出：格式化战报文本推送到飞书
"""
import json, urllib.request, ssl, sys, re, os, html as html_mod
from datetime import datetime, timedelta, timezone

BJ_TZ = timezone(timedelta(hours=8))

def _decode_unicode(s):
    """解码头条搜索返回的双重转义unicode（如 \\u4e16\\u754c -> 世界）"""
    if not s:
        return s
    def _replace(m):
        try:
            return chr(int(m.group(1), 16))
        except:
            return m.group(0)
    # 完整的4位hex转义
    result = re.sub(r'\\u([0-9a-fA-F]{4})', _replace, s)
    # 截断的不完整转义（如 \u4 后面没跟够4位hex）直接去掉
    result = re.sub(r'\\u[0-9a-fA-F]{1,3}(?![0-9a-fA-F])', '', result)
    return result
OUT_DIR = "/home/mjclaw/hermes/output/worldcup2026"

TEAM_CN = {
    "USA": "美国", "Canada": "加拿大", "Mexico": "墨西哥",
    "France": "法国", "England": "英格兰", "Germany": "德国", "Spain": "西班牙",
    "Italy": "意大利", "Brazil": "巴西", "Argentina": "阿根廷", "Portugal": "葡萄牙",
    "Netherlands": "荷兰", "Belgium": "比利时", "Croatia": "克罗地亚",
    "Japan": "日本", "South Korea": "韩国", "Australia": "澳大利亚",
    "Saudi Arabia": "沙特", "Iran": "伊朗", "Iraq": "伊拉克", "Jordan": "约旦",
    "Uzbekistan": "乌兹别克斯坦",
    "Senegal": "塞内加尔", "Nigeria": "尼日利亚", "Cameroon": "喀麦隆",
    "Ghana": "加纳", "Morocco": "摩洛哥", "Tunisia": "突尼斯", "Algeria": "阿尔及利亚",
    "Egypt": "埃及", "Congo DR": "刚果(金)", "Ivory Coast": "科特迪瓦",
    "Costa Rica": "哥斯达黎加", "Jamaica": "牙买加", "Panama": "巴拿马",
    "Honduras": "洪都拉斯", "Colombia": "哥伦比亚", "Chile": "智利", "Uruguay": "乌拉圭",
    "Ecuador": "厄瓜多尔", "Paraguay": "巴拉圭", "Peru": "秘鲁", "Venezuela": "委内瑞拉",
    "Bolivia": "玻利维亚", "Serbia": "塞尔维亚", "Switzerland": "瑞士", "Denmark": "丹麦",
    "Sweden": "瑞典", "Norway": "挪威", "Poland": "波兰", "Ukraine": "乌克兰",
    "Austria": "奥地利", "Scotland": "苏格兰", "Wales": "威尔士", "Czechia": "捷克",
    "Romania": "罗马尼亚", "Turkey": "土耳其", "Greece": "希腊",
    "Republic of Ireland": "爱尔兰", "Bosnia-Herz": "波黑",
    "North Macedonia": "北马其顿", "Slovakia": "斯洛伐克", "Slovenia": "斯洛文尼亚",
    "Hungary": "匈牙利", "Finland": "芬兰", "Iceland": "冰岛",
    "New Zealand": "新西兰", "Qatar": "卡塔尔", "South Africa": "南非",
    "Haiti": "海地", "Türkiye": "土耳其", "Curacao": "库拉索", "Curaçao": "库拉索",
    "Dominican Rep.": "多米尼加", "Cape Verde": "佛得角",
}

GROUPS = {
    "A": ["Mexico", "South Africa", "Czechia", "South Korea"],
    "B": ["Canada", "Bosnia-Herz", "Switzerland", "Qatar"],
    "C": ["USA", "Paraguay", "Türkiye", "Haiti"],
    "D": ["Brazil", "Morocco", "Scotland", "Australia"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Spain", "Cape Verde", "Egypt", "Belgium"],
    "H": ["Argentina", "Algeria", "Uruguay", "Saudi Arabia"],
    "I": ["France", "Senegal", "Norway", "Iraq"],
    "J": ["Portugal", "Congo DR", "Croatia", "England"],
    "K": ["Austria", "Jordan", "Panama", "Ghana"],
    "L": ["Colombia", "Uzbekistan", "New Zealand", "Iran"],
}

ctx = ssl.create_default_context()

def cn(name):
    return TEAM_CN.get(name, name)

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=20, context=ctx)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return None

def fetch_teams():
    data = fetch_json("https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams")
    teams = {}
    if data and data.get("sports"):
        leagues = data["sports"][0].get("leagues", [])
        if leagues:
            for t in leagues[0].get("teams", []):
                team = t.get("team", {})
                short = team.get("shortDisplayName", "?")
                teams[short] = {
                    "id": team.get("id", "?"), "name": team.get("displayName", "?"),
                    "short": short, "abbreviation": team.get("abbreviation", "?"),
                    "color": team.get("color", "333333"), "altColor": team.get("altColor", "ffffff"),
                    "logo": team.get("logos", [{}])[0].get("href", "") if team.get("logos") else "",
                    "cn": TEAM_CN.get(short, short), "group": "?",
                }
    for gname, gteams in GROUPS.items():
        for t in gteams:
            if t in teams:
                teams[t]["group"] = gname
    return teams

def fetch_matches(teams_info):
    data = fetch_json("https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260720")
    if not data:
        return []
    results = []
    for e in data.get("events", []):
        comps = e.get("competitions", [{}])
        c = comps[0] if comps else {}
        state = c.get("status", {}).get("type", {}).get("state", "pre")
        status_detail = c.get("status", {}).get("type", {}).get("shortDetail", "")
        competitors = c.get("competitors", [])
        home = [x for x in competitors if x.get("homeAway") == "home"]
        away = [x for x in competitors if x.get("homeAway") == "away"]
        h_short = home[0].get("team", {}).get("shortDisplayName", "?") if home else "?"
        a_short = away[0].get("team", {}).get("shortDisplayName", "?") if away else "?"
        h_score = home[0].get("score", "0") if home else "0"
        a_score = away[0].get("score", "0") if away else "0"
        h_id = home[0].get("team", {}).get("id", "?") if home else "?"
        a_id = away[0].get("team", {}).get("id", "?") if away else "?"
        date_str = c.get("date", "?")
        venue = c.get("venue", {}).get("fullName", "")
        venue_city = c.get("venue", {}).get("address", {}).get("city", "")
        try:
            utc_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            bj_dt = utc_dt.astimezone(BJ_TZ)
            bj_str = bj_dt.strftime("%Y-%m-%d %H:%M")
            bj_date = bj_dt.strftime("%m/%d")
            bj_time = bj_dt.strftime("%H:%M")
        except:
            bj_str = bj_date = bj_time = "?"
        goals = []
        for det in c.get("details", []):
            det_type = det.get("type", {}).get("text", "")
            if "Goal" in det_type or "Penalty" in det_type:
                player = "?"
                if det.get("athletesInvolved"):
                    player = det["athletesInvolved"][0].get("shortName", "?")
                clock = det.get("clock", {}).get("displayValue", "?")
                is_own = "Own" in det_type
                is_penalty = "Penalty" in det_type
                team_id = det.get("team", {}).get("id", "?")
                scorer = "home" if team_id == h_id else "away" if team_id == a_id else "?"
                goals.append({"player": player, "time": clock, "own": is_own, "penalty": is_penalty, "side": scorer})
        h_group = teams_info.get(h_short, {}).get("group", "?")
        a_group = teams_info.get(a_short, {}).get("group", "?")
        if h_group != "?" and a_group != "?" and h_group == a_group:
            match_group = h_group
        elif h_group != "?" and a_group != "?":
            match_group = f"{a_group}/{h_group}"
        elif h_group != "?":
            match_group = h_group
        elif a_group != "?":
            match_group = a_group
        else:
            match_group = "淘汰赛"
        results.append({
            "id": c.get("id", ""), "date_utc": date_str, "date_bj": bj_str,
            "bj_date": bj_date, "bj_time": bj_time,
            "home": h_short, "away": a_short,
            "home_cn": TEAM_CN.get(h_short, h_short), "away_cn": TEAM_CN.get(a_short, a_short),
            "home_score": h_score, "away_score": a_score,
            "home_id": h_id, "away_id": a_id,
            "home_logo": teams_info.get(h_short, {}).get("logo", ""),
            "away_logo": teams_info.get(a_short, {}).get("logo", ""),
            "home_color": teams_info.get(h_short, {}).get("color", "333333"),
            "away_color": teams_info.get(a_short, {}).get("color", "333333"),
            "state": state, "status": status_detail,
            "venue": venue, "venue_city": venue_city,
            "group": match_group, "goals": goals,
        })
    return results

def fetch_news():
    """从头条搜索抓取世界杯新闻，包含链接和摘要。
    头条搜索返回的HTML有unicode escape，需要二次解码。
    备选方案：直接从页面article ID构建URL。
    """
    news = []
    try:
        url = "https://so.toutiao.com/search?keyword=2026%E4%B8%96%E7%95%8C%E6%9D%AF&pd=information&source=input&dvpf=pc&aid=4916&page_num=0"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Referer": "https://so.toutiao.com/",
        })
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        raw_bytes = resp.read()
        
        # Try JSON parse from __INITIAL_STATE__
        try:
            # Decode as utf-8 first
            raw = raw_bytes.decode("utf-8", errors="ignore")
            data_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', raw, re.DOTALL)
            if data_match:
                raw_json = re.sub(r'\bundefined\b', 'null', data_match.group(1))
                jdata = json.loads(raw_json)
                feed = jdata.get("data", jdata.get("search", {}))
                if isinstance(feed, dict):
                    feed = feed.get("list", feed.get("rawData", []))
                if isinstance(feed, list):
                    for item in feed[:15]:
                        title = item.get("title", "")
                        abstract = item.get("abstract", "")
                        url_link = item.get("url", item.get("source_url", ""))
                        source_name = item.get("source", item.get("media_name", "头条"))
                        if title and ("世界杯" in _decode_unicode(title) or "World Cup" in title):
                            title = html_mod.unescape(re.sub(r'<[^>]+>', '', _decode_unicode(title))).strip()
                            abstract = html_mod.unescape(re.sub(r'<[^>]+>', '', _decode_unicode(abstract))).strip() if abstract else ""
                            # Build clean toutiao URL from article ID
                            article_match = re.search(r'/a(\d+)', url_link) if url_link else None
                            clean_url = f"https://www.toutiao.com/a{article_match.group(1)}/" if article_match else url_link
                            news.append({
                                "title": title, "summary": abstract[:200],
                                "url": clean_url, "source": source_name,
                                "date": datetime.now(BJ_TZ).strftime("%Y-%m-%d")
                            })
        except Exception as e2:
            print(f"JSON parse fallback: {e2}", file=sys.stderr)
        
        # Fallback: extract article IDs and titles from HTML
        if not news:
            raw = raw_bytes.decode("utf-8", errors="ignore")
            # Extract article IDs (format: /aXXXXXXXXXXXXXXXX)
            article_ids = re.findall(r'/a(\d{16,})', raw)
            # Extract titles near world cup keywords
            title_pattern = re.compile(r'"title"\s*:\s*"((?:[^"\\]|\\.)*?世界杯(?:[^"\\]|\\.)*?)"', re.IGNORECASE)
            abstract_pattern = re.compile(r'"abstract"\s*:\s*"((?:[^"\\]|\\.)*?)"')
            source_pattern = re.compile(r'"(?:source|media_name)"\s*:\s*"((?:[^"\\]|\\.)*?)"')
            titles = title_pattern.findall(raw)
            abstracts = abstract_pattern.findall(raw)
            sources = source_pattern.findall(raw)
            
            for i, raw_title in enumerate(titles[:15]):
                # Decode unicode escapes - 头条返回双重转义的unicode
                decoded = _decode_unicode(raw_title)
                decoded = html_mod.unescape(re.sub(r'<[^>]+>', '', decoded)).strip()
                if not decoded or len(decoded) < 5:
                    continue
                abstract = ""
                if i < len(abstracts):
                    abstract = _decode_unicode(abstracts[i])
                    abstract = html_mod.unescape(re.sub(r'<[^>]+>', '', abstract)).strip()[:200]
                clean_url = f"https://www.toutiao.com/a{article_ids[i]}/" if i < len(article_ids) else ""
                source_name = sources[i] if i < len(sources) else "头条搜索"
                source_name = _decode_unicode(source_name)
                news.append({
                    "title": decoded, "summary": abstract,
                    "url": clean_url, "source": source_name,
                    "date": datetime.now(BJ_TZ).strftime("%Y-%m-%d")
                })
    except Exception as e:
        print(f"News error: {e}", file=sys.stderr)
    
    if not news:
        news.append({
            "title": "2026 FIFA世界杯正在进行",
            "summary": "第23届FIFA世界杯由美国、加拿大、墨西哥联合主办，48支球队参赛，共104场比赛。",
            "url": "https://www.fifa.com/fifaplus/en/tournaments/mens/worldcup/2026",
            "source": "FIFA官网", "date": datetime.now(BJ_TZ).strftime("%Y-%m-%d")
        })
    return news

def format_daily_report(matches):
    now_bj = datetime.now(BJ_TZ)
    today_str = f"{now_bj.month}月{now_bj.day}日"
    completed = [m for m in matches if m["state"] == "post"]
    upcoming_today = [m for m in matches if m["state"] != "post" and m["bj_date"] == now_bj.strftime("%m/%d")]
    upcoming_tomorrow = [m for m in matches if m["state"] != "post" and m["bj_date"] == (now_bj + timedelta(days=1)).strftime("%m/%d")]
    lines = [f"## ⚽ 世界杯每日战报（{today_str}）", ""]
    if completed:
        lines.append("### ✅ 今日已完赛")
        for m in completed:
            h, a = cn(m["home"]), cn(m["away"])
            lines.append(f"**{h} {m['home_score']}-{m['away_score']} {a}**（{m['bj_time']}，{m['venue']}）")
            for g in m["goals"]:
                suffix = "(乌龙)" if g["own"] else "(点球)" if g["penalty"] else ""
                lines.append(f"  ⚽ {g['time']}' {g['player']}{suffix}")
        lines.append("")
    if upcoming_today:
        lines.append("### 🕐 今日待赛")
        for m in upcoming_today:
            h, a = cn(m["home"]), cn(m["away"])
            lines.append(f"- {m['bj_time']} {h} vs {a}（{m['venue']}）")
        lines.append("")
    if upcoming_tomorrow:
        lines.append("### 📅 明日赛程")
        for m in upcoming_tomorrow:
            h, a = cn(m["home"]), cn(m["away"])
            lines.append(f"- {m['bj_time']} {h} vs {a}（{m['venue']}）")
        lines.append("")
    total_goals = sum(len(m["goals"]) for m in completed)
    if completed:
        lines.append("### 📊 今日数据")
        lines.append(f"- 完赛 {len(completed)} 场，共 {total_goals} 球")
    lines.append("\n---\n数据来源：ESPN API | 网站查看：http://localhost:8899")
    return "\n".join(lines)

def main():
    now_bj = datetime.now(BJ_TZ)
    hour = now_bj.hour
    print("Updating World Cup data...", file=sys.stderr)
    teams_info = fetch_teams()
    matches = fetch_matches(teams_info)
    if not matches:
        print("[SILENT]")
        return
    output = {
        "last_updated": now_bj.strftime("%Y-%m-%d %H:%M:%S CST"),
        "teams": teams_info, "groups": GROUPS, "matches": matches,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "data.json"), "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    # Update news every 6 hours
    if hour % 6 == 0:
        news = fetch_news()
        with open(os.path.join(OUT_DIR, "news.json"), "w") as f:
            json.dump(news, f, ensure_ascii=False, indent=2)
    # Push daily report at 21:00
    if hour == 21:
        report = format_daily_report(matches)
        print(report)
    else:
        print("[SILENT]")

if __name__ == "__main__":
    main()
