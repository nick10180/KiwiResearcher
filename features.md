Program: Kiwix Depth-Search Auto-Researcher
Goal

Given a user topic (string), the program should:

Find the best matching Wikipedia article(s) in a local Kiwix library.

Perform a depth-limited link crawl (BFS/priority) from those seed pages.

Extract structured claims and evidence signals from each page.

Build a small “topic corpus” with metadata + cross-links.

Produce a research brief: consensus, disputes, numbers, timeline, open questions, and a bibliography of visited pages.

Output should be reproducible and debuggable: same topic + same Kiwix snapshot → same crawl set (unless settings change).

Inputs / Outputs
Inputs

topic: string (e.g., “causes of the Bronze Age collapse”)

settings:

max_pages (e.g., 80)

max_depth (e.g., 2 or 3)

max_links_per_page (e.g., 30)

crawl_strategy: bfs | priority

link_filters:

namespace filters (main articles only, exclude Talk/File/Category)

disambiguation handling on/off

exclude list (stop words like “ISBN”, “Help:”)

scoring_weights:

relevance score weight

novelty/diversity weight

authority/quality heuristics weight

llm settings:

model name

context window strategy (chunking)

extraction temperature low (0–0.3)

writeup temperature medium (0.4–0.7)

Outputs

report.md (final writeup)

corpus.jsonl (one entry per page: title, url, plain text, links, sections, metadata)

claims.jsonl (one entry per claim: claim text, type, page, section, confidence cues, supporting snippets)

graph.json (nodes/pages and edges/links + scores)

run.log (why each page was chosen; crawl trace)

Optional: report.html with citations linking to local Kiwix URLs

Architecture Overview
Modules

Kiwix Access Layer

Responsible for finding articles and retrieving content.

Two common implementations:

Kiwix Serve HTTP endpoints (local server), scrape HTML.

Direct ZIM access via a ZIM reader library (faster, cleaner, less HTML noise).

Outputs:

page HTML

extracted plain text

outbound links list (article titles/URLs)

Page Normalizer

Converts HTML → structured document:

title

lead section

headings + section text

infobox key/value (if present)

references count (if parseable)

templates flags: stub, “citation needed”, “disputed”

Emits a PageDoc object.

Relevance Scorer

Scores candidate links for crawl expansion.

Score components:

lexical similarity to topic + extracted keywords

embedding similarity (optional but great locally)

link context: anchor text + surrounding sentence

page signals: length, stub flags, disambiguation flags

novelty penalty: avoid too many near-duplicates

Output: priority_score for each candidate page.

Crawler / Corpus Builder

Maintains frontier and visited sets.

Strategy options:

Priority BFS: BFS by depth, but within each depth pick top N by score.

Pure priority: always expand best scoring next, depth as soft limit.

Stops when reaching max_pages or frontier empty.

Logs rationale for each selection.

Claim Extractor (LLM)

Runs per page (or per section chunk).

Produces structured claims as JSON objects:

claim: concise statement

claim_type: definition | causal | numeric | timeline | comparative | disputed | quote

scope: what it applies to

hedging: detects “may”, “often”, “some historians…”

support_snippet: 1–3 short supporting excerpts (not long quotes)

page_title, section, anchor

evidence_signals: citation count in section (if known), “citation needed”, etc.

confidence: 0–1 (model-estimated, calibrated by heuristics)

Keeps extraction deterministic-ish (low temp).

Synthesis Engine (LLM + rules)

Clusters claims by theme:

definitions, timeline, mechanisms, key actors, competing theories, numbers

Detects:

contradictions (same variable different values)

disputes (explicit “debated”, “disputed”, “some argue”)

gaps (important subtopic with low coverage)

Produces the final report with structured sections and a bibliography of visited pages.

Crawl Strategy Details
Seed Selection

Search Kiwix for the topic string.

Pick top matches:

exact title match > redirect target > close match > disambiguation page

If disambiguation:

extract candidate targets

