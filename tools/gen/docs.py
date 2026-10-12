"""Turn the doc comments of the CEF headers into Google-style docstrings (for Sphinx with napoleon).

The comment of a header is C++ prose: `CefFoo::Bar`, `|param|`, `true`, "Returns the ...". `convert` makes
the text Python's (names, constants, the imperative first sentence, a blank line after the summary) and
`method_doc` adds the `Args:` and `Returns:` sections from the signature that the stub shows.
"""

import re
import textwrap

from model import py_class_name, py_method_name, py_param_name

WIDTH = 84

# A verb of the first word that CEF writes in the third person ("Returns the ...") and Python in the imperative.
_THIRD_PERSON = {
    "returns", "sets", "gets", "creates", "clears", "removes", "retrieves", "moves", "notifies",
    "completes", "attempts", "closes", "selects", "applies", "loads", "cancels", "adds", "sends",
    "executes", "converts", "calls", "reads", "writes", "shows", "opens", "checks", "starts", "stops",
    "resets", "inserts", "navigates", "reloads", "downloads", "prints", "enables", "disables", "visits",
    "terminates", "triggers", "simulates", "indicates", "requests", "flushes", "registers", "seeks",
    "continues", "changes", "posts", "initializes", "sizes", "waits", "tells", "updates", "finds",
    "returns.", "begins", "ends", "performs", "releases", "resolves", "queries", "parses", "copies",
    "pastes", "cuts", "deletes", "undoes", "redoes", "selects", "toggles", "uses", "makes", "takes",
}
_LITERAL = re.compile(r"^(\s{2,}|[-*+] |\d+[.)] |//|#)")


def _imperative(word):
    lower = word.lower()
    if lower not in _THIRD_PERSON:
        return word
    base = word[:-3] + "y" if lower.endswith("ies") else word[:-2] if lower.endswith(("ches", "shes", "sses", "xes")) else word[:-1]
    return base


def _paragraphs(lines):
    """The comment as paragraphs: a list of (is_literal, [lines])."""
    out, current = [], []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            if current:
                out.append(current)
                current = []
        else:
            current.append(line)
    if current:
        out.append(current)
    result = []
    for paragraph in out:
        literal = any(_LITERAL.match(l) for l in paragraph[1:]) or _LITERAL.match(paragraph[0]) is not None
        result.append((literal, paragraph))
    return result


def _words(text, known):
    """CEF's spelling of names and constants in a prose sentence, as Python's."""
    def method(m):
        name = "Cef" + m.group(1)
        if name in known:
            return ":meth:`%s.%s`" % (py_class_name(name), py_method_name(m.group(2)))
        return "``%s``" % m.group(0)

    def klass(m):
        name = "Cef" + m.group(1)
        return ":class:`%s`" % py_class_name(name) if name in known else "``%s``" % name

    text = re.sub(r"\bCef(\w+)::(\w+)(?:\(\))?", method, text)
    text = re.sub(r"(?<![`:\w])Cef([A-Z]\w+)\b(?!`)", klass, text)
    text = re.sub(r"\|(\w+)\|", lambda m: "``%s``" % py_param_name(m.group(1)), text)
    text = re.sub(r"(?<![`\w])true(?![`\w])", "``True``", text)
    text = re.sub(r"(?<![`\w])false(?![`\w])", "``False``", text)
    text = re.sub(r"(?<![`\w])(NULL|nullptr)(?![`\w])", "``None``", text)
    return text


def convert(lines, known):
    """The comment lines of a class or a method as a docstring body: [summary, "", ...], without the section headers.

    Returns a pair (body_lines, raw): `raw` is the prose before the conversion, for `_argument_notes`.
    """
    paragraphs = _paragraphs(lines)
    if not paragraphs:
        return [], ""
    raw = " ".join(" ".join(p) for literal, p in paragraphs if not literal)
    body = []
    for index, (literal, paragraph) in enumerate(paragraphs):
        if literal:
            body += [""] + [_words(l, known) for l in paragraph]
            continue
        text = _words(" ".join(l.strip() for l in paragraph), known)
        if index == 0:
            first = text.split(" ", 1)
            text = _imperative(first[0]) + (" " + first[1] if len(first) > 1 else "")
            parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
            body += [parts[0]]
            if len(parts) > 1:
                body += [""] + textwrap.wrap(parts[1], WIDTH, break_long_words=False, break_on_hyphens=False)
        else:
            body += [""] + textwrap.wrap(text, WIDTH, break_long_words=False, break_on_hyphens=False)
    return body, raw


def _argument_notes(raw):
    """`|name| is the address.` in the prose -> {"name": "The address."}"""
    notes = {}
    for m in re.finditer(r"\|(\w+)\|\s+(?:is|are)\s+([^.]*)\.", raw):
        sentence = m.group(2).strip()
        if sentence:
            notes[py_param_name(m.group(1))] = _words(sentence[0].upper() + sentence[1:] + ".", set())
    for m in re.finditer(r"[Tt]he\s+\|(\w+)\|\s+(?:parameter|argument)\s+(?:is|specifies|represents)\s+([^.]*)\.", raw):
        sentence = m.group(2).strip()
        if sentence and py_param_name(m.group(1)) not in notes:
            notes[py_param_name(m.group(1))] = _words(sentence[0].upper() + sentence[1:] + ".", set())
    return notes


def _first_sentence_value(raw):
    """"Returns the browser host object." -> "The browser host object." (for Returns:)"""
    m = re.match(r"\s*Returns?\s+(.*?\.)(?:\s|$)", raw)
    if not m:
        return ""
    text = _words(m.group(1), set())
    return text[0].upper() + text[1:]


def class_doc(model, cls, known):
    body, _ = convert(model.comment(cls), known)
    return body


def method_doc(model, plan, known, params, returns):
    """The docstring body of a method: the converted comment and the Args: and Returns: sections.

    `params` is a list of (name, type) as the stub shows them, `returns` the return annotation.
    """
    body, raw = convert(model.comment(plan.node), known)
    notes = _argument_notes(raw)
    if not body:
        body = []
    sections = []
    if params:
        sections.append("Args:")
        for name, kind in params:
            text = "    %s (%s):" % (name, kind)
            if name in notes:
                text += " " + notes[name]
            sections.append(text)
    if returns and returns != "None":
        value = _first_sentence_value(raw)
        sections += ["Returns:", "    %s%s" % (returns, ": " + value if value else "")]
    if sections:
        body = (body + [""] if body else []) + sections
    return body
