import { parseBountyMarkdown, ParsedBounty } from '../src/bounty_parser';

describe('parseBountyMarkdown', () => {
  const sampleMarkdown = `
1. [Bounty #18 claim: NOT IN tag filter](https://github.com/josedab/chronicle/issues/33)
- **Project:** [josedab/chronicle](https://github.com/josedab/chronicle)
- **Source:** GitHub Issue
- **Reward:** $100
- **Task:** hey, the bounty program currently lists #18 “Implement NOT IN tag filter” for $100 and marks it open.
- **Deadline:** 待确认
- **Submission:** GitHub Issue
- **Payment method:** PayPal、银行转账

2. [Bounty #16 claim: Implement LAST_VALUE aggregation](https://github.com/josedab/chronicle/issues/35)
- **Project:** [josedab/chronicle](https://github.com/josedab/chronicle)
- **Source:** GitHub Issue
- **Reward:** 待确认
- **Task:** Implement LASTVALUE aggregation.
- **Deadline:** 待确认
- **Submission:** 待确认
- **Payment method:** PayPal
`;

  it('extracts two bounty entries with correct fields', () => {
    const result: ParsedBounty[] = parseBountyMarkdown(sampleMarkdown);
    expect(result).toHaveLength(2);

    const first = result[0];
    expect(first.index).toBe(1);
    expect(first.bountyId).toBe('#18');
    expect(first.title).toBe('NOT IN tag filter');
    expect(first.url).toBe('https://github.com/josedab/chronicle/issues/33');
    expect(first.project).toBe('josedab/chronicle');
    expect(first.source).toBe('GitHub Issue');
    expect(first.reward).toBe('$100');
    expect(first.task).toContain('Implement NOT IN tag filter');
    expect(first.deadline).toBe('待确认');
    expect(first.submission).toBe('GitHub Issue');
    expect(first.paymentMethod).toBe('PayPal、银行转账');

    const second = result[1];
    expect(second.index).toBe(2);
    expect(second.bountyId).toBe('#16');
    expect(second.title).toBe('Implement LAST_VALUE aggregation');
    expect(second.url).toBe('https://github.com/josedab/chronicle/issues/35');
    expect(second.project).toBe('josedab/chronicle');
    expect(second.source).toBe('GitHub Issue');
    expect(second.reward).toBe('待确认');
    expect(second.task).toContain('Implement LASTVALUE aggregation');
    expect(second.paymentMethod).toBe('PayPal');
  });

  it('gracefully handles missing optional fields', () => {
    const minimal = `
3. [Bounty #99 claim: Minimal Example](https://example.com/issue/99)
- **Project:** ExampleOrg/ExampleRepo
- **Source:** GitHub Issue
- **Reward:** $0
- **Task:** Do nothing.
`;
    const result = parseBountyMarkdown(minimal);
    expect(result).toHaveLength(1);
    const bounty = result[0];
    expect(bounty.index).toBe(3);
    expect(bounty.bountyId).toBe('#99');
    expect(bounty.title).toBe('Minimal Example');
    expect(bounty.url).toBe('https://example.com/issue/99');
    expect(bounty.project).toBe('ExampleOrg/ExampleRepo');
    expect(bounty.source).toBe('GitHub Issue');
    expect(bounty.reward).toBe('$0');
    expect(bounty.task).toBe('Do nothing.');
    // Missing fields should be undefined, not cause crashes
    expect(bounty.deadline).toBeUndefined();
    expect(bounty.submission).toBeUndefined();
    expect(bounty.paymentMethod).toBeUndefined();
  });
});
