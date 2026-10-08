"""Coverage report: how much of the CEF API the generator handles, and what blocks the rest."""

import collections

from typesys import plan_method


def all_plans(model, scope):
    """Plans for every method of every class and every function in `scope`'s universe."""
    plans = []
    for name, cls in sorted(model.classes.items()):
        client = cls.is_client_side()
        for method in cls.get_virtual_funcs():
            plans.append(plan_method(model, scope, name, method, client_side=client))
        for method in cls.get_static_funcs():
            plans.append(plan_method(model, scope, name, method, client_side=client, static=True))
    for name, function in sorted(model.functions.items()):
        plans.append(plan_method(model, scope, "", function, client_side=False, static=True))
    return plans


def _bucket(reason):
    """Group reasons: 'struct cef_rect_t' and 'struct cef_point_t' are one problem."""
    for prefix in ("struct ", "class ", "output parameter", "pointer to", "struct-like value type",
                   "untyped pointer"):
        if reason.startswith(prefix):
            return prefix.strip()
    return reason


def build_report(model, current, universe):
    """Text report: what is generated now, and what the whole API would need."""
    lines = []
    generated = [
        p for p in all_plans(model, current)
        if p.supported and (p.owner in (current._library | current._client) or
                            (p.owner == "" and p.cef_name in current.functions))
    ]
    lines.append("Generated now: %d methods/functions in %d classes, %d global functions"
                 % (len(generated), len(current._library | current._client), len(current.functions)))

    lines.append("")
    lines.append("Skipped inside the generated classes (type not supported yet):")
    skipped = [
        p for p in all_plans(model, current)
        if not p.supported and (p.owner in (current._library | current._client) or
                                (p.owner == "" and p.cef_name in current.functions))
    ]
    counts = collections.Counter(_bucket(p.reason) for p in skipped)
    for reason, count in counts.most_common():
        lines.append("  %4d  %s" % (count, reason))
    lines.append("  ----  %d skipped" % len(skipped))

    everything = all_plans(model, universe)
    supported = sum(1 for p in everything if p.supported)
    lines.append("")
    lines.append("If every class were generated, the type support alone would cover "
                 "%d of %d methods/functions (%.0f%%)." % (supported, len(everything),
                                                          100.0 * supported / len(everything)))
    lines.append("What blocks the rest, by type:")
    blockers = collections.Counter(_bucket(p.reason) for p in everything if not p.supported)
    for reason, count in blockers.most_common():
        lines.append("  %4d  %s" % (count, reason))

    lines.append("")
    lines.append("Per class (supported/total methods, when every class is generated):")
    per_class = collections.defaultdict(lambda: [0, 0])
    for p in everything:
        if p.owner:
            per_class[p.owner][1] += 1
            per_class[p.owner][0] += p.supported
    for name in sorted(per_class):
        good, total = per_class[name]
        side = "client " if model.classes[name].is_client_side() else "library"
        mark = "*" if (current.is_library(name) or current.is_client(name)) else " "
        lines.append("  %s %-38s %s %3d/%-3d" % (mark, name, side, good, total))
    lines.append("  (* = generated now)")
    lines += _java_cef_sections(model, current, generated)
    return "\n".join(lines) + "\n"


def generated_methods(model, current):
    """{(class, method)} that are generated."""
    return {(p.owner, p.cef_name) for p in all_plans(model, current)
            if p.supported and p.owner in (current._library | current._client)}


def java_cef_gaps(model, current):
    """{class: [methods]}: what java-cef opens and cefweaver has not generated yet. java-cef is
    the floor of the API (tools/gen/surface.py is its list)."""
    from surface import SURFACE
    done = generated_methods(model, current)
    gaps = {}
    for name in sorted(SURFACE):
        if name not in model.classes:
            continue  # java-cef's own class (the message router), not a CEF one
        cls = model.classes[name]
        wanted = {m.get_name() for m in list(cls.get_virtual_funcs()) + list(cls.get_static_funcs())}
        wanted &= SURFACE[name]
        missing = sorted(m for m in wanted if (name, m) not in done)
        if missing:
            gaps[name] = (missing, len(wanted))
    return gaps


def beyond_java_cef(model, current):
    """{class: [methods]}: generated, and not opened by java-cef (the whole class when
    java-cef has none of it)."""
    from surface import SURFACE
    beyond = {}
    for owner, method in sorted(generated_methods(model, current)):
        if method not in SURFACE.get(owner, ()):
            beyond.setdefault(owner, []).append(method)
    return beyond


def _java_cef_sections(model, current, generated):
    """java-cef is the floor: what it opens and cefweaver has not yet, and what cefweaver
    opens that java-cef does not."""
    from surface import SURFACE
    lines = ["", "Opened by java-cef, not generated yet (the gaps):"]
    gap_total = 0
    for name, (missing, wanted) in java_cef_gaps(model, current).items():
        gap_total += len(missing)
        why = ("class not generated yet" if not (current.is_library(name) or current.is_client(name))
               else "type not supported yet")
        lines.append("  %-30s %3d/%-3d  %s" % (name, len(missing), wanted, why))
    lines.append("  ----  %d methods" % gap_total)

    lines += ["", "Generated, and not opened by java-cef (beyond the floor):"]
    extra_total = 0
    for name, methods in beyond_java_cef(model, current).items():
        extra_total += len(methods)
        whole = "the whole class" if name not in SURFACE else "%d methods" % len(methods)
        lines.append("  %-30s %3d  %s" % (name, len(methods), whole))
    lines.append("  ----  %d methods" % extra_total)
    return lines
