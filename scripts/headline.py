"""오늘의 핵심 이슈 한 줄 고르기.

AI 없이 규칙으로 점수를 매깁니다.
- 그날의 큰 이야기: 여러 기사에 반복해서 나오는 회사·주제일수록 가산점
- 사실 보도(복귀·선임·사임·발표·실적·인수·상장·결정 등) 가산점, 의견·해설 기사는 감점
- 키워드(실적, 상장, 연준, 물가·고용, 관세, 인수합병, 경영진 변동 등) 가산점
- 헤드라인에 나온 종목이 실제로 크게 움직였으면 등락률만큼 가산점
직접 입력한 문장(HEADLINE 환경변수)이 있으면 그것을 우선합니다.
"""
import re

# (태그, 가중치, 정규식)
TOPICS = [
    ("경영", 4, r"\bCEO\b|chief executive|reinstat\w*|resign\w*|steps? down|ousted|appoint\w*|board of directors|succession"),
    ("상장", 4, r"\bIPOs?\b|initial public offering|goes public|go public|public debut|listing"),
    ("실적", 3, r"earnings|quarterly results|revenue|guidance|profit|beats? estimates|misses? estimates|forecast"),
    ("연준", 4, r"\bFed\b|Federal Reserve|FOMC|Powell|rate cuts?|rate hikes?|interest rates?"),
    ("물가·고용", 3, r"\bCPI\b|\bPCE\b|inflation|jobs report|payrolls|unemployment|jobless"),
    ("관세·정책", 2, r"tariffs?|trade war|sanctions?|export controls?|White House|Congress|shutdown"),
    ("인수합병", 2, r"acquir\w*|merger|takeover|buyout|\bdeal\b"),
    ("AI", 1, r"\bAI\b|artificial intelligence|data center|chips?"),
]
MOVE = r"record|plunge|plummet|soar|surge|tumble|sink|rally|sell-?off|crash|jump|slump|rout"
NOISE = (r"\?|^how |should you|opinion|\bI\b|\bmy\b|retire|my wife|my husband|personal finance|quiz|podcast"
         r"|social security|medicare|medicaid|hospice|nursing home|health benefits|recipe|travel|wedding"
         r"|here's|here is|these \d|\d (?:dividend )?stocks? (?:to|for)|to look at|to buy now|bargains"
         r"|lives on|a year\W|salary|millionaire|billionaires?\b.*thanks|watch industry")
MARKET = (r"stocks?|shares|equit|market|wall street|S&P|nasdaq|\bdow\b|index|futures|investors?|treasur"
          r"|yields?|\bbonds\b|bond (?:market|yields?|prices?)|\boil\b|crude|\bgold\b|dollar|currenc|bitcoin|crypto|sector|valuation|bubble"
          r"|selloff|sell-off|volatility|\bVIX\b|IPO|earnings|economy|economic|recession|GDP|bank")

# 사건을 전하는 표현 (사실 보도)
FACT = (r"\b(?:returns?|reinstat\w*|names?|named|appoint\w*|resign\w*|ousted|fired|steps? down|announc\w*|unveil\w*"
        r"|files?|filed|reports?|posts?|beats?|miss(?:es)?|raises?|cuts?|hikes?|approv\w*|blocks?|bans?|acquir\w*"
        r"|agrees?|sues?|launch\w*|debuts?|halts?|delays?|wins?|loses?|engineer\w*)\b")
# 의견·해설·투자 조언성 기사
COMMENTARY = (r"Cramer|Mad Money|what to know|what investors|should (?:you|investors)|here are|here's|\bsees\b"
              r"|newsletter|roundup|market talk|options[- ]trading|big trades|chasing"
              r"|lessons|\bwhy\b|\bhow\b|opinion|analysts? (?:say|see)|strategist|explain|takeaways|biggest gainers"
              r"|biggest losers|stocks? to (?:buy|watch)|the trade now")

STOP = {"the", "and", "for", "with", "from", "that", "this", "after", "over", "into", "stock", "stocks",
        "market", "markets", "says", "said", "will", "than", "what", "more", "shares", "amid"}


