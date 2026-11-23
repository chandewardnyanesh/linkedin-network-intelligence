#!/bin/sh
# Configure the GitHub repository for discoverability.
#
#     sh scripts/setup-github.sh [owner/repo]
#
# Sets the repository description, homepage and topics, and turns on GitHub
# Pages from /docs. Needs the `gh` CLI authenticated with a token that has
# repo scope — repository settings cannot be changed through a read-only or
# proxied token.
#
# Everything here is a one-off. The files that do the lasting work — README,
# llms.txt, docs/index.html with its structured data, docs/FAQ.md — are already
# in the repository.
set -e

REPO="${1:-chandewardnyanesh/linkedin-network-intelligence}"
OWNER=$(echo "$REPO" | cut -d/ -f1)
NAME=$(echo "$REPO" | cut -d/ -f2)
PAGES_URL="https://${OWNER}.github.io/${NAME}/"

# 350 characters is GitHub's limit. Front-loaded with what people search for,
# and it names the differentiator, because this line is the snippet the skill
# directories and search engines show.
DESCRIPTION="12 Claude Agent Skills for LinkedIn network intelligence: ICP builder, candidate discovery, a configurable 100-point scoring engine, engagement propensity, networking CRM (SQLite/Postgres), lead intelligence, connection drafting and funnel reporting. No scraping, no automation, no session cookies - it drafts and records, you act. MIT."

# Up to 20 topics. These drive GitHub's own search and are read by the skill
# directories that index this ecosystem.
TOPICS="linkedin claude-skills agent-skills claude-code linkedin-crm crm icp lead-scoring lead-generation networking relationship-management b2b-sales social-selling personal-branding python pydantic sqlite no-scraping open-source ai-agents"

echo "Repository: $REPO"
echo

echo "Description and homepage..."
gh repo edit "$REPO" --description "$DESCRIPTION" --homepage "$PAGES_URL"

echo "Topics..."
# One flag per topic: portable across gh versions, and a single bad topic then
# fails loudly instead of silently dropping the whole list.
TOPIC_ARGS=""
for t in $TOPICS; do
  TOPIC_ARGS="$TOPIC_ARGS --add-topic $t"
done
# shellcheck disable=SC2086
gh repo edit "$REPO" $TOPIC_ARGS

echo "Issues on, wiki and projects off..."
gh repo edit "$REPO" --enable-issues --enable-wiki=false --enable-projects=false

echo "GitHub Pages from /docs..."
BRANCH=$(gh repo view "$REPO" --json defaultBranchRef --jq '.defaultBranchRef.name')
if gh api "repos/$REPO/pages" >/dev/null 2>&1; then
  gh api -X PUT "repos/$REPO/pages" \
    -f "source[branch]=$BRANCH" -f "source[path]=/docs" >/dev/null
  echo "  updated (was already on)"
else
  gh api -X POST "repos/$REPO/pages" \
    -f "source[branch]=$BRANCH" -f "source[path]=/docs" >/dev/null
  echo "  enabled"
fi

echo
echo "Verify:"
echo "  gh repo view $REPO --json description,homepage,repositoryTopics"
echo
echo "Pages takes a minute or two to build, then check:"
echo "  $PAGES_URL"
echo "  ${PAGES_URL}llms.txt"
echo "  ${PAGES_URL}sitemap.xml"
echo
echo "Then submit the sitemap once in Google Search Console and Bing Webmaster"
echo "Tools. The skill directories find the repository on their own crawl."
echo "See docs/DISCOVERABILITY.md."
