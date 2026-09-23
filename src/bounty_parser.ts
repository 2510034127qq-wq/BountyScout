/**
 * bounty_parser.ts
 *
 * Parses markdown files that list bounty opportunities.
 *
 * Expected markdown snippet (as shown in the issue description):
 *
 * 1. [Bounty #18 claim: NOT IN tag filter](https://github.com/josedab/chronicle/issues/33)
 * - **Project:** [josedab/chronicle](https://github.com/josedab/chronicle)
 * - **Source:** GitHub Issue
 * - **Reward:** $100
 * - **Task:** hey, the bounty program currently lists #18 “Implement NOT IN tag filter” for $100 and marks it open...
 * - **Deadline:** 待确认
 * - **Submission:** GitHub Issue
 * - **Payment method:** PayPal、银行转账
 *
 * The parser extracts each bullet‑point block into a structured object.
 */

export interface ParsedBounty {
  /** Numeric order in the list (optional, may be undefined) */
  index?: number;
  /** Bounty identifier (e.g., "#18") */
  bountyId: string;
  /** Short title of the bounty */
  title: string;
  /** Direct URL to the bounty description */
  url: string;
  /** Project name (e.g., "josedab/chronicle") */
  project: string;
  /** Source type (e.g., "GitHub Issue") */
  source: string;
  /** Reward string (raw, e.g., "$100" or "待确认") */
  reward: string;
  /** Full task description */
  task: string;
  /** Deadline string (raw) */
  deadline: string;
  /** Submission instructions */
  submission: string;
  /** Payment method description */
  paymentMethod: string;
}

/**
 * Parses a markdown file containing bounty listings.
 *
 * @param markdownContent The raw markdown string.
 * @returns An array of ParsedBounty objects.
 */
export function parseBountyMarkdown(markdownContent: string): ParsedBounty[] {
  const lines = markdownContent.split(/\r?\n/);
  const bounties: ParsedBounty[] = [];

  // Helper regexes
  const headerRegex = /^\s*(\d+)\.\s*\[Bounty\s*#(\d+)\s*claim:\s*([^\]]+)\]\(([^)]+)\)/i;
  const kvRegex = /^\s*-\s*\*\*(.+?)\*\*:\s*(.+)$/i;

  let current: Partial<ParsedBounty> | null = null;

  for (const rawLine of lines) {
    const line = rawLine.trim();

    // Detect start of a new bounty block
    const headerMatch = headerRegex.exec(line);
    if (headerMatch) {
      // Push previous bounty if any
      if (current && current.bountyId && current.title && current.url) {
        // Type assertion – we have validated required fields
        bounties.push(current as ParsedBounty);
      }

      // Initialise new bounty object
      const [, indexStr, bountyNum, title, url] = headerMatch;
      current = {
        index: Number(indexStr),
        bountyId: `#${bountyNum}`,
        title: title.trim(),
        url: url.trim(),
      };
      continue;
    }

    // Inside a bounty block, parse key‑value lines
    if (current) {
      const kvMatch = kvRegex.exec(line);
      if (kvMatch) {
        const key = kvMatch[1].toLowerCase().replace(/\s+/g, '');
        const value = kvMatch[2].trim();

        switch (key) {
          case 'project':
            // Extract the markdown link text if present
            const projMatch = /\[([^\]]+)]\([^)]+\)/.exec(value);
            current.project = projMatch ? projMatch[1] : value;
            break;
          case 'source':
            current.source = value;
            break;
          case 'reward':
            current.reward = value;
            break;
          case 'task':
            current.task = value;
            break;
          case 'deadline':
            current.deadline = value;
            break;
          case 'submission':
            current.submission = value;
            break;
          case 'paymentmethod':
          case 'paymentmethod':
            current.paymentMethod = value;
            break;
          default:
            // Unknown key – ignore but keep extensibility
            break;
        }
      }
    }
  }

  // Push the final bounty if it exists
  if (current && current.bountyId && current.title && current.url) {
    bounties.push(current as ParsedBounty);
  }

  return bounties;
}
