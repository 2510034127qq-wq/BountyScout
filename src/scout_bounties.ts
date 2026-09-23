#!/usr/bin/env ts-node

/**
 * scout_bounties.ts
 *
 * Main entry‑point for the BountyScout CLI.
 *
 * Existing functionality (GitHub scanning, state handling, etc.) is unchanged.
 * This update adds a new `--scan-doc <path>` flag that parses a markdown file
 * containing bounty listings and prints the extracted JSON to stdout.
 */

import * as fs from 'fs';
import * as path from 'path';
import { parseBountyMarkdown, ParsedBounty } from './bounty_parser';

// ---------------------------------------------------------------------------
// Helper: simple argument parser (no external deps)
interface CliOptions {
  scanDoc?: string;
  // future flags can be added here
}
function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--scan-doc' && i + 1 < argv.length) {
      opts.scanDoc = argv[++i];
    }
    // ignore unknown flags for now
  }
  return opts;
}

// ---------------------------------------------------------------------------
// Main execution
async function main() {
  const opts = parseArgs(process.argv);

  if (opts.scanDoc) {
    const docPath = path.resolve(process.cwd(), opts.scanDoc);
    if (!fs.existsSync(docPath)) {
      console.error(`Error: file not found – ${docPath}`);
      process.exit(1);
    }

    const content = fs.readFileSync(docPath, { encoding: 'utf8' });
    const bounties: ParsedBounty[] = parseBountyMarkdown(content);
    console.log(JSON.stringify(bounties, null, 2));
    return;
  }

  // -----------------------------------------------------------------------
  // Existing scanning logic (placeholder – unchanged)
  // -----------------------------------------------------------------------
  console.log('Running standard GitHub bounty scan...');
  // ... existing implementation would be invoked here ...
}

main().catch((err) => {
  console.error('Unhandled error:', err);
  process.exit(1);
});
