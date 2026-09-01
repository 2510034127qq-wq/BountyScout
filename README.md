# 🎯 BountyScout: Micro Bounty Scanner

BountyScout 是一个无第三方依赖的 GitHub 扫描器，用来发现几十分钟到一天左右可完成的付费技术小任务。它保留原有的 GitHub Issue bounty 搜索，同时扫描 README、CONTRIBUTING 和独立的 Challenge/Bounty Markdown 文档，降低只依赖 `bounty` 关键词造成的漏报。

扫描器每小时通过 GitHub Actions 运行，使用 `seen_bounties.json` 记录已经通知过的原始链接，并支持 GitHub Issue、Telegram 和 Discord 通知。

## 发现范围

### GitHub Issues

扫描开放 Issue 中的 `bounty`、`cash prize`、`paid challenge`、`paid contribution`、`paid PR` 和 `contributor reward` 等表达。原有规则仍然有效：跳过 PR、已有负责人、超过 25 条评论的拥挤任务、广告/博彩/内容写作等噪声。

### 仓库 Markdown

有 `GITHUB_TOKEN` 时，使用 GitHub Code Search 查找全站 Markdown，包括：

- README 和 CONTRIBUTING；
- `CHALLENGE.md`、`BOUNTY.md`、活动说明等独立文件；
- 包含 `cash prize`、`prize pool`、`engineering challenge`、`micro bounty` 等表达的其他 Markdown。

没有令牌时，脚本自动降级为 GitHub Repository Search：先查匹配的 README，再检查仓库中名称带 `challenge`、`bounty`、`reward`、`prize` 或 `contribut` 的少量 Markdown。这个模式能运行，但覆盖率低于认证后的 Code Search。

## 筛选和结果字段

候选优先按“明确奖励 + 小任务信号 + 编码任务信号 + 提交方式完整度”排序。大型 Hackathon、招聘/实习岗位、`bounty-large`、明确的长期/重型实现、过期活动、已暂停任务和常见垃圾内容会被排除；镜像 Issue 会尽量恢复并去重到原始 Issue。其余不确定候选会保留，避免隐藏悬赏被过度过滤。

每条通知尽量给出：

- 项目、来源类型和原始链接；
- 奖励金额与币种；
- 任务摘要、截止时间和提交方式；
- 明确写出的付款方式或结算资产（PayPal、Wise、Stripe、银行转账、USDC、XLM、ETH、SOL、GrantFox 等）；
- Coding Agent 适配度和预估工作量。

付款方式未在原文明确出现时始终显示 `待确认`，不会据金额或项目所在地推测中国大陆用户能否收款。Agent 适配度和无明确耗时的工作量是关键词启发式结果，领取任务前仍需打开原始链接核对资格、有效期和付款条款。

## 本地运行

只需 Python 3.9+，不需要安装依赖。

```bash
# 完整扫描；正常模式会发送已配置的通知并更新状态
GITHUB_TOKEN=your_token python3 scout_bounties.py

# 推荐先只读试跑：显示已见结果，不发通知、不修改状态
GITHUB_TOKEN=your_token python3 scout_bounties.py \
  --dry-run --include-seen --max-results 10

# 只检查仓库文档，并输出便于二次处理的 JSON
GITHUB_TOKEN=your_token python3 scout_bounties.py \
  --dry-run --include-seen --source docs --json --max-results 20

# 只保留原来的 Issue 扫描
python3 scout_bounties.py --dry-run --source issues

# 运行离线测试
python3 -m unittest -v
```

可选参数：

- `--source all|issues|docs`：限制扫描来源，默认 `all`；
- `--dry-run`：不通知、不写入 `seen_bounties.json`；
- `--include-seen`：试跑时也展示已经记录过的链接；
- `--json`：输出结构化候选；
- `--max-results N`：本轮最多通知多少条，默认 20；也可通过 `BOUNTYSCOUT_MAX_RESULTS` 设置。

## GitHub Actions

工作流 `.github/workflows/bounty-scout.yml` 每小时运行，也可在 Actions 页面手动触发。默认的 `GITHUB_TOKEN` 用于搜索、创建本仓库的通知 Issue 和提交状态文件，无需单独创建。

仓库结构：

```text
BountyScout/
├── .github/workflows/bounty-scout.yml
├── scout_bounties.py
├── test_scout_bounties.py
├── seen_bounties.json
└── README.md
```

### GitHub Issue 通知

无需额外配置。工作流会在本仓库创建带 `bounty-alert` 标签的结构化 Issue；扫描器会排除这些通知 Issue，避免反馈循环。

### Telegram

在仓库的 **Settings → Secrets and variables → Actions** 添加：

- `TELEGRAM_BOT_TOKEN`：从 `@BotFather` 获取；
- `TELEGRAM_CHAT_ID`：目标聊天或频道 ID。

### Discord

创建频道 Webhook，然后添加仓库 Secret `DISCORD_WEBHOOK_URL`。

## 状态与限制

- 去重键是候选的原始 GitHub URL；同一活动若有多个不同文档，仍可能出现多条，方便人工选择最完整来源。
- GitHub Search 只返回索引到的内容，刚提交的文件、外链页面正文和仅存在于 Discussion 的内容不保证可见；Markdown 中出现的外链和提交说明仍会被提取。
- `seen_bounties.json` 只在非 dry-run 且存在新结果时追加，已有顺序保持不变，避免每小时产生大面积无意义 diff。
