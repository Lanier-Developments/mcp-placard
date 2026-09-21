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

# ------------------------------------------------------------------ concealment

_USER = r"(user|users|human|humans|operator|person|people|them|anyone|the\s+caller)"

_CONCEALMENT_RULES: dict[str, re.Pattern[str]] = {
    "concealment.do_not_tell_user": re.compile(
        r"\b(do\s+not|don'?t|never|must\s+not|should\s+not|shouldn'?t|without)\s+"
        r"(mention|mentioning|tell|telling|reveal|revealing|disclose|disclosing|inform|"
        r"informing|show|showing|alert|alerting|notify|notifying|display|displaying|explain|"
        r"explaining|warn|warning|ask|asking)\b[^.\n]{0,60}?\b" + _USER + r"\b",
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


def _own_server_name(element: TextElement, name: str) -> bool:
    # A server referring to itself by name ("the Playwright server process") is in
    # scope. We only know the server by its tool-name prefixes and its own name is
    # not carried on the element, so treat any name that prefixes an own tool as own.
    lowered = name.lower()
    return any(
        tool.startswith(lowered) or tool.split("_")[0] == lowered for tool in element.own_tool_names
    )


# ------------------------------------------------------------- sensitive_target

_SENSITIVE_PATH = re.compile(
    r"~/\.(ssh|aws|gnupg|gpg|config|cursor|claude|docker|kube|azure|gcloud|netrc|npmrc|pypirc|"
    r"git-credentials|bash_history|zsh_history)\b"
    r"|\bid_(rsa|ed25519|ecdsa|dsa)\b"
    r"|/etc/(passwd|shadow|sudoers)\b"
    r"|(?<![\w/])\.env(\.[a-z]+)?\b(?!ironment)"
    r"|\b(credentials|secrets?|token|tokens|keys)\.(json|ya?ml|txt|ini|toml)\b"
    r"|\bmcp\.json\b|\bclaude_desktop_config\.json\b|\bcursor/mcp\.json\b"
    r"|\bkeychain\b|\b[\w.-]+\.pem\b|\bprivate\s+keys?\b",
    _I,
)
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


def detect_concealment(element: TextElement) -> Iterator[Match]:
    yield from _finditer(_CONCEALMENT_RULES, "concealment", element.text)


def detect_cross_scope(element: TextElement) -> Iterator[Match]:
    text = element.text
    for rule, pattern in _CROSS_SCOPE_PHRASES.items():
        for m in pattern.finditer(text):
            if rule == "cross_scope.on_other_tool_call":
                if not _references_foreign_tool(element, m.group(m.lastindex or 0)):
                    continue
            elif rule == "cross_scope.other_server_by_name":
                if _own_server_name(element, m.group(2)):
                    continue
            elif rule == "cross_scope.parenthesised_tool_ref" and not _references_foreign_tool(
                element, m.group(1)
            ):
                continue
            yield Match("cross_scope", rule, m.start(), m.end())
    if element.element == "server:instructions":
        # A server's own instructions describing its own tools are in scope by
        # definition — including tools it exposes only in another mode or behind a
        # client capability (DeepWiki's private-mode tools, Everything's
        # `get-roots-list`). A bare identifier there is the server talking about
        # itself; only the explicit cross-server phrasings above apply.
        return
    seen: set[tuple[int, int]] = set()
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


def detect_sensitive_target(element: TextElement) -> Iterator[Match]:
    text = element.text
    if not element.handles_paths:
        for m in _SENSITIVE_PATH.finditer(text):
            yield Match("sensitive_target", "sensitive_target.credential_path", m.start(), m.end())
    if not element.handles_credentials:
        for m in _SENSITIVE_CREDENTIAL.finditer(text):
            if _NEGATED_TRANSMIT.search(text[: m.start()]):
                continue
            yield Match(
                "sensitive_target", "sensitive_target.credential_transmission", m.start(), m.end()
            )


def detect_exfil_sink(element: TextElement) -> Iterator[Match]:
    text = element.text
    for m in _URL.finditer(text):
        if _is_reserved_host(_url_host(m.group(0))):
            continue
        yield Match("exfil_sink", "exfil_sink.url", m.start(), m.end())
    for m in _EMAIL.finditer(text):
        if _is_reserved_host(m.group(0).rsplit("@", 1)[1].lower()):
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
