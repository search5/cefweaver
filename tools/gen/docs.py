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
_ITEM = re.compile(r"^(\s*)(?:([-*+])|(\d+)[.)]|\((\d+)\))\s+(\S.*)$")
_LITERAL_SPAN = re.compile(r"(``[^`]*``|:\w+:`[^`]*`)")


def _imperative(word):
    lower = word.lower()
    if lower not in _THIRD_PERSON:
        return word
    base = word[:-3] + "y" if lower.endswith("ies") else word[:-2] if lower.endswith(("ches", "shes", "sses", "xes")) else word[:-1]
    return base


def _blocks(lines):
    """The comment lines as blocks: ("p", text), ("l", [(depth, marker, text)]) and ("c", [code lines])."""
    blocks, prose, items, code = [], [], [], []
    seen_blank = False

    def flush():
        nonlocal prose, items, code
        if prose:
            blocks.append(("p", " ".join(prose)))
        if items:
            blocks.append(("l", _nest(items)))
        if code:
            blocks.append(("c", code))
        prose, items, code = [], [], []

    for raw in lines:
        line = raw.rstrip()
        if re.match(r"^\s*</?pre>\s*$", line):
            continue
        if not line.strip():
            if prose or code:
                flush()
            seen_blank = True
            continue
        indent = len(line) - len(line.lstrip())
        found = _ITEM.match(line)
        if found:
            if prose or code:
                flush()
            marker = ("%s." % (found.group(3) or found.group(4))) if (found.group(3) or found.group(4)) else "-"
            items.append([indent, marker, [found.group(5).strip()]])
        elif items and (indent > items[-1][0] or not seen_blank):
            items[-1][2].append(line.strip())
        elif indent >= 2 and not items:
            if prose:
                blocks.append(("p", " ".join(prose)))
                prose = []
            code.append(line)
        else:
            if items or code:
                flush()
            prose.append(line.strip())
        seen_blank = False
    flush()
    return blocks


def _nest(items):
    """[(indent, marker, lines)] -> [(depth, marker, text)]: a bullet that has the indent of a numbered item
    belongs under it."""
    out, stack, numbered = [], [], set()
    for indent, marker, text in items:
        level = float(indent)
        if marker == "-" and indent in numbered:
            level = indent + 0.5
        elif marker != "-":
            numbered.add(indent)
        while stack and stack[-1] > level:
            stack.pop()
        if not stack or stack[-1] < level:
            stack.append(level)
        out.append((len(stack) - 1, marker, " ".join(text)))
    return out


# {class: {method: the class that declares it}} (nearest ancestor first), filled by `set_owners`
OWNERS = {}


def set_owners(model, known):
    """Find the declaring class of every method, so that `:meth:` points where Sphinx documents the method."""
    own = {}
    for name in known:
        cls = model.classes.get(name)
        funcs = (cls.get_virtual_funcs() + cls.get_static_funcs()) if cls is not None else []
        own[name] = {py_method_name(f.get_name()) for f in funcs}
    OWNERS.clear()
    for name in known:
        table, current = {}, name
        while current in own:
            for method in own[current]:
                table.setdefault(method, current)
            cls = model.classes.get(current)
            current = cls.get_parent_name() if cls is not None else None
        OWNERS[name] = table


def _words(text, known):
    """CEF's spelling of names and constants in a prose sentence, as Python's."""
    def method(m):
        name = "Cef" + m.group(1)
        if name in known and "*" not in m.group(2):
            owner = OWNERS.get(name, {}).get(py_method_name(m.group(2)))
            if owner:
                return ":meth:`~cefweaver.%s.%s`" % (py_class_name(owner), py_method_name(m.group(2)))
            return "``%s.%s``" % (py_class_name(name), py_method_name(m.group(2)))
        return "``%s``" % m.group(0)

    def klass(m):
        name = "Cef" + m.group(1)
        return ":class:`~cefweaver.%s`" % py_class_name(name) if name in known else "``%s%s``" % (name, m.group(2) or "")

    text = re.sub(r"(?<!`)`([^`\n]+)`(?!`)", r"``\1``", text)      # Markdown code -> literal
    text = re.sub(r"<code>(.*?)</code>", r"``\1``", text)
    text = re.sub(r"<(?:b|strong)>(.*?)</(?:b|strong)>", r"**\1**", text)
    text = re.sub(r"<(?:i|em)>(.*?)</(?:i|em)>", r"*\1*", text)
    text = re.sub(r"\bCef(\w+)::([\w*]+)(?:\([^()]*\))?", method, text)
    text = re.sub(r"(?<![`:\w])Cef([A-Z]\w+)(\(\))?(?!`)\b", klass, text)
    text = re.sub(r"\|([\w*]+)\|", lambda m: "``%s``" % py_param_name(m.group(1)), text)
    text = re.sub(r"(?<![`\w])true(?![`\w])", "``True``", text)
    text = re.sub(r"(?<![`\w])false(?![`\w])", "``False``", text)
    text = re.sub(r"(?<![`\w])(NULL|nullptr)(?![`\w])", "``None``", text)
    # a wildcard is no emphasis: "text/*", "*.png"
    parts = _LITERAL_SPAN.split(text)
    for index in range(0, len(parts), 2):
        parts[index] = re.sub(r"(?<![`\w*])([\w./-]*\*[\w./*-]*?)(?=[\"')\]]*[.,;:]?[\"')\]]*(?:\s|$))", r"``\1``", parts[index])
    text = "".join(parts)
    parts = _LITERAL_SPAN.split(text)
    for index in range(1, len(parts), 2):
        if index + 1 < len(parts) and re.match(r"[\w(]", parts[index + 1]):
            parts[index] += " "
    return "".join(parts)


