"""Template for one repository's migration to Linear (see SKILL.md).

Copy it to a scratch folder, fill in CONFIG and the ISSUES section, then:

    python3 migrate.py --dry [--cites] [--show KEY,KEY]   # no network
    python3 migrate.py --run                              # creates the project
    python3 migrate.py --verify                           # re-reads Linear

The key is read fresh from KEY_FILE on every run and never printed.
"""
import json, os, re, subprocess, sys, textwrap, time, urllib.error, urllib.request

# ---- CONFIG (from local.md and the repository) ----
REPO = "/path/to/repo"                       # local checkout
GH = "https://github.com/<owner>/<repo>"     # for links to quoted lines
SHA = "abc1234"                              # the commit every quote cites (prefer a pushed one)
NAME = "<Linear project name>"
TEAM = "<team uuid>"
ST = {"Backlog": "<id>", "Ready": "<id>", "Needs Input": "<id>"}  # add the others you use
KEY_FILE, KEY_PREFIX = "~/.zshrc", "export LINEAR_API_KEY="
PRIVATE = []                                 # names or ids to replace in quotes
HERE = os.path.dirname(os.path.abspath(__file__))
ID_MAP = os.path.join(HERE, "created.json")

# ---- quoting helpers ----
def show(path, sha=SHA): return subprocess.check_output(["git", "-C", REPO, "show", f"{sha}:{path}"], text=True).split("\n")
DOCS = {}
def doc(path):
    if path not in DOCS: DOCS[path] = show(path)
    return DOCS[path]
def redact(t):
    for n in PRIVATE: t = t.replace(n, "[redacted]")
    return t
def cells(line): return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
def detable(lines):
    """Tables become labelled list items: Linear mangles tables inside quotes and lists."""
    out, i = [], 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            head = cells(lines[i]); i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                out.append("- " + " · ".join(f"**{h}:** {c}" for h, c in zip(head, cells(lines[i])))); i += 1
        else: out.append(lines[i]); i += 1
    return out
def bq(t): return "\n".join("> " + l if l else ">" for l in t.split("\n"))
def link(path, a, b): return f"[`{path}`]({GH}/blob/{SHA}/{path}#L{a}" + (f"-L{b}" if b != a else "") + f") at `{SHA}`"
CITED = []
def cite(path, a, b, note=""):
    """Quote lines a..b of path at SHA, verbatim, under a link to them."""
    raw = doc(path)[a - 1:b]
    t = textwrap.dedent("\n".join(detable(raw))).strip("\n")
    r = redact(t)
    CITED.append((path, a, b))
    tag = "verbatim" + ("; tables as labelled fields" if any(l.lstrip().startswith("|") for l in raw) else "") + ("; private details replaced" if r != t else "")
    return (note + "\n\n" if note else "") + f"_From {link(path, a, b)}, lines {a}–{b} ({tag})._\n\n" + bq(r)
def join(*parts): return "\n\n".join(p for p in parts if p)

# ---- ISSUES: (key, title, milestone index or None, status, parent key or None, description) ----
MILESTONES = ["In flight", "Backlog"]
SWITCH = join(f"Move this repository's planning to the Linear project **{NAME}**.",
              "## Acceptance\n\n1. A root `AGENTS.md` `## Driver` section:\n\n   ```text\n   ## Driver\n\n"
              f"   Linear: team <KEY>, project {NAME}\n   Worker: <kind>\n   ```\n2. The old plan frozen with a banner; binding rules kept.\n"
              "3. Every statement naming the old plan as the queue reconciled (grep for it).\n\n## Out of scope\n\nChanging any rule's meaning; app code.")
ISSUES = [
    ("SWITCH", f"Move planning to Linear", None, "Ready", None, SWITCH),
    # ("S1", "1/2 Step 1 — ...", 0, "Ready", None, join("note", cite("ROADMAP.md", 10, 24))),
]
PRIORITY = {"SWITCH": 2}                      # 1 Urgent, 2 High, 3 Medium, 4 Low
RELATIONS = []                                # (blocker key, blocked key), only where a source states it
PROJECT_CONTENT = f"Planning migrated from <source> at `{SHA}`. Still binding in the repository: <rules>."

keys = [k for k, *_ in ISSUES]
assert len(keys) == len(set(keys)), "duplicate keys"
assert all(a in keys and b in keys for a, b in RELATIONS)

# ---- Linear ----
def api_key():
    for line in open(os.path.expanduser(KEY_FILE)):
        if line.startswith(KEY_PREFIX): return line[len(KEY_PREFIX):].strip().strip("'\"")
    raise SystemExit("no key in " + KEY_FILE)
