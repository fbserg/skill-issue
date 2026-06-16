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

1. Fetch all push/admin collaborators' public keys from GitHub
2. Encrypt `.env` to all of them → `.env.age`
3. Commit `.env.age` and `.env.age.recipients` (shows the recipient set in diffs); keep `.env*` in `.gitignore`
4. Each collaborator decrypts with their own SSH private key

No key rotation needed when someone joins — re-encrypt with updated collaborator list. Remove someone → re-encrypt without their key and rotate the secrets.

## Install

The script lives at `tools/secrets/secrets` in this repo.  Put it on your PATH with one command:

```bash
curl -fsSL https://raw.githubusercontent.com/fbserg/skill-issue/main/tools/secrets/secrets \
  -o ~/.local/bin/secrets && chmod +x ~/.local/bin/secrets
```

**Caveat:** this curl one-liner pulls from `main` with no checksum — inspect the script before `chmod +x`, or pin a specific commit SHA in the URL (replace `main` with the full SHA). The inline dependency ranges (`pyrage>=1.2`, `httpx>=0.28`) float: `uv` resolves them fresh from PyPI on each run. Acceptable for a private team tool; pin the versions in the script header if you need reproducible builds.

Or just symlink it if you have the repo checked out:

```bash
ln -s "$(pwd)/tools/secrets/secrets" ~/.local/bin/secrets
```

Dependencies install automatically via `uv` (the shebang uses `uv run --script`). You also need the `gh` CLI authenticated.

## Usage

```bash
# One-time: add .env* to .gitignore before encrypting (.env.bak is also plaintext)
echo '.env*' >> .gitignore

# Encrypt for all push/admin collaborators
secrets encrypt

# Commit both encrypted files (recipient set is visible in the diff)
git add .env.age .env.age.recipients
git commit -m "chore: update encrypted env"

# Decrypt (auto-discovers your SSH key; backs up existing .env if it differs)
secrets decrypt

# Decrypt with a specific key:
secrets decrypt --key ~/.ssh/id_ed25519

# Decrypt via 1Password:
secrets decrypt --key-cmd op --key-arg read --key-arg op://Vault/SSH/private_key

# Print plaintext to stdout (pipe to another tool):
secrets decrypt --print

# CI: skip interactive confirmation (off-TTY requires --yes)
secrets encrypt --yes

# CI: when the recipient set has changed, also pass --accept-recipient-change
secrets encrypt --yes --accept-recipient-change

# Encrypt even if some collaborators have no GitHub SSH key (they won't decrypt)
secrets encrypt --allow-missing
```

## When to re-encrypt

| Event | Action |
|---|---|
| `.env` values changed | `encrypt` + commit |
| Collaborator added | `encrypt` + commit |
| Collaborator removed | rotate secrets in `.env`, then `encrypt` + commit |

Re-encrypting without rotating doesn't revoke access — the old ciphertext is still in git history and the removed person still has their private key.

## Threat model

- **Recipient set is the trust root (most important).** Recipients are resolved live from `github.com/<user>.keys` every encrypt. A collaborator who adds an attacker-controlled key — or whose account is compromised — silently becomes able to decrypt on the next encrypt+commit. Defense: the `encrypt` confirmation table + the committed `.env.age.recipients` manifest + the drift warning make any change reviewable. Review manifest diffs like you review code, and use branch protection on `.env.age`.
- **Manifest fingerprints are reviewer-verifiable, not cryptographic proof.** The manifest now contains canonical OpenSSH SHA256 fingerprints (the same format `ssh-keygen -lf` prints). A reviewer CAN verify a fingerprint against GitHub: `ssh-keygen -lf <(curl -fsSL https://github.com/<login>.keys)`. However, pyrage does not expose a way to enumerate the actual recipient keys baked into `.env.age`, so the manifest is reviewer-verifiable evidence of the *intended* recipients — not cryptographic proof of the ciphertext's real recipients. Treat the manifest diff as a code-review surface, backed by branch protection.
- **`affiliation=all` over-inclusion.** On an *org* repo, GitHub's collaborator list can include org members who have access via default org permissions, not just directly-added people. The confirmation table shows exactly who will be a recipient — read it before confirming. (The script scopes to push/admin collaborators, but verify the list on org repos.)
- **No sender authentication.** age multi-recipient ciphertext is integrity-protected against outsiders, but ANY recipient can re-encrypt a forged `.env.age` that every other recipient will decrypt without warning. Treat a decrypted `.env` as only as trustworthy as the least-trusted collaborator; require reviewed/signed commits for `.env.age`.
- **Anyone with write access can re-encrypt** to a new recipient set; the only signal is the manifest diff. This is why the manifest must be committed and reviewed.
- **`--key-cmd` runs an arbitrary command.** Never populate it from repo-controlled input (Makefile, config). It's for your local key manager only.
- **Plaintext & keys at rest.** `decrypt` (without `--print`) writes `.env` to disk (mode 600, but still plaintext). Prefer `--print` piped to the consumer on shared machines. A decrypted `.env` is exactly as sensitive as the secrets in it.
- **Public-repo fingerprint oracle.** age embeds a 32-bit fingerprint per recipient key. On a PUBLIC repo, anyone can enumerate fingerprints and confirm which GitHub accounts a file was encrypted to — a membership oracle. Keep `.env.age` in private repos.
- **Removed collaborators / git history.** Every committed `.env.age` is a permanent grant to whoever its recipients were at that commit. Re-encrypting does not revoke old ciphertext. On removal OR suspected key compromise: rotate the actual secret values, don't just re-encrypt.

## Gotchas

**Key type filtering** — the script only accepts `ssh-ed25519` and `ssh-rsa`. Users with only `ecdsa-sha2-nistp256` or hardware security keys (`sk-*`) will be excluded and won't be able to decrypt. Have them add an ed25519 key to GitHub.

**Weak-key warning** — `ssh-rsa` keys trigger a stderr warning per recipient. ed25519 is preferred; rsa is the weak link.

**Passphrase-protected keys** — `find_ssh_identity` reads the key file directly. If your key has a passphrase, `ssh.Identity.from_buffer` will prompt for it on decrypt.

**Bot accounts** — logins ending in `[bot]` (e.g. `dependabot[bot]`) are automatically excluded from the recipient list.

**Missing-key safety** — if any collaborator has no usable GitHub SSH key, `encrypt` refuses by default. Pass `--allow-missing` to proceed anyway (those people cannot decrypt).

**Sub-2048 RSA keys** — if a collaborator's RSA key is smaller than 2048 bits, it will be skipped with a warning rather than crashing. They fall into the missing-key path and `--allow-missing` governs whether encrypt proceeds.

## Alternatives

| Tool | When to use instead |
|---|---|
| [SOPS](https://getsops.io/) | Need cloud KMS (AWS/GCP/Azure), YAML/JSON format support, or audit metadata |
| [agebox](https://github.com/slok/agebox) | Multiple secret files in a GitOps repo with a persistent recipients file |
| [git-crypt](https://github.com/AGWA/git-crypt) | Transparent git filter; no per-collaborator key management needed |

For a single `.env` file on a GitHub-hosted team, this script is the minimal solution. SOPS is the next step up if requirements grow.
