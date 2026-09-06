#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const skillDir = dirname(scriptDir);
const statePath = process.env.X_SCOUT_STATE_PATH || `${skillDir}/state/last-run.json`;
const queriesPath = `${skillDir}/queries.json`;
const fetcherScriptsDir = '/Users/serg/projects/etc/tools/x-tweet-fetcher/scripts';
const queries = JSON.parse(readFileSync(queriesPath, 'utf8'));
const defaultNitterMirrors = [
  'nitter.tiekoetter.com',
  'xcancel.com',
  'nitter.catsarch.com',
];
const blockedTerms = [
  'mechanical cad',
  'product design',
  'fusion',
  'onshape',
  'solidworks',
  'blender',
  'stl',
  'mesh',
  '3d model',
  '3d print',
  'render',
  'midjourney',
  'dall-e',
  'dalle',
  'enscape',
  'lumion',
  'twinmotion',
  'ai art',
  'art prompt',
  'search console',
  'seo',
  'seo stack',
  'single site plan',
  'premium site plan',
  'webflow',
  'website crawler',
  'organic and llm rankings',
  'web3',
  'shooter',
  'crypto',
];

function readState() {
  try {
    const state = JSON.parse(readFileSync(statePath, 'utf8'));
    return {
      lastRunAt: typeof state.lastRunAt === 'string' ? state.lastRunAt : null,
      seenTweetIds: Array.isArray(state.seenTweetIds) ? state.seenTweetIds : [],
    };
  } catch {
    return { lastRunAt: null, seenTweetIds: [] };
  }
}

function writeState(state) {
  mkdirSync(dirname(statePath), { recursive: true });
  writeFileSync(`${statePath}.tmp`, `${JSON.stringify(state, null, 2)}\n`);
  renameSync(`${statePath}.tmp`, statePath);
}

function readLastRun() {
  return readState().lastRunAt;
}

function usage() {
  console.error('Usage: x-scout-queries.mjs [--markdown|--json|--open|--scan|--mark-run] [--days N]');
}

function parseArgs(argv) {
  let mode = '--markdown';
  let days = null;

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === '--days') {
      const value = argv[index + 1];
      if (!value) {
        throw new Error('--days requires a positive number');
      }
      days = parseDays(value);
      index += 1;
      continue;
    }

    if (arg.startsWith('--days=')) {
      days = parseDays(arg.slice('--days='.length));
      continue;
    }

    if (arg.startsWith('--')) {
      mode = arg;
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  return { mode, days };
}

function parseDays(value) {
  const days = Number.parseInt(value, 10);
  if (!Number.isFinite(days) || days < 1 || String(days) !== String(value).trim()) {
    throw new Error('--days requires a positive whole number');
  }
  return days;
}

function lookbackRunAt(days) {
  if (!days) return null;
  return new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
}

function markRun() {
  const state = readState();
  const lastRunAt = new Date().toISOString();
  writeState({ ...state, lastRunAt });
  console.log(lastRunAt);
}

function sinceDate(lastRunAt) {
  return lastRunAt ? lastRunAt.slice(0, 10) : null;
}

function withSince(query, lastRunAt) {
  const date = sinceDate(lastRunAt);
  const windowed = date ? `${query} since:${date}` : query;
  return `${windowed} lang:en`;
}

function xSearchUrl(query, lastRunAt = readLastRun()) {
  return `https://x.com/search?q=${encodeURIComponent(withSince(query, lastRunAt))}&src=typed_query&f=live`;
}