def _wrap(text, initial="", subsequent=""):
    return textwrap.wrap(text, WIDTH, initial_indent=initial, subsequent_indent=subsequent,
                         break_long_words=False, break_on_hyphens=False)


def convert(lines, known):
    """The comment lines of a class or a method as a docstring body: [summary, "", ...], without the section headers.

    Returns a pair (body_lines, raw): `raw` is the prose before the conversion, for `_argument_notes`.
    """
    blocks = _blocks(lines)
    if not blocks:
        return [], ""
    raw = " ".join(value for kind, value in blocks if kind == "p")
    body, first = [], True
    for kind, value in blocks:
        if kind == "p":
            text = _words(value, known)
            if first:
                head = text.split(" ", 1)
                text = _imperative(head[0]) + (" " + head[1] if len(head) > 1 else "")
                parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
                body += [parts[0]]
                if len(parts) > 1:
                    body += [""] + _wrap(parts[1])
            else:
                if body and body[-1] != "":
                    body.append("")
                body += _wrap(text)
        elif kind == "l":
            if body and body[-1] != "":
                body.append("")
            widths, previous = [], None
            for depth, marker, text in value:
                if previous is not None and depth != previous:
                    body.append("")
                previous = depth
                del widths[depth:]
                pad = " " * sum(widths)
                widths.append(len(marker) + 1)
                body += _wrap(_words(text, known), pad + marker + " ", pad + " " * (len(marker) + 1))
        else:
            if body and body[-1] != "":
                body.append("")
            if body and body[-1] == "" and len(body) > 1 and body[-2].endswith(":"):
                body[-2] += ":"
            else:
                body.append("::")
                body.append("")
            width = min(len(l) - len(l.lstrip()) for l in value)
            body += ["    " + l[width:] for l in value]
        first = False
    return body, raw


def _argument_notes(raw):
    """`|name| is the address.` in the prose -> {"name": "The address."}"""
    notes = {}
    for m in re.finditer(r"\|(\w+)\|\s+(?:is|are)\s+(.*?)\.(?:\s|$)", raw):
        sentence = m.group(2).strip()
        if sentence:
            notes[py_param_name(m.group(1))] = _words(sentence[0].upper() + sentence[1:] + ".", set())
    for m in re.finditer(r"[Tt]he\s+\|(\w+)\|\s+(?:parameter|argument)\s+(?:is|specifies|represents)\s+(.*?)\.(?:\s|$)", raw):
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


def _qualified(model, known, kind):
    """The type of a stub annotation with the names of the classes and of the enumerations and value types
    qualified, so that Sphinx finds them wherever the docstring is shown (`Frame` is also a class of `ui`)."""
    classes = {py_class_name(c) for c in known}
    types = set(info.py_name for info in model.enum_defs.values()) | set(model.structs)

    def name(m):
        word = m.group(0)
        if word in classes:
            return "cefweaver." + word
        return "cefweaver.types." + word if word in types else word
    return re.sub(r"(?<![\w.])[A-Za-z_]\w*", name, kind)


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
            text = "    %s (%s):" % (name, _qualified(model, known, kind))
            if name in notes:
                text += " " + notes[name]
            sections.append(text)
    if returns and returns != "None":
        value = _first_sentence_value(raw)
        sections += ["Returns:", "    %s%s" % (_qualified(model, known, returns), ": " + value if value else "")]
    if sections:
        body = (body + [""] if body else []) + sections
    return body