def q(query, variables=None, write=False):
    """Reads retry on HTTP errors. A write never retries: it may have landed; reconcile first."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    for attempt in range(1 if write else 5):
        req = urllib.request.Request("https://api.linear.app/graphql", data=body, headers={"Content-Type": "application/json", "Authorization": api_key()})
        try: d = json.load(urllib.request.urlopen(req))
        except urllib.error.HTTPError as e:
            if write: raise SystemExit(f"HTTP {e.code} on a write: list the project's issues and relations before retrying")
            time.sleep(5 * (attempt + 1)); continue
        if d.get("errors"): raise SystemExit("GraphQL error: " + d["errors"][0]["message"])
        return d["data"]
    raise SystemExit("gave up after retries")

def run():
    if q('query($n:String!){ projects(filter:{name:{eq:$n}}){ nodes{ id } } }', {"n": NAME})["projects"]["nodes"]: raise SystemExit("project exists")
    out = {"issues": {}}
    p = q("mutation($i:ProjectCreateInput!){ projectCreate(input:$i){ project{ id url } } }", {"i": {"name": NAME, "teamIds": [TEAM], "content": PROJECT_CONTENT}}, write=True)["projectCreate"]["project"]
    out["project"] = p; print("project", p["url"], flush=True)
    out["milestones"] = [q("mutation($i:ProjectMilestoneCreateInput!){ projectMilestoneCreate(input:$i){ projectMilestone{ id } } }",
                           {"i": {"projectId": p["id"], "name": n, "sortOrder": float(i + 1)}}, write=True)["projectMilestoneCreate"]["projectMilestone"]["id"]
                         for i, n in enumerate(MILESTONES)]
    for k, title, m, status, parent, desc in ISSUES:
        inp = {"teamId": TEAM, "projectId": p["id"], "title": title, "description": desc, "stateId": ST[status]}
        if m is not None: inp["projectMilestoneId"] = out["milestones"][m]
        if parent: inp["parentId"] = out["issues"][parent]["id"]
        if k in PRIORITY: inp["priority"] = PRIORITY[k]
        out["issues"][k] = q("mutation($i:IssueCreateInput!){ issueCreate(input:$i){ issue{ id identifier } } }", {"i": inp}, write=True)["issueCreate"]["issue"]
        json.dump(out, open(ID_MAP, "w"), indent=1)            # saved after every issue
        print(out["issues"][k]["identifier"], status, title, flush=True)
    for a, b in RELATIONS:
        q("mutation($i:IssueRelationCreateInput!){ issueRelationCreate(input:$i){ success } }",
          {"i": {"issueId": out["issues"][a]["id"], "relatedIssueId": out["issues"][b]["id"], "type": "blocks"}}, write=True)
    print("done")

def verify():
    """Re-read every issue; exit 1 on any mismatch."""
    an = lambda t: re.sub(r"[^A-Za-z0-9]", "", t)
    def unlink(t):  # Linear auto-links bare domains as [x](<http://x>); collapse only identity links
        return re.sub(r"\[([^\]]+)\]\(<?https?://([^)\s>]*?)/?>?\)", lambda m: m.group(1) if m.group(2) == m.group(1).replace("\\", "") else m.group(0), t)
    saved = json.load(open(ID_MAP)); ids = saved["issues"]; bad = 0
    for k, title, m, status, parent, desc in ISSUES:
        g = q("""query($id:String!){ issue(id:$id){ identifier title description priority state{ name } parent{ id }
                 projectMilestone{ id } relations{ nodes{ type relatedIssue{ id } } } } }""", {"id": ids[k]["id"]})["issue"]
        want_ms = saved["milestones"][m] if m is not None else None
        checks = (("title", g["title"] == title), ("status", g["state"]["name"] == status),
                  ("parent", (g["parent"] or {}).get("id") == (ids[parent]["id"] if parent else None)),
                  ("milestone", (g["projectMilestone"] or {}).get("id") == want_ms),
                  ("priority", g["priority"] == PRIORITY.get(k, 0)),
                  ("description", an(unlink(g["description"])) == an(desc)),
                  ("relations", sorted(r["relatedIssue"]["id"] for r in g["relations"]["nodes"] if r["type"] == "blocks")
                                == sorted(ids[b]["id"] for a, b in RELATIONS if a == k)))
        errs = [name for name, ok in checks if not ok]
        bad += bool(errs); print(g["identifier"], k, "OK" if not errs else "FAIL " + ", ".join(errs))
    print(bad, "issues with mismatches")
    if bad: sys.exit(1)

if __name__ == "__main__":
    if "--run" in sys.argv: run()
    elif "--verify" in sys.argv: verify()
    else:
        for k, title, m, status, parent, desc in ISSUES: print(f"{k:8} {status:11} {parent or '-':8} {len(desc):6}  {title}")
        print(len(ISSUES), "issues;", len(RELATIONS), "relations;", len(CITED), "citations")
        if "--cites" in sys.argv:
            for c in sorted(set(CITED)): print("CITE", *c)
        if "--show" in sys.argv:
            for k in sys.argv[sys.argv.index("--show") + 1].split(","): print("\n=====", k); print(next(d for kk, *_, d in ISSUES if kk == k))
