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
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


STATE_FILE = "seen_bounties.json"
API_ROOT = "https://api.github.com"
MAX_COMMENTS = 25
DEFAULT_MAX_RESULTS = 20
SEARCH_RESULTS_PER_QUERY = 10
ISSUE_RESULTS_PER_QUERY = 50
MAX_DOCUMENTS_TO_FETCH = 60
MAX_FALLBACK_REPOSITORIES = 12
DOCUMENT_RESULTS_PER_QUERY = 6
CODE_SEARCH_INTERVAL_SECONDS = 7
MAX_RATE_LIMIT_RETRIES = 3
RATE_LIMIT_FALLBACK_SECONDS = 60
FILTER_SAMPLE_LIMIT = 7
MAX_DISCOVERY_TARGETS = 12

# Keep the legacy Issue scan, but broaden the vocabulary beyond "bounty".
ISSUE_SEARCH_QUERIES = [
    "is:issue is:open bounty in:title,body sort:updated-desc",
    'is:issue is:open "cash prize" in:title,body sort:updated-desc',
    'is:issue is:open "paid challenge" in:title,body sort:updated-desc',
    'is:issue is:open "paid contribution" in:title,body sort:updated-desc',
    'is:issue is:open "paid PR" in:title,body sort:updated-desc',
    'is:issue is:open "contributor reward" in:title,body sort:updated-desc',
    'is:issue is:open "paid task" in:title,body sort:updated-desc',
    'is:issue is:open "cash reward" in:title,body sort:updated-desc',
    "is:issue is:open payment in:title,body sort:updated-desc",
    "is:issue is:open payout in:title,body sort:updated-desc",
    "is:issue is:open compensation in:title,body sort:updated-desc",
    "is:issue is:open reward in:title,body sort:updated-desc",
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
    ('paid after merge', '"paid after merge" language:Markdown'),
    ('paid upon acceptance', '"paid upon acceptance" language:Markdown'),
    ('payment after accepted PR', '"payment after accepted PR" language:Markdown'),
    ('compensation + Pull Request', 'compensation "pull request" language:Markdown'),
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
    "compensation",
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
    "paid task",
    "paid after merge",
    "paid upon acceptance",
    "payment after accepted pr",
    "monetary reward",
    "bounty",
)
GENERIC_REWARD_TERMS = ("reward", "prize", "payment", "payout", "compensation")
REWARD_INTENT_TERMS = ("bounty", "reward", "prize", "payout", "cash", "paid", "compensation", "winner")
NON_CASH_REWARD_PATTERNS = (
    ("京东卡", r"京东卡"),
    ("礼品卡", r"礼品卡|购物卡|代金券|\bgift cards?\b|\bstore credits?\b|\bvouchers?\b"),
    ("积分", r"积分|\bpoints?\b|\bcredits?\b"),
    ("证书", r"证书|\bcertificates?\b"),
    ("实物", r"实物|奖品|\bswag\b|\bmerch(?:andise)?\b|\bphysical (?:gift|prize|item)\b"),
)
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
    "multi-milestone",
    "multi milestone",
    "semester-long",
    "12-week",
    "six months",
    "long-term commitment",
    "full security audit",
    "large empirical reproduction",
    "long-running project",
    "long running project",
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
PRODUCT_BILLING_TERMS = (
    "stripe checkout",
    "stripe credit pack",
    "stripe-metered",
    "stripe_payment_id",
    "paymentsheet",
    "payment intent",
    "paymentintent",
    "destination charge",
    "platform fee",
    "application fee",
    "card charge",
    "charged a real card",
    "monthly prices",
    "customer portal",
    "revenuecat",
    "subscription price",
    "subscription tier",
    "credit pack",
    "credit pricing",
    "credit cost",
    "customer billing",
    "customer purchase",
    "billable tool",
    "api usage price",
    "tool usage price",
    "paid api",
    "paid resource",
    "endpoint charges",
    "pricing is per",
    "price per proof",
    "x-payment-info",
)
NON_REWARD_FINANCIAL_PATTERNS = (
    r"\bgovernment (?:funding|top-up|spending|expenditure)\b",
    r"\bmarket size\b",
    r"\bannual revenue\b",
    r"\b(?:financial|actuarial|economic) assumptions?\b",
    r"\b(?:publisher|source) (?:facts?|figures?|cells?|values?)\b",
    r"\b(?:customer|account) (?:balance|billing|charge|payment)\b",
    r"\b(?:benefit|entitlement|pension) (?:amount|value|income|payment|funding)\b",
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
    (
        "RTC",
        r"\b\d+(?:\.\d+)?\s*rtc\b|\b(?:auto[- ]?pays?|payout|paid only in|payment in)\b.{0,40}\brtc\b"
        r"|\brtc\b.{0,40}\b(?:token|wallet|address)\b",
    ),
    ("ETH", r"\beth\b|\bether\b"),
    ("SOL", r"\bsol\b"),
    ("链上钱包", r"\bon[- ]chain (?:wallet|address)\b|\bcrypto(?:currency)? wallet\b"),
    ("支付宝", r"\balipay\b|支付宝"),
    ("微信支付", r"\bwechat pay\b|微信支付"),
)

FIAT_PAYMENT_METHODS = {"PayPal", "Wise", "Stripe", "银行转账", "支付宝", "微信支付"}
CRYPTO_PAYMENT_METHODS = {"USDC", "USDT", "DAI", "BTC", "sats", "XLM", "RTC", "ETH", "SOL", "链上钱包"}

# Platform payout rules are applied only when an official source explicitly
# documents the payout rail. Platform names that are not listed here remain
# unknown instead of being guessed from their branding or ecosystem.
VERIFIED_PLATFORM_PAYMENT_RULES = (
    {
        "name": "GrantFox",
        "issue_labels": {"grantfox oss"},
        "source_hosts": {"grantfox.xyz", "docs.grantfox.xyz", "contribute.grantfox.xyz"},
        "text_patterns": (r"\bgrantfox\s+(?:oss|campaign|reward|rewards)\b",),
        "methods": ("USDC",),
        "crypto_only": True,
        "evidence_url": "https://docs.grantfox.xyz/core-info/what-is-grantfox",
    },
)

RADAR_LABEL_HINTS = {"radar", "aggregator", "external-mirror", "bounty-hunter", "mirror"}
MAX_SOURCE_HOPS = 3

FIRST_WIN_PATTERNS = (
    r"\bfirst\s+(?:merged|accepted|valid)(?:\s+(?:pr|pull request|submission|solution))?(?:\s+wins?)?\b",
    r"\bfirst\s+(?:pr|pull request|submission|solution)\s+(?:merged|accepted|valid)\s+wins?\b",
    r"\bfirst\s+(?:to be\s+)?(?:merged|accepted)\s+(?:wins?|gets? paid|is rewarded)\b",
)

AMOUNT_PATTERNS = (
    r"(?:US\$|USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|RTC|ETH|SOL|USDT|DAI|BTC|€|£|¥|₹|\$)\s*"
    r"\d[\d,]*(?:\.\d+)?(?:\s*(?:USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|RTC|ETH|SOL|USDT|DAI|BTC))?"
    r"(?:\s*[-–—]\s*(?:(?:US\$|USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|RTC|ETH|SOL|USDT|DAI|BTC|€|£|¥|₹|\$)\s*)?\d[\d,]*(?:\.\d+)?)?",
    r"\b\d[\d,]*(?:\.\d+)?\s*(?:USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|RTC|ETH|SOL|USDT|DAI|BTC)\b",
)


