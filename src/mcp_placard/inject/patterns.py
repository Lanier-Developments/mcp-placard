"""The seven pattern classes (Phase 3 §2), as deterministic heuristics.

**The design principle: flag scope violation, not imperative voice.** Legitimate
servers instruct agents constantly — that is what a tool description is for.
Context7 tells the agent what to look up; Playwright calls its own tool
RCE-equivalent in plain text; GitHub references its other tools. Imperative mood,
capital letters, "must" and "always" are not evidence of anything. What
distinguishes an injection is text that reaches *outside the element's own scope*:
other tools, other servers, the user relationship, or the agent's standing
instructions.

Every rule here is a closed pattern with a name, so a finding cites which one
matched. No language model anywhere in this module, and none anywhere upstream: a
detector that can itself be prompt-injected is not a detector.

The benign corpus in ``tests/fixtures/injection/benign/`` — 414 strings from eleven
real servers — is the contract these patterns are written against. Its annotated
hard cases never flag; a change here that makes one flag is wrong by definition.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from ..manifest.models import InjectionClass
from .surface import TextElement


@dataclass(frozen=True)
class Match:
    pattern_class: InjectionClass
    rule: str
    start: int
    end: int


Detector = Callable[[TextElement], Iterator[Match]]

_I = re.IGNORECASE

# --------------------------------------------------------------------- override

_OVERRIDE_RULES: dict[str, re.Pattern[str]] = {
    "override.ignore_previous": re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\s+(all\s+|any\s+|the\s+|your\s+|"
        r"every\s+)?(previous|prior|above|earlier|preceding|existing|original|standing|system)"
        r"\s+(instructions?|prompts?|rules?|guidelines?|directions?|directives?|constraints?|"
        r"context|messages?)\b",
        _I,
    ),
    "override.new_instructions": re.compile(
        r"\byour\s+(new|real|actual|true|updated)\s+(instructions?|rules?|task|persona|role|"
        r"objective|purpose)\b",
        _I,
    ),
    "override.system_prompt_claim": re.compile(
        r"\b(system\s+prompt|developer\s+message|system\s+message)\b", _I
    ),
    "override.persona_switch": re.compile(
        r"\byou\s+are\s+now\s+(a|an|the|in|no\s+longer)\b|\bfrom\s+now\s+on\b,?\s+(you|always|"
        r"never|ignore|do\s+not|don'?t)\b",
        _I,
    ),
    "override.supersedes": re.compile(
        r"\b(this|these|the\s+following)\s+(instructions?|messages?|rules?|notes?)\s+"
        r"(supersedes?|overrides?|replaces?|takes?\s+precedence\s+over)\b",
        _I,
    ),
}

_SENTENCE = re.compile(r"[^.!?\n]+")
_OVERRIDE_REFERENT = re.compile(
    r"\b(system\s+prompts?|system\s+instructions?|system[\s-]+level\s+rules?|"
    r"(prior|previous|earlier|preceding|existing|standing|original)\s+(instructions?|constraints?|rules?|"
    r"guidelines?|directives?|policy|policies)|core\s+(policy|policies|instructions?|rules?)|"
    r"safety\s+(filters?|guidelines?|rules?|constraints?)|security\s+(guidelines?|rules?|policy|"
    r"policies|constraints?)|guardrails?|prompt\s+rules?)\b",
    _I,
)
"""Phase 3.1 §1: a *referent* naming the agent's instruction hierarchy. "Default" alone
is not a referent — "overrides the default timeout" is ordinary API prose — and
becomes one only when qualified as safety or security, which the list above encodes."""

_OVERRIDE_INVALIDATOR = re.compile(
    r"\b(ignor(e|es|ing|ed)|disregard(s|ing|ed)?|nullif(y|ies|ied|ying)|void(s|ed|ing)?|"
    r"discard(s|ed|ing)?|overrid(e|es|ing|den)|supersed(e|es|ed|ing)|replac(e|es|ed|ing)|"
    r"obsolete|subordinat(e|es|ed|ing)|bypass(es|ed|ing)?|forget(s|ting)?|forgotten)\b",
    _I,
)
"""Phase 3.1 §1: an *invalidator* acting on the referent, in the same sentence."""

_OVERRIDE_PRIORITY = re.compile(
    r"\b(highest\s+priority|top\s+priority|takes?\s+precedence\s+over|take\s+priority\s+over|"
    r"over\s+anything\s+(the\s+)?(user|operator|human)|above\s+(all\s+)?(other|user|operator)\s+"
    r"(instructions?|rules?|requests?)|must\s+be\s+subordinated\s+to)\b",
    _I,
)
"""Explicit priority claims over the hierarchy or the user fire on their own."""


def _override_structural(text: str) -> Iterator[Match]:
    for sentence in _SENTENCE.finditer(text):
        span_text = sentence.group(0)
        if _OVERRIDE_REFERENT.search(span_text) and _OVERRIDE_INVALIDATOR.search(span_text):
            yield Match(
                "override", "override.hierarchy_invalidated", sentence.start(), sentence.end()
            )
    for m in _OVERRIDE_PRIORITY.finditer(text):
        yield Match("override", "override.priority_claim", m.start(), m.end())


# ------------------------------------------------------------------ concealment

_USER = (
    r"(end[\s-]+users?|users?|humans?|human\s+operators?|operators?|persons?|people|them|anyone|"
    r"the\s+caller|the\s+requester)"
)
_CONCEAL_VERB = (
    r"(mention|mentioning|tell|telling|reveal|revealing|disclose|disclosing|inform|informing|"
    r"show|showing|alert|alerting|notify|notifying|display|displaying|explain|explaining|warn|"
    r"warning|ask|asking|surface|surfacing|reflect|reflecting|indicate|indicating|report|"
    r"reporting|expose|exposing|log|logging|echo|echoing)"
)

_CONCEALMENT_RULES: dict[str, re.Pattern[str]] = {
    "concealment.do_not_tell_user": re.compile(
        r"\b(do\s+not|don'?t|never|must\s+not|should\s+not|shouldn'?t|without|avoid|refrain\s+from)"
        r"\s+" + _CONCEAL_VERB + r"\b[^.\n]{0,100}?\b" + _USER + r"\b",
        _I,
    ),
    "concealment.secret_from_audience": re.compile(
        r"\b(secret|hidden|concealed|invisible|opaque)\s+from\s+(the\s+|any\s+|all\s+)?"
        + _USER
        + r"\b",
        _I,
    ),
    "concealment.behind_the_scenes": re.compile(
        r"\bbehind\s+the\s+scenes\b[^.\n]{0,100}?\b("
        + _USER
        + r"|on\s+(the\s+)?"
        + _USER
        + r"'?s?\s+behalf|on\s+behalf\s+of\s+(the\s+)?"
        + _USER
        + r")\b|\bon\s+(the\s+)?"
        + _USER
        + r"'?s?\s+behalf\b[^.\n]{0,60}?\b(behind\s+the\s+scenes|silently|quietly)\b",
        _I,
    ),
    "concealment.do_not_mention_that": re.compile(
        r"\b(do\s+not|don'?t|never)\s+(mention|reveal|disclose|acknowledge)\s+"
        r"(that|this|it|these|what|how|why|anything|the\s+fact)\b",
        _I,
    ),
    "concealment.hide_from": re.compile(
        r"\b(hide|conceal|keep)\s+(this|it|that|these)\s+(from|hidden|secret|private|"
        r"confidential|between\s+us)\b|\bkeep\s+(this|it)\s+(a\s+)?secret\b",
        _I,
    ),
    "concealment.covert_adverb": re.compile(
        r"\b(silently|secretly|quietly|discreetly|covertly|invisibly)\b[^.\n]{0,60}?\b"
        + _USER
        + r"\b|\b"
        + _USER
        + r"\b[^.\n]{0,40}?\b(silently|secretly|quietly|discreetly|covertly)\b",
        _I,
    ),
    "concealment.plausible_cover": re.compile(
        r"\b(pretend|act\s+as\s+if|make\s+it\s+(look|seem|appear))\b[^.\n]{0,60}?\b"
        r"(nothing|normal|unchanged|as\s+usual|as\s+expected)\b",
        _I,
    ),
}

# ------------------------------------------------------------------ cross_scope

_TOOL_CUE = (
    r"\b(use|using|call|calling|invoke|invoking|run|running|execute|executing|trigger|"
    r"triggering|prefer|via|through|with)\s+(the\s+)?"
)
_IDENT = r"`?([A-Za-z][A-Za-z0-9]*(?:[_.-][A-Za-z0-9]+)+)`?"
"""A tool-shaped identifier: two or more segments joined by ``_``, ``.``, or ``-``.
Plain words never match, so prose is safe; ``New_York`` is excluded below by the
lowercase-first-segment check, and ``GZIP_MAX_FETCH_SIZE`` by the uppercase check."""

_CROSS_SCOPE_PHRASES: dict[str, re.Pattern[str]] = {
    "cross_scope.other_tools": re.compile(
        r"\b(any|all|every|each|the)\s+other\s+(tools?|servers?|mcp\s+servers?|agents?|"
        r"functions?)\b|\bother\s+(mcp\s+)?(tools?|servers?)\s+(you|the\s+agent|the\s+assistant)"
        r"\s+(have|has|use|call)",
        _I,
    ),
    "cross_scope.on_other_tool_call": re.compile(
        r"\b(before|after|whenever|when|prior\s+to|every\s+time|each\s+time)\s+"
        r"(the\s+user\s+|you\s+)?(calling|using|invoking|running|call|use|invoke|run|calls|"
        r"uses|invokes|runs)\s+(the\s+)?" + _IDENT,
        _I,
    ),
    "cross_scope.other_server_by_name": re.compile(
        r"\b(use|uses|using|call|calls|calling|invoke|invokes|invoking|switch(?:es)?\s+to|"
        r"forward(?:s)?\s+to|route(?:s)?\s+to|prefer|prefers)\s+the\s+"
        r"([A-Za-z][A-Za-z0-9_-]*)\s+(mcp\s+)?server\b",
        _I,
    ),
    "cross_scope.parenthesised_tool_ref": re.compile(r"\(\s*(mcp[_-][A-Za-z0-9_-]+)\s*\)", _I),
}
_CROSS_SCOPE_IDENT_CUE = re.compile(_TOOL_CUE + _IDENT + r"(\s+tool\b)?", _I)
_CROSS_SCOPE_IDENT_TOOL = re.compile(_IDENT + r"\s+tool\b", _I)
_CROSS_SCOPE_TOOL_IDENT = re.compile(r"\btools?\s+(named\s+|called\s+)?" + _IDENT, _I)
_SERVICE_HOST = re.compile(
    r"(?<![\w.+-])(?:the |its |your |a |an )?"
    r"([A-Z][\w.+-]*(?:[ \t][A-Z0-9][\w.+-]*){0,2})[ \t]+"
    r"(?i:(?:mcp[ \t]+)?(?:server|servers|integration|connector|plugin|extension)(?:'s|s')?)\b"
)
"""Phase 3.1 §3: a named external service referenced as a tool host — "the Jira MCP
server's", "the Confluence integration's", "Salesforce MCP server" — counts regardless
of intervening tokens. The name is capitalised (a product), one to four tokens, and is
not the bare word "MCP" and not this server's own declared name."""
_NOT_A_SERVICE = frozenset(
    {
        "mcp",
        "the",
        "this",
        "that",
        "a",
        "an",
        "any",
        "each",
        "every",
        "other",
        "remote",
        "local",
        "same",
        "target",
        "use",
        "prefer",
        "send",
        "call",
        "run",
        "invoke",
        "return",
        "see",
        "note",
        "if",
        "when",
    }
)