score targets against topic + user-provided hint (optional)

pick 1–3 seeds

Link Extraction and Filtering

For each visited page:

Extract outbound article links from:

lead + first N sections (bias toward early content)

infobox links (often highly relevant)

“See also” links (high relevance but can be spammy)

Filter out:

non-main namespaces

self-links

list pages optionally (or include with penalty)

years-only pages unless topic is explicitly historical timeline

Expansion Policy

At each step:

Candidate pages get a score from relevance scorer.

Apply diversity constraint:

avoid picking 10 pages all about the same sub-branch

e.g., cap per “category cluster” if you parse categories, or use embedding clustering

Choose next pages until:

max_links_per_page added to frontier

depth limit reached

Depth Handling

Store depth per page (seed depth 0).

Only expand links from pages with depth < max_depth.

Still allowed to visit pages at depth == max_depth, but do not expand them.

Report Format Specification (what it writes)
report.md structure

Title

“Research Brief: <Topic>”

Executive Summary

6–10 bullet claims that appear most supported across pages.

Key Concepts & Definitions

definitions with page references

Timeline / Historical Development (if relevant)

Mechanisms / Explanations

grouped by theory / mechanism

Competing Views & Disputes

“View A vs View B” with signals like hedging phrases and “disputed” tags

Numbers & Quantitative Claims

table-like listing: value, what it measures, which pages say it

highlight disagreements

What Wikipedia Doesn’t Settle Yet

gaps found by:

high centrality concepts with low claim density

lots of hedging but few citations

Bibliography

list of visited pages (local Kiwix links)

Run Metadata

max_pages, max_depth, crawl strategy, Kiwix dataset name/version (if detectable)

Citations are not external URLs; they should reference local page titles + section anchors, e.g.:

[Bronze Age collapse — “Theories” section]
so you can click in Kiwix.

Data Structures (minimal but effective)
PageDoc

id (hash of title)

title

url

plain_text

sections: [{heading, text, start_offset}]

links: [{target_title, anchor_text, context_snippet, section}…]

signals: {is_stub, has_citation_needed, is_disambiguation, ref_count_estimate, length_chars}

Claim

claim_id

claim

claim_type

topic_tags (LLM-generated keywords)

page_title

section_heading

support_snippets (short!)

hedging_flags: {may, some, debated, uncertain}

evidence_signals

confidence

Graph

nodes: page_id with relevance score

edges: from_page_id → to_page_id with weight (how often + link context relevance)

LLM Prompting Strategy (reliable-ish)
Extraction prompt (per section chunk)

System-ish constraints:

“Extract claims as JSON. Do not invent facts. If uncertain, lower confidence and mark hedging.”

“Prefer short atomic claims.”

Synthesis prompt

Give it:

top clustered claims

contradiction list

page list with scores/signals
Ask it to write:

“structured research brief” with explicitly marked uncertainty and disagreements.

Two-model option (nice):

Model A writes report

Model B critiques: “find overclaims, missing disputes, unsupported leaps”

Merge revisions

Quality / Safety Controls (the boring part that saves you)

No hallucination rule: every claim in report must map to at least one extracted claim object.

Contradiction detector:

compare numeric claims with same units/targets

flag ± thresholds

Deterministic crawl mode:

fixed random seed for tie breaks

stable sorting of candidate links

CLI Spec (example)

kiwiresearch "Bronze Age collapse" --depth 2 --max-pages 80 --strategy priority --out ./runs/2025-12-23_bronze-age

Flags:

--include-lists / --exclude-lists

--fast (skip embeddings; lexical scoring only)

--critic (enable second-pass critique)

--focus "metallurgy, drought" (optional query hint)

MVP Build Order (so it actually ships)

Kiwix fetch + HTML → plain text + links

Basic crawler with depth + max_pages

Save corpus + graph + run log

LLM extraction to claims.jsonl

Synthesis to report.md

Add scoring improvements: embeddings + diversity constraint

Add contradiction detection + critic pass
