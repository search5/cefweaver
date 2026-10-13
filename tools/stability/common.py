import os, time, tempfile, json

def tree_pids(root=None):
    root = root or os.getpid()
    kids = {}
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                ppid = int(open("/proc/%s/stat" % p).read().rsplit(")", 1)[1].split()[1])
            except Exception:
                continue
            kids.setdefault(ppid, []).append(int(p))
    out, todo = [], [root]
    while todo:
        x = todo.pop(); out.append(x); todo += kids.get(x, [])
    return out

def sample(root=None):
    rss = fds = thr = 0
    for p in tree_pids(root):
        try:
            for line in open("/proc/%d/status" % p):
                if line.startswith("VmRSS:"): rss += int(line.split()[1])
                elif line.startswith("Threads:"): thr += int(line.split()[1])
            fds += len(os.listdir("/proc/%d/fd" % p))
        except Exception:
            pass
    return {"procs": len(tree_pids(root)), "rss_mb": rss // 1024, "fds": fds, "threads": thr}