function nitterMirrors() {
  const fromEnv = (process.env.NITTER_URL || process.env.NITTER_INSTANCE || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => item.replace(/^https?:\/\//, '').replace(/\/$/, ''));
  return [...new Set([...fromEnv, ...defaultNitterMirrors])];
}

function isBlockedCandidate(tweet) {
  const text = `${tweet.text || ''} ${tweet.author_name || ''} ${tweet.author || ''}`.toLowerCase();
  return blockedTerms.some((term) => text.includes(term));
}

function matchesLaneTerms(tweet, lane) {
  if (!Array.isArray(lane.keepAny) || lane.keepAny.length === 0) return true;
  const text = `${tweet.text || ''} ${tweet.author_name || ''} ${tweet.author || ''}`.toLowerCase();
  return lane.keepAny.some((term) => text.includes(term.toLowerCase()));
}

function normalizeTweet(tweet, lane, mirror) {
  const username = (tweet.author || '').replace(/^@/, '');
  const id = tweet.tweet_id || '';
  return {
    lane,
    id,
    url: username && id ? `https://x.com/${username}/status/${id}` : '',
    mirror,
    author: tweet.author || '',
    authorName: tweet.author_name || '',
    timeAgo: tweet.time_ago || '',
    text: tweet.text || '',
    replies: tweet.replies || 0,
    retweets: tweet.retweets || 0,
    likes: tweet.likes || 0,
  };
}

function searchNitter(query, mirror, limit) {
  const python = `
import json
import sys
sys.path.insert(0, ${JSON.stringify(fetcherScriptsDir)})
from playwright_client import playwright_search_nitter

query = sys.argv[1]
mirror = sys.argv[2]
limit = int(sys.argv[3])
tweets, cursor = playwright_search_nitter(query, count=limit, nitter=mirror)
print(json.dumps({"tweets": tweets, "hasNextCursor": bool(cursor)}, ensure_ascii=False))
`;
  const result = spawnSync('python3', ['-c', python, query, mirror, String(limit)], {
    encoding: 'utf8',
    maxBuffer: 1024 * 1024 * 8,
  });
  if (result.status !== 0) {
    return {
      ok: false,
      tweets: [],
      error: (result.stderr || result.stdout || `python exited ${result.status}`).trim(),
    };
  }
  try {
    const parsed = JSON.parse(result.stdout);
    return {
      ok: true,
      tweets: parsed.tweets || [],
      hasNextCursor: Boolean(parsed.hasNextCursor),
      stderr: result.stderr.trim(),
    };
  } catch {
    return {
      ok: false,
      tweets: [],
      error: `Could not parse Nitter search output: ${result.stdout.slice(0, 500)}`,
    };
  }
}

function scan(options = {}) {
  const state = readState();
  const lastRunAt = options.lastRunAt || state.lastRunAt;
  const seenTweetIds = options.ignoreSeen ? new Set() : new Set(state.seenTweetIds);
  const newSeenTweetIds = new Set(state.seenTweetIds);
  const mirrors = nitterMirrors();
  const limit = Number.parseInt(process.env.X_SCOUT_LIMIT || '20', 10);
  const posts = [];
  const diagnostics = [];

  for (const item of queries) {
    const searchQuery = withSince(item.query, lastRunAt);
    let laneScanned = false;

    for (const mirror of mirrors) {
      const result = searchNitter(searchQuery, mirror, limit);
      diagnostics.push({
        lane: item.title,
        mirror,
        ok: result.ok,
        count: result.tweets.length,
        error: result.error || null,
      });

      if (!result.ok) continue;
      laneScanned = true;

      for (const tweet of result.tweets) {
        const normalized = normalizeTweet(tweet, item.title, mirror);
        if (
          !normalized.id
          || seenTweetIds.has(normalized.id)
          || isBlockedCandidate(normalized)
          || !matchesLaneTerms(normalized, item)
        ) {
          continue;
        }
        posts.push(normalized);
        newSeenTweetIds.add(normalized.id);
      }

      break;
    }

    if (!laneScanned) {
      diagnostics.push({
        lane: item.title,
        mirror: null,
        ok: false,
        count: 0,
        error: 'All Nitter mirrors failed for this lane.',
      });
    }
  }

  const scannedLanes = new Set(diagnostics.filter((item) => item.ok).map((item) => item.lane));
  if (scannedLanes.size === 0) {
    console.error('No free X source available. Browser-backed Nitter failed for every lane.');
    console.error('Durable free fix: run a local self-hosted Nitter and set NITTER_URL=http://127.0.0.1:8788.');
    console.error('Manual fallback URLs:');
    printMarkdown();
    process.exit(3);
  }

  if (!options.readOnly) {
    writeState({
      ...state,
      seenTweetIds: [...newSeenTweetIds].slice(-1000),
    });
  }

  console.log(JSON.stringify({
    provider: 'browser-nitter',
    lastRunAt,
    searchWindow: sinceDate(lastRunAt) ? `since ${sinceDate(lastRunAt)}` : null,
    mirrors,
    posts,
    diagnostics,
  }, null, 2));
}

function printMarkdown(lastRunAt = readLastRun()) {
  console.log(lastRunAt ? `Last run: ${lastRunAt}` : 'Last run: never recorded');
  console.log(lastRunAt ? `Search window: since ${lastRunAt.slice(0, 10)}` : 'Search window: no previous run timestamp');
  for (const item of queries) {
    console.log(`- ${item.title}: ${item.signal}`);
    console.log(`  ${xSearchUrl(item.query, lastRunAt)}`);
  }
}

function printJson(lastRunAt = readLastRun()) {
  console.log(JSON.stringify(queries.map((item) => ({
    ...item,
    lastRunAt,
    searchWindow: sinceDate(lastRunAt) ? `since ${sinceDate(lastRunAt)}` : null,
    url: xSearchUrl(item.query, lastRunAt),
  })), null, 2));
}

function openUrls(lastRunAt = readLastRun()) {
  for (const item of queries) {
    const result = spawnSync('open', [xSearchUrl(item.query, lastRunAt)], { stdio: 'inherit' });
    if (result.status !== 0) process.exit(result.status ?? 1);
  }
}

let args;
try {
  args = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(error.message);
  usage();
  process.exit(2);
}

const lastRunAt = lookbackRunAt(args.days) || readLastRun();

if (args.mode === '--markdown') {
  printMarkdown(lastRunAt);
} else if (args.mode === '--json') {
  printJson(lastRunAt);
} else if (args.mode === '--open') {
  openUrls(lastRunAt);
} else if (args.mode === '--scan') {
  await scan({
    lastRunAt,
    readOnly: Boolean(args.days),
    ignoreSeen: Boolean(args.days),
  });
} else if (args.mode === '--mark-run') {
  if (args.days) {
    console.error('--mark-run cannot be combined with --days');
    process.exit(2);
  }
  markRun();
} else {
  usage();
  process.exit(2);
}
