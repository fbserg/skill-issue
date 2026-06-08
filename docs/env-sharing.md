# Team env sharing with age + GitHub SSH keys

Optional pattern for private team repos: encrypt `.env` once for every
collaborator. Anyone with a GitHub SSH key and repo access can decrypt — no
shared passwords, no out-of-band key exchange.

Do not use this pattern for public repositories unless the encrypted file is
intentionally public metadata and the underlying secrets can be rotated. If a
collaborator is removed, re-encrypting is not enough; rotate the plaintext
secrets because old ciphertext remains in git history.

## How it works

[age](https://github.com/FiloSottile/age) supports multiple recipients: encrypt once, any matching private key decrypts. GitHub exposes every user's public SSH keys at `github.com/<user>.keys`. Combine the two:

1. Fetch all collaborators' public keys from GitHub
2. Encrypt `.env` to all of them → `.env.age`
3. Commit `.env.age`; keep `.env` in `.gitignore`
4. Each collaborator decrypts with their own SSH private key

No key rotation needed when someone joins — re-encrypt with updated collaborator list. Remove someone → re-encrypt without their key and rotate the secrets.

## Dependencies

```bash
pip install pyrage httpx   # or: uv add pyrage httpx
```

`pyrage` is the Python binding for age. `httpx` fetches GitHub keys. You also need the `gh` CLI authenticated.

## Script

Drop this in `scripts/secrets` (or anywhere on `PATH`) and make it executable:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["pyrage>=1.2", "httpx>=0.28"]
# ///
"""Encrypt/decrypt .env using age + GitHub SSH keys.

Usage:
    uv run scripts/secrets encrypt
    uv run scripts/secrets decrypt
    uv run scripts/secrets decrypt --print
    uv run scripts/secrets decrypt --key ~/.ssh/id_ed25519
    uv run scripts/secrets decrypt --key-cmd op --key-arg read --key-arg op://Vault/SSH/private_key
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx
import pyrage
from pyrage import ssh

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
AGE_FILE = ROOT / ".env.age"

DEFAULT_SSH_KEY_PATHS = [
    Path.home() / ".ssh" / "id_ed25519",
    Path.home() / ".ssh" / "id_rsa",
]


def get_repo_slug() -> str:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        capture_output=True, text=True, check=True, cwd=ROOT,
    )
    return result.stdout.strip()


def get_collaborators(repo: str) -> list[str]:
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/collaborators", "--paginate"],
        capture_output=True, text=True, check=True,
    )
    return [u["login"] for u in json.loads(result.stdout)]


def fetch_ssh_keys(username: str) -> list[str]:
    resp = httpx.get(f"https://github.com/{username}.keys", timeout=10)
    resp.raise_for_status()
    return [
        line.strip()
        for line in resp.text.strip().splitlines()
        if line.strip().startswith(("ssh-ed25519", "ssh-rsa"))
    ]


def collect_recipients() -> list[ssh.Recipient]:
    repo = get_repo_slug()
    collaborators = get_collaborators(repo)
    print(f"repo: {repo}", file=sys.stderr)
    print(f"collaborators: {', '.join(collaborators)}", file=sys.stderr)

    recipients: list[ssh.Recipient] = []
    for user in collaborators:
        keys = fetch_ssh_keys(user)
        if not keys:
            print(f"  WARNING: {user} has no SSH keys on GitHub — they won't be able to decrypt", file=sys.stderr)
            continue
        for key in keys:
            recipients.append(ssh.Recipient.from_str(key))
        print(f"  {user}: {len(keys)} key(s)", file=sys.stderr)

    if not recipients:
        print("ERROR: no SSH keys found for any collaborator", file=sys.stderr)
        sys.exit(1)

    return recipients


def find_ssh_identity(
    key_path: str | None = None,
    key_cmd: str | None = None,
    key_args: list[str] | None = None,
) -> ssh.Identity:
    if key_cmd:
        result = subprocess.run([key_cmd, *(key_args or [])], capture_output=True, check=True)
        return ssh.Identity.from_buffer(result.stdout)

    if key_path:
        path = Path(key_path).expanduser()
        if not path.exists():
            print(f"ERROR: key not found: {path}", file=sys.stderr)
            sys.exit(1)
        return ssh.Identity.from_buffer(path.read_bytes())

    for path in DEFAULT_SSH_KEY_PATHS:
        if path.exists():
            return ssh.Identity.from_buffer(path.read_bytes())

    print(
        "ERROR: no SSH private key found.\n"
        f"  searched: {', '.join(str(p) for p in DEFAULT_SSH_KEY_PATHS)}\n"
        "  hint: use --key <path> or --key-cmd <command>",
        file=sys.stderr,
    )
    sys.exit(1)


def cmd_encrypt() -> None:
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found", file=sys.stderr)
        sys.exit(1)
    recipients = collect_recipients()
    encrypted = pyrage.encrypt(ENV_FILE.read_bytes(), recipients)
    AGE_FILE.write_bytes(encrypted)
    print(f"\nencrypted {ENV_FILE.name} → {AGE_FILE.name} ({len(recipients)} recipient key(s))", file=sys.stderr)


def cmd_decrypt(
    *,
    to_stdout: bool = False,
    key_path: str | None = None,
    key_cmd: str | None = None,
    key_args: list[str] | None = None,
) -> None:
    if not AGE_FILE.exists():
        print(f"ERROR: {AGE_FILE} not found — run 'encrypt' first", file=sys.stderr)
        sys.exit(1)
    identity = find_ssh_identity(key_path, key_cmd, key_args)
    plaintext = pyrage.decrypt(AGE_FILE.read_bytes(), [identity])
    if to_stdout:
        sys.stdout.buffer.write(plaintext)
    else:
        ENV_FILE.write_bytes(plaintext)
        print(f"decrypted {AGE_FILE.name} → {ENV_FILE.name}", file=sys.stderr)


def parse_flag(args: list[str], flag: str) -> str | None:
    try:
        idx = args.index(flag)
        return args[idx + 1]
    except (ValueError, IndexError):
        return None


def parse_repeated_flag(args: list[str], flag: str) -> list[str]:
    values: list[str] = []
    index = 0
    while index < len(args):
        if args[index] == flag and index + 1 < len(args):
            values.append(args[index + 1])
            index += 2
            continue
        index += 1
    return values


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("encrypt", "decrypt"):
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    match args[0]:
        case "encrypt":
            cmd_encrypt()
        case "decrypt":
            cmd_decrypt(
                to_stdout="--print" in args,
                key_path=parse_flag(args, "--key"),
                key_cmd=parse_flag(args, "--key-cmd"),
                key_args=parse_repeated_flag(args, "--key-arg"),
            )


if __name__ == "__main__":
    main()
```

## Usage

```bash
# Add to .gitignore
echo ".env" >> .gitignore

# First time or after changing .env or collaborators
uv run scripts/secrets encrypt

# Commit the encrypted file
git add .env.age && git commit -m "chore: update encrypted env"

# New collaborator onboarding
uv run scripts/secrets decrypt
# or with a specific key:
uv run scripts/secrets decrypt --key ~/.ssh/id_ed25519
# or via 1Password:
uv run scripts/secrets decrypt --key-cmd op --key-arg read --key-arg op://Vault/SSH/private_key
```

## When to re-encrypt

| Event | Action |
|---|---|
| `.env` values changed | `encrypt` + commit |
| Collaborator added | `encrypt` + commit |
| Collaborator removed | rotate secrets in `.env`, then `encrypt` + commit |

Re-encrypting without rotating doesn't revoke access — the old ciphertext is still in git history and the removed person still has their private key.

## Gotchas

**Key type filtering** — the script only accepts `ssh-ed25519` and `ssh-rsa`. Users with only `ecdsa-sha2-nistp256` or hardware security keys (`sk-*`) will hit the "no SSH keys" warning and won't be able to decrypt. Have them add an ed25519 key to GitHub.

**Non-anonymous recipients** — age embeds a 32-bit fingerprint of each recipient's public key in the ciphertext. Anyone with the `.env.age` file can see *which* SSH keys it was encrypted for (not the content). Non-issue for a private team repo; worth knowing if the repo is public.

**Passphrase-protected keys** — `find_ssh_identity` reads the key file directly. If your key has a passphrase, `ssh.Identity.from_buffer` will prompt for it on decrypt.

## Alternatives

| Tool | When to use instead |
|---|---|
| [SOPS](https://getsops.io/) | Need cloud KMS (AWS/GCP/Azure), YAML/JSON format support, or audit metadata |
| [agebox](https://github.com/slok/agebox) | Multiple secret files in a GitOps repo with a persistent recipients file |
| [git-crypt](https://github.com/AGWA/git-crypt) | Transparent git filter; no per-collaborator key management needed |

For a single `.env` file on a GitHub-hosted team, this script is the minimal solution. SOPS is the next step up if requirements grow.
