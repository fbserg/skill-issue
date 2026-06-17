# gmail-tools

A deliberately **draft-only** Gmail CLI: search, read threads, manage labels,
download attachments, and compose drafts from the terminal or an agent — but
**never send**.

Every Gmail API resource is wrapped in a proxy (`NoSendGmailService`) that raises
on any `send` endpoint. The only way a message leaves the mailbox is a human
opening the draft in Gmail and clicking send. There is no flag to override this,
which makes the tool safe to hand to an automated agent: the worst it can do is
queue a draft for your review.

## Why

Letting an LLM agent send email is a standing liability. This tool gives an agent
everything it needs to triage an inbox and prepare replies — full read access,
labels, attachments, multipart drafts with your real signature — while making the
send action structurally impossible. Review and send stay human.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — the script declares its Google dependencies
  inline (PEP 723) and `uv` installs them into an isolated cache on first run. No
  manual `pip install` or virtualenv.
- A Google Cloud OAuth client (Desktop type). See setup below.

## Setup

1. **Create an OAuth client.** In the [Google Cloud Console](https://console.cloud.google.com/),
   create (or pick) a project, enable the **Gmail API**, then under
   *APIs & Services → Credentials* create an **OAuth client ID** of type
   **Desktop app**. Download the JSON.

2. **Save the client JSON** to `~/.gmail-tools/oauth-keys.json` (the JSON should
   have a top-level `"installed"` key — Desktop clients do).

3. **Authorize.** Run:

   ```bash
   gmail-tools auth                 # opens a browser; sign in and grant access
   gmail-tools auth-check           # -> {"ok": true, ...}
   ```

   `auth` caches a refresh token at `~/.gmail-tools/credentials.json`. Tokens
   refresh automatically afterward.

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `GMAIL_TOOLS_TOKEN` | `~/.gmail-tools/credentials.json` | Cached OAuth token (written by `auth`). |
| `GMAIL_TOOLS_OAUTH_KEYS` | `~/.gmail-tools/oauth-keys.json` | Your downloaded OAuth client JSON. |

Scopes requested: `gmail.modify` (read/label/draft) and `gmail.settings.basic`
(read your signature). No send scope is requested.

## Subcommands

| Command | What it does |
|---|---|
| `auth [--email HINT] [--port N]` | Authorize OAuth and cache a token. |
| `auth-check [--query Q] [--max N]` | Refresh the token and confirm search works. |
| `search QUERY [--max N]` | Search messages; prints id/threadId/subject/from/date/snippet. |
| `thread REF [--latest N] [--compact]` | Read a thread by thread **or** message id. |
| `attachments THREAD_ID` | List attachment metadata across a thread. |
| `save-attachment MSG_ID ATT_ID --out PATH` | Download one attachment to disk. |
| `signature` | Print your primary send-as signature as plain text. |
| `draft --to --subject --body [--thread-id] [--from-addr] [--html] [--append-signature] [--attach PATH]` | Create a draft (multipart plain+HTML). **Never sends.** |
| `message-id THREAD_ID` | Print the newest `Message-ID` header in a thread. |
| `label THREAD_ID LABEL` | Apply a label to a thread (creates it if missing). |
| `labels` | List user labels with thread/message counts. |
| `delete-label NAME [--yes]` | Delete a user label (emails untouched; system labels refused). |
| `rename-label OLD NEW` | Rename a user label. |
| `list-drafts [--subject-q SUBSTR] [--max N]` | List drafts, optionally by subject substring. |
| `delete-draft SUBJECT_SUBSTR [--yes]` | Delete all drafts matching a subject substring. |

`delete-label` and `delete-draft` prompt for confirmation; pass `--yes` to skip
it in scripts.

Most commands print JSON to stdout, so they pipe cleanly into `jq` or an agent.

## Examples

```bash
gmail-tools search "is:unread in:inbox" --max 10
gmail-tools thread 18c2f… --latest 3 --compact
gmail-tools draft \
  --to client@example.com \
  --subject "Re: your question" \
  --body "Thanks — here's the update…" \
  --thread-id 18c2f… \
  --append-signature
# Then open Gmail, review the draft, and send it yourself.
```

## Safety notes

- **Draft-only by construction.** The send guard is in the API proxy, not behind a
  flag. Removing it requires editing the source.
- Drafts created in a thread reuse the thread's `Message-ID` for proper
  `In-Reply-To`/`References` headers, so replies thread correctly once you send.
- `delete-label`/`delete-draft` only touch labels and draft messages — never your
  received or sent mail.
