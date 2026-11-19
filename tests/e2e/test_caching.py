"""Prompt caching tables: session ids, cache markers, long retention, where cache hits are read from (the chat part,
the startup line and /clear, is in test_chat.py).
Provider behaviour is matched on a fragment of the API URL, so putting the fragment in the path of the fake server's
URL (http://127.0.0.1:8781/api.openai.com/v1) makes it behave as that provider."""
from lib import DEFAULT_SHELL, Suite, section

s = Suite()
U = "http://127.0.0.1:8781"
LOG = s.w / "req.log"
s.serve("caching_server.py", LOG)
s.ready()

def run(**env):
    """Run teh once; return (its stderr, the logged requests, with header names lower-cased)."""
    LOG.write_text("")
    r = s.teh("go", env={"TEH_AUTO": 1, "TEH_SHELL": DEFAULT_SHELL, **env})
    reqs = s.requests(LOG)
    for q in reqs:
        q["headers"] = {k.lower(): v for k, v in q["headers"].items()}
    return r.err, reqs

section("session id routing")
err, reqs = run(TEH_BASE_URL=f"{U}/api.openai.com/v1", TEH_MODEL="gpt")
s.check("openai: prompt_cache_key sent, same id on both calls", len(reqs) == 2
        and reqs[0]["body"].get("prompt_cache_key") and len({q["body"].get("prompt_cache_key") for q in reqs}) == 1)
s.check("openai: max_completion_tokens instead of max_tokens", "max_completion_tokens" in reqs[0]["body"]
        and "max_tokens" not in reqs[0]["body"])
s.check("openai: no retention field by default", "prompt_cache_retention" not in reqs[0]["body"])
s.check("openai: cached tokens read (OpenAI style)", "in 100 (88 cached)" in err)
_, reqs = run(TEH_BASE_URL=f"{U}/api.openai.com/v1", TEH_MODEL="gpt", TEH_CACHE_RETENTION="long")
s.check("openai + TEH_CACHE_RETENTION=long: prompt_cache_retention=24h",
        reqs[0]["body"].get("prompt_cache_retention") == "24h")
for frag, header in [("api.x.ai", "x-grok-conv-id"), ("api.fireworks.ai", "x-session-affinity"),
                     ("opencode.ai", "x-opencode-session")]:
    _, reqs = run(TEH_BASE_URL=f"{U}/{frag}/v1", TEH_MODEL="m")
    s.check(f"{frag}: {header} header sent, same on both calls, not in body", reqs[0]["headers"].get(header)
            and len({q["headers"].get(header) for q in reqs}) == 1 and header not in reqs[0]["body"])
_, reqs = run(TEH_BASE_URL=f"{U}/api.groq.com/openai/v1", TEH_MODEL="m")
s.check("unlisted provider: no cache fields or headers, plain max_tokens",
        not ({"prompt_cache_key", "cache_control", "prompt_cache_retention"} & set(reqs[0]["body"]))
        and "max_tokens" in reqs[0]["body"]
        and not any(h.startswith(("x-grok", "x-session", "x-opencode")) for h in reqs[0]["headers"]))

section("effort and auth")
_, reqs = run(TEH_BASE_URL=f"{U}/openrouter.ai/api/v1", TEH_MODEL="m", TEH_EFFORT="low")
s.check("openrouter: effort as reasoning.effort, title header", reqs[0]["body"].get("reasoning") == {"effort": "low"}
        and reqs[0]["headers"].get("x-openrouter-title") == "teh")
_, reqs = run(TEH_BASE_URL=f"{U}/api.groq.com/openai/v1", TEH_MODEL="m", TEH_EFFORT="low")
s.check("openai format: effort as reasoning_effort", reqs[0]["body"].get("reasoning_effort") == "low")
_, reqs = run(TEH_BASE_URL=f"{U}/api.anthropic.com/v1", TEH_MODEL="claude-x", TEH_EFFORT="low", TEH_API_KEY="k9")
s.check("anthropic: effort in output_config, key in x-api-key", reqs[0]["body"].get("output_config") == {
    "effort": "low"} and reqs[0]["headers"].get("x-api-key") == "k9" and "authorization" not in reqs[0]["headers"])

section("cache markers")
_, reqs = run(TEH_BASE_URL=f"{U}/api.anthropic.com/v1", TEH_MODEL="claude-x")
s.check("anthropic: cache_control ephemeral (5m)", reqs[0]["body"].get("cache_control") == {"type": "ephemeral"})
_, reqs = run(TEH_BASE_URL=f"{U}/api.anthropic.com/v1", TEH_MODEL="claude-x", TEH_CACHE_RETENTION="long")
s.check("anthropic + long: ttl 1h", reqs[0]["body"]["cache_control"].get("ttl") == "1h")
_, reqs = run(TEH_BASE_URL=f"{U}/openrouter.ai/api/v1", TEH_MODEL="anthropic/claude-sonnet-5.5")
s.check("openrouter + claude: cache_control in OpenAI-format request", reqs[0]["path"].endswith("/chat/completions")
        and reqs[0]["body"].get("cache_control") == {"type": "ephemeral"})
_, reqs = run(TEH_BASE_URL=f"{U}/openrouter.ai/api/v1", TEH_MODEL="deepseek/deepseek-chat")
s.check("openrouter + non-claude: no marker", "cache_control" not in reqs[0]["body"])
_, reqs = run(TEH_BASE_URL=f"{U}/api.nano-gpt.com/api/v1", TEH_MODEL="claude-sonnet-5-5")
s.check("nanogpt + claude: marker", "cache_control" in reqs[0]["body"])
_, reqs = run(TEH_FORMAT="anthropic", TEH_BASE_URL=f"{U}/minimax/v1", TEH_MODEL="m")
s.check("other Anthropic-format endpoint: no marker", "cache_control" not in reqs[0]["body"])

section("cache-hit reporting")
s.check("DeepSeek field (prompt_cache_hit_tokens)",
        "in 100 (77 cached)" in run(TEH_BASE_URL=f"{U}/usage-deepseek/v1", TEH_MODEL="m")[0])
s.check("Fireworks response header",
        "in 100 (66 cached)" in run(TEH_BASE_URL=f"{U}/api.fireworks.ai/usage-header/v1", TEH_MODEL="m")[0])
s.check("top-level cached_tokens (Kimi)",
        "in 100 (55 cached)" in run(TEH_BASE_URL=f"{U}/usage-top/v1", TEH_MODEL="m")[0])
s.check("Anthropic usage",
        "in 100 (90 cached)" in run(TEH_BASE_URL=f"{U}/api.anthropic.com/v1", TEH_MODEL="claude-x")[0])

s.finish()