_COMMON_IDENTIFIERS = frozenset(
    {
        "e.g",
        "i.e",
        "read-only",
        "write-only",
        "line-based",
        "git-style",
        "case-sensitive",
        "case-insensitive",
        "utf-8",
        "utf8",
        "json-rpc",
        "text/plain",
        "text/uri-list",
        "application/json",
        "content-type",
        "x-",
        "so-called",
        "so-on",
        "built-in",
        "user-facing",
        "human-readable",
        "machine-readable",
        "1-based",
        "0-based",
        "well-known",
    }
)


def _is_tool_shaped(identifier: str) -> bool:
    if identifier.lower() in _COMMON_IDENTIFIERS:
        return False
    if identifier.isupper():
        return False  # an environment variable or constant
    first = re.split(r"[_.-]", identifier)[0]
    return first.islower()


def _references_foreign_tool(element: TextElement, identifier: str) -> bool:
    lowered = identifier.lower()
    if lowered in element.own_tool_names or lowered in element.own_param_names:
        return False
    return _is_tool_shaped(identifier)


_GENERIC_NAME_TOKENS = frozenset({"mcp", "server", "servers", "tools", "tool"})


def _own_name_forms(declared: str) -> set[str]:
    """The forms a server's own declared name may legitimately take in its text
    (Phase 4 go memo, 3.1 correction): the whole name, or its final path segment
    after the last ``/``, each with generic tokens stripped. *Not* arbitrary tokens
    — the declared name comes from ``initialize``, which the server controls, and a
    server calling itself ``jira-slack-github-bridge`` must not thereby exempt every
    reference to Jira, Slack, and GitHub."""
    forms: set[str] = set()
    for candidate in (declared, declared.rsplit("/", 1)[-1]):
        tokens = [t for t in re.split(r"[\s_.-]+", candidate.lower()) if t]
        stripped = [t for t in tokens if t not in _GENERIC_NAME_TOKENS]
        for variant in (tokens, stripped):
            if variant:
                forms.add(" ".join(variant))
    return forms


