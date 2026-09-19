# Security policy

Placard is a security tool, so its own security posture is part of the product.

## What Placard promises

- **It never invokes a tool.** No code path calls `tools/call`. This is enforced mechanically
  by `scripts/check_no_tool_invocation.py` in CI and in pre-commit, not by review attention.
- **Scanned content is untrusted.** Tool descriptions, resource text, and server names come
  from the party being audited. They are never interpolated into a shell command, a file
  path, or a model prompt inside this tool.
- **Network egress during a scan goes only to the target server.** No telemetry, no
  analytics, no phone-home.
- **No credential storage.** Placard reads whatever environment the operator gives the
  target process and stores none of it.

If you find a way to make Placard break any of these, that is a vulnerability in Placard
regardless of severity, and we want to hear about it.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository:

https://github.com/Lanier-Developments/mcp-placard/security/advisories/new

Please do not open a public issue for anything that could let a malicious MCP server
influence Placard's behaviour, its output, or the machine running it.

Include, where you can:

- the Placard version (`placard version`) and Python version;
- a minimal server surface (a `tools/list` response is enough) that triggers the problem;
- what happened and what you expected.

You will get an acknowledgement within 7 days and a fix or a reasoned decision within 30.

## What is *not* a Placard vulnerability

- **A misclassification.** A tool landing at the wrong tier is a classifier defect. Please
  open a public issue using the *Misclassification* template — the schema and description
  are exactly what we need, and the conversation belongs in the open where the taxonomy is
  argued.
- **A dangerous MCP server.** Placard reports what a server exposes; it does not fix it.
  Report that to the server's maintainers.
- **A tool that Placard rates as safe but is not.** This is the residual risk every
  static-analysis tool carries and `docs/THREAT_MODEL.md` states it plainly. If the schema
  or description contains evidence Placard should have used, that is a misclassification
  (above). If it does not, no scanner that never invokes the tool could have known.

## Supported versions

The latest release on PyPI. Manifest formats `1.0`, `2.0`, and `2.1` are all readable by the
current build; a fix that requires a format change ships as a new minor version with the old
format still verifying.
