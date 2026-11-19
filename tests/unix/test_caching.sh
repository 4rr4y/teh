#!/bin/bash
# Prompt caching tables: session ids, cache markers, long retention, where cache hits are read from, the startup line.
# Provider behaviour is matched on a fragment of the API URL, so putting the fragment in the path of the fake server's
# URL (http://127.0.0.1:8781/api.openai.com/v1) makes it behave as that provider.
source "$(dirname "$0")/lib.sh"
PTY="$TESTS/pty_run.py"
U=http://127.0.0.1:8781
LOG="$W/req.log"
serve caching_server.py "$LOG"
ready

run() { : > "$LOG"; env TEH_AUTO=1 "$@" python3 -B "$H" go </dev/null 2>&1; }
q() {  # q <python expression over reqs>: evaluate against the logged requests (header names lower-cased)
    python3 -c "import json; reqs=[json.loads(l) for l in open('$LOG')]; [r.update(headers={k.lower(): v for k, v in r['headers'].items()}) for r in reqs]; print($1)"
}

echo "== session id routing"
out=$(run TEH_BASE_URL=$U/api.openai.com/v1 TEH_MODEL=gpt)
check "openai: prompt_cache_key sent, same id on both calls" '[[ "$(q "len({r[\"body\"].get(\"prompt_cache_key\") for r in reqs}) == 1 and bool(reqs[0][\"body\"].get(\"prompt_cache_key\")) and len(reqs) == 2")" == True ]]'
check "openai: max_completion_tokens instead of max_tokens" '[[ "$(q "\"max_completion_tokens\" in reqs[0][\"body\"] and \"max_tokens\" not in reqs[0][\"body\"]")" == True ]]'
check "openai: no retention field by default" '[[ "$(q "\"prompt_cache_retention\" not in reqs[0][\"body\"]")" == True ]]'
check "openai: cached tokens read (OpenAI style)" '[[ "$out" == *"in 100 (88 cached)"* ]]'
run TEH_BASE_URL=$U/api.openai.com/v1 TEH_MODEL=gpt TEH_CACHE_RETENTION=long >/dev/null
check "openai + TEH_CACHE_RETENTION=long: prompt_cache_retention=24h" '[[ "$(q "reqs[0][\"body\"].get(\"prompt_cache_retention\")")" == 24h ]]'
for p in "api.x.ai:x-grok-conv-id" "api.fireworks.ai:x-session-affinity" "opencode.ai:x-opencode-session"; do
  frag=${p%%:*}; hdr=${p##*:}; run TEH_BASE_URL=$U/$frag/v1 TEH_MODEL=m >/dev/null
  check "$frag: $hdr header sent, same on both calls, not in body" '[[ "$(q "len({r[\"headers\"].get(\"'$hdr'\") for r in reqs}) == 1 and bool(reqs[0][\"headers\"].get(\"'$hdr'\")) and \"'$hdr'\" not in reqs[0][\"body\"]")" == True ]]'
done
run TEH_BASE_URL=$U/api.groq.com/openai/v1 TEH_MODEL=m >/dev/null
check "unlisted provider: no cache fields or headers, plain max_tokens" '[[ "$(q "not ({\"prompt_cache_key\",\"cache_control\",\"prompt_cache_retention\"} & set(reqs[0][\"body\"])) and \"max_tokens\" in reqs[0][\"body\"] and not any(h.startswith((\"x-grok\",\"x-session\",\"x-opencode\")) for h in reqs[0][\"headers\"])")" == True ]]'

echo "== effort and auth"
run TEH_BASE_URL=$U/openrouter.ai/api/v1 TEH_MODEL=m TEH_EFFORT=low >/dev/null
check "openrouter: effort as reasoning.effort, title header" '[[ "$(q "reqs[0][\"body\"].get(\"reasoning\") == {\"effort\": \"low\"} and reqs[0][\"headers\"].get(\"x-openrouter-title\") == \"teh\"")" == True ]]'
run TEH_BASE_URL=$U/api.groq.com/openai/v1 TEH_MODEL=m TEH_EFFORT=low >/dev/null
check "openai format: effort as reasoning_effort" '[[ "$(q "reqs[0][\"body\"].get(\"reasoning_effort\")")" == low ]]'
run TEH_BASE_URL=$U/api.anthropic.com/v1 TEH_MODEL=claude-x TEH_EFFORT=low TEH_API_KEY=k9 >/dev/null
check "anthropic: effort in output_config, key in x-api-key" '[[ "$(q "reqs[0][\"body\"].get(\"output_config\") == {\"effort\": \"low\"} and reqs[0][\"headers\"].get(\"x-api-key\") == \"k9\" and \"authorization\" not in reqs[0][\"headers\"]")" == True ]]'

echo "== cache markers"
run TEH_BASE_URL=$U/api.anthropic.com/v1 TEH_MODEL=claude-x >/dev/null
check "anthropic: cache_control ephemeral (5m)" '[[ "$(q "reqs[0][\"body\"].get(\"cache_control\") == {\"type\": \"ephemeral\"}")" == True ]]'
run TEH_BASE_URL=$U/api.anthropic.com/v1 TEH_MODEL=claude-x TEH_CACHE_RETENTION=long >/dev/null
check "anthropic + long: ttl 1h" '[[ "$(q "reqs[0][\"body\"][\"cache_control\"].get(\"ttl\")")" == 1h ]]'
run TEH_BASE_URL=$U/openrouter.ai/api/v1 TEH_MODEL=anthropic/claude-sonnet-5.5 >/dev/null
check "openrouter + claude: cache_control in OpenAI-format request" '[[ "$(q "reqs[0][\"path\"].endswith(\"/chat/completions\") and reqs[0][\"body\"].get(\"cache_control\") == {\"type\": \"ephemeral\"}")" == True ]]'
run TEH_BASE_URL=$U/openrouter.ai/api/v1 TEH_MODEL=deepseek/deepseek-chat >/dev/null
check "openrouter + non-claude: no marker" '[[ "$(q "\"cache_control\" not in reqs[0][\"body\"]")" == True ]]'
run TEH_BASE_URL=$U/api.nano-gpt.com/api/v1 TEH_MODEL=claude-sonnet-5-5 >/dev/null
check "nanogpt + claude: marker" '[[ "$(q "\"cache_control\" in reqs[0][\"body\"]")" == True ]]'
run TEH_FORMAT=anthropic TEH_BASE_URL=$U/minimax/v1 TEH_MODEL=m >/dev/null
check "other Anthropic-format endpoint: no marker" '[[ "$(q "\"cache_control\" not in reqs[0][\"body\"]")" == True ]]'

echo "== cache-hit reporting"
check "DeepSeek field (prompt_cache_hit_tokens)" '[[ "$(run TEH_BASE_URL=$U/usage-deepseek/v1 TEH_MODEL=m)" == *"in 100 (77 cached)"* ]]'
check "Fireworks response header" '[[ "$(run TEH_BASE_URL=$U/api.fireworks.ai/usage-header/v1 TEH_MODEL=m)" == *"in 100 (66 cached)"* ]]'
check "top-level cached_tokens (Kimi)" '[[ "$(run TEH_BASE_URL=$U/usage-top/v1 TEH_MODEL=m)" == *"in 100 (55 cached)"* ]]'
check "Anthropic usage" '[[ "$(run TEH_BASE_URL=$U/api.anthropic.com/v1 TEH_MODEL=claude-x)" == *"in 100 (90 cached)"* ]]'

echo "== startup line and /clear (chat mode)"
out=$(TEH_BASE_URL=$U/api.anthropic.com/v1 TEH_MODEL=claude-x TEH_CACHE_RETENTION=long timeout 20 python3 -B "$PTY" "$H" '\x04')
check "anthropic long: 'cache    cache_control marker (1h)'" '[[ "$out" == *"cache    cache_control marker (1h)"* ]]'
out=$(TEH_BASE_URL=$U/api.openai.com/v1 TEH_MODEL=gpt TEH_CACHE_RETENTION=long timeout 20 python3 -B "$PTY" "$H" '\x04')
check "openai long: session id + retention" '[[ "$out" == *"cache    session id in prompt_cache_key · long retention (prompt_cache_retention=24h)"* ]]'
out=$(TEH_BASE_URL=$U/api.groq.com/openai/v1 TEH_MODEL=m timeout 20 python3 -B "$PTY" "$H" '\x04')
check "unlisted: 'provider default'" '[[ "$out" == *"cache    provider default (automatic, if any)"* ]]'
: > "$LOG"; TEH_BASE_URL=$U/api.x.ai/v1 TEH_MODEL=m TEH_AUTO=1 timeout 30 python3 -B "$PTY" "$H" 'one\n' '/clear\n' 'two\n' '\x04' >/dev/null
check "/clear gives a new session id" '[[ "$(q "len({r[\"headers\"][\"x-grok-conv-id\"] for r in reqs}) == 2 and len(reqs) == 4")" == True ]]'

finish