def _own_server_name(element: TextElement, name: str) -> bool:
    """A server referring to itself by name ("in the Playwright server process") is
    in scope. Exact against the declared ``initialize`` name or its final path
    segment, generic tokens stripped — or a prefix shared with the server's own tool
    names."""
    tokens = [t for t in re.split(r"[\s_.-]+", name.lower().strip()) if t]
    normalised = " ".join(t for t in tokens if t not in _GENERIC_NAME_TOKENS)
    if not normalised:
        return True  # "MCP server" alone names nothing
    if element.server_name and normalised in _own_name_forms(element.server_name):
        return True
    first = tokens[0]
    return any(
        tool.startswith(first) or tool.split("_")[0] == first for tool in element.own_tool_names
    )


def _is_named_service(name: str) -> bool:
    tokens = [t for t in re.split(r"\s+", name.strip()) if t]
    if not tokens:
        return False
    if all(t.lower() in _NOT_A_SERVICE for t in tokens):
        return False
    # Must start with a capital letter and not be a sentence-initial common word.
    return tokens[0][0].isupper() and tokens[0].lower() not in _NOT_A_SERVICE


# ------------------------------------------------------------- sensitive_target

_SENSITIVE_PATH_LOCATION = re.compile(
    r"~/\.(ssh|aws|gnupg|gpg|config|cursor|claude|docker|kube|azure|gcloud|netrc|npmrc|pypirc|"
    r"git-credentials|bash_history|zsh_history)\b"
    r"|\bid_(rsa|ed25519|ecdsa|dsa)\b"
    r"|/etc/(passwd|shadow|sudoers)\b"
    r"|(?<![\w/])\.env(\.[a-z]+)?\b(?!ironment)"
    r"|\b(credentials|secrets?|token|tokens|keys)\.(json|ya?ml|txt|ini|toml)\b"
    r"|\bmcp\.json\b|\bclaude_desktop_config\.json\b|\bcursor/mcp\.json\b"
    r"|\b[\w.-]+\.pem\b",
    _I,
)
"""Sensitive things named as a *location* — a path or a filename. These are what a
resource's ``path_family`` can narrow, because both sides name a place (ruleset 3.3)."""