def log(message):
    print(message, file=sys.stderr)


def add_diagnostic_sample(samples, reason, url):
    if not url:
        return
    urls = samples.setdefault(reason, [])
    if url not in urls and len(urls) < FILTER_SAMPLE_LIMIT:
        urls.append(url)


def log_diagnostic_samples(source, samples):
    for reason in sorted(samples):
        log(f"{source} triage sample [{reason}]: {', '.join(samples[reason])}")


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


def response_header(headers, name):
    if not headers:
        return ""
    value = headers.get(name)
    if value is None:
        value = headers.get(name.lower())
    return str(value or "").strip()


def rate_limit_wait_seconds(error, message, retry_index):
    """Return GitHub's required wait and its source, or None for non-rate errors."""
    if error.code not in (403, 429):
        return None
    headers = error.headers or {}
    retry_after = response_header(headers, "Retry-After")
    if retry_after:
        try:
            return max(1, math.ceil(float(retry_after))), "Retry-After"
        except ValueError:
            pass

    remaining = response_header(headers, "X-RateLimit-Remaining")
    reset = response_header(headers, "X-RateLimit-Reset")
    if remaining == "0" and reset:
        try:
            return max(1, math.ceil(float(reset) - time.time())), "X-RateLimit-Reset"
        except ValueError:
            pass

    lower_message = message.lower()
    rate_limited = error.code == 429 or "rate limit" in lower_message or "abuse" in lower_message
    if not rate_limited:
        return None
    return RATE_LIMIT_FALLBACK_SECONDS * (2**retry_index), "exponential backoff"


def normalized_request_url(url):
    """Percent-encode raw path/query characters returned by GitHub search."""
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%:@-._~!$&'()*+,;=")
    query = urllib.parse.quote(parts.query, safe="=&%:@/?+-._~!$'()*;,")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def github_api_get(
    url,
    token=None,
    accept="application/vnd.github+json",
    max_rate_limit_retries=MAX_RATE_LIMIT_RETRIES,
):
    """Return decoded JSON, retrying bounded GitHub rate-limit responses."""
    if url.startswith("/"):
        url = API_ROOT + url
    url = normalized_request_url(url)
    headers = {
        "Accept": accept,
        "User-Agent": "BountyScout-MicroChallengeScanner",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for retry_index in range(max_rate_limit_retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = ""
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                message = str(payload.get("message") or "")
            except (ValueError, UnicodeDecodeError):
                pass
            detail = f": {message}" if message else ""
            log(f"GitHub API {exc.code} for {url}{detail}")
            retry = rate_limit_wait_seconds(exc, message, retry_index)
            if retry is None or retry_index >= max_rate_limit_retries:
                return None
            delay, source = retry
            log(
                f"GitHub rate limit: waiting {delay}s from {source} "
                f"before retry {retry_index + 1}/{max_rate_limit_retries}."
            )
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            log(f"GitHub API error for {url}: {exc}")
            return None
    return None


def search_endpoint(endpoint, query, token=None, per_page=SEARCH_RESULTS_PER_QUERY):
    params = urllib.parse.urlencode({"q": query, "per_page": per_page})
    accept = "application/vnd.github.text-match+json, application/vnd.github+json"
    return github_api_get(f"/search/{endpoint}?{params}", token, accept=accept)


BLOCKED_HTTP_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.internal",
        "kubernetes.default.svc",
    }
)
BLOCKED_HTTP_HOST_SUFFIXES = (".local", ".internal")
GITHUB_REDIRECT_HOST_SUFFIXES = (
    ".github.com",
    ".githubusercontent.com",
    ".github.io",
)


def _parse_ip_literal(hostname):
    """Parse decimal/hex/octal and shortened dotted IP encodings used in SSRF bypasses."""
    if not hostname:
        return None
    candidate = hostname.strip().lower()
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        pass

    if re.fullmatch(r"\d{1,10}", candidate):
        value = int(candidate)
        if 0 <= value <= 0xFFFFFFFF:
            try:
                return ipaddress.ip_address(value)
            except ValueError:
                return None

    if re.fullmatch(r"0x[0-9a-f]{1,8}", candidate):
        value = int(candidate, 16)
        if value <= 0xFFFFFFFF:
            try:
                return ipaddress.ip_address(value)
            except ValueError:
                return None

    if "." not in candidate:
        return None

    parts = candidate.split(".")
    if not 1 <= len(parts) <= 4:
        return None
    numbers = []
    for part in parts:
        if not part:
            return None
        if re.fullmatch(r"0x[0-9a-f]+", part):
            numbers.append(int(part, 16))
        elif len(part) > 1 and part.startswith("0") and part[1:].isdigit():
            numbers.append(int(part, 8))
        elif re.fullmatch(r"\d+", part):
            numbers.append(int(part))
        else:
            return None
    while len(numbers) < 4:
        numbers.append(0)
    if len(numbers) != 4 or any(number < 0 or number > 255 for number in numbers):
        return None
    packed = (numbers[0] << 24) | (numbers[1] << 16) | (numbers[2] << 8) | numbers[3]
    try:
        return ipaddress.ip_address(packed)
    except ValueError:
        return None


def _is_blocked_http_host(hostname):
    lowered = (hostname or "").strip().lower()
    if not lowered:
        return True
    if lowered in BLOCKED_HTTP_HOSTNAMES or lowered.endswith(BLOCKED_HTTP_HOST_SUFFIXES):
        return True
    address = _parse_ip_literal(lowered)
    if address is not None:
        return (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
        )
    return False


def _is_github_redirect_host(hostname):
    lowered = (hostname or "").strip().lower()
    return lowered == "github.com" or lowered.endswith(GITHUB_REDIRECT_HOST_SUFFIXES)


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects to private/internal targets when fetching untrusted URLs."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _is_github_redirect_host(urllib.parse.urlparse(req.full_url).hostname):
            if _is_github_redirect_host(urllib.parse.urlparse(newurl).hostname):
                return urllib.request.HTTPRedirectHandler.redirect_request(
                    self, req, fp, code, msg, headers, newurl
                )
        if not safe_public_http_url(newurl):
            return None
        return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)


def fetch_text_url(url, token=None, restrict_redirects=False):
    headers = {"User-Agent": "BountyScout-MicroChallengeScanner"}
    if token and url.startswith(API_ROOT):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    opener = (
        urllib.request.build_opener(SafeRedirectHandler())
        if restrict_redirects
        else urllib.request.build_opener()
    )
    try:
        with opener.open(request, timeout=25) as response:
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