def relevant(title, config_stocks):
    """증시와 관련 있는 헤드라인인지 (칼럼·생활경제 기사는 제외)."""
    if re.search(NOISE, title, re.I):
        return False
    if re.search(MARKET, title, re.I) or re.search(MOVE, title, re.I):
        return True
    if any(re.search(pat, title, re.I) for _, _, pat in TOPICS):
        return True
    for cs in config_stocks:
        for a in cs.get("aliases", []):
            if re.search(r"\b" + re.escape(a) + r"\b", title):
                return True
    return False


def _words(title):
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z&.'-]{3,}", title)} - STOP


def pick(news, stocks, config_stocks, manual="", indices=None):
    """indices 를 넘기면, 지수가 2% 이상 움직인 날은 아주 강한 기사(8점 이상)가 아니면
    지수 움직임 자체를 핵심 이슈로 씁니다."""
    manual = " ".join((manual or "").split())
    if manual:
        return {"text": manual[:160], "tag": "편집", "link": "", "source": "", "note": "", "manual": True}
    if not news:
        return None

    alias = {}
    for cs in config_stocks:
        for a in cs.get("aliases", []) + [cs["symbol"]]:
            alias[a.lower()] = cs["symbol"]
    moves = {s["symbol"]: s for s in stocks or []}

    def symbols_in(t):
        found = set()
        for a, sym in alias.items():
            if re.search(r"\b" + re.escape(a) + r"\b", t, re.I if len(a) > 4 else 0):
                found.add(sym)
        return found

    syms = [symbols_in(n["title"]) for n in news]
    bags = [_words(n["title"]) for n in news]

    best, best_score = None, 0.0
    for i, n in enumerate(news):
        t = n["title"]
        score, tag = 0.0, ""
        for name, w, pat in TOPICS:
            if re.search(pat, t, re.I):
                score += w
                tag = tag or name
        if re.search(MOVE, t, re.I):
            score += 1
        if re.search(FACT, t, re.I):
            score += 2
        if re.search(COMMENTARY, t, re.I):
            score -= 5
        if re.search(NOISE, t, re.I):
            score -= 4
        hit = None
        for sym in syms[i]:
            q = moves.get(sym)
            if q and (hit is None or abs(q["pct"]) > abs(hit["pct"])):
                hit = q
        # 종목 이름만 나온 생활 기사에 점수를 주지 않도록, 시장·주제 단어가 함께 있을 때만 가산
        if hit and (score > 0 or re.search(MARKET, t, re.I)):
            score += 1 + min(abs(hit["pct"]), 8)
        # 그날의 큰 이야기: 같은 종목을 다룬 기사 수, 핵심 단어를 2개 이상 공유하는 기사 수
        same_sym = sum(1 for j in range(len(news)) if j != i and syms[i] & syms[j])
        same_words = sum(1 for j, b in enumerate(bags) if j != i and len(bags[i] & b) >= 2)
        score += min(max(same_sym, same_words), 6) * 1.0
        if score > best_score:
            note = ""
            if hit:
                note = hit["name"] + " " + format(hit["pct"], "+.2f") + "%"
            best, best_score = {"text": t, "tag": tag or "시장", "link": n.get("link", ""),
                                "source": n.get("source", ""), "note": note, "manual": False}, score
    main = [i for i in indices or [] if i.get("symbol") != "^RUT"]
    if main and max(abs(i["pct"]) for i in main) >= 2 and best_score < 8:
        return None
    return best if best_score >= 3 else None


def fallback(indices):
    """뉴스로 고르지 못했을 때: 가장 크게 움직인 지수로 한 줄."""
    if not indices:
        return None
    main = [i for i in indices if i.get("symbol") != "^RUT"] or indices
    top = max(main, key=lambda i: abs(i["pct"]))
    same = all((i["pct"] > 0) == (top["pct"] > 0) for i in main)
    big = abs(top["pct"]) >= 1.5
    verb = ("급등" if big else "상승") if top["pct"] > 0 else ("급락" if big else "하락")
    if same and len(main) > 1:
        parts = ", ".join(i["name"] + " " + format(i["pct"], "+.2f") + "%" for i in sorted(main, key=lambda i: i["pct"]))
        text = "뉴욕증시 " + verb + " 마감: " + parts
    else:
        text = top["name"] + " " + format(top["pct"], "+.2f") + "% " + verb + "으로 마감"
    return {"text": text, "tag": "시장", "link": "", "source": "", "note": "", "manual": False}