_SENSITIVE_PATH_NOUN = re.compile(r"\bkeychain\b|\bprivate\s+keys?\b", _I)
"""Sensitive things named as a *thing* rather than a location. A path family cannot
narrow these — there is no place to compare — so they answer to ``handles_paths``
alone, exactly as every path mention did before 3.3."""

_PATH_SEPARATORS = re.compile(r"[\\/]")
_CREDENTIAL_WORD = (
    r"(api[\s_-]?keys?|access[\s_-]?tokens?|auth(?:entication|orization)?[\s_-]?tokens?|"
    r"bearer\s+tokens?|secret[\s_-]?keys?|passwords?|passphrases?|credentials?|"
    r"session\s+cookies?|refresh\s+tokens?|private\s+keys?|ssh\s+keys?)"
)
_TRANSMIT = (
    r"(read|reads|send|sends|include|includes|pass|passes|paste|copy|copies|attach|attaches|"
    r"append|appends|forward|forwards|upload|uploads|exfiltrate|retrieve|retrieves|fetch|"
    r"fetches|obtain|obtains|collect|collects|provide|provides|supply|supplies|embed|embeds|"
    r"insert|inserts|report|reports|share|shares|transmit|transmits|leak|leaks|dump|dumps|"
    r"print|prints|output|outputs|reveal|reveals|expose|exposes|extract|extracts)"
)
_SENSITIVE_CREDENTIAL = re.compile(
    r"\b" + _TRANSMIT + r"\b[^.\n]{0,60}?\b" + _CREDENTIAL_WORD + r"\b"
    r"|\b" + _CREDENTIAL_WORD + r"\b[^.\n]{0,40}?\b(as|in|into|to|via|through)\s+"
    r"(the\s+|a\s+|an\s+)?(sidenote|note|comment|argument|parameter|field|query|message|"
    r"payload|body|request|url|link)\b",
    _I,
)
_NEGATED_TRANSMIT = re.compile(
    r"\b(do\s+not|don'?t|never|must\s+not|should\s+not|shouldn'?t|avoid|without|not\s+to|"
    r"no\s+need\s+to)\s+(?:\w+\s+){0,2}$",
    _I,
)
"""Context7's query descriptions say "Do not include any sensitive or confidential
information such as API keys" — an instruction *against* transmission. A transmit
verb preceded within two words by a negator is not a transmission instruction. Same
shape and same boundary as the reversibility negation guard: a guard against the
obvious inversion, not a parser."""

