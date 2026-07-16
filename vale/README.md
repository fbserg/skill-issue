# AItells — a vale style for catching AI-tell prose

`AItells` is a merged, curated [vale](https://vale.sh) style for flagging the
recurring tells of LLM-written prose: banned slop phrases, chatbot artifacts,
rhetorical tics (mic-drops, stacked anaphora, despite-formulas), and
speculative structural patterns (tricolons, hedging density) that correlate
with generated text but also false-positive against normal human writing.

It merges three sources:

1. **Base** — the house `etc` style (`Slop`, `Swaps`, `Artifacts`, and the
   rest), carried over rule-for-rule, severity-for-severity.
2. **Upstream** — high-precision rules cherry-picked from
   [`ammil-industries/vale-signs-of-ai-writing`](https://github.com/ammil-industries/vale-signs-of-ai-writing).
3. **Reference pack** — a curated, trimmed subset of a richer 44-rule
   AI-tells pack, merged and deduplicated against 1 and 2.

## Severity tiers

Every rule carries one of three `level`s:

- **`error`** — unambiguous slop (`Slop.yml`, `Swaps.yml`, `Artifacts.yml`).
  Nothing was promoted into this tier beyond what the base style already
  flagged as `error`.
- **`warning`** — high-precision structural AI tells: despite-formulas,
  copula dodges ("serves as"/"stands as"), rhetorical self-answers,
  mic-drops, stacked anaphora, sycophancy/closing-pleasantry chat register,
  scare quotes.
- **`suggestion`** — speculative or false-positive-prone patterns: hedging
  density, formal transitions ("however"/"therefore"/"consequently"),
  stuffy vocabulary, false-balance both-sidesing, verb tricolons,
  defensive hedges, absolute-assertion overreach. Worth a second look, not
  worth blocking on.

A repo that sets `MinAlertLevel = warning` never sees the `suggestion` tier.
Opt in with `MinAlertLevel = suggestion` to see everything.

Known false-positive traps were deliberately encoded as exclusions rather
than rediscovered per-repo: bare "elevated", "navigate", "beacon",
"harness", "gateway" are never flagged (only narrowed forms like "elevate
your/the", "beacon of", "gateway to", "harness(ing) the" are); solo
"significant"/"important" are never flagged (anti-tells — more common in
human prose); plain A-B-and-C tricolons are suggestion-tier at most, never
warning or above.

## Wiring it into a repo

```ini
# .vale.ini
StylesPath = .vale/styles
MinAlertLevel = warning   # or `suggestion` to opt into the speculative tier
Packages = https://raw.githubusercontent.com/fbserg/skill-issue/main/vale/AItells.zip

[*.{md,txt}]
BasedOnStyles = AItells
```

Then:

```sh
vale sync
vale .
```

`vale sync` downloads `AItells.zip` and unpacks it under
`StylesPath/AItells/`.

### Disabling a single rule

Per-file, in `.vale.ini`:

```ini
[*.md]
BasedOnStyles = AItells
AItells.VerbTricolon = NO
```

### Updating the pinned package

Since `Packages` points at a raw URL rather than a GitHub release feed,
consumers get whatever is at `main` on their next `vale sync` — there's no
version pinning. Re-run `vale sync` to pick up changes.

## Rebuilding the package

After editing anything under `styles/AItells/`:

```sh
./build.sh
```

This re-zips `styles/AItells/` into `AItells.zip` with the same internal
layout vale expects (`AItells/*.yml` at the zip root, no wrapping
directory) — verified against the upstream `signs-of-ai-writing` release
zip's layout. Commit the rebuilt zip alongside the source changes.

## Rule inventory

| File | Tier | What it catches |
|---|---|---|
| `Slop.yml` | error | Banned AI-slop phrases (base) |
| `Swaps.yml` | error | Word substitutions: delve→dig, leverage→use, etc. (base) |
| `Artifacts.yml` | error | Raw chatbot/citation paste artifacts (base + upstream citation markers) |
| `Antithesis.yml` | warning | "not X, it's Y" AI antithesis (base) |
| `ColonLeadIns.yml` | warning | Colon lead-ins: ": including", ": such as" (base) |
| `EmDash.yml` | warning | Em dash (base) |
| `HedgedEnumeration.yml` | warning | "one of the most/first/few" (base) |
| `Intensifiers.yml` | warning | Weasel intensifiers: actually, truly, essentially (base) |
| `NumberedTransitions.yml` | warning | Firstly/secondly/thirdly scaffolding (base) |
| `Suspects.yml` | warning | AI-staple nouns: landscape, ecosystem, tapestry, paradigm (base) |
| `VagueAttribution.yml` | warning | "experts say", "studies show" with no source (base) |
| `DespiteChallenges.yml` | warning | "despite these challenges" dismissal formula |
| `CopulaDodge.yml` | warning | "serves as an"/"represents a significant"/"boasts a" copula-inflation dodges |
| `RhetoricalDrama.yml` | warning | Self-answered rhetorical questions, antithetical-balance pairs, stacked anaphora |
| `ChatRegister.yml` | warning | Chatbot pleasantries, sycophancy, and explainer announcements leaking into prose |
| `ScareQuotes.yml` | warning | "so-called 'X'" scare quotes (straight and curly quotes) |
| `MicDrop.yml` | suggestion | Short dramatic sentence closers ("It matters.", "Full stop.") — matches ordinary human sentences too, so kept speculative |
| `Hedging.yml` | suggestion | Hedging-phrase density (>2 per scope) |
| `FormalTransitions.yml` | suggestion | However/therefore/consequently-style formal connectors |
| `FormalVocabulary.yml` | suggestion | "aspect"/"facet" overuse plus stuffy register (facilitate, commence, ascertain) |
| `FalseBalance.yml` | suggestion | Both-sidesing and manufactured nuance |
| `VerbTricolon.yml` | suggestion | Three parallel verb phrases in a row |
| `DefensiveHedges.yml` | suggestion | Preemptive "might seem X, but" concessions |
| `AbsoluteAssertions.yml` | suggestion | "the only way to"/"make no mistake" overreach |

## Verifying changes

There's no CI wired up for this package yet. Before committing a rule
change, do a scratch-directory check:

```sh
mkdir -p /tmp/vale-check/styles
cp -r styles/AItells /tmp/vale-check/styles/
cat > /tmp/vale-check/.vale.ini <<'EOF'
StylesPath = styles
MinAlertLevel = suggestion

[*.md]
BasedOnStyles = AItells
EOF
cd /tmp/vale-check
vale sample.md   # sample.md: your test prose
```

Confirm known slop flags, known-clean text doesn't, and the run exits
without rule-compile errors.
