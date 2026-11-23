#!/bin/sh
# Configure the GitHub repository for discoverability.
#
#     sh scripts/setup-github.sh [owner/repo]
#
# Sets the repository description, homepage and topics, and turns on GitHub
# Pages from /docs on the default branch. Needs the `gh` CLI, authenticated
# with a token that has repo scope.
#
# Everything here is a one-off. The files that do the lasting work — README,
# llms.txt, docs/index.html with its structured data, docs/FAQ.md — are already
# in the repository.
set -e

REPO="${1:-chandewardnyanesh/linkedin-network-intelligence}"
OWNER="$(echo "$REPO" | cut -d/ -f1)"
NAME="$(echo "$REPO" | cut -d/ -f2)"
PAGES_URL="https://${OWNER}.github.io/${NAME}/"

# 350 characters is GitHub's limit. Front-loaded with what people search for,
# and it names the differentiator, because this line is what the skill
# directories and search engines show as the snippet.
DESCRIPTION="12 Claude Agent Skills for LinkedIn network intelligence: ICP builder, candidate discovery, a configurable 100-point scoring engine, engagement propensity, networking CRM (SQLite/Postgres), lead intelligence, connection drafting and funnel reporting. No scraping, no automation, no session cookies - it drafts and records, you act. MIT."

# Up to 20 topics. GitHub topics drive GitHub's own search and are read by the
# skill directories that index this ecosystem.
TOPICS="linkedin,claude-skills,agent-skills,claude-code,linkedin-crm,crm,icp,lead-scoring,lead-generation,networking,relationship-management,b2b-sales,social-selling,personal-branding,python,pydantic,sqlite,no-scraping,open-source,ai-agents"

echo "Repository: $REPO"
echo

echo "Setting description and homepage..."
gh repo edit "$REPO" --description "$DESCRIPTION" --homepage "$PAGES_URL"

echo "Setting topics..."
gh repo edit "$REPO" --add-topic "$(echo "$TOPICS" | tr ',' ' ' | tr ' ' ',')" 2>/dev/null || {
  # Older gh versions take one --add-topic per flag.
  for t in $(echo "$TOPICS" | tr ',' ' '); do
    gh repo edit "$REPO" --add-topic "$t" >/dev/null
  done
}

echo "Enabling GitHub Pages from /docs..."
BRANCH="$(gh repo view "$REPO" --json defaultBranchRef --jq '.defaultBranchRef.name')"
gh api -X POST "repos/$REPO/pages" \
  -f "source[branch]=$BRANCH" -f "source[path]=/docs" >/dev/null 2>&1 || \
gh api -X PUT "repos/$REPO/pages" \
  -f "source[branch]=$BRANCH" -f "source[path]=/docs" >/dev/null 2>&1 || \
  echo "  (Pages may already be on, or needs enabling in Settings > Pages)"

echo
echo "Done. Verify:"
echo "  gh repo view $REPO --json description,homepage,repositoryTopics"
echo
echo "The Pages site takes a minute or two to build, then:"
echo "  $PAGES_URL"
echo "  ${PAGES_URL}llms.txt"
echo "  ${PAGES_URL}sitemap.xml"
echo
echo "Then submit the sitemap once, in Google Search Console and Bing Webmaster"
echo "Tools, and the skill directories will pick the repository up on their own"
echo "crawl. See docs/DISCOVERABILITY.md."