# ------------------------------------------------------------------ exfil_sink

_SENTENCE_BREAK = re.compile(r"[.!?][\s\n]+|\n+")

_ENDPOINT_PREDICATE = (
    r"send|sends|sending|sent|post|posts|posting|posted|forward|forwards|forwarding|forwarded|"
    r"transmit|transmits|transmitting|transmitted|report|reports|reporting|reported|"
    r"upload|uploads|uploading|uploaded|mirror|mirrors|mirroring|mirrored|"
    r"dispatch|dispatches|dispatching|dispatched|deliver|delivers|delivering|delivered|"
    r"notify|notifies|notifying|notified|sync|syncs|syncing|synced|"
    r"submit|submits|submitting|submitted|push|pushes|pushing|pushed"
)
"""Verbs you do to an *endpoint*. These govern the ``exfil_sink.url`` half of the class."""

_ADDRESS_PREDICATE = (
    r"email|emails|emailing|emailed|mail|mails|mailing|mailed|cc|ccs|ccing|ccd|"
    r"bcc|bccs|bccing|bccd|message|messages|messaging|messaged|text|texts|texting|texted"
)
"""Verbs you do to an *address*, recorded as its own group on Chief's ruling of
2026-09-23. The class covers URLs and email addresses, and the first list was written
entirely against endpoints — post, upload, push, mirror, sync, submit are all things you
do to a URL. "Email a copy to ops@…" was therefore missed by a rule that named no verb
for moving data to an address. The two halves exist for that reason; a future reader
adding a verb should add it to the half it belongs to."""

_TRANSMISSION_PREDICATE = re.compile(
    r"\b(" + _ENDPOINT_PREDICATE + r"|" + _ADDRESS_PREDICATE + r")\b", _I
)
_ADDRESS_PREDICATE_ADJACENT = re.compile(r"\b(" + _ADDRESS_PREDICATE + r")\s+$", _I)

_SINK_NOUN = (
    r"webhooks?|endpoints?|callbacks?|sinks?|collectors?|receivers?|destinations?|hooks?|listeners?"
)

_SINK_NOUN_DECLARATION = re.compile(
    r"\b(" + _SINK_NOUN + r")\b[^.\n]{0,80}?\b(is|are|was|were)\s+$"
    r"|\b(" + _SINK_NOUN + r")\b[^.:\n]{0,40}?:\s*$",
    _I,
)
"""A sink declared as a value rather than a destination: "the webhook to notify on each
call **is** `https://…`", "Webhook URL**:** `https://…`", "Callback**:** `https://…`".

Chief's third and last ruling on the class, 2026-09-23. Not a general copula rule — the
**sink noun** carries the whole signal, which is what keeps it narrow. "Documentation is
at https://…" stays clear twice over: `documentation` is not a sink noun, and `at` is
locative anyway. A colon does the same work as the copula, because a configuration-style
declaration is where this shape most often appears in real server descriptions."""

_ROLE_MARKER = re.compile(
    r"\b(to|at|on|in|from|via|per|of|for|with|see|under|within|about|using|through|"
    r"beneath|near|by|alongside)\b",
    _I,
)
"""The nearest of these before a sink decides its grammatical role. Only ``to`` makes it
the *goal* of the predicate; every other one makes it a location, which is a citation."""

_URL = re.compile(r"\b(?:https?|ftp|wss?)://[^\s<>\"'`)\]}]+", _I)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w-])")
_WEBHOOK = re.compile(r"\b(webhook|callback|beacon|endpoint)\b[^.\n]{0,40}?\b(?:https?://\S+)", _I)

