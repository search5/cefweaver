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
    return "\n".join(lines) + "\n"
