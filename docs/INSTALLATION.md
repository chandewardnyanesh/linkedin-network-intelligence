# Installation

Python 3.12 or newer. Two runtime dependencies. No credentials.

## 1. Get the package

```bash
git clone https://github.com/chandewardnyanesh/linkedin-network-intelligence.git
cd linkedin-network-intelligence
pip install -r requirements.txt
```

Or install it as a package, which also gives you an `lni` command:

```bash
pip install -e .
lni config-check
```

Verify:

```bash
python -m lni config-check
```

You should see the layers that loaded, the active scoring weights, the active
ICPs, `Safety rules loaded: 11`, and a list of the skills that will ask you for
something before they can work. That list is your setup task.

## 2. Install the skills in Claude Code

Three ways, in order of preference.

### As a plugin repository

The repository ships `.claude-plugin/plugin.json`, so Claude Code can load all
twelve skills plus the root workflow from a marketplace entry or a local path.
Point your plugin configuration at the repository root.

### By copying the skills

```bash
mkdir -p ~/.claude/skills
cp -R skills/* ~/.claude/skills/
cp SKILL.md ~/.claude/skills/linkedin-network-growth/SKILL.md  # the root workflow
```

Each `skills/<name>/` directory is self-contained and independently
installable: copy only the ones you want. `linkedin-policy-safety-governor` is
the exception — install it whatever else you take, because every other skill
routes through it.

### Per project

```bash
mkdir -p .claude/skills
cp -R /path/to/linkedin-network-intelligence/skills/* .claude/skills/
```

Project skills take precedence over personal ones, which is useful if you keep
a filled configuration per client.

## 3. Point it at your configuration

The package ships no personal data, so the next step is telling it who you are
and who you are looking for. Keep that outside the repository:

```bash
mkdir -p ~/.config/lni
cp config/examples/b2b-sales.yaml ~/.config/lni/local.yaml   # or another example
export LNI_CONFIG_DIR=~/.config/lni
$EDITOR ~/.config/lni/local.yaml
python -m lni config-check
```

Add the export to your shell profile so it persists. Details of every setting:
`CONFIGURATION.md`.

## 4. Create the store

```bash
python -m lni init
```

SQLite, at `./data/network.db` by default. Create it wherever you keep working
data; `data/` is gitignored.

### PostgreSQL instead

For a longer-lived or shared store:

```bash
pip install 'psycopg[binary]>=3.1'
export LNI_POSTGRES_DSN='postgresql://user:password@localhost:5432/lni'
```

Then set `storage.backend: postgres` in your configuration. The DSN is read
from the environment on purpose: a DSN in a YAML file is a DSN in git. The
schema and every repository method are identical across both backends.

## 5. Check it works

```bash
pip install -r requirements-dev.txt
python -m pytest
```

444 tests. If they pass, the safety layer, the scoring engine, the store and the
CLI are all behaving as documented.

A quick end-to-end check without any of your own data:

```bash
python -m lni safety-check "automate the invites"      # should refuse, exit 3
python -m lni safety-check "draft a note for this one" # should allow, exit 0
```

## Importing the skills into another compatible agent

The skills are plain Markdown with YAML frontmatter, following the Agent Skills
open standard. Nothing in them is Claude-specific.

To use them elsewhere:

1. **Copy the `skills/` directory** into whatever location your agent reads
   skills from. Each `SKILL.md` carries `name`, `description`, `license` and
   `metadata` in its frontmatter, and the body is the instruction set.
2. **Install the Python package too.** The skills call `python -m lni …` rather
   than reimplementing logic in prose, so an agent that can run shell commands
   gets the real engine; one that cannot will follow the documented workflow but
   cannot score, store or report.
3. **Keep the root `SKILL.md`** as the entry point. It routes to the other
   twelve and holds the twelve-step workflow.
4. **Install the governor.** If your agent cannot run the Python, the governor's
   prohibited list in its `SKILL.md` and in `config/safety.yaml` still needs to
   be in front of the model, because the rules are the point.

What the skills assume of the host: a way to read files, a way to ask the user
a question, and ideally a shell. They assume no network access, no browser and
no LinkedIn integration — by design.

## Updating

```bash
git pull
python -m pytest
python -m lni config-check
```

Your configuration lives in `$LNI_CONFIG_DIR` and your store in `data/`, so
neither is touched by a pull. If the schema version has moved, the first command
that opens the store migrates it. An older build refuses to write to a newer
store rather than corrupting it.

## Uninstalling

```bash
pip uninstall linkedin-network-intelligence
rm -rf ~/.claude/skills/linkedin-*
```

Your store and configuration are files you chose the location of; remove them
yourself. `python -m lni forget <id> --approve` removes one person's records if
you would rather do it selectively first.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Configuration problem: …` | A YAML file is malformed, or a setting tries to relax a control that cannot be relaxed. The message names the file and the setting. |
| `safety.prohibited is missing required rule(s)` | A rule was removed from `safety.yaml`. The configuration is invalid rather than permissive; restore the rule. |
| `scoring weights sum to 95, not 100` | Weights must total 100 so two profiles are never silently compared. Rescale. |
| `postgres backend selected but $LNI_POSTGRES_DSN is empty` | Export the DSN, or set the backend back to `sqlite`. |
| `the store is at schema version 2; this build understands 1` | Upgrade the package. An older build writing to a newer store is how data gets corrupted. |
| A skill keeps asking for an ICP | `python -m lni missing <skill-name>` lists exactly what it needs. No active ICP is falsifiable yet — it has no exclusion criteria or observable signals. |
| Everything scores low | Check the abstention counts. A thin record scores low by design; the fix is evidence, not a different weighting. |