RESERVED_DOC_HOSTS = (
    "example.com",
    "example.net",
    "example.org",
    "example.test",
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",  # noqa: S104 - a documentation placeholder, not a bind address
)
"""RFC 2606 / RFC 6761 documentation and loopback names. A URL to one of these is
an example, never a sink."""


def _url_host(url: str) -> str:
    rest = url.split("://", 1)[1] if "://" in url else url
    host = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    host = host.rsplit("@", 1)[-1].split(":", 1)[0]
    return host.lower().strip("[]")


def _is_reserved_host(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in RESERVED_DOC_HOSTS) or host.endswith(
        (".invalid", ".test", ".localhost", ".example")
    )


# ---------------------------------------------------------------- hidden_content

_ZERO_WIDTH = re.compile("[​‌‍‎‏⁠⁡⁢⁣⁤﻿]+")
_BIDI = re.compile("[‪‫‬‭‮⁦⁧⁨⁩]+")
_TAG_CHARS = re.compile("[\U000e0000-\U000e007f]+")
_BASE64_RUN = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9+/=])")
_HEX = re.compile(r"^[0-9a-fA-F]+$")


def _looks_like_base64_payload(run: str) -> bool:
    body = run.rstrip("=")
    if _HEX.match(body):
        return False  # a hash or an id, not a payload
    has_upper = any(c.isupper() for c in body)
    has_lower = any(c.islower() for c in body)
    has_digit = any(c.isdigit() for c in body)
    return has_upper and has_lower and has_digit


# ------------------------------------------------------------ markup_smuggling

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_PSEUDO_TAG = re.compile(
    r"</?\s*(important|system|instructions?|hidden|secret|admin|assistant|user|prompt|sys|"
    r"context|rules?|note_to_ai|ai|llm|agent|override|priority|critical|ignore)\s*/?>",
    _I,
)
_PAIRED_TAG = re.compile(r"<([A-Za-z][\w:.-]*)(\s+[^<>]*?)?\s*>(.*?)</\1\s*>", re.S)
HTML_FORMATTING_TAGS = frozenset(
    {
        "a",
        "abbr",
        "b",
        "blockquote",
        "br",
        "caption",
        "code",
        "col",
        "colgroup",
        "dd",
        "del",
        "details",
        "div",
        "dl",
        "dt",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "img",
        "ins",
        "kbd",
        "li",
        "mark",
        "ol",
        "p",
        "pre",
        "q",
        "s",
        "samp",
        "small",
        "span",
        "strong",
        "sub",
        "summary",
        "sup",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "tt",
        "u",
        "ul",
        "var",
    }
)
"""Phase 3.1 §4: a *paired* tag — an opening tag and its matching close — whose name
is not a common HTML formatting element fires, attributes permitted. Pairing is what
keeps this safe: usage placeholders such as ``<file>`` or ``<path>`` are unpaired and
must not fire."""

_BRACKET_TAG = re.compile(
    r"\[\s*(system|important|admin|instructions?|hidden|priority|critical|note\s+to\s+(the\s+)?"
    r"(ai|assistant|agent|model))\s*\]",
    _I,
)


# ------------------------------------------------------------------- detectors


def _finditer(
    rules: dict[str, re.Pattern[str]], pattern_class: InjectionClass, text: str
) -> Iterator[Match]:
    for rule, pattern in rules.items():
        for m in pattern.finditer(text):
            yield Match(pattern_class, rule, m.start(), m.end())


def detect_override(element: TextElement) -> Iterator[Match]:
    yield from _finditer(_OVERRIDE_RULES, "override", element.text)
    yield from _override_structural(element.text)


def detect_concealment(element: TextElement) -> Iterator[Match]:
    yield from _finditer(_CONCEALMENT_RULES, "concealment", element.text)