def extract_structured_reward_amount(text):
    """Read common Reward currency / Reward amount field pairs."""
    text = "\n".join(clean_line(line.lstrip()) for line in text.splitlines())
    currency_match = re.search(
        r"(?:^|\n)\s*(?:reward currency|奖励币种)\s*:?[ \t]*\n\s*([A-Z]{3}(?:\s+[A-Z]{3})?|人民币|RMB|CNY)",
        text,
        re.IGNORECASE,
    )
    amount_match = re.search(
        r"(?:^|\n)\s*(?:reward amount|奖励金额)\s*:?[ \t]*\n\s*(\d[\d,]*(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if not currency_match or not amount_match:
        return ""
    currency_text = currency_match.group(1).upper()
    if "RMB" in currency_text or "CNY" in currency_text or "人民币" in currency_match.group(1):
        currency_text = "RMB"
    return f"{amount_match.group(1)} {currency_text}"


def extract_reward_amounts(text):
    """Prefer amounts on reward lines over prices mentioned elsewhere nearby."""
    structured = extract_structured_reward_amount(text)
    if structured:
        return [structured]
    lines = text.splitlines()
    selected = set()
    for index, line in enumerate(lines):
        lower = line.lower()
        if any(term in lower for term in REWARD_INTENT_TERMS):
            selected.update(range(index, min(len(lines), index + 2)))
    focused = "\n".join(lines[index] for index in sorted(selected))
    # If the source has explicit reward wording, unrelated prices elsewhere in
    # the page must not become the fallback bounty amount.
    return extract_amounts(focused) if selected else extract_amounts(text)


def has_explicit_no_current_reward(text):
    """Return true when the source explicitly denies a funded/current task."""
    return bool(
        re.search(
            r"\bproduction payouts? (?:are |is )?not live yet\b"
            r"|\bpayment capture remains disabled\b|\bpayouts? (?:are |is )?disabled\b"
            r"|\b(?:this|it) does(?: not|n't) promise an award\b"
            r"|\b(?:must not|cannot|can't) (?:choose or imply|authori[sz]e) payment\b"
            r"|\bcannot become paid\b"
            r"|\b(?:this (?:issue|task) )?does(?: not|n't) have any rewards? yet\b"
            r"|\b(?:no|without) (?:current )?(?:monetary )?(?:bounty|rewards?) yet\b"
            r"|\bno reward (?:has been )?added yet\b"
            r"|\bzero[- ]bounty\b|\bzero monetary rewards?\b"
            r"|\b(?:this|the) (?:issue|task) is unfunded\b|\bunfunded\b|\bnot funded\b"
            r"|\bnot a build ticket\b"
            r"|\b(?:bounty|reward)\s*[:=]\s*(?:\$?0(?:\.0+)?|none)\b",
            text,
            re.IGNORECASE,
        )
    )


def has_generic_backing_template(text):
    return bool(
        re.search(
            r"\beveryone can add rewards?\b"
            r"|\bpost a bounty\b"
            r"|\bwant to back this issue\b"
            r"|\b(?:sponsor|fund|back) this issue\b"
            r"|\badd (?:a |your )?(?:bounty|reward) to this issue\b",
            text,
            re.IGNORECASE,
        )
    )


def has_current_reward_evidence(text, reward_label=False):
    """Recognize positive evidence that this task is currently funded."""
    amount = "(?:" + "|".join(AMOUNT_PATTERNS) + ")"
    explicit_amount = (
        r"(?:^|\n|[.!?]\s+)\s*(?:#{1,6}\s*)?(?:[*_]{0,2})?(?:current\s+)?"
        r"(?:bounty|reward|payout)(?:\s+amount)?(?:[*_]{0,2})?\s*[:|=–—-]\s*" + amount
        + r"|(?:^|\n)[^\n]{0,30}\[(?:bounty|reward)\][^\n]{0,140}" + amount
        + r"|\b(?:this|the|current) (?:issue|task)\b[^.\n]{0,100}"
        r"\b(?:has|offers?|is funded (?:with|for))\b[^.\n]{0,60}" + amount
        + r"|\b(?:added|pledged|funded)\b[^.\n]{0,80}" + amount
        + r"[^.\n]{0,80}\b(?:bounty|reward)\b"
    )
    if re.search(explicit_amount, text, re.IGNORECASE):
        return True
    if re.search(
        r"\b(?:this|the) (?:issue|task|bounty) (?:is|has been) funded\b"
        r"|\bfunded (?:bounty|reward)\b"
        r"|\b(?:bounty|reward) bot\b.{0,120}\bconfirmed\b",
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        return True
    first_line = text.splitlines()[0] if text.splitlines() else ""
    return bool(
        reward_label
        and re.search(amount, first_line, re.IGNORECASE)
        and re.search(r"\b(?:bounty|reward|paid task|cash)\b", first_line, re.IGNORECASE)
    )


def has_direct_contributor_offer_evidence(text):
    """Recognize a payout specifically offered for completing a contribution."""
    contributor = (
        r"(?:contributors?|submitters?|participants?|entrants?|winners?"
        r"|accepted (?:pr|pull request|submission)|merged? (?:pr|pull request))"
    )
    payout = r"(?:claim|earn|receive (?:a |the )?(?:cash|payment|payout)|get paid|be paid|paid|payout|compensation)"
    return bool(
        re.search(contributor + r".{0,180}\b" + payout + r"\b", text, re.IGNORECASE | re.DOTALL)
        or re.search(
            r"\b(?:paid|payment|payout|compensation)\b.{0,80}\b(?:after|upon)\s+(?:the\s+)?"
            r"(?:merge|acceptance|accepted (?:pr|pull request)|completion)\b",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        or re.search(
            r"\b(?:payment|payout|compensation)\b.{0,80}\b(?:to|for)\s+" + contributor + r"\b",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    )


def has_direct_bounty_offer_evidence(text):
    """Return true for a current/direct task offer rather than monetary context."""
    action = r"(?:fix|implement|build|create|write|test|document|submit|complete|pull request|contribution)"
    reward = r"(?:bounty|cash reward|cash prize|payout|compensation)"
    return bool(
        has_current_reward_evidence(text)
        or has_direct_contributor_offer_evidence(text)
        or re.search(
            r"(?:^|\n)\s*\[bounty\]\s+\S"
            r"|(?:^|\n)\s*(?:#{1,6}\s*)?(?:\[[^]]+\]\s*)?(?:bounty|cash prize|cash reward)\s*[:–—-]"
            r"|\bpaid\b.{0,50}\bbounty\b"
            r"|\b(?:claim|earn)\b.{0,80}\b(?:the\s+)?bounty\b"
            r"|\b" + action + r"\b.{0,120}\b(?:to claim|for)\s+(?:a |the )?" + reward + r"\b"
            r"|\b" + reward + r"\b.{0,120}\b(?:for|to)\s+(?:the\s+)?" + action + r"\b",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    )


def is_historical_reward_summary(title, text):
    title_lower = title.lower()
    if re.search(
        r"\bhall of fame\b|\bleaderboard\b|\bmonthly stats?\b|\bpast (?:payouts?|winners?)\b",
        title_lower,
    ) and not has_current_reward_evidence(text):
        return True
    history_patterns = (
        r"\bhall of fame\b",
        r"\bleaderboard\b",
        r"\btotal bounty distributed\b",
        r"\btotal earned\b",
        r"\bmonthly stats?\b",
        r"\bpast payouts?\b",
        r"\bpast winners?\b",
    )
    hits = sum(bool(re.search(pattern, text, re.IGNORECASE)) for pattern in history_patterns)
    return hits >= 2 and not has_current_reward_evidence(text)


def is_product_billing_only(text):
    lower = text.lower()
    if not any(term in lower for term in PRODUCT_BILLING_TERMS):
        return False
    return not has_direct_bounty_offer_evidence(text)


def is_non_reward_financial_context(text):
    """Reject business/statistical money figures without a contributor offer."""
    if has_direct_bounty_offer_evidence(text):
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in NON_REWARD_FINANCIAL_PATTERNS)


def is_discovery_source_document(text):
    """Identify general program/index pages that should lead to concrete tasks."""
    lower = text.lower()
    specific_task = re.search(
        r"(?:^|\n)\s*(?:#{1,6}\s*)?(?:task|work item|deliverable)\s*[:–—-]"
        r"|(?:^|\n)\s*(?:#{1,6}\s*)?\[(?:bounty|reward)\]\s+[^\n]+",
        lower,
    )
    if specific_task and has_current_reward_evidence(text):
        return False

    general_range = re.search(
        r"\breward ranges?\b|\bcategory\b[^\n|]{0,40}\breward\b"
        r"|\b(?:small|medium|major) features?\b.{0,80}(?:\$|usd|eur|gbp|rmb|cny)\s*\d"
        r"|(?:\$|usd|eur|gbp|rmb|cny)\s*\d[^\n]{0,30}\bfor (?:bug fixes|guides|documentation|features|vulnerabilities)\b",
        lower,
        re.DOTALL,
    )
    marketplace = re.search(
        r"\b(?:bounty |task )?(?:marketplace|market|platform|community)\b.{0,180}"
        r"\b(?:browse|find|list|post|discover|claim)\b.{0,80}\b(?:bount(?:y|ies)|tasks?|issues?)\b",
        lower,
        re.DOTALL,
    )
    program_signals = sum(
        term in lower
        for term in (
            "bounty program",
            "how to claim bounties",
            "find issue tagged",
            "current bounty tasks",
            "active bounties",
            "browse github issues",
        )
    )
    table_rows = len(re.findall(r"^\s*\|[^\n]+\|\s*$", text, re.MULTILINE))
    competition_directory = bool(
        table_rows >= 4
        and re.search(r"\b(?:competition|contest|challenge)s?\b", lower)
        and re.search(r"(?:/archive\b|\barchived?\b|\bpast competitions?\b)", lower)
    )
    return bool(general_range or marketplace or program_signals >= 2 or competition_directory)


def has_task_contributor_reward_link(text, reward_label=False):
    """Require evidence that the reward belongs to this contribution task."""
    lower = text.lower()
    if has_explicit_no_current_reward(text):
        return False
    if has_generic_backing_template(text) and not has_current_reward_evidence(text, reward_label):
        return False
    if is_product_billing_only(text):
        return False
    if re.search(
        r"\b(?:no|not offering|without)\s+(?:a\s+)?(?:cash\s+)?(?:bug\s+)?(?:bounty|reward|prize)\b"
        r"|\b(?:can't|cannot|can not|unable to)\s+offer\s+(?:any\s+)?(?:cash\s+)?(?:bounty|reward|prize)\b"
        r"|\b(?:this|the) (?:task|issue|contribution) (?:is )?(?:unpaid|not paid)\b"
        r"|\bdo not (?:offer|pay)\b",
        lower,
    ):
        return False

    if reward_label and re.search(
        r"\b(?:fix|implement|add|build|create|write|test|document|submit|contribute)\b"
        r"|修复|实现|提交|贡献|测评|文档|测试",
        lower,
    ):
        return True

    game_context = re.search(
        r"\b(?:game|gameplay|player|inventory|boss|shop|minecraft|server economy|in-game|gamestate)\b",
        lower,
    )
    external_offer_marker = re.search(
        r"\b(?:bounty|cash prize|cash reward|paid task|paid contribution|contributors?|submit|pull request)\b"
        r"|提交|贡献者|悬赏|现金奖励",
        lower,
    )
    if game_context and not external_offer_marker:
        return False

    explicit_offer = re.search(
        r"(?:^|\n)\s*(?:[^\w\n]{0,4}\s*)?(?:bounty|cash prize|cash reward)"
        r"\s*(?::|[-–—]|\n)"
        r"|(?:^|\n)\s*\[(?:bounty|reward)\]"
        r"|\b(?:cash prize|cash reward|monetary reward|paid task|paid challenge|paid pr|paid issue)\b"
        r"|\b(?:we|maintainers?|organizers?)\s+(?:will\s+)?(?:pay|award|reward)\b"
        r"|\b(?:we|maintainers?|organizers?)\s+(?:will\s+)?offer\b.{0,100}"
        r"\b(?:bounty|cash reward|cash prize|compensation)\b"
        r"|(?:\bwill pay\b|\b(?:we|maintainers?|organizers?)\s+(?:are\s+)?offering\b)"
        r".{0,100}(?:\d|bounty|reward|prize)"
        r"|(?:奖励形式|奖励金额|报酬|悬赏)\s*[:：]",
        lower,
        re.DOTALL,
    )
    if explicit_offer:
        return True

    completion_payment = re.search(
        r"\b(?:paid|payment|payout|compensation)\b.{0,40}\b(?:after|upon)\s+(?:the\s+)?"
        r"(?:merge|acceptance|accepted (?:pr|pull request)|completion)\b"
        r"|\b(?:after|upon)\s+(?:the\s+)?(?:merge|acceptance|accepted (?:pr|pull request)|completion)\b"
        r".{0,40}\b(?:paid|payment|payout|compensation)\b",
        lower,
        re.DOTALL,
    )
    if completion_payment:
        return True

    reward_heading = r"(?:^|\n)\s*(?:[^\w\n]{0,4}\s*)?reward\s*(?::|[-–—]|\n)"
    coding_action = r"(?:\b(?:fix|implement|add|create|write|test|document)\b|修复|实现|编写|测试|文档)"
    if re.search(reward_heading + r".{0,300}" + coding_action, lower, re.DOTALL) or re.search(
        coding_action + r".{0,300}" + reward_heading,
        lower,
        re.DOTALL,
    ):
        return True

    return has_direct_bounty_offer_evidence(text)


def non_cash_reward_types(text):
    """Return explicitly offered non-cash reward forms, excluding incidental mentions."""
    found = []
    for name, pattern in NON_CASH_REWARD_PATTERNS:
        linked = (
            rf"(?:reward|prize|award|payment|payout|奖励|奖品|报酬|酬谢|发放)[^.;\n]{{0,100}}(?:{pattern})"
            rf"|(?:{pattern})[^.;\n]{{0,100}}(?:reward|prize|award|payment|payout|奖励|奖品|报酬|酬谢|发放)"
        )
        if re.search(linked, text, re.IGNORECASE):
            found.append(name)
    return found


def is_non_cash_only_reward(text):
    if not non_cash_reward_types(text):
        return False
    if set(extract_payment_methods(text)) & FIAT_PAYMENT_METHODS:
        return False
    fiat_amount = (
        r"(?:(?:US\$|USD|EUR|GBP|CNY|RMB|CAD|AUD|INR|€|£|¥|₹|\$)\s*\d[\d,]*(?:\.\d+)?"
        r"|\d[\d,]*(?:\.\d+)?\s*(?:USD|EUR|GBP|CNY|RMB|CAD|AUD|INR))"
    )
    non_cash = "(?:" + "|".join(pattern for _, pattern in NON_CASH_REWARD_PATTERNS) + ")"
    reward_joiner = r"\s*(?:cash\s*)?(?:\+|plus\b|and\b|or\b)\s*(?:an?\s+|the\s+)?"
    mixed_reward = re.search(
        fiat_amount + reward_joiner + non_cash
        + r"|" + non_cash + reward_joiner + fiat_amount + r"(?:\s*cash\b)?",
        text,
        re.IGNORECASE,
    )
    if mixed_reward:
        return False
    cash_alternative = re.search(
        r"\b(?:cash prize|cash reward|cash payment|paid via (?:paypal|wise|stripe)|bank transfer|wire transfer)\b"
        r"|" + fiat_amount + r"\s*cash\b"
        r"|现金(?:奖励|奖品|支付|发放)|银行转账|支付宝|微信支付",
        text,
        re.IGNORECASE,
    )
    return not bool(cash_alternative)


def has_document_reward_assertion(context):
    """Require an actual offer, not merely words such as challenge or reward model."""
    lower = context.lower()
    if has_explicit_no_current_reward(context):
        return False
    if has_generic_backing_template(context) and not has_current_reward_evidence(context):
        return False
    if is_product_billing_only(context):
        return False
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
        "paid task",
        "paid after merge",
        "paid upon acceptance",
        "payment after accepted pr",
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

    amount = r"(?:(?:US\$|USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|RTC|ETH|SOL|USDT|DAI|BTC|€|£|¥|₹|\$)\s*\d|\d[\d,]*\s*(?:USD|USDC|EUR|GBP|CNY|RMB|CAD|AUD|INR|XLM|RTC|ETH|SOL|USDT|DAI|BTC))"
    reward = r"(?:bounty|reward|prize|payment|payout|compensation|paid|winner)"
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
        r"\b(?:discover|search|browse|track|manage|post|paid contribution opportunities|bount(?:y|ies))\b"
        r"|\b(?:discover|search|browse|track|list|aggregate)\b.{0,100}"
        r"\b(?:bounty issues|bount(?:y|ies)|paid contribution opportunities)\b",
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


def payment_context(text):
    lines = text.splitlines()
    selected = []
    for line in lines:
        lower = line.lower()
        if is_product_billing_only(line):
            continue
        if any(term in lower for term in STRONG_REWARD_TERMS + GENERIC_REWARD_TERMS) or re.search(
            r"\bpay(?:ment|out|pal|ing|able|ed)?\b|winner|receive|bank transfer|wire transfer"
            r"|usdc|usdt|tether|\bbtc\b|bitcoin|sats?|satoshi|lightning|\bxlm\b|\brtc\b|\beth\b|\bsol\b|\bdai\b"
            r"|on[- ]chain|wallet address|crypto(?:currency)? wallet",
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


def is_crypto_only_payment(methods, text=""):
    method_set = set(methods)
    if method_set & FIAT_PAYMENT_METHODS:
        return False
    if method_set & CRYPTO_PAYMENT_METHODS:
        return True
    chain_payout = (
        r"\b(?:auto[- ]?pays?|pay(?:ment|out|s|ing|ed)?|reward(?:ed)?|claim)\b"
        r"[^.;\n]{0,120}\b(?:crypto(?:currency)?|tokens?|on[- ]chain|wallet(?: address)?)\b"
        r"|\b(?:crypto(?:currency)?|tokens?|on[- ]chain|wallet(?: address)?)\b"
        r"[^.;\n]{0,120}\b(?:auto[- ]?pays?|pay(?:ment|out|s|ing|ed)?|reward(?:ed)?|claim)\b"
    )
    return bool(re.search(chain_payout, text, re.IGNORECASE))


def verified_platform_payment_rule(text="", labels=(), url=""):
    """Return a documented platform payout rule only after a positive match."""
    normalized_labels = {str(label).strip().lower() for label in labels if label}
    haystack = "\n".join((str(text or ""), str(url or "")))
    hostname = (urllib.parse.urlparse(str(url or "")).hostname or "").lower()
    for rule in VERIFIED_PLATFORM_PAYMENT_RULES:
        if normalized_labels & set(rule.get("issue_labels", ())):
            return rule
        if hostname in set(rule.get("source_hosts", ())):
            return rule
        if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in rule.get("text_patterns", ())):
            return rule
    return None


def merge_payment_methods(explicit_methods, platform_rule=None):
    methods = list(explicit_methods)
    if platform_rule:
        for method in platform_rule.get("methods", ()):
            if method not in methods:
                methods.append(method)
    return methods


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


def analyze_candidate(
    title,
    project,
    url,
    source,
    text,
    comments=None,
    updated_at=None,
    now=None,
    platform_payment_rule=None,
    reward_offer_confirmed=False,
    rejection_reasons=None,
):
    """Normalize and score an Issue or Markdown document candidate."""
    context = relevant_context(text)
    focused_text = "\n".join(part for part in (title, context) if part)
    lower = focused_text.lower()
    full_lower = text.lower()

    def reject(reason):
        if rejection_reasons is not None:
            rejection_reasons.append(reason)
        return None

    if has_explicit_no_current_reward(text):
        return reject("no reward link")
    if has_generic_backing_template(text) and not has_current_reward_evidence(text):
        return reject("no reward link")
    if is_historical_reward_summary(title, text):
        return reject("historical reward")
    if is_product_billing_only(text):
        return reject("product billing")
    if is_non_reward_financial_context(text):
        return reject("non-reward financial")
    if source == "Repository Markdown" and is_discovery_source_document(text):
        return reject("discovery source")
    if any(term in lower for term in SPAM_TERMS + JOB_TERMS):
        return reject("spam/job")
    if any(term in full_lower for term in LONG_PROJECT_TERMS):
        return reject("heavy scope")
    if re.search(
        r"\b(?:3|4|5|6|three|four|five|six)\s*[-–—]\s*(?:3|4|5|6|three|four|five|six)\s+weeks?\b"
        r"|\blarge[- ]scale empirical reproduction\b"
        r"|\bempirically reproduce\b.{0,120}\b(?:across\s+)?(?:\d{2,}|dozens?|many)\b",
        full_lower,
        re.DOTALL,
    ):
        return reject("heavy scope")
    if sum(term in full_lower for term in HEAVY_SCOPE_TERMS) >= 2 and not any(
        term in full_lower for term in MICRO_TASK_TERMS
    ):
        return reject("heavy scope")
    if source == "Repository Markdown" and re.search(r"\b(?:2|3|4|5|6|7|8|9|1\d)\s*[- ]?months?\b", lower):
        return reject("heavy scope")
    if not reward_offer_confirmed and not has_task_contributor_reward_link(text):
        return reject("no reward link")
    if is_non_cash_only_reward(text):
        return reject("non-cash")

    amounts = extract_reward_amounts(text)
    methods = merge_payment_methods(extract_payment_methods(text), platform_payment_rule)
    if is_crypto_only_payment(methods, text):
        return reject("crypto-only")
    strong_hit = any(term in lower for term in STRONG_REWARD_TERMS)
    generic_hit = any(term in lower for term in GENERIC_REWARD_TERMS)
    cash_hit = bool(amounts or methods or re.search(r"\bcash\b|\bpaid\b|\bmonetary\b", lower))
    if not strong_hit and not (generic_hit and cash_hit):
        return reject("no reward link")
    if source == "Repository Markdown" and not has_document_reward_assertion(context):
        return reject("no reward link")

    micro_hit = any(term in lower for term in MICRO_TASK_TERMS)
    coding_hit = any(term in lower for term in CODING_TASK_TERMS)
    large_event = any(term in lower for term in ("hackathon", "game jam", "multi-day competition"))
    if large_event and not micro_hit:
        return reject("heavy scope")

    deadline = extract_deadline(text)
    deadline_date = parsed_deadline_date(deadline)
    current = now or datetime.now(timezone.utc)
    if deadline_date and deadline_date.date() < current.date():
        return reject("expired")

    submission = extract_submission(text)
    qualification_submission = extract_submission(context)
    if source == "Repository Markdown" and not has_actionable_document_offer(context, qualification_submission):
        return reject("no reward link")
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
        "payment_rule_source": (
            platform_payment_rule.get("evidence_url") if platform_payment_rule else None
        ),
        "agent_fit": estimate_agent_fit(focused_text),
        "effort": estimate_effort(focused_text),
        "comments": comments,
        "updated_at": updated_at,
        "score": score,
    }


def issue_label_names(item):
    return {
        str(label.get("name", "")).strip().lower()
        for label in item.get("labels", [])
        if isinstance(label, dict)
    }


def exclusive_claim_rule(text):
    return bool(
        re.search(
            r"\bonly (?:the )?(?:assigned contributor|assignee|claimant)\b.{0,80}\b(?:eligible|may|can|will)\b"
            r"|\bonce (?:assigned|claimed)\b.{0,120}\b(?:others?|other contributors?)\b.{0,60}"
            r"\b(?:cannot|can't|may not|must not|not eligible)\b"
            r"|\b(?:do not|don't) (?:start|work|submit|open (?:a )?(?:pr|pull request))\b.{0,80}"
            r"\b(?:already assigned|already claimed|unless (?:you are )?assigned)\b"
            r"|\bnew contributors? should not start(?: parallel)? work\b"
            r"|\bno new claims\b"
            r"|\bno longer available once claimed\b"
            r"|仅限(?:被)?(?:分配|认领)(?:的)?(?:贡献者|人员|用户)|已认领后.{0,40}(?:其他人|他人).{0,30}(?:不能|不可)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    )


def issue_is_explicitly_completed(item):
    labels = issue_label_names(item)
    if labels & {"completed", "done", "resolved", "fixed", "status: completed", "status: done"}:
        return True
    body = str(item.get("body") or "")
    return bool(
        re.search(
            r"\b(?:this|the) (?:issue|task|bounty) (?:has been|is) (?:completed|done|resolved|finished)\b"
            r"|(?:^|\n)\s*(?:status\s*:\s*)?(?:completed|done|resolved)\s*(?:\n|$)"
            r"|(?:当前)?(?:任务|悬赏)(?:已经|已)(?:完成|结束|解决)",
            body,
            re.IGNORECASE,
        )
    )


def issue_safeguard_reason(item, host_repo=None):
    """Return a hard-filter reason; ordinary participation is competition only."""
    if item.get("state") not in (None, "open"):
        return "completed"
    if "pull_request" in item:
        return "pull request"
    labels = issue_label_names(item)
    if "bounty-alert" in labels:
        return "host alert"
    if "radar" in labels:
        return "radar"
    if any(
        label in {"bounty-large", "size: large", "size/large"} or label.endswith("-large")
        for label in labels
    ):
        return "heavy scope"
    if issue_is_explicitly_completed(item):
        return "completed"
    text = "\n".join((str(item.get("title") or ""), str(item.get("body") or "")))
    if exclusive_claim_rule(text):
        return "assigned / claimed"
    repository_url = str(item.get("repository_url", ""))
    if host_repo and repository_url.rstrip("/").endswith("/repos/" + host_repo):
        return "host repository"
    return ""


def is_clean_issue(item, host_repo=None):
    return not issue_safeguard_reason(item, host_repo)


def has_issue_reward_offer(item):
    """Reject Issues that merely discuss bounty systems or unrelated rewards."""
    title = str(item.get("title") or "")
    body = str(item.get("body") or "")
    lower_title = title.lower()
    lower_body = body.lower()
    combined = lower_title + "\n" + lower_body

    if has_explicit_no_current_reward(combined):
        return False
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
    reward_label = any("bounty" in label or "reward" in label for label in labels)
    return has_task_contributor_reward_link(combined, reward_label=reward_label)


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


def issue_timeline_url(item):
    timeline_url = str(item.get("timeline_url") or "")
    if timeline_url:
        return timeline_url
    repository_url = str(item.get("repository_url") or "").rstrip("/")
    number = item.get("number")
    if repository_url and number is not None:
        return f"{repository_url}/issues/{number}/timeline"
    return ""


def pr_explicitly_closes_issue(pr, item):
    number = item.get("number")
    if number is None:
        match = re.search(r"/issues/(\d+)/?$", str(item.get("html_url") or ""))
        number = match.group(1) if match else None
    if number is None:
        return False
    repository = str(item.get("repository_url") or "").split("/repos/")[-1]
    qualified = rf"(?:{re.escape(repository)}\s*)?" if repository else ""
    issue_url = str(item.get("html_url") or "")
    reference_parts = [rf"{qualified}#\s*{re.escape(str(number))}\b"]
    if issue_url:
        reference_parts.append(re.escape(issue_url))
    reference = "(?:" + "|".join(reference_parts) + ")"
    closing = rf"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?[ \t]*(?:[-*][ \t]*)?{reference}"
    return bool(re.search(closing, str(pr.get("body") or ""), re.IGNORECASE))


def fetch_related_pr_info(item, token=None):
    """Count PR cross-references and flag only clearly completed merged work."""
    timeline_url = issue_timeline_url(item)
    unknown = {
        "open_pr_count": None,
        "merged_pr_count": None,
        "completed_by_merged_pr": False,
    }
    if not timeline_url:
        return unknown
    separator = "&" if "?" in timeline_url else "?"
    events = github_api_get(f"{timeline_url}{separator}per_page=100", token)
    if not isinstance(events, list):
        return unknown

    pull_requests = {}
    for event in events:
        if not isinstance(event, dict) or event.get("event") != "cross-referenced":
            continue
        source_issue = event.get("source", {}).get("issue", {})
        if not isinstance(source_issue, dict) or not source_issue.get("pull_request"):
            continue
        pr_url = str(source_issue.get("html_url") or source_issue.get("url") or "")
        if pr_url:
            pull_requests[pr_url] = source_issue

    open_prs = []
    merged_prs = []
    for pr in pull_requests.values():
        merged_at = (pr.get("pull_request") or {}).get("merged_at")
        if merged_at:
            merged_prs.append(pr)
        elif pr.get("state") == "open":
            open_prs.append(pr)
    return {
        "open_pr_count": len(open_prs),
        "merged_pr_count": len(merged_prs),
        "completed_by_merged_pr": any(pr_explicitly_closes_issue(pr, item) for pr in merged_prs),
    }


def first_win_rule(text):
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in FIRST_WIN_PATTERNS)


def apply_pr_competition(candidate, pr_info, text, item=None):
    """Attach participation signals and apply ranking penalties without filtering."""
    item = item or {}
    open_count = pr_info.get("open_pr_count")
    merged_count = pr_info.get("merged_pr_count")
    first_wins = first_win_rule(text)
    labels = issue_label_names(item)
    participation_labels = sorted(labels & {"assigned", "claimed", "in progress"})
    assignee_count = len(item.get("assignees") or [])
    comments = int(item.get("comments", 0) or 0)
    candidate["open_pr_count"] = open_count
    candidate["merged_pr_count"] = merged_count
    candidate["first_wins"] = first_wins
    candidate["assignee_count"] = assignee_count
    candidate["participation_labels"] = participation_labels
    signals = []
    penalty = 0

    if assignee_count:
        signals.append(f"{assignee_count} 个 assignee")
        penalty += min(assignee_count, 2)
    if participation_labels:
        signals.append("/".join(participation_labels))
        penalty += 1
    if comments > MAX_COMMENTS:
        signals.append(f"{comments} 条评论")
        penalty += min(1 + comments // 50, 3)

    if open_count is None:
        signals.append("相关 PR 检查失败")
    elif open_count:
        if first_wins:
            penalty += min(open_count * 3, 9)
            signals.append(f"{open_count} 个相关 open PR，且规则为 first wins")
        else:
            penalty += min(open_count, 3)
            signals.append(f"{open_count} 个相关 open PR")

    candidate["competition"] = "有竞争：" + "；".join(signals) if signals else "未发现明显竞争"
    candidate["score"] -= penalty
    return candidate


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
    if hostname in {"docs.google.com", "forms.gle"}:
        return False
    return not _is_blocked_http_host(hostname)


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
    content = fetch_text_url(url, restrict_redirects=True)
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
    diagnostic_samples = {}
    stats = {
        "raw": 0,
        "duplicates": 0,
        "unresolved": 0,
        "safeguards": 0,
        "no_reward_offer": 0,
        "analysis_filtered": 0,
        "merged_completed": 0,
        "matched": 0,
    }
    for query in ISSUE_SEARCH_QUERIES:
        log(f"Issue search: {query}")
        results = search_endpoint("issues", query, token, per_page=ISSUE_RESULTS_PER_QUERY)
        if not results:
            continue
        items = results.get("items", [])
        stats["raw"] += len(items)
        for search_item in items:
            search_url = search_item.get("html_url")
            if not search_url:
                stats["unresolved"] += 1
                continue
            if search_url in seen_search_urls:
                stats["duplicates"] += 1
                continue
            seen_search_urls.add(search_url)
            resolved = resolve_radar_source(search_item, token)
            if not resolved:
                stats["unresolved"] += 1
                continue

            if resolved["kind"] in ("document", "external"):
                url = resolved["url"]
                if url in seen_api_urls:
                    stats["duplicates"] += 1
                    continue
                seen_api_urls.add(url)
                platform_rule = verified_platform_payment_rule(text=resolved["text"], url=url)
                rejection_reasons = []
                candidate = analyze_candidate(
                    title=resolved["title"],
                    project=resolved["project"],
                    url=url,
                    source="Repository Markdown",
                    text=resolved["text"],
                    platform_payment_rule=platform_rule,
                    rejection_reasons=rejection_reasons,
                )
                if candidate:
                    if resolved["kind"] == "external":
                        candidate["source"] = "External bounty page"
                        candidate["project_url"] = resolved["project_url"]
                    candidate["discovered_via"] = resolved.get("discovered_via")
                    candidates.append(candidate)
                    stats["matched"] += 1
                else:
                    stats["analysis_filtered"] += 1
                    add_diagnostic_sample(
                        diagnostic_samples,
                        rejection_reasons[0] if rejection_reasons else "other",
                        url,
                    )
                continue

            item = resolved["item"]
            url = item.get("html_url")
            if not url:
                stats["unresolved"] += 1
                continue
            if url in seen_api_urls:
                stats["duplicates"] += 1
                continue
            safeguard_reason = issue_safeguard_reason(item, host_repo)
            if safeguard_reason:
                stats["safeguards"] += 1
                add_diagnostic_sample(diagnostic_samples, safeguard_reason, url)
                continue
            if not has_issue_reward_offer(item):
                stats["no_reward_offer"] += 1
                add_diagnostic_sample(diagnostic_samples, "no reward link", url)
                continue
            seen_api_urls.add(url)
            text = "\n".join((str(item.get("title") or ""), str(item.get("body") or "")))
            labels_set = issue_label_names(item)
            if item.get("assignees") or labels_set & {"assigned", "claimed", "in progress"}:
                add_diagnostic_sample(diagnostic_samples, "assigned / claimed (competition)", url)
            if int(item.get("comments", 0) or 0) > MAX_COMMENTS:
                add_diagnostic_sample(diagnostic_samples, "too many comments (competition)", url)
            repo = str(item.get("repository_url", "")).split("/repos/")[-1]
            if not repo:
                repo = url.removeprefix("https://github.com/").split("/issues/")[0]
            labels = [
                label.get("name")
                for label in item.get("labels", [])
                if isinstance(label, dict)
            ]
            platform_rule = verified_platform_payment_rule(text=text, labels=labels, url=url)
            rejection_reasons = []
            candidate = analyze_candidate(
                title=str(item.get("title") or "Untitled bounty"),
                project=repo,
                url=url,
                source="GitHub Issue",
                text=text,
                comments=item.get("comments"),
                updated_at=item.get("updated_at"),
                platform_payment_rule=platform_rule,
                reward_offer_confirmed=True,
                rejection_reasons=rejection_reasons,
            )
            if candidate:
                pr_info = fetch_related_pr_info(item, token)
                if pr_info["completed_by_merged_pr"]:
                    stats["merged_completed"] += 1
                    add_diagnostic_sample(diagnostic_samples, "merged/completed", url)
                    continue
                apply_pr_competition(candidate, pr_info, text, item=item)
                if resolved.get("discovered_via"):
                    candidate["discovered_via"] = resolved["discovered_via"]
                candidates.append(candidate)
                stats["matched"] += 1
            else:
                stats["analysis_filtered"] += 1
                add_diagnostic_sample(
                    diagnostic_samples,
                    rejection_reasons[0] if rejection_reasons else "other",
                    url,
                )
    log(
        "Issue scan summary (Actions log only): "
        f"raw={stats['raw']}, unique={len(seen_search_urls)}, duplicates={stats['duplicates']}, "
        f"unresolved={stats['unresolved']}, safeguards={stats['safeguards']}, "
        f"no_reward_offer={stats['no_reward_offer']}, analysis_filtered={stats['analysis_filtered']}, "
        f"merged_completed={stats['merged_completed']}, "
        f"matched={stats['matched']}"
    )
    log_diagnostic_samples("Issue", diagnostic_samples)
    return candidates


def candidate_markdown_path(path):
    """Prioritize likely offer documents during fallback discovery only."""
    lower = path.lower()
    if not lower.endswith((".md", ".markdown", ".mdx")):
        return False
    basename = lower.rsplit("/", 1)[-1]
    return basename.startswith(("readme", "contributing")) or any(
        term in lower
        for term in (
            "bounty",
            "challenge",
            "reward",
            "prize",
            "contribut",
            "governance",
            "program",
            "payout",
            "payment",
            "compensation",
        )
    )


def fetch_code_search_documents(token):
    documents = []
    seen_urls = set()
    search_worked = False
    for index, (label, query) in enumerate(DOCUMENT_SEARCH_QUERIES):
        if index:
            time.sleep(CODE_SEARCH_INTERVAL_SECONDS)
        log(f"Markdown code search: {label}")
        results = search_endpoint(
            "code",
            query,
            token,
            per_page=DOCUMENT_RESULTS_PER_QUERY,
        )
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


def extract_discovery_task_urls(text, base_url, limit=5):
    """Extract a few task-looking links from a program or marketplace page."""
    links = []
    for label, raw_target in re.findall(r"\[([^]\n]+)\]\(([^)\n]+)\)", text):
        target = re.split(r"\s+[\"']", raw_target.strip(), maxsplit=1)[0].strip("<>")
        if target.startswith("#"):
            continue
        hint = f"{label} {target}".lower()
        if not any(term in hint for term in ("bounty", "reward", "paid", "task", "challenge", "issue")):
            continue
        url = urllib.parse.urldefrag(urllib.parse.urljoin(base_url, target))[0]
        if url == urllib.parse.urldefrag(base_url)[0]:
            continue
        if url.startswith(("http://", "https://")) and url not in links:
            links.append(url)
    for url in re.findall(
        r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/\d+",
        text,
        re.IGNORECASE,
    ):
        if url not in links:
            links.append(url)
    return links[:limit]


def fetch_discovery_target(url, token=None):
    issue = fetch_github_issue_url(url, token)
    if issue:
        project = str(issue.get("repository_url") or "").split("/repos/")[-1]
        return {
            "source": "GitHub Issue",
            "title": str(issue.get("title") or "Untitled bounty"),
            "project": project,
            "url": str(issue.get("html_url") or url),
            "text": "\n".join((str(issue.get("title") or ""), str(issue.get("body") or ""))),
            "item": issue,
        }
    document = fetch_github_document_url(url, token)
    if document:
        document["source"] = "Repository Markdown"
        return document
    if urllib.parse.urlparse(url).netloc.lower() == "github.com":
        return None
    external = fetch_external_page_source(url)
    if external:
        external["source"] = "External bounty page"
    return external


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
    diagnostic_samples = {}
    queue = [{**document, "source": "Repository Markdown", "discovery_depth": 0} for document in documents]
    seen_urls = {document["url"] for document in documents}
    followed = 0
    filtered = 0
    for document in queue:
        source = document.get("source", "Repository Markdown")
        if source != "GitHub Issue" and is_discovery_source_document(document["text"]):
            filtered += 1
            add_diagnostic_sample(diagnostic_samples, "discovery source", document["url"])
            if document.get("discovery_depth", 0) >= 2:
                continue
            for target_url in extract_discovery_task_urls(document["text"], document["url"]):
                if followed >= MAX_DISCOVERY_TARGETS or target_url in seen_urls:
                    continue
                seen_urls.add(target_url)
                target = fetch_discovery_target(target_url, token)
                if not target:
                    continue
                target["discovered_via"] = document.get("discovered_via") or document["url"]
                target["discovery_depth"] = document.get("discovery_depth", 0) + 1
                queue.append(target)
                followed += 1
            continue

        item = document.get("item") if source == "GitHub Issue" else None
        if item:
            safeguard_reason = issue_safeguard_reason(item)
            if safeguard_reason:
                filtered += 1
                add_diagnostic_sample(diagnostic_samples, safeguard_reason, document["url"])
                continue
            if not has_issue_reward_offer(item):
                filtered += 1
                add_diagnostic_sample(diagnostic_samples, "no reward link", document["url"])
                continue

        labels = [
            label.get("name")
            for label in (item or {}).get("labels", [])
            if isinstance(label, dict)
        ]
        platform_rule = verified_platform_payment_rule(
            text=document["text"], labels=labels, url=document["url"]
        )
        rejection_reasons = []
        candidate = analyze_candidate(
            title=document["title"],
            project=document["project"],
            url=document["url"],
            source="GitHub Issue" if item else "Repository Markdown",
            text=document["text"],
            comments=(item or {}).get("comments"),
            updated_at=(item or {}).get("updated_at"),
            platform_payment_rule=platform_rule,
            reward_offer_confirmed=bool(item),
            rejection_reasons=rejection_reasons,
        )
        if not candidate:
            filtered += 1
            add_diagnostic_sample(
                diagnostic_samples,
                rejection_reasons[0] if rejection_reasons else "other",
                document["url"],
            )
            continue
        if item:
            pr_info = fetch_related_pr_info(item, token)
            if pr_info["completed_by_merged_pr"]:
                filtered += 1
                add_diagnostic_sample(diagnostic_samples, "merged/completed", document["url"])
                continue
            apply_pr_competition(candidate, pr_info, document["text"], item=item)
        if source == "External bounty page":
            candidate["source"] = source
            candidate["project_url"] = document.get("project_url")
        if document.get("discovered_via"):
            candidate["discovered_via"] = document["discovered_via"]
        candidates.append(candidate)
    log(
        "Document scan summary (Actions log only): "
        f"fetched={len(documents)}, followed={followed}, analysis_filtered={filtered}, matched={len(candidates)}"
    )
    log_diagnostic_samples("Document", diagnostic_samples)
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
        if "open_pr_count" in candidate:
            open_prs = candidate["open_pr_count"]
            entry.append(f"Related open PRs: {open_prs if open_prs is not None else '待确认'}")
            entry.append(f"Competition: {candidate['competition']}")
        if candidate.get("payment_rule_source"):
            entry.append(f"Payment rule source: {candidate['payment_rule_source']}")
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
        if "open_pr_count" in candidate:
            open_prs = candidate["open_pr_count"]
            lines.append(f"- **Related open PRs:** {open_prs if open_prs is not None else '待确认'}")
            lines.append(f"- **Competition:** {candidate['competition']}")
        if candidate.get("payment_rule_source"):
            lines.append(f"- **Payment rule source:** {candidate['payment_rule_source']}")
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

    discovered_count = len(candidates)
    ranked = deduplicate_and_rank(candidates)
    deduplicated_count = len(ranked)
    if not args.include_seen:
        ranked = [candidate for candidate in ranked if candidate["url"] not in seen_urls]
    unseen_count = len(ranked)
    selected = ranked[: args.max_results]
    log(
        "Final selection summary (Actions log only): "
        f"discovered={discovered_count}, deduplicated={deduplicated_count}, "
        f"unseen={unseen_count}, selected={len(selected)}"
    )

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
