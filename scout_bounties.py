"""Find small, paid engineering opportunities on GitHub.

The scout deliberately stays dependency-free so it can run in GitHub Actions.
It combines the original open-issue scan with authenticated GitHub code search
for bounty/challenge language in Markdown files. When code search is not
available, it falls back to repository README search and a small Markdown crawl.
"""

import argparse
import base64
import html
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


STATE_FILE = "seen_bounties.json"
API_ROOT = "https://api.github.com"
MAX_COMMENTS = 25
DEFAULT_MAX_RESULTS = 20
SEARCH_RESULTS_PER_QUERY = 10
ISSUE_RESULTS_PER_QUERY = 20
MAX_DOCUMENTS_TO_FETCH = 60
MAX_FALLBACK_REPOSITORIES = 12
DOCUMENT_RESULTS_PER_QUERY = 6

# Keep the legacy Issue scan, but broaden the vocabulary beyond "bounty".
ISSUE_SEARCH_QUERIES = [
    "is:issue is:open bounty in:title,body sort:updated-desc",
    'is:issue is:open "cash prize" in:title,body sort:updated-desc',
    'is:issue is:open "paid challenge" in:title,body sort:updated-desc',
    'is:issue is:open "paid contribution" in:title,body sort:updated-desc',
    'is:issue is:open "paid PR" in:title,body sort:updated-desc',
    'is:issue is:open "contributor reward" in:title,body sort:updated-desc',
]

# Code search covers README, CONTRIBUTING and standalone challenge documents.
DOCUMENT_SEARCH_QUERIES = [
    ('cash prize + GitHub Issue', '"cash prize" "GitHub Issue" language:Markdown'),
    ('cash prize + Pull Request', '"cash prize" "pull request" language:Markdown'),
    ('cash prize + Google Form', '"cash prize" "Google Form" language:Markdown'),
    ('paid challenge + submit', '"paid challenge" submit language:Markdown'),
    ('contributor reward', '"contributor reward" language:Markdown'),
    ('paid contribution + issue', '"paid contribution" issue language:Markdown'),
    ('micro bounty + available', '"micro bounty" available language:Markdown'),
    ('paid PR', '"paid PR" language:Markdown'),
    ('prize pool + task', '"prize pool" task language:Markdown'),
    ('engineering challenge + reward', '"engineering challenge" reward language:Markdown'),
]

# Unauthenticated code search is unavailable. These queries provide a useful,
# lower-coverage README fallback for local runs without a token.
README_SEARCH_TERMS = [
    "cash prize",
    "paid challenge",
    "contributor reward",
    "micro bounty",
]

STRONG_REWARD_TERMS = (
    "cash prize",
    "cash reward",
    "prize pool",
    "paid challenge",
    "engineering challenge",
    "contributor reward",
    "paid contribution",
    "micro bounty",
    "paid bounty",
    "paid issue",
    "paid pr",
    "monetary reward",
    "bounty",
)
GENERIC_REWARD_TERMS = ("reward", "prize", "payout", "compensation")
REWARD_INTENT_TERMS = ("bounty", "reward", "prize", "payout", "cash", "paid", "compensation", "winner")
MICRO_TASK_TERMS = (
    "good first issue",
    "beginner friendly",
    "small task",
    "quick task",
    "micro",
    "few hours",
    "couple of hours",
    "under an hour",
    "less than an hour",
    "simple fix",
    "reproduce",
    "report an issue",
)
CODING_TASK_TERMS = (
    "bug",
    "fix",
    "code",
    "coding",
    "test",
    "documentation",
    "docs",
    "api",
    "cli",
    "integration",
    "pull request",
    "implement",
    "代码",
    "文档",
    "测试",
    "问题",
    "缺陷",
    "仓库",
)
ACTION_TERMS = (
    "submit",
    "submission",
    "implement",
    "build",
    "fix",
    "find a bug",
    "report an issue",
    "open an issue",
    "pull request",
    "contribute",
    "how to participate",
    "how to enter",
    "提交",
    "修复",
    "实现",
    "报告",
    "体验",
    "测评",
    "试用",
    "发现",
)
SPAM_TERMS = (
    "airdrop",
    "referral",
    "casino",
    "gambling",
    "trading bot",
    "blog post",
    "article writing",
    "tutorial proposal",
    "content creator",
    "spam:",
    "lottery",
    "lotto",
    "sweepstakes",
)
JOB_TERMS = (
    "full-time role",
    "full time role",
    "part-time role",
    "part time role",
    "job opening",
    "we are hiring",
    "internship position",
    "salary range",
    "apply for this role",
    "paid internship",
    "internship application",
    "take-home engineering challenge",
    "take home engineering challenge",
    "take-home coding challenge",
    "interview process",
    "internship post",
)
LONG_PROJECT_TERMS = (
    "multi-month",
    "multi month",
    "semester-long",
    "12-week",
    "six months",
    "long-term commitment",
)
HEAVY_SCOPE_TERMS = (
    "meaningful production implementation",
    "migration behavior",
    "signer rotation",
    "security review",
    "end-to-end flow",
    "ios, android, and web",
    "multi-week",
    "architecture redesign",
)
NOISY_DOCUMENT_PATH_TERMS = (
    " — archive/",
    " — docs/old/",
    " — changelog",
    " — release-notes/",
    " — release_notes/",
    "privacy-policy-historical",
    "antigravity-threads/",
    "implementation_complete",
    " — skill.md",
    "/skill.md",
)

PAYMENT_METHOD_PATTERNS = (
    ("PayPal", r"\bpaypal\b"),
    ("Wise", r"\bwise\b"),
    ("Stripe", r"\bstripe\b"),
    ("银行转账", r"\b(?:bank|wire)\s+transfer\b|银行转账"),
    ("USDC", r"\busdc\b"),
    ("USDT", r"\busdt\b|\btether\b"),
    ("DAI", r"\bdai\b"),
    ("BTC", r"\bbtc\b|\bbitcoin\b"),
    ("sats", r"\bsats?\b|\bsatoshis?\b|\blightning(?: network)?\b"),
    ("XLM", r"\bxlm\b"),
    ("ETH", r"\beth\b|\bether\b"),
    ("SOL", r"\bsol\b"),
    ("支付宝", r"\balipay\b|支付宝"),
    ("微信支付", r"\bwechat pay\b|微信支付"),
)