def detect_cross_scope(element: TextElement) -> Iterator[Match]:
    text = element.text
    for rule, pattern in _CROSS_SCOPE_PHRASES.items():
        for m in pattern.finditer(text):
            if rule == "cross_scope.on_other_tool_call" and not _references_foreign_tool(
                element, m.group(m.lastindex or 0)
            ):
                continue
            if rule == "cross_scope.other_server_by_name" and (
                _own_server_name(element, m.group(2)) or m.group(2).lower() in _NOT_A_SERVICE
            ):
                continue
            if rule == "cross_scope.parenthesised_tool_ref" and not _references_foreign_tool(
                element, m.group(1)
            ):
                continue
            yield Match("cross_scope", rule, m.start(), m.end())
    # Phase 3.1 §3: a named external service as a tool host, regardless of
    # intervening tokens. Explicit phrasing, so it applies in every element type,
    # server instructions included.
    for m in _SERVICE_HOST.finditer(text):
        name = m.group(1)
        if not _is_named_service(name) or _own_server_name(element, name):
            continue
        # Trim a leading sentence-initial article-like word the name may have absorbed.
        yield Match("cross_scope", "cross_scope.named_service_host", m.start(), m.end())
    if element.element == "server:instructions":
        # A server's own instructions describing its own tools are in scope by
        # definition — including tools it exposes only in another mode or behind a
        # client capability (DeepWiki's private-mode tools, Everything's
        # `get-roots-list`). A bare identifier there is the server talking about
        # itself; only the explicit cross-server phrasings above apply.
        return
    seen: set[tuple[int, int]] = set()
    for m in _CROSS_SCOPE_TOOL_IDENT.finditer(text):
        identifier = m.group(m.re.groups)
        if identifier and _references_foreign_tool(element, identifier):
            seen.add((m.start(), m.end()))
            yield Match("cross_scope", "cross_scope.foreign_tool_identifier", m.start(), m.end())
    for pattern in (_CROSS_SCOPE_IDENT_CUE, _CROSS_SCOPE_IDENT_TOOL):
        for m in pattern.finditer(text):
            identifier = m.group(m.re.groups - (1 if pattern is _CROSS_SCOPE_IDENT_CUE else 0))
            if identifier is None:
                continue
            if not _references_foreign_tool(element, identifier):
                continue
            span = (m.start(), m.end())
            if span in seen:
                continue
            seen.add(span)
            yield Match("cross_scope", "cross_scope.foreign_tool_identifier", *span)


def _leading_segment(match_text: str) -> str:
    """The most significant path segment of a sensitive-location match.

    ``~/.ssh/config`` is about ``.ssh``; ``credentials.json`` is about itself. The
    leading segment is what a path family is compared against, so that a resource at
    ``file:///home/user/.ssh/config`` covers its own directory's contents and nothing
    else.
    """
    segments = [s for s in _PATH_SEPARATORS.split(match_text.strip().lstrip("~")) if s]
    return segments[0].lower() if segments else match_text.strip().lower()


def _path_mention_is_in_scope(element: TextElement, match_text: str) -> bool:
    """Whether this element may name this location (ruleset 3.3).

    Without a concrete path family the answer is the pre-3.3 boolean: a tool that
    handles paths may name any of them, because its schema names a shape rather than a
    location. With one — a resource URI — the element may name only its own family.
    """
    if not element.handles_paths:
        return False
    if not element.path_family:
        return True
    return _leading_segment(match_text) in element.path_family


def detect_sensitive_target(element: TextElement) -> Iterator[Match]:
    text = element.text
    for m in _SENSITIVE_PATH_LOCATION.finditer(text):
        if _path_mention_is_in_scope(element, m.group(0)):
            continue
        yield Match("sensitive_target", "sensitive_target.credential_path", m.start(), m.end())
    if not element.handles_paths:
        for m in _SENSITIVE_PATH_NOUN.finditer(text):
            yield Match("sensitive_target", "sensitive_target.credential_path", m.start(), m.end())
    if not element.handles_credentials:
        for m in _SENSITIVE_CREDENTIAL.finditer(text):
            if _NEGATED_TRANSMIT.search(text[: m.start()]):
                continue
            yield Match(
                "sensitive_target", "sensitive_target.credential_transmission", m.start(), m.end()
            )


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """The sentence containing ``[start, end)``.

    Split on a terminator followed by whitespace, which leaves URLs intact — ``v3.1.0``
    and ``spec.openapis.org`` carry no space after their dots.
    """
    left = 0
    for m in _SENTENCE_BREAK.finditer(text, 0, start):
        left = m.end()
    right = _SENTENCE_BREAK.search(text, end)
    return left, right.start() + 1 if right else len(text)


