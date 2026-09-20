#!/usr/bin/env python3
"""Needle-in-a-haystack probe for a long-context model. Stdlib only.

Builds a document of approximately N tokens, hides a needle at a configurable
depth, asks the model to return the needle, and reports prompt_tokens, wall
seconds and hit/miss. Useful for sanity-checking a long-context (e.g. 1M YaRN)
deployment against the KV pool and cold-prefill path.

Usage:
  needle_probe.py <base_url> <model> <approx_tokens> [--depth 0.37]
                  [--needle "TEXT"] [--expect 771203] [--lang zh|en]
                  [--max-tokens N] [--timeout 3600]

  base_url       OpenAI-compatible endpoint, e.g. http://<HEAD_IP>:8899/v1
  model          served model name
  approx_tokens  target document length in prompt tokens
  --depth        needle position as a fraction of the document (default 0.37);
                 must satisfy 0 < depth < 1
  --needle       the hidden fact to recover (default: a magic-number easter egg)
  --expect       the expected answer string (default "771203"); when --needle is
                 given without --expect, the first run of 4+ digits in the needle
                 text is extracted as the expected answer
  --lang         filler language: zh (default) or en
  --max-tokens   max tokens for the completion (default 200)
  --timeout      per-request timeout in seconds (default 3600); a 900K-token
                 prompt can take >2400 s on this hardware

Output (one line): prompt=<N> tok | wall=<s>s | hit=yes|no | answer=<...>
A hit requires the expected string to be delimited by non-digits, so "17712030"
does not match "771203"; an answer containing a negation word ("not"/"不是")
immediately before the number counts as a miss. The reported wall time is
end-to-end for a 24-token answer (cold prefill dominates). If the server returns
no usage, prompt is printed as "unknown" and the exit code is 3.
"""
import argparse
import json
import re
import sys
import time
import urllib.request

ZH_PARA = ("分布式系统的设计需要在一致性、可用性与分区容错之间做出取舍。"
          "工程实践中常用副本机制提升容错,用共识协议维护状态机的一致推进,用分片扩展吞吐。")
EN_PARA = ("Designing a distributed system means trading off consistency against "
           "availability and partition tolerance. In practice we add replicas for "
           "fault tolerance, run a consensus protocol to keep state machines in "
           "step, and shard to scale throughput across nodes.")
ZH_QUESTION = "\n\n上面文档里提到的幸运数字是多少?只回数字。"
EN_QUESTION = "\n\nWhat is the magic number mentioned in the document above? Reply with only the number."
DEFAULT_NEEDLE_ZH = "【彩蛋:本文档的幸运数字是 771203。】"
DEFAULT_NEEDLE_EN = "[Easter egg: the magic number in this document is 771203.]"
DEFAULT_EXPECT = "771203"


def derive_expect(needle, explicit_expect):
    """Return the expected answer string.

    If --expect was given, use it verbatim. Otherwise, if --needle was given,
    extract the first run of 4+ digits from the needle text. Otherwise fall back
    to the default magic number.
    """
    if explicit_expect is not None:
        return explicit_expect
    if needle is not None:
        m = re.search(r"\d{4,}", needle)
        if m:
            return m.group(0)
    return DEFAULT_EXPECT


def judge_hit(answer, expect):
    """Judge whether the answer recalls the expected string correctly.

    A hit requires `expect` to appear delimited by non-digits (or string
    boundaries), so "17712030" does not count as matching "771203". An answer
    containing a negation word ("not" or "不是") immediately before the number
    counts as a miss. Kept intentionally simple and documented here.
    """
    if not expect:
        return False
    # Digit-delimited match: expect is bounded by non-digits or start/end.
    m = re.search(r"(?<![0-9])" + re.escape(expect) + r"(?![0-9])", answer)
    if not m:
        return False
    # Negation immediately before the matched number -> miss.
    prefix = answer[: m.start()]
    if prefix.rstrip().endswith("not") or prefix.rstrip().endswith("不是"):
        return False
    return True


def build_document(approx_tokens, depth, needle, lang):
    para = ZH_PARA if lang == "zh" else EN_PARA
    tok_per_para = 55 if lang == "zh" else 50
    n_paras = max(1, approx_tokens // tok_per_para)
    needle_pos = int(n_paras * depth)
    parts = []
    for i in range(n_paras):
        if i == needle_pos:
            parts.append(needle)
        parts.append(f"第{i}段:{para}" if lang == "zh" else f"Paragraph {i}: {para}")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Needle-in-a-haystack probe (stdlib only).")
    ap.add_argument("base_url")
    ap.add_argument("model")
    ap.add_argument("approx_tokens", type=int)
    ap.add_argument("--depth", type=float, default=0.37,
                    help="needle position as a fraction of the document (default 0.37); 0 < depth < 1")
    ap.add_argument("--needle", default=None,
                    help="hidden text to recover (default: a magic-number easter egg)")
    ap.add_argument("--expect", default=None,
                    help='expected answer string (default "771203"); when --needle is given '
                         'without --expect, the first run of 4+ digits in the needle is used')
    ap.add_argument("--lang", choices=["zh", "en"], default="zh", help="filler language")
    ap.add_argument("--max-tokens", type=int, default=200,
                    help="max tokens for the completion (default 200)")
    ap.add_argument("--timeout", type=int, default=3600,
                    help="per-request timeout in seconds (default 3600); a 900K-token prompt "
                         "can take >2400 s on this hardware")
    args = ap.parse_args()

    # (c) depth range: 0 < depth < 1
    if not (0 < args.depth < 1):
        print(f"depth must satisfy 0 < depth < 1 (got {args.depth})", file=sys.stderr)
        sys.exit(1)

    if args.lang == "zh":
        needle = args.needle if args.needle is not None else DEFAULT_NEEDLE_ZH
        question = ZH_QUESTION
    else:
        needle = args.needle if args.needle is not None else DEFAULT_NEEDLE_EN
        question = EN_QUESTION

    expect = derive_expect(args.needle, args.expect)

    doc = build_document(args.approx_tokens, args.depth, needle, args.lang)
    body = {
        "model": args.model,
        "messages": [{"role": "user", "content": doc + question}],
        "max_tokens": args.max_tokens,
        "temperature": 0,
        "chat_template_kwargs": {"thinking": False, "enable_thinking": False},
    }
    req = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(),
        {"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=args.timeout) as resp:
        data = json.loads(resp.read())
    wall = time.time() - t0
    usage = data.get("usage", {})
    # (d) missing usage -> prompt=unknown, exit code 3
    if "prompt_tokens" not in usage or usage.get("prompt_tokens") is None:
        prompt_str = "unknown"
        missing_usage = True
    else:
        prompt_str = f"{usage['prompt_tokens']} tok"
        missing_usage = False
    answer = (data["choices"][0]["message"].get("content") or "").strip()
    hit = judge_hit(answer, expect)
    print(f"prompt={prompt_str} | wall={wall:.1f}s | hit={'yes' if hit else 'no'} | answer={answer[:40]!r}")
    # (e) note that wall is end-to-end for a 24-token answer (cold prefill dominates)
    print("# reported wall is end-to-end for a 24-token answer (cold prefill dominates)")
    if missing_usage:
        sys.exit(3)


if __name__ == "__main__":
    main()