FIAT_PAYMENT_METHODS = {"PayPal", "Wise", "Stripe", "银行转账", "支付宝", "微信支付"}
CRYPTO_PAYMENT_METHODS = {"USDC", "USDT", "DAI", "BTC", "sats", "XLM", "ETH", "SOL"}
RADAR_LABEL_HINTS = {"radar", "aggregator", "external-mirror", "bounty-hunter", "mirror"}
MAX_SOURCE_HOPS = 3

AMOUNT_PATTERNS = (
    r"(?:US\$|USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|ETH|SOL|USDT|DAI|BTC|€|£|¥|₹|\$)\s*"
    r"\d[\d,]*(?:\.\d+)?(?:\s*(?:USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|ETH|SOL|USDT|DAI|BTC))?"
    r"(?:\s*[-–—]\s*(?:(?:US\$|USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|ETH|SOL|USDT|DAI|BTC|€|£|¥|₹|\$)\s*)?\d[\d,]*(?:\.\d+)?)?",
    r"\b\d[\d,]*(?:\.\d+)?\s*(?:USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|ETH|SOL|USDT|DAI|BTC)\b",
)


def log(message):
    print(message, file=sys.stderr)


def load_seen_bounties(state_file=STATE_FILE):
    """Load previously seen opportunity URLs, preserving legacy list state."""
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return {str(url) for url in data if url}
        except (OSError, ValueError) as exc:
            log(f"Error loading state file: {exc}")
    return set()


