#!/usr/bin/env python3
"""Scan a work dir (renders, lane reports, digests, the draft report) for credential-looking strings before
anything is shared. Usage: secret_scan.py <dir-or-file> [--all]   exit 1 if any HIGH finding.

Transcripts contain whatever people pasted: API keys, tokens, connection strings, private keys. Renders and
lane reports quote transcripts, so they inherit them. Run this on the work dir before a report leaves the
machine, and on the report file itself. Findings are printed masked (first 4 + last 2 chars).
By default sessions.jsonl / grade_in.jsonl / graded.jsonl are skipped (bulk files that never leave the
machine and would flood the output); --all includes them.
"""
import os, re, sys, argparse

HIGH = {
    'private_key_block': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY'),
    'aws_access_key': re.compile(r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b'),
    'github_token': re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b'),
    'anthropic_key': re.compile(r'\bsk-ant-[A-Za-z0-9_-]{20,}'),
    'openai_key': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}'),
    'slack_token': re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}'),
    'google_api_key': re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b'),
    'stripe_key': re.compile(r'\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b'),
    'jwt': re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
    'url_with_password': re.compile(r'\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]{4,}@[^\s/]+'),
    'bearer_token': re.compile(r'\b[Bb]earer\s+[A-Za-z0-9._~+/-]{20,}=*'),
    # `_` counts as a separator so DB_PASSWORD= / AWS_SECRET_ACCESS_KEY= / X_API_KEY= match; bare `pwd` excluded (shell builtin)
    'password_assignment': re.compile(r'(?i)(?:^|[^A-Za-z0-9])(?:password|passwd|secret(?:[_-]?access)?[_-]?key|secret|api[_-]?key|access[_-]?token|auth[_-]?token|oauth[_-]?token|client[_-]?secret|private[_-]?key)\s*[=:]\s*["\']?[^\s"\',;]{8,}'),
    'curl_basic_auth': re.compile(r'(?:^|\s)(?:-u|--user)\s+["\']?[^\s:"\']{2,}:[^\s"\']{4,}'),
}
LOW = {
    'email_address': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    'ipv4_non_local': re.compile(r'\b(?!10\.|127\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|0\.)(?:\d{1,3}\.){3}\d{1,3}\b'),
}
FALSE_POSITIVE_VALUES = re.compile(r'(?i)^(?:\$\{?[a-z_]+|<[^>]+>|\*{3,}|[a-z]{0,6}_?x{3,}\b|\.{3,}|redacted|changeme|example|placeholder|your[_-])')
BULK = {'sessions.jsonl', 'grade_in.jsonl', 'graded.jsonl', 'risky_cmds.jsonl'}
EXT = {'.md', '.txt', '.json', '.jsonl', '.js', '.py', '.csv', '.html'}


def mask(s):
    return s if len(s) <= 8 else s[:4] + '…' + s[-2:]


def scan_file(path, findings):
    try:
        text = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return
    for ln, line in enumerate(text.splitlines(), 1):
        for name, rx in HIGH.items():
            for m in rx.finditer(line):
                val = m.group(0)
                if name == 'password_assignment':
                    tail = re.split(r'[=:]', val, 1)[-1].strip(' "\'')
                elif name == 'bearer_token':
                    tail = val.split(None, 1)[1]
                elif name == 'curl_basic_auth':
                    tail = val.split(':', 1)[-1]
                else:
                    tail = val
                if tail.startswith('/'):
                    continue  # a path, not a credential (e.g. orig_pwd=/some/dir)
                if FALSE_POSITIVE_VALUES.match(tail):
                    continue
                findings.append(('HIGH', name, path, ln, mask(val)))
        for name, rx in LOW.items():
            n = len(rx.findall(line))
            if n:
                findings.append(('low', name, path, ln, f'{n}×'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target')
    ap.add_argument('--all', action='store_true', help='include bulk jsonl files')
    a = ap.parse_args()
    findings = []
    if os.path.isfile(a.target):
        scan_file(a.target, findings)
    else:
        for root, dirs, files in os.walk(a.target):
            dirs[:] = [d for d in dirs if d != '.git']
            for fn in files:
                if os.path.splitext(fn)[1] not in EXT:
                    continue
                if fn in BULK and not a.all:
                    continue
                scan_file(os.path.join(root, fn), findings)
    high = [f for f in findings if f[0] == 'HIGH']
    low = [f for f in findings if f[0] == 'low']
    for sev, name, path, ln, val in high:
        print(f"{sev} {name:22s} {path}:{ln}  {val}")
    lowc = {}
    for f in low:
        lowc[(f[1], f[2])] = lowc.get((f[1], f[2]), 0) + 1
    for (name, path), n in sorted(lowc.items()):
        print(f"low  {name:22s} {path}  ({n} lines)")
    print(f"\n{len(high)} HIGH findings, {len(low)} low-severity lines (emails / public IPs: fine locally, redact before sharing outside)", file=sys.stderr)
    return 1 if high else 0


if __name__ == '__main__':
    raise SystemExit(main())