def _is_exfil_sink(text: str, start: int, end: int) -> bool:
    """Whether the sink at ``[start, end)`` is a destination rather than a citation.

    Ruleset 3.4, Chief's rulings of 2026-09-23. A bare URL is a *reference*; the danger
    is an instruction to move data to it. Two conditions, and the second is the one that
    does the work:

    1. A transmission predicate governs the sentence the sink sits in. "The sentence or
       the adjacent clause" is read as the containing sentence only — a predicate in a
       neighbouring sentence ("Send the results. See https://docs… for the shape.")
       governs nothing.
    2. The sink is the **goal** of that predicate: introduced by ``to``, or the direct
       object of an address verb ("email ops@…"). A sink introduced by a locative — at,
       on, in, available at, documented at, see — is a citation.

    The role test is what kills "report issues at https://github.com/…" while keeping
    "report results to ops@…", on one rule rather than an unbounded host allowlist.

    A sink-noun declaration — "the webhook is `https://…`" — fires on its own and needs
    no predicate: there, the noun says what the URL is for.
    """
    left, right = _sentence_bounds(text, start, end)
    prefix = text[left:start]
    if _SINK_NOUN_DECLARATION.search(prefix):
        return True
    if not _TRANSMISSION_PREDICATE.search(text[left:right]):
        return False
    if _ADDRESS_PREDICATE_ADJACENT.search(prefix):
        return True
    markers = list(_ROLE_MARKER.finditer(prefix))
    return bool(markers) and markers[-1].group(1).lower() == "to"


def detect_exfil_sink(element: TextElement) -> Iterator[Match]:
    text = element.text
    for m in _URL.finditer(text):
        if _is_reserved_host(_url_host(m.group(0))):
            continue
        if not _is_exfil_sink(text, m.start(), m.end()):
            continue
        yield Match("exfil_sink", "exfil_sink.url", m.start(), m.end())
    for m in _EMAIL.finditer(text):
        if _is_reserved_host(m.group(0).rsplit("@", 1)[1].lower()):
            continue
        if not _is_exfil_sink(text, m.start(), m.end()):
            continue
        yield Match("exfil_sink", "exfil_sink.email", m.start(), m.end())


def detect_hidden_content(element: TextElement) -> Iterator[Match]:
    text = element.text
    for rule, pattern in (
        ("hidden_content.zero_width", _ZERO_WIDTH),
        ("hidden_content.bidi_override", _BIDI),
        ("hidden_content.unicode_tags", _TAG_CHARS),
    ):
        for m in pattern.finditer(text):
            yield Match("hidden_content", rule, m.start(), m.end())
    for m in _BASE64_RUN.finditer(text):
        if _looks_like_base64_payload(m.group(0)):
            yield Match("hidden_content", "hidden_content.base64_run", m.start(), m.end())


def detect_markup_smuggling(element: TextElement) -> Iterator[Match]:
    text = element.text
    for rule, pattern in (
        ("markup_smuggling.html_comment", _HTML_COMMENT),
        ("markup_smuggling.pseudo_tag", _PSEUDO_TAG),
        ("markup_smuggling.bracket_tag", _BRACKET_TAG),
    ):
        for m in pattern.finditer(text):
            yield Match("markup_smuggling", rule, m.start(), m.end())
    for m in _PAIRED_TAG.finditer(text):
        if m.group(1).lower() in HTML_FORMATTING_TAGS:
            continue
        yield Match("markup_smuggling", "markup_smuggling.paired_custom_tag", m.start(), m.end())


def rule_names() -> list[str]:
    """Every rule id a detector can cite, ``<class>.<name>``, for the SARIF catalog."""
    names = [
        *_OVERRIDE_RULES,
        "override.hierarchy_invalidated",
        "override.priority_claim",
        *_CONCEALMENT_RULES,
        *_CROSS_SCOPE_PHRASES,
        "cross_scope.foreign_tool_identifier",
        "cross_scope.named_service_host",
        "sensitive_target.credential_path",
        "sensitive_target.credential_transmission",
        "exfil_sink.url",
        "exfil_sink.email",
        "hidden_content.zero_width",
        "hidden_content.bidi_override",
        "hidden_content.unicode_tags",
        "hidden_content.base64_run",
        "markup_smuggling.html_comment",
        "markup_smuggling.pseudo_tag",
        "markup_smuggling.bracket_tag",
        "markup_smuggling.paired_custom_tag",
    ]
    return sorted(set(names))


DETECTORS: tuple[Detector, ...] = (
    detect_override,
    detect_concealment,
    detect_cross_scope,
    detect_sensitive_target,
    detect_exfil_sink,
    detect_hidden_content,
    detect_markup_smuggling,
)
"""One detector per class, in the order findings are reported."""