def save_seen_bounties(seen_urls, state_file=STATE_FILE):
    """Append new URLs without needlessly reordering the large state file."""
    old_order = []
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                old_order = [str(url) for url in data if url]
        except (OSError, ValueError):
            old_order = []

    seen_set = set(seen_urls)
    ordered = []
    already_added = set()
    for url in old_order:
        if url in seen_set and url not in already_added:
            ordered.append(url)
            already_added.add(url)
    ordered.extend(sorted(seen_set - already_added))

    try:
        with open(state_file, "w", encoding="utf-8") as handle:
            json.dump(ordered, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except OSError as exc:
        log(f"Error saving state file: {exc}")


def github_api_get(url, token=None, accept="application/vnd.github+json"):
    """Return decoded JSON, or None after logging a concise API error."""
    if url.startswith("/"):
        url = API_ROOT + url
    headers = {
        "Accept": accept,
        "User-Agent": "BountyScout-MicroChallengeScanner",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            detail = f": {payload.get('message', '')}"
        except (ValueError, UnicodeDecodeError):
            pass
        log(f"GitHub API {exc.code} for {url}{detail}")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        log(f"GitHub API error for {url}: {exc}")
    return None


def search_endpoint(endpoint, query, token=None, per_page=SEARCH_RESULTS_PER_QUERY):
    params = urllib.parse.urlencode({"q": query, "per_page": per_page})
    accept = "application/vnd.github.text-match+json, application/vnd.github+json"
    return github_api_get(f"/search/{endpoint}?{params}", token, accept=accept)


def fetch_text_url(url, token=None):
    headers = {"User-Agent": "BountyScout-MicroChallengeScanner"}
    if token and url.startswith(API_ROOT):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.read(1_000_000).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        log(f"Unable to fetch document {url}: {exc}")
        return ""


def decode_content_payload(payload, token=None):
    if not isinstance(payload, dict):
        return ""
    content = payload.get("content")
    if content and payload.get("encoding") == "base64":
        try:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return ""
    if payload.get("download_url"):
        return fetch_text_url(payload["download_url"], token)
    return ""


def clean_line(line):
    line = re.sub(r"^\s{0,3}(?:#{1,6}\s*|[-*+]\s+|\d+[.)]\s+|>\s*)", "", line)
    line = re.sub(r"!\[[^]]*\]\([^)]*\)", "", line)
    line = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1 (\2)", line)
    line = re.sub(r"[`*_]", "", line)
    return re.sub(r"\s+", " ", line).strip()


def relevant_context(text, window=4, max_lines=32):
    """Keep lines around reward signals so unrelated README prose adds less noise."""
    lines = text.splitlines()
    selected = set()
    for index, line in enumerate(lines):
        lower = line.lower()
        textual_match = any(term in lower for term in STRONG_REWARD_TERMS + GENERIC_REWARD_TERMS)
        amount_match = any(re.search(pattern, line, re.IGNORECASE) for pattern in AMOUNT_PATTERNS)
        nearby = "\n".join(lines[max(0, index - window) : min(len(lines), index + window + 1)]).lower()
        amount_match = amount_match and any(term in nearby for term in REWARD_INTENT_TERMS)
        if textual_match or amount_match:
            selected.update(range(max(0, index - window), min(len(lines), index + window + 1)))
    cleaned = [clean_line(lines[index]) for index in sorted(selected)[:max_lines]]
    return "\n".join(line for line in cleaned if line)[:8000]


def extract_amounts(text):
    amounts = []
    occupied_spans = []
    for pattern in AMOUNT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if any(match.start() < end and match.end() > start for start, end in occupied_spans):
                continue
            value = re.sub(r"\s+", " ", match.group(0)).strip().rstrip(",")
            numeric = re.search(r"\d[\d,]*(?:\.\d+)?", value)
            if numeric and float(numeric.group(0).replace(",", "")) <= 0:
                continue
            if value and value not in amounts:
                amounts.append(value)
                occupied_spans.append(match.span())
    return amounts[:4]


def extract_reward_amounts(text):
    """Prefer amounts on reward lines over prices mentioned elsewhere nearby."""
    lines = text.splitlines()
    selected = set()
    for index, line in enumerate(lines):
        lower = line.lower()
        if any(term in lower for term in REWARD_INTENT_TERMS):
            selected.update(range(index, min(len(lines), index + 2)))
    focused = "\n".join(lines[index] for index in sorted(selected))
    return extract_amounts(focused) or extract_amounts(text)


def has_document_reward_assertion(context):
    """Require an actual offer, not merely words such as challenge or reward model."""
    lower = context.lower()
    if re.search(
        r"\b(?:no|not offering|without)\s+(?:a\s+)?(?:cash\s+)?(?:bug\s+)?(?:bounty|reward|prize)\b"
        r"|\b(?:can't|cannot|can not|unable to)\s+offer\s+(?:any\s+)?(?:cash\s+)?(?:bounty|reward|prize)\b"
        r"|\b(?:unpaid|not paid)\b|\bdo not (?:offer|pay)\b",
        lower,
    ):
        return False
    explicit = (
        "cash prize",
        "cash reward",
        "paid challenge",
        "paid bounty",
        "paid issue",
        "paid pr",
        "monetary reward",
        "contributor reward",
        "prize pool",
    )
    if any(term in lower for term in explicit):
        return True

    opportunity = re.search(
        r"\b(?:claim|earn|win|receive|award(?:ed)?|available|submit|report|fix|implement|complete|solve)\b",
        lower,
    )
    if "bounty" in lower and opportunity:
        return True
    paid_contributor = re.search(
        r"\b(?:contributors?|participants?|submitters?)\b.{0,100}\b(?:will be|are|can be|get) paid\b"
        r"|\bpaid (?:for|to) contribut(?:e|ion|ors?)\b",
        lower,
        re.DOTALL,
    )
    if paid_contributor and opportunity:
        return True

    amount = r"(?:(?:US\$|USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|ETH|SOL|USDT|DAI|BTC|€|£|¥|₹|\$)\s*\d|\d[\d,]*\s*(?:USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|ETH|SOL|USDT|DAI|BTC))"
    reward = r"(?:bounty|reward|prize|payout|paid|winner)"
    return bool(
        re.search(reward + r".{0,160}" + amount, lower, re.DOTALL)
        or re.search(amount + r".{0,160}" + reward, lower, re.DOTALL)
    )


def has_actionable_document_offer(context, submission):
    lower = context.lower()
    inactive = re.search(
        r"\b(?:nominations?|submissions?|entries|applications?) (?:are |were )?closed\b"
        r"|\bwinners? (?:were|have been|announced)\b|\bpast winners?\b|\bprevious winners?\b"
        r"|\b(?:challenge|contest|competition) (?:has |is )?(?:ended|over|closed)\b",
        lower,
    )
    if inactive:
        return False

    aggregator = re.search(
        r"\b(?:platform|system|marketplace|application|app|dapp|tool)\b.{0,160}"
        r"\b(?:discover|search|browse|track|manage|post|paid contribution opportunities|bounties)\b"
        r"|\b(?:discover|search|browse|track|list|aggregate)\b.{0,100}"
        r"\b(?:bounty issues|bounties|paid contribution opportunities)\b",
        lower,
        re.DOTALL,
    )
    if aggregator:
        return False

    direct_action = re.search(
        r"(?:^|\n)\s*(?:[-*+]\s*)?(?:find|submit|participate|enter|apply|fix|implement|build|report|solve|contribute)\b"
        r"|\b(?:you|participants?|contributors?|entrants?)\s+(?:must|should|can|may|need to|will)\s+"
        r"(?:find|submit|participate|enter|apply|fix|implement|build|report|solve|contribute)\b"
        r"|\b(?:open|file) (?:a |an )?(?:github )?issue\b|\bpull request\b"
        r"|\btask\s*(?::|is\b)|\bhow to (?:enter|participate|submit|apply)\b"
        r"|\b(?:eligibility|deadline|submission instructions|entry requirements)\b",
        lower,
    )
    if direct_action:
        return True

    # A recognized submission method elsewhere in a short challenge document is
    # useful evidence, but do not accept it without offer-oriented wording.
    return submission != "待确认" and bool(
        re.search(r"\b(?:cash prize|cash reward|paid bounty|reward for|bounty for|prize for)\b", lower)
    )


def document_path_from_title(title):
    return title.split(" — ", 1)[-1].strip()


def major_currency_prize_is_large(amounts):
    """Identify prizes outside the intended tens-to-hundreds range."""
    for amount in amounts:
        if not re.search(r"(?:US\$|USD|EUR|GBP|€|£|\$)", amount, re.IGNORECASE):
            continue
        number = re.search(r"\d[\d,]*(?:\.\d+)?", amount)
        if number and float(number.group(0).replace(",", "")) >= 2000:
            return True
    return False


def payment_context(text):
    lines = text.splitlines()
    selected = []
    for line in lines:
        lower = line.lower()
        if any(term in lower for term in STRONG_REWARD_TERMS + GENERIC_REWARD_TERMS) or re.search(
            r"\bpay(?:ment|out|pal|ing|able|ed)?\b|winner|receive|bank transfer|wire transfer"
            r"|usdc|usdt|tether|\bbtc\b|bitcoin|sats?|satoshi|lightning|\bxlm\b|\beth\b|\bsol\b|\bdai\b",
            lower,
        ):
            selected.append(line)
    return "\n".join(selected)


def extract_payment_methods(text):
    context = payment_context(text)
    methods = []
    clauses = re.split(r"[;,\n]|\b(?:but|and)\b", context, flags=re.IGNORECASE)
    for name, pattern in PAYMENT_METHOD_PATTERNS:
        matching_clauses = [clause for clause in clauses if re.search(pattern, clause, re.IGNORECASE)]
        usable_clauses = [
            clause
            for clause in matching_clauses
            if not payment_method_is_negated(clause, pattern)
        ]
        if usable_clauses:
            methods.append(name)
    return methods


def payment_method_is_negated(clause, pattern):
    wrapped_pattern = f"(?:{pattern})"
    negative_pattern = (
        r"\b(?:no|without|unsupported|not(?!\s+only))\b.{0,30}"
        + wrapped_pattern
        + r"|"
        + wrapped_pattern
        + r".{0,30}\b(?:unavailable|unsupported|not supported|not available)\b"
    )
    return bool(re.search(negative_pattern, clause, re.IGNORECASE))


def is_crypto_only_payment(methods):
    method_set = set(methods)
    return bool(method_set & CRYPTO_PAYMENT_METHODS) and not bool(method_set & FIAT_PAYMENT_METHODS)


def first_matching_line(text, patterns, max_length=280):
    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if line and any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns):
            return line[:max_length]
    return ""


def extract_deadline(text):
    patterns = (
        r"\bdeadline\b",
        r"\bdue date\b",
        r"\bsubmit(?:ted)? by\b",
        r"\bsubmissions? due\b",
        r"\bentries close\b",
        r"\bcloses? (?:on|at)\b",
        r"\bends? (?:on|at)\b",
        r"截止(?:日期|时间)?",
        r"结束时间",
    )
    return first_matching_line(text, patterns) or "待确认"


def parsed_deadline_date(deadline):
    """Parse only unambiguous dates; unknown formats remain eligible."""
    if deadline == "待确认":
        return None
    iso_match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", deadline)
    if not iso_match:
        iso_match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", deadline)
    if iso_match:
        try:
            return datetime(*(int(value) for value in iso_match.groups()), tzinfo=timezone.utc)
        except ValueError:
            return None

    month_names = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    match = re.search(
        r"\b(" + "|".join(month_names) + r")\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b",
        deadline,
        re.IGNORECASE,
    )
    if match:
        try:
            return datetime(
                int(match.group(3)), month_names[match.group(1).lower()], int(match.group(2)), tzinfo=timezone.utc
            )
        except ValueError:
            return None
    day_first = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?("
        + "|".join(month_names)
        + r")[,]?\s+(20\d{2})\b",
        deadline,
        re.IGNORECASE,
    )
    if day_first:
        try:
            return datetime(
                int(day_first.group(3)),
                month_names[day_first.group(2).lower()],
                int(day_first.group(1)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None
    return None


def extract_submission(text):
    methods = []
    checks = (
        ("Google Form", r"(?:docs\.google\.com/forms|forms\.gle|google form)"),
        ("GitHub Issue", r"\b(?:github )?issue\b|open an issue|file an issue|report an issue"),
        ("Pull Request", r"\bpull request\b|\bsubmit (?:a )?pr\b|\bopen (?:a )?pr\b"),
        ("电子邮件", r"\bemail\b|mailto:"),
        ("Discord", r"\bdiscord\b"),
    )
    action_context = "\n".join(
        line
        for line in text.splitlines()
        if re.search(
            r"submit|submission|apply|enter|participat|issue|pull request|\bpr\b|form|email|discord",
            line,
            re.IGNORECASE,
        )
    )
    for name, pattern in checks:
        if re.search(pattern, action_context, re.IGNORECASE):
            methods.append(name)
    if methods:
        return "、".join(methods)
    line = first_matching_line(
        text,
        (r"\bsubmit\b", r"\bapply (?:here|at|via|for)\b", r"how to (?:enter|participate)"),
    )
    return line or "待确认"


def extract_task(text, fallback):
    action_lines = []
    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        lower = line.lower()
        if not line or not any(term in lower for term in ACTION_TERMS):
            continue
        score = sum(term in lower for term in ACTION_TERMS)
        score += 2 * sum(term in lower for term in CODING_TASK_TERMS)
        score += min(len(line.split()), 20) / 20
        if re.search(r"\b(?:do not|don't|not accepted|must not)\b|不算|不接受|不要|禁止", lower):
            score -= 4
        action_lines.append((score, line[:320]))
    if action_lines:
        return max(action_lines, key=lambda item: item[0])[1]
    context = relevant_context(text)
    for line in context.splitlines():
        if line:
            return line[:320]
    return fallback[:320]


def estimate_agent_fit(text):
    lower = text.lower()
    coding_hits = sum(term in lower for term in CODING_TASK_TERMS)
    human_evidence = any(
        term in lower
        for term in ("hands-on", "real usage", "screenshot", "screen recording", "真实使用", "截图", "录屏", "人工验证")
    )
    unsuitable = any(
        term in lower
        for term in ("in person", "on-site", "onsite", "hardware assembly", "phone interview", "video production")
    )
    if unsuitable:
        return "不太适合（包含线下、硬件或非编码要求）"
    if human_evidence:
        return "部分适合（需要人工试用或证据，Coding Agent 可辅助）"
    if coding_hits >= 2:
        return "是（代码、测试、文档或 Issue/PR 类任务）"
    if coding_hits == 1:
        return "可能适合（需人工确认交付范围）"
    return "待确认"


def estimate_effort(text):
    explicit = first_matching_line(
        text,
        (
            r"\b\d+(?:\s*[-–—]\s*\d+)?\s*(?:minutes?|mins?|hours?|hrs?|days?)\b",
            r"\b(?:under|less than) an? hour\b",
            r"\b(?:a few|a couple of) hours\b",
        ),
        max_length=180,
    )
    if explicit:
        return f"页面描述：{explicit}"
    lower = text.lower()
    if any(term in lower for term in MICRO_TASK_TERMS):
        return "推测：几十分钟到数小时"
    if any(term in lower for term in CODING_TASK_TERMS):
        return "推测：数小时到 1 天（需人工确认范围）"
    return "待确认"


def analyze_candidate(title, project, url, source, text, comments=None, updated_at=None, now=None):
    """Normalize and score an Issue or Markdown document candidate."""
    context = relevant_context(text)
    focused_text = "\n".join(part for part in (title, context) if part)
    lower = focused_text.lower()

    if any(term in lower for term in SPAM_TERMS + JOB_TERMS):
        return None
    if any(term in lower for term in LONG_PROJECT_TERMS):
        return None
    full_lower = text.lower()
    if sum(term in full_lower for term in HEAVY_SCOPE_TERMS) >= 2 and not any(
        term in full_lower for term in MICRO_TASK_TERMS
    ):
        return None
    if source == "Repository Markdown" and any(term in lower for term in NOISY_DOCUMENT_PATH_TERMS):
        return None
    if source == "Repository Markdown" and re.search(r"\b(?:2|3|4|5|6|7|8|9|1\d)\s*[- ]?months?\b", lower):
        return None

    amounts = extract_reward_amounts(context)
    methods = extract_payment_methods(text)
    if is_crypto_only_payment(methods):
        return None
    strong_hit = any(term in lower for term in STRONG_REWARD_TERMS)
    generic_hit = any(term in lower for term in GENERIC_REWARD_TERMS)
    cash_hit = bool(amounts or methods or re.search(r"\bcash\b|\bpaid\b|\bmonetary\b", lower))
    if not strong_hit and not (generic_hit and cash_hit):
        return None
    if source == "Repository Markdown" and not has_document_reward_assertion(context):
        return None

    micro_hit = any(term in lower for term in MICRO_TASK_TERMS)
    coding_hit = any(term in lower for term in CODING_TASK_TERMS)
    large_event = any(term in lower for term in ("hackathon", "game jam", "multi-day competition"))
    if large_event and not micro_hit:
        return None
    if source == "Repository Markdown" and major_currency_prize_is_large(amounts) and not micro_hit:
        return None

    if source == "Repository Markdown":
        path = document_path_from_title(title)
        named_path = " — " not in title or candidate_markdown_path(path)
        explicit_cash_offer = re.search(
            r"\b(?:cash prize|cash reward|paid bounty|paid challenge|monetary reward)\b",
            context,
            re.IGNORECASE,
        )
        if not named_path and not (explicit_cash_offer and amounts):
            return None
        basename = path.lower().rsplit("/", 1)[-1]
        generic_doc = basename.startswith(("readme", "contributing"))
        if generic_doc and not (amounts or methods or explicit_cash_offer):
            return None

    deadline = extract_deadline(text)
    deadline_date = parsed_deadline_date(deadline)
    current = now or datetime.now(timezone.utc)
    if deadline_date and deadline_date.date() < current.date():
        return None

    submission = extract_submission(text)
    qualification_submission = extract_submission(context)
    if source == "Repository Markdown" and not has_actionable_document_offer(context, qualification_submission):
        return None
    score = 3 if strong_hit else 0
    score += 2 if amounts else 0
    score += 1 if methods else 0
    score += 2 if micro_hit else 0
    score += 1 if coding_hit else 0
    score += 1 if submission != "待确认" else 0
    if "prize pool" in lower and not micro_hit:
        score -= 2

    return {
        "title": title,
        "project": project,
        "url": url,
        "source": source,
        "reward": "；".join(amounts) if amounts else "金额待确认",
        "task": extract_task(text, title),
        "deadline": deadline,
        "submission": submission,
        "payment_method": "、".join(methods) if methods else "待确认",
        "agent_fit": estimate_agent_fit(focused_text),
        "effort": estimate_effort(focused_text),
        "comments": comments,
        "updated_at": updated_at,
        "score": score,
    }


def is_clean_issue(item, host_repo=None):
    """Retain original safeguards and prevent alert feedback loops."""
    if item.get("state") not in (None, "open"):
        return False
    if "pull_request" in item or item.get("assignees"):
        return False
    if int(item.get("comments", 0) or 0) > MAX_COMMENTS:
        return False
    labels = {str(label.get("name", "")).lower() for label in item.get("labels", []) if isinstance(label, dict)}
    if "bounty-alert" in labels:
        return False
    if any(
        label in {"radar", "claimed", "in progress", "bounty-large", "size: large", "size/large"}
        or label.endswith("-large")
        for label in labels
    ):
        return False
    repository_url = str(item.get("repository_url", ""))
    if host_repo and repository_url.rstrip("/").endswith("/repos/" + host_repo):
        return False
    return True


def has_issue_reward_offer(item):
    """Reject Issues that merely discuss bounty systems or unrelated rewards."""
    title = str(item.get("title") or "")
    body = str(item.get("body") or "")
    lower_title = title.lower()
    lower_body = body.lower()
    combined = lower_title + "\n" + lower_body

    if re.search(
        r"\b(?:paused|cancelled|canceled|unfunded|not funded|not payable|ineligible)\b"
        r"|\bdoes not prove\b|\bdoes not claim\b|\bnot claim current\b",
        combined,
    ):
        return False
    if lower_title.startswith("[radar]") or re.search(r"\b(?:i am submitting|my submission)\b", lower_body[:1000]):
        return False
    if re.search(r"\b(?:bounty|reward) (?:platform|marketplace|adapter|protocol|settlement audit)\b", lower_title):
        return False

    labels = [str(label.get("name") or "").lower() for label in item.get("labels", []) if isinstance(label, dict)]
    if any("bounty" in label or "reward" in label for label in labels):
        return True

    explicit_title = re.search(
        r"(?:^|[\[(:-])\s*(?:micro\s+)?bounty\b|\b(?:cash prize|paid challenge|paid contribution|contributor reward)\b",
        lower_title,
    )
    title_amount = any(re.search(pattern, title, re.IGNORECASE) for pattern in AMOUNT_PATTERNS)
    if explicit_title and (title_amount or re.search(r"\b(?:fix|implement|add|build|create|write|test|document)\b", lower_title)):
        return True

    amount = (
        r"(?:(?:US\$|USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|ETH|SOL|USDT|DAI|BTC|€|£|¥|₹|\$)\s*\d"
        r"|\d[\d,]*(?:\.\d+)?\s*(?:USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|ETH|SOL|USDT|DAI|BTC))"
    )
    heading_offer = (
        r"(?:^|\n)\s*(?:#{1,6}\s*)?(?:[^\w\n]{0,3}\s*)?"
        r"(?:bounty|reward|payment|payout|cash prize)\s*(?::|[-–—])?.{0,100}"
    )
    if re.search(heading_offer + amount, lower_body, re.DOTALL):
        return True
    if re.search(r"\b(?:will pay|we pay|offering)\b.{0,100}" + amount, lower_body, re.DOTALL):
        return True
    return bool(
        re.search(
            r"\b(?:this|the) (?:issue|task|contribution)\b.{0,120}\b(?:is paid|will be paid|has a bounty|earns? a reward)\b",
            lower_body,
            re.DOTALL,
        )
    )


def is_radar_issue(item):
    labels = {
        str(label.get("name") or "").lower()
        for label in item.get("labels", [])
        if isinstance(label, dict)
    }
    title = str(item.get("title") or "").lower()
    body = str(item.get("body") or "").lower()
    return bool(
        labels & RADAR_LABEL_HINTS
        or re.search(r"(?:^|[\[(:-])\s*(?:bounty\s+)?(?:radar|aggregator|mirror)\b", title)
        or "外部 bounty 任务镜像" in body
        or "this bounty is now mirrored" in body
    )


def extract_linked_source_urls(text):
    labelled_patterns = (
        r"(?:原\s*URL|original\s+(?:issue|task|bounty|source)?\s*URL|source\s+URL|bounty\s+URL|task\s+URL)"
        r"\s*[:|]\s*(https?://[^\s<>|)\]]+)",
        r"\[(?:original|source|原始)(?:\s+(?:issue|task|bounty|page))?\]\((https?://[^)]+)\)",
    )
    urls = []
    for pattern in labelled_patterns:
        urls.extend(re.findall(pattern, text, re.IGNORECASE))
    urls.extend(
        re.findall(
            r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/\d+",
            text,
            re.IGNORECASE,
        )
    )
    deduplicated = []
    for url in urls:
        cleaned = url.replace("&amp;", "&").rstrip(".,;|`")
        if cleaned not in deduplicated:
            deduplicated.append(cleaned)
    return deduplicated


def fetch_github_issue_url(url, token=None):
    parsed = urllib.parse.urlparse(url)
    match = re.fullmatch(r"/([^/]+)/([^/]+)/issues/(\d+)/?", parsed.path)
    if parsed.netloc.lower() != "github.com" or not match:
        return None
    owner, repo, number = match.groups()
    payload = github_api_get(f"/repos/{owner}/{repo}/issues/{number}", token)
    if not isinstance(payload, dict) or "pull_request" in payload:
        return None
    return payload


def fetch_github_document_url(url, token=None):
    parsed = urllib.parse.urlparse(url)
    match = re.fullmatch(r"/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", parsed.path)
    if parsed.netloc.lower() != "github.com" or not match:
        return None
    owner, repo, ref, path = (urllib.parse.unquote(part) for part in match.groups())
    if not path.lower().endswith((".md", ".markdown", ".mdx")):
        return None
    encoded_repo = urllib.parse.quote(f"{owner}/{repo}", safe="/")
    encoded_path = urllib.parse.quote(path, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    payload = github_api_get(f"/repos/{encoded_repo}/contents/{encoded_path}?ref={encoded_ref}", token)
    content = decode_content_payload(payload, token)
    if not content:
        return None
    return {
        "kind": "document",
        "title": f"{owner}/{repo} — {path}",
        "project": f"{owner}/{repo}",
        "url": url,
        "text": content,
    }


def safe_public_http_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "docs.google.com", "forms.gle"} or hostname.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(hostname)
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            return False
    except ValueError:
        pass
    return True


def html_to_plain_text(content):
    without_scripts = re.sub(
        r"<(?:script|style|noscript)\b[^>]*>.*?</(?:script|style|noscript)>",
        " ",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    with_breaks = re.sub(
        r"</?(?:p|div|section|article|main|h[1-6]|li|tr|br)\b[^>]*>",
        "\n",
        without_scripts,
        flags=re.IGNORECASE,
    )
    without_tags = re.sub(r"<[^>]+>", " ", with_breaks)
    decoded = html.unescape(without_tags)
    return "\n".join(re.sub(r"\s+", " ", line).strip() for line in decoded.splitlines() if line.strip())


def fetch_external_page_source(url):
    if not safe_public_http_url(url):
        return None
    content = fetch_text_url(url)
    if not content:
        return None
    title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    page_text = html_to_plain_text(content) if "<" in content and ">" in content else content
    if len(page_text.strip()) < 80:
        return None
    parsed = urllib.parse.urlparse(url)
    page_title = clean_line(html_to_plain_text(title_match.group(1))) if title_match else ""
    return {
        "kind": "external",
        "title": page_title or f"{parsed.hostname} bounty page",
        "project": parsed.hostname,
        "project_url": f"{parsed.scheme}://{parsed.netloc}",
        "url": url,
        "text": page_text,
    }


def resolve_radar_source(item, token=None, max_hops=MAX_SOURCE_HOPS):
    """Follow a short chain of explicit GitHub source links from radar Issues."""
    if not is_radar_issue(item):
        return {"kind": "issue", "item": item}

    discovery_url = str(item.get("html_url") or "")
    current = item
    visited = {discovery_url} if discovery_url else set()
    for _ in range(max_hops):
        links = extract_linked_source_urls(str(current.get("body") or ""))
        next_radar = None
        for source_url in links:
            if source_url in visited:
                continue
            visited.add(source_url)
            linked_issue = fetch_github_issue_url(source_url, token)
            if linked_issue:
                if is_radar_issue(linked_issue):
                    next_radar = linked_issue
                    continue
                if has_issue_reward_offer(linked_issue):
                    return {"kind": "issue", "item": linked_issue, "discovered_via": discovery_url}
                continue
            parsed_source = urllib.parse.urlparse(source_url)
            source_path = parsed_source.path
            if parsed_source.netloc.lower() == "github.com" and re.fullmatch(
                r"/[^/]+/[^/]+/issues/\d+/?", source_path
            ):
                continue
            linked_document = fetch_github_document_url(source_url, token)
            if linked_document:
                linked_document["discovered_via"] = discovery_url
                return linked_document
            if parsed_source.netloc.lower() == "github.com" and re.fullmatch(
                r"/[^/]+/[^/]+/blob/[^/]+/.+", source_path
            ):
                continue
            linked_page = fetch_external_page_source(source_url)
            if linked_page:
                linked_page["discovered_via"] = discovery_url
                return linked_page
        if next_radar is None:
            return None
        current = next_radar
    return None


def extract_original_issue_url(text):
    for url in extract_linked_source_urls(text):
        if re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/\d+", url, re.IGNORECASE):
            return url
    return ""


def scan_issues(token=None, host_repo=None):
    candidates = []
    seen_api_urls = set()
    seen_search_urls = set()
    for query in ISSUE_SEARCH_QUERIES:
        log(f"Issue search: {query}")
        results = search_endpoint("issues", query, token, per_page=ISSUE_RESULTS_PER_QUERY)
        if not results:
            continue
        for search_item in results.get("items", []):
            search_url = search_item.get("html_url")
            if not search_url or search_url in seen_search_urls:
                continue
            seen_search_urls.add(search_url)
            resolved = resolve_radar_source(search_item, token)
            if not resolved:
                continue

            if resolved["kind"] in ("document", "external"):
                url = resolved["url"]
                if url in seen_api_urls:
                    continue
                seen_api_urls.add(url)
                candidate = analyze_candidate(
                    title=resolved["title"],
                    project=resolved["project"],
                    url=url,
                    source="Repository Markdown",
                    text=resolved["text"],
                )
                if candidate:
                    if resolved["kind"] == "external":
                        candidate["source"] = "External bounty page"
                        candidate["project_url"] = resolved["project_url"]
                    candidate["discovered_via"] = resolved.get("discovered_via")
                    candidates.append(candidate)
                continue

            item = resolved["item"]
            url = item.get("html_url")
            if (
                not url
                or url in seen_api_urls
                or not is_clean_issue(item, host_repo)
                or not has_issue_reward_offer(item)
            ):
                continue
            seen_api_urls.add(url)
            text = "\n".join((str(item.get("title") or ""), str(item.get("body") or "")))
            repo = str(item.get("repository_url", "")).split("/repos/")[-1]
            if not repo:
                repo = url.removeprefix("https://github.com/").split("/issues/")[0]
            candidate = analyze_candidate(
                title=str(item.get("title") or "Untitled bounty"),
                project=repo,
                url=url,
                source="GitHub Issue",
                text=text,
                comments=item.get("comments"),
                updated_at=item.get("updated_at"),
            )
            if candidate:
                if resolved.get("discovered_via"):
                    candidate["discovered_via"] = resolved["discovered_via"]
                candidates.append(candidate)
    return candidates


def candidate_markdown_path(path):
    lower = path.lower()
    if not lower.endswith((".md", ".markdown", ".mdx")):
        return False
    basename = lower.rsplit("/", 1)[-1]
    return basename.startswith(("readme", "contributing")) or any(
        term in lower for term in ("bounty", "challenge", "reward", "prize", "contribut")
    )


def fetch_code_search_documents(token):
    documents = []
    seen_urls = set()
    search_worked = False
    for label, query in DOCUMENT_SEARCH_QUERIES:
        log(f"Markdown code search: {label}")
        results = search_endpoint("code", query, token, per_page=DOCUMENT_RESULTS_PER_QUERY)
        if results is None:
            continue
        search_worked = True
        for item in results.get("items", []):
            if len(documents) >= MAX_DOCUMENTS_TO_FETCH:
                return documents, search_worked
            url = item.get("html_url")
            repository = item.get("repository") or {}
            if not url or url in seen_urls or repository.get("archived"):
                continue
            seen_urls.add(url)
            payload = github_api_get(item.get("url", ""), token)
            content = decode_content_payload(payload, token)
            if content:
                documents.append(
                    {
                        "title": f"{repository.get('full_name', 'Unknown repository')} — {item.get('path', item.get('name', 'Markdown'))}",
                        "project": repository.get("full_name", "Unknown repository"),
                        "url": url,
                        "text": content,
                    }
                )
    return documents, search_worked


def repository_document_payload(repo, path, token=None):
    encoded_repo = urllib.parse.quote(repo, safe="/")
    encoded_path = urllib.parse.quote(path, safe="/")
    payload = github_api_get(f"/repos/{encoded_repo}/contents/{encoded_path}", token)
    return decode_content_payload(payload, token)


def fetch_readme_fallback_documents(token=None):
    """Discover README matches, then inspect a few clearly named Markdown files."""
    repositories = {}
    for term in README_SEARCH_TERMS:
        query = f'"{term}" in:readme archived:false'
        log(f"README repository search: {term}")
        results = search_endpoint("repositories", query, token)
        if not results:
            continue
        for repository in results.get("items", []):
            full_name = repository.get("full_name")
            if full_name and full_name not in repositories and len(repositories) < MAX_FALLBACK_REPOSITORIES:
                repositories[full_name] = repository

    documents = []
    seen_urls = set()
    for full_name, repository in repositories.items():
        encoded_repo = urllib.parse.quote(full_name, safe="/")
        readme_payload = github_api_get(f"/repos/{encoded_repo}/readme", token)
        readme = decode_content_payload(readme_payload, token)
        if readme and readme_payload.get("html_url") not in seen_urls:
            url = readme_payload.get("html_url") or repository.get("html_url")
            seen_urls.add(url)
            documents.append({"title": f"{full_name} — README", "project": full_name, "url": url, "text": readme})

        branch = urllib.parse.quote(str(repository.get("default_branch") or "main"), safe="")
        tree = github_api_get(f"/repos/{encoded_repo}/git/trees/{branch}?recursive=1", token)
        if not tree:
            continue
        paths = [
            node.get("path")
            for node in tree.get("tree", [])
            if node.get("type") == "blob" and node.get("path") and candidate_markdown_path(node["path"])
        ]
        non_readmes = [path for path in paths if not path.lower().rsplit("/", 1)[-1].startswith("readme")]
        for path in non_readmes[:3]:
            url = f"https://github.com/{full_name}/blob/{repository.get('default_branch', 'main')}/{path}"
            if url in seen_urls:
                continue
            content = repository_document_payload(full_name, path, token)
            if content:
                seen_urls.add(url)
                documents.append({"title": f"{full_name} — {path}", "project": full_name, "url": url, "text": content})
    return documents


def scan_documents(token=None):
    documents = []
    code_search_worked = False
    if token:
        documents, code_search_worked = fetch_code_search_documents(token)
    if not token or not code_search_worked:
        if not token:
            log("No GITHUB_TOKEN: using lower-coverage README fallback (authenticated code search is recommended).")
        else:
            log("Code search was unavailable: using README fallback.")
        documents = fetch_readme_fallback_documents(token)

    candidates = []
    for document in documents:
        candidate = analyze_candidate(
            title=document["title"],
            project=document["project"],
            url=document["url"],
            source="Repository Markdown",
            text=document["text"],
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def deduplicate_and_rank(candidates):
    """Prefer the richer/highest-scoring form when the same URL appears twice."""
    by_url = {}
    by_title = {}
    for candidate in candidates:
        old = by_url.get(candidate["url"])
        if old is None or candidate["score"] > old["score"]:
            by_url[candidate["url"]] = candidate
    for candidate in by_url.values():
        normalized_title = re.sub(
            r"\s+#\d+\s*$",
            "",
            str(candidate.get("title") or candidate["url"]).lower(),
        ).strip()
        key = (str(candidate.get("project") or "").lower(), normalized_title)
        old = by_title.get(key)
        if old is None or candidate["score"] > old["score"]:
            by_title[key] = candidate
    return sorted(
        by_title.values(),
        key=lambda item: (item["score"], item.get("updated_at") or ""),
        reverse=True,
    )


def format_plain_notification(candidates, now_str, limit=3900):
    lines = [f"🎯 New Micro Bounty Alert ({now_str})", f"Found {len(candidates)} new opportunities:", ""]
    for index, candidate in enumerate(candidates, 1):
        entry = [
            f"{index}. {candidate['title']}",
            f"Project: {candidate['project']}",
            f"Source: {candidate['source']}",
            f"Reward: {candidate['reward']}",
            f"Task: {candidate['task']}",
            f"Deadline: {candidate['deadline']}",
            f"Submit: {candidate['submission']}",
            f"Payment: {candidate['payment_method']}",
            f"Coding Agent: {candidate['agent_fit']}",
            f"Effort: {candidate['effort']}",
        ]
        if candidate.get("comments") is not None:
            entry.append(f"Original comments: {candidate['comments']}")
        if candidate.get("discovered_via"):
            entry.append(f"Discovered via: {candidate['discovered_via']}")
        entry.extend((f"Link: {candidate['url']}", ""))
        proposed = "\n".join(lines + entry)
        if len(proposed) > limit:
            remaining = len(candidates) - index + 1
            lines.append(f"…and {remaining} more; see the GitHub alert or dry-run output.")
            break
        lines.extend(entry)
    return "\n".join(lines).strip()


def format_github_issue_body(candidates, now_str):
    lines = ["### Active Micro Bounty Scan Results", "", f"**Scan Time:** {now_str}", ""]
    for index, candidate in enumerate(candidates, 1):
        project_url = candidate.get("project_url", "https://github.com/" + candidate["project"])
        lines.extend(
            [
                f"#### {index}. [{candidate['title']}]({candidate['url']})",
                f"- **Project:** [{candidate['project']}]({project_url})",
                f"- **Source:** {candidate['source']}",
                f"- **Reward:** {candidate['reward']}",
                f"- **Task:** {candidate['task']}",
                f"- **Deadline:** {candidate['deadline']}",
                f"- **Submission:** {candidate['submission']}",
                f"- **Payment method:** {candidate['payment_method']}",
                f"- **Coding Agent fit:** {candidate['agent_fit']}",
                f"- **Estimated effort:** {candidate['effort']}",
            ]
        )
        if candidate.get("discovered_via"):
            lines.append(f"- **Discovered via:** {candidate['discovered_via']}")
        if candidate.get("comments") is not None:
            lines.append(f"- **Original Issue comments:** {candidate['comments']}")
        if candidate.get("updated_at"):
            lines.append(f"- **Last updated:** {candidate['updated_at']}")
        lines.append("")
    lines.append(
        "> Payment methods are reported only when explicitly mentioned by the source; 待确认 means manual verification is required."
    )
    return "\n".join(lines)


def post_json(url, payload, headers, timeout=15):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout):
        return True


def send_telegram_notification(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        post_json(
            url,
            {"chat_id": chat_id, "text": message, "disable_web_page_preview": False},
            {"Content-Type": "application/json"},
            10,
        )
        log("Telegram notification sent successfully.")
    except (urllib.error.URLError, TimeoutError) as exc:
        log(f"Failed to send Telegram notification: {exc}")


def send_discord_notification(webhook_url, message):
    try:
        post_json(webhook_url, {"content": message[:1990]}, {"Content-Type": "application/json"}, 10)
        log("Discord notification sent successfully.")
    except (urllib.error.URLError, TimeoutError) as exc:
        log(f"Failed to send Discord notification: {exc}")


def create_github_issue(repo_fullname, token, title, body):
    url = f"{API_ROOT}/repos/{repo_fullname}/issues"
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "BountyScout-MicroChallengeScanner",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }
    try:
        post_json(url, {"title": title, "body": body, "labels": ["bounty-alert"]}, headers)
        log("GitHub Issue notification created successfully.")
    except (urllib.error.URLError, TimeoutError) as exc:
        log(f"Failed to create GitHub Issue notification: {exc}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Scan GitHub for small paid engineering opportunities.")
    parser.add_argument("--dry-run", action="store_true", help="print results without notifications or state changes")
    parser.add_argument("--include-seen", action="store_true", help="include URLs already present in the state file")
    parser.add_argument("--source", choices=("all", "issues", "docs"), default="all", help="limit discovery source")
    parser.add_argument("--json", action="store_true", help="print candidates as JSON (best combined with --dry-run)")
    parser.add_argument(
        "--max-results",
        type=int,
        default=int(os.environ.get("BOUNTYSCOUT_MAX_RESULTS", DEFAULT_MAX_RESULTS)),
        help=f"maximum new results to notify (default: {DEFAULT_MAX_RESULTS})",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.max_results < 1:
        raise SystemExit("--max-results must be at least 1")

    github_token = os.environ.get("GITHUB_TOKEN")
    repo_fullname = os.environ.get("GITHUB_REPOSITORY")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")

    seen_urls = load_seen_bounties()
    candidates = []
    log("Scouting GitHub for micro bounties and engineering challenges...")
    if args.source in ("all", "issues"):
        candidates.extend(scan_issues(github_token, repo_fullname))
    if args.source in ("all", "docs"):
        candidates.extend(scan_documents(github_token))

    ranked = deduplicate_and_rank(candidates)
    if not args.include_seen:
        ranked = [candidate for candidate in ranked if candidate["url"] not in seen_urls]
    selected = ranked[: args.max_results]

    if args.json:
        print(json.dumps(selected, indent=2, ensure_ascii=False))
    elif selected:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(format_plain_notification(selected, now_str, limit=12000 if args.dry_run else 3900))

    if not selected:
        log("No matching new opportunities found.")
        return 0
    log(f"Discovered {len(selected)} matching opportunities.")

    if args.dry_run:
        log("Dry run: notifications and state updates were skipped.")
        return 0

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    notification = format_plain_notification(selected, now_str)
    if telegram_token and telegram_chat_id:
        send_telegram_notification(telegram_token, telegram_chat_id, notification)
    if discord_webhook:
        send_discord_notification(discord_webhook, notification)
    if github_token and repo_fullname:
        title = f"🎯 Micro Bounty Alert: {len(selected)} New Opportunit{'y' if len(selected) == 1 else 'ies'}"
        create_github_issue(repo_fullname, github_token, title, format_github_issue_body(selected, now_str))

    seen_urls.update(candidate["url"] for candidate in selected)
    save_seen_bounties(seen_urls)
    log("State saved successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
