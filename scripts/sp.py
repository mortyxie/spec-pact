#!/usr/bin/env python3
# spec-pact v2 state machine. stdlib only, python 3.8+.
# state.json is written by this script only. never hand-edit.

import argparse
import glob
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

MIN_PY = (3, 8)
if sys.version_info[:2] < MIN_PY:
    sys.stderr.write("ERR sp: python %d.%d too old, need >= %d.%d\n"
                     % (sys.version_info[0], sys.version_info[1], MIN_PY[0], MIN_PY[1]))
    raise SystemExit(6)

SCHEMA_VERSION = 2
SPEC_DIR = ".spec-pact"
PHASES = ("draft", "execute", "verify", "blocked", "done")
TASK_PHASES = ("plan", "execute", "review", "done")
DID_VALUES = ("+1", "0", "-1", "wait")

DEFAULT_CONFIG = {
    "schema_version": SCHEMA_VERSION,
    "dirs": ["resource", "work", "output", "log"],
    "naming": {
        # 按类型分派：工程代码 snake_case，文档 kebab-case，目录 kebab-case
        "style_by_kind": {"doc": "kebab_case", "code": "snake_case",
                          "dir": "kebab_case", "code_dir": "snake_case"},
        "doc_exts": [".md", ".txt", ".rst"],
        "code_zones": ["src", "lib", "tests", "app", "packages"],
        "whitelist": ["readme.md", "license", "skill.md", "makefile",
                      "package.json", "skill_meta.json", "sp.py"],
        "strict_existing": False,
    },
    "watchdog": {
        "stalled_turns": 3,
        "max_turns_per_step": 12,
        "backtrack_review": 2,
        "tick_stale_minutes": 180,
    },
    "max_depth": 3,
    "steps_dir": "steps",
}

MARK_OK = "\u25b8"
MARK_WARN = "!"
VERBOSE_HEADER = False  # -v：状态头由「一行横表」变为「竖表」，附待同步与未过项

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def out(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.replace(MARK_OK, ">").replace("\u00b7", "|"))


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M")


def fstamp():
    # for filenames: snake_case forbids '-' and ':'
    return datetime.now().strftime("%Y%m%d_%H%M")


def fail(msg, code=2):
    sys.stderr.write("ERR " + msg + "\n")
    sys.exit(code)


# ---------- root / io ----------

def find_root(explicit=None):
    if explicit:
        p = Path(explicit).resolve()
    else:
        p = Path.cwd().resolve()
    for cand in [p] + list(p.parents):
        if (cand / SPEC_DIR).is_dir():
            return cand
    return None


def require_root(explicit=None):
    root = find_root(explicit)
    if root is None:
        fail("not-initialized: no .spec-pact found. run: sp.py init", 3)
    return root


def paths(root):
    s = root / SPEC_DIR
    return {
        "spec": s,
        "state": s / "state.json",
        "config": s / "config.json",
        "plan": s / "plan.md",
        "steps": s / "steps",
        "decisions": s / "decisions.md",
        "changes": s / "changes.md",
        "refs": s / "refs.md",
        "snapshots": s / "snapshots",
        "archive": s / "archive",
        "log": root / "log",
    }


def read_json(p, default=None):
    if not Path(p).exists():
        return default
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        fail("corrupt-json: %s" % p, 4)


def write_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def backup_state(root, state_path):
    logdir = root / "log"
    logdir.mkdir(parents=True, exist_ok=True)
    if not Path(state_path).exists():
        return
    dst = logdir / ("state_%s.json" % fstamp())
    shutil.copy2(state_path, dst)
    olds = sorted(logdir.glob("state_*.json"))
    for f in olds[:-5]:
        f.unlink()


def load_state(root):
    p = paths(root)
    st = read_json(p["state"], None)
    if st is None:
        fail("no-state: run sp.py init", 3)
    if st.get("schema_version") != SCHEMA_VERSION:
        fail("schema-mismatch: %s" % st.get("schema_version"), 4)
    return st


def load_config(root):
    p = paths(root)
    cfg = read_json(p["config"], None)
    if cfg is None:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        write_json(p["config"], cfg)
    return cfg


def logline(root, line):
    logdir = root / "log"
    logdir.mkdir(parents=True, exist_ok=True)
    with open(logdir / "tick.log", "a", encoding="utf-8") as f:
        f.write("[%s] %s\n" % (now(), line))


# ---------- naming / boundary ----------

STYLE_PATTERNS = {
    "snake_case": ("^[a-z0-9]+(_[a-z0-9]+)*\\.[a-z0-9]+$", "^[a-z0-9]+(_[a-z0-9]+)*$"),
    "kebab_case": ("^[a-z0-9]+(-[a-z0-9]+)*\\.[a-z0-9]+$", "^[a-z0-9]+(-[a-z0-9]+)*$"),
}


def style_for(cfg, name, is_dir, rel_parts):
    n = cfg["naming"]
    sk = n["style_by_kind"]
    if is_dir:
        first = rel_parts[0] if rel_parts else ""
        return sk["code_dir"] if first in n["code_zones"] else sk["dir"]
    ext = os.path.splitext(name)[1].lower()
    return sk["doc"] if ext in n["doc_exts"] else sk["code"]


def name_ok(name, cfg, is_dir=False, rel_parts=()):
    low = name.lower()
    if name.startswith("."):
        # dotfiles / dot dirs are ecosystem convention, exempt
        return True, "dot-name"
    if low in [w.lower() for w in cfg["naming"]["whitelist"]]:
        return True, "whitelist"
    style = style_for(cfg, name, is_dir, rel_parts)
    fp, dp = STYLE_PATTERNS.get(style, STYLE_PATTERNS["snake_case"])
    if re.match(dp if is_dir else fp, name):
        return True, style
    return False, "not-%s" % style


def in_root(root, target):
    try:
        t = Path(target).resolve()
    except Exception:
        return False
    r = Path(root).resolve()
    return t == r or r in t.parents


def check_path(root, rel, cfg, kind):
    rel = rel.replace("\\", "/").strip().strip("/")
    full = (Path(root) / rel).resolve()
    if not in_root(root, full):
        return False, "outside-root: %s" % rel
    parts = rel.split("/")
    if parts[0] not in cfg["dirs"] and parts[0] != SPEC_DIR:
        return False, "bad-zone: '%s' not in %s" % (parts[0], cfg["dirs"] + [SPEC_DIR])
    if kind and parts[0] != kind:
        return False, "zone-mismatch: declared %s, path says %s" % (kind, parts[0])
    if len(parts) > cfg["max_depth"] and not rel.startswith(SPEC_DIR + "/steps"):
        return False, "too-deep: %d > %d" % (len(parts), cfg["max_depth"])
    for i, seg in enumerate(parts):
        isd = (i < len(parts) - 1) if "." in parts[-1] else True
        ok, why = name_ok(seg, cfg, is_dir=isd)
        if not ok:
            return False, "bad-name[%s]: %s" % (seg, why)
    return True, str(full)


# ---------- markdown parsing ----------

def plan_step_section(text):
    # only the 步骤总表 section is authoritative; other tables must not be parsed
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#") and "步骤总表" in line:
            start = i + 1
            break
    if start is None:
        return lines
    out_lines = []
    for line in lines[start:]:
        if line.lstrip().startswith("#"):
            break
        out_lines.append(line)
    return out_lines


def parse_plan_steps(plan_path):
    rows = {}
    if not Path(plan_path).exists():
        return rows
    for line in plan_step_section(Path(plan_path).read_text(encoding="utf-8")):
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        cid = cells[0]
        if not cid or set(cid) <= set("-: ") or cid.lower() == "id":
            continue
        phase = next((c for c in cells if c in PHASES), None)
        if phase is None:
            continue
        doc = next((c for c in cells if "steps/" in c), None)
        title = cells[1] if len(cells) > 1 and cells[1] not in PHASES else ""
        rest = [c for c in cells if c not in (cid, title, doc, phase) and c and c != "-"]
        hint = max(rest, key=len) if rest else ""
        rows[cid] = {"phase": phase, "doc": doc, "title": title, "hint": hint}
    return rows


def parse_front(md_path):
    d = {}
    if not Path(md_path).exists():
        return d
    for line in Path(md_path).read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            m = re.match(r">\s*([a-zA-Z_]+)\s*:\s*(.*)", line)
            if m:
                d[m.group(1).lower()] = m.group(2).strip()
        elif d:
            break
    return d


def checklist(md_path):
    if not Path(md_path).exists():
        return []
    items = []
    for line in Path(md_path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*- \[( |x)\]\s*(.+)", line)
        if m:
            items.append([m.group(1) == "x", m.group(2).strip()])
    return items


# ---------- risk ----------

def assess(step, cfg, did, last_did):
    w = cfg["watchdog"]
    if step["no_progress"] >= w["stalled_turns"] and did != "wait":
        return "stalled", "连续 %d 轮无 +1，建议：中断当前方案 / 换策略 / 拆小步骤" % step["no_progress"]
    if step["turns"] >= w["max_turns_per_step"]:
        return "overrun", "本步已 %d 轮（上限 %d），建议：拆分为多个步骤或重估范围" % (
            step["turns"], w["max_turns_per_step"])
    if did == "-1" and last_did == "-1" and w["backtrack_review"] <= 2:
        return "backtrack-review", "连续 2 次回退，强制停下对齐，不得继续推进"
    if did == "-1":
        return "backtrack", "本轮发生回退，记录决策并评估影响面"
    return None, ""


PHASE_LABEL = {"draft": "尚未开始", "execute": "进行中", "verify": "验收中",
               "blocked": "受阻", "done": "已完成"}


def step_progress(root, sid):
    """验收进度：读 step.md 的 checkbox，返回 (done, total) 或 (None, None)。"""
    if not sid:
        return None, None
    items = checklist(paths(Path(root))["steps"] / sid / "step.md")
    if not items:
        return None, None
    return sum(1 for d, _ in items if d), len(items)


def step_goal(root, sid):
    """取 step.md「## 目标」下第一段，压成一行——状态头的「下一轮」要说人话。"""
    md = paths(Path(root))["steps"] / sid / "step.md"
    if not md.exists():
        return ""
    lines = md.read_text(encoding="utf-8").splitlines()
    try:
        i = next(n for n, l in enumerate(lines) if l.strip().startswith("## 目标"))
    except StopIteration:
        return ""
    buf = []
    for l in lines[i + 1:]:
        t = l.strip()
        if t.startswith("#"):
            break
        if not t:
            if buf:
                break
            continue
        buf.append(t)
    txt = " ".join(buf)
    txt = re.sub(r"[。；]$", "", txt)
    return txt[:90] + ("…" if len(txt) > 90 else "")


def next_hint(root, st, ids, active):
    """下一轮要做的事：本步没完就说还差什么，完了就指向下一步要做什么。"""
    if not ids:
        return "还没导入步骤：先在 plan.md 写「步骤总表」，再跑 `sp.sh plan --import`"
    s = st["steps"].get(active, {})
    title = s.get("title") or ""
    if s.get("phase") != "done":
        d, total = step_progress(root, active)
        if total and d < total:
            items = checklist(paths(Path(root))["steps"] / active / "step.md")
            first_open = next((txt for ok, txt in items if not ok), "")
            return "继续 %s「%s」：验收还差 %d 项，先做「%s」" % (
                active, title, total - d, first_open[:50])
        if total and d >= total:
            return "本步验收已全过：跑 `sp.sh step %s --phase done` 收尾，再进下一步" % active
        what = step_goal(root, active) or s.get("hint") or ""
        return "继续 %s「%s」%s" % (active, title, ("：" + what) if what else "")
    if active in ids and ids.index(active) + 1 < len(ids):
        nxt = ids[ids.index(active) + 1]
        ntitle = st["steps"][nxt].get("title") or ""
        what = step_goal(root, nxt) or st["steps"][nxt].get("hint") or ""
        for pre in (ntitle, nxt):
            if pre and what.startswith(pre):
                what = what[len(pre):].lstrip("：:，,· ")
                break
        return "进入 %s「%s」%s" % (nxt, ntitle, ("：" + what) if what else "")
    return "%d 步已全部完成，可以 `sp.sh handoff` 交接或 `sp.sh archive` 冻结" % len(ids)


def risk_sentence(risk, s, cfg):
    """风险点用人话说，不甩代码名。"""
    if not risk:
        return "无"
    w = cfg["watchdog"]
    if risk == "stalled":
        return "连续 %d 轮没有实际产出，大概率是方向或粒度不对——建议停下来换策略，或把这步拆小" % s.get("no_progress", 0)
    if risk == "overrun":
        return "这一步已经打了 %d 轮，超过上限 %d——通常说明这一步该拆开，而不是继续硬推" % (
            s.get("turns", 0), w["max_turns_per_step"])
    if risk == "backtrack":
        return "本轮推翻了已定的东西，先确认影响面再往下走"
    if risk == "backtrack-review":
        return "连续两次回退，先停下来对齐目标，不要继续推进"
    return risk


def header(root, st, cfg, risk=None, advice=""):
    """状态头：两列表格。四行讲清「在哪、上轮做了什么、下轮做什么、有什么风险」。"""
    steps = st["steps"]
    ids = sorted(steps.keys())
    active = st.get("active_step")
    idx = ids.index(active) + 1 if active in ids else 0
    s = steps.get(active, {"phase": "-", "turns": 0, "title": "", "no_progress": 0})
    title = (s.get("title") or "").strip()
    done_steps = sum(1 for c in ids if steps[c].get("phase") == "done")
    adone, atotal = step_progress(root, active)
    last = st.get("last_round", {})
    summary = (last.get("summary") or "").strip()

    step_txt = "%s%s（第 %d 步 / 共 %d 步，%s）" % (
        active or "未开始", ("「" + title + "」") if title else "", idx, len(ids),
        PHASE_LABEL.get(s.get("phase"), s.get("phase", "-")))
    last_txt = summary or ("（上一轮没写摘要）" if last.get("n") else "还没开始做")

    out("%s spec-pact · %s · %d/%d 步完成" % (
        MARK_OK, st.get("task", "unnamed"), done_steps, len(ids)))
    out("")
    out("| 项 | 内容 |")
    out("|---|---|")
    out("| 步骤 | %s |" % step_txt)
    out("| 上一轮做完的事 | %s |" % last_txt)
    out("| 下一轮要做的事 | %s |" % next_hint(root, st, ids, active))
    out("| 风险点 | %s |" % risk_sentence(risk, s, cfg))
    if VERBOSE_HEADER:
        out("| 阶段 | %s |" % PHASE_LABEL.get(s.get("phase"), s.get("phase", "-")))
        out("| 轮次 | %d/%d |" % (s.get("turns", 0), cfg["watchdog"]["max_turns_per_step"]))
        out("| 验收 | %s |" % (("%d/%d" % (adone, atotal)) if atotal else "-"))
        out("| 待同步 | %s |" % ("; ".join(st["pending_sync"]) if st.get("pending_sync") else "无"))

    if st.get("pending_sync") and not VERBOSE_HEADER:
        out("")
        out("%s pending-sync: %s" % (MARK_WARN, "; ".join(st["pending_sync"])))


# ---------- commands ----------

def cmd_init(a):
    root = Path(a.root).resolve() if a.root else Path.cwd().resolve()
    root.mkdir(parents=True, exist_ok=True)
    p = paths(root)
    if p["state"].exists() and not a.force:
        fail("already-initialized: %s (use --force to re-init)" % root, 2)
    p["spec"].mkdir(parents=True, exist_ok=True)
    for d in DEFAULT_CONFIG["dirs"]:
        (root / d).mkdir(exist_ok=True)
    for d in ("steps", "snapshots", "archive"):
        (p["spec"] / d).mkdir(exist_ok=True)
    write_json(p["config"], DEFAULT_CONFIG)
    st = {
        "schema_version": SCHEMA_VERSION,
        "root": str(root),
        "task": a.task or "unnamed",
        "plan_version": 1,
        "phase": "plan",
        "active_step": None,
        "steps": {},
        "counts": {"decisions": 0, "changes": 0, "pending": 0, "diff": 0},
        "last_round": {"n": 0, "did": "-", "summary": ""},
        "pending_sync": [],
        "risk": None,
        "updated_at": now(),
    }
    write_json(p["state"], st)
    if not p["plan"].exists():
        p["plan"].write_text(PLAN_TMPL % {"task": st["task"], "date": now()}, encoding="utf-8")
    if not p["refs"].exists():
        p["refs"].write_text(REFS_TMPL, encoding="utf-8")
    if not p["decisions"].exists():
        p["decisions"].write_text("# decisions\n\n> 决策 = 会改变方向 / 边界 / 标准的判断，必须写清「为什么」。\n\n", encoding="utf-8")
    if not p["changes"].exists():
        p["changes"].write_text("# changes\n\n> 改动 = 已定方向内的增删改，只记「改了什么」，不记理由。\n\n", encoding="utf-8")
    out("ok init · root=%s · task=%s" % (root, st["task"]))
    # init 自带解释器体检：不留到"忘了跑 env"那一步
    ce = collect_env()
    info, reg, reg_path = persist_env(root, ce)
    out("  python %s [%s] %s" % (info["running"]["version"], ce["cur_tier"], ce["cur"]))
    if ce["cur_tier"] != "A-system" and ce["best"] and ce["best"]["tier"] == "A-system":
        out("  ! 改用系统解释器：SP_PYTHON=%s（或直接 %s scripts/sp.py …）；不要为此下载新 python"
            % (ce["best"]["path"], ce["best"]["path"]))
    if ce["cur_tier"] == "C-sandbox":
        out("  ! 当前解释器在沙箱临时目录：可用，但禁止用它装依赖")
    out("  env → .spec-pact/env.json · 候选 %d · registry deps=%d"
        % (len(ce["ranked"]), len(reg["deps"])))
    out("next: 1) 写 plan.md 步骤总表  2) sp.py plan --import  3) sp.py tick --did +1")


def cmd_doctor(a):
    root = find_root(a.root)
    if root is None:
        out("fail python-ok")
        out("fail root-writable: no .spec-pact found")
        sys.exit(3)
    p = paths(root)
    ok = True
    cur_tier = python_tier(sys.executable)
    out("python %s [%s] %s" % ("%d.%d.%d" % sys.version_info[:3], cur_tier, sys.executable))
    if cur_tier != "A-system":
        out("warn python-tier %s · 优先用 A-system；B 只复用不重下，C 禁止装依赖" % cur_tier)
    if not (p["spec"] / "env.json").exists():
        persist_env(root, collect_env())
        out("env regenerated · .spec-pact/env.json 缺失，已重建")
    for key in ("state", "config", "plan", "decisions", "changes"):
        if not p[key].exists():
            out("missing %s" % p[key].name)
            ok = False
    if not os.access(root, os.W_OK):
        out("fail root-writable")
        ok = False
    for d in DEFAULT_CONFIG["dirs"]:
        if not (root / d).is_dir():
            out("missing dir %s/" % d)
            ok = False
    st = read_json(p["state"], None)
    if st is None:
        out("fail state-unreadable")
        ok = False
    else:
        if st.get("schema_version") != SCHEMA_VERSION:
            out("fail schema-mismatch")
            ok = False
        last = st.get("updated_at", "")
        try:
            delta = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() / 60
            if delta > DEFAULT_CONFIG["watchdog"]["tick_stale_minutes"]:
                out("warn last-tick %d min ago (疑似漏调 tick)" % delta)
        except Exception:
            pass
    out("ok doctor" if ok else "doctor found problems")
    sys.exit(0 if ok else 2)


def cmd_plan_import(a):
    root = require_root(a.root)
    p = paths(root)
    st = load_state(root)
    rows = parse_plan_steps(p["plan"])
    if not rows:
        fail("no-steps: plan.md 步骤总表为空或格式不符", 2)
    created = []
    for cid, info in rows.items():
        if cid not in st["steps"]:
            st["steps"][cid] = {"title": info.get("title") or "", "phase": info["phase"], "turns": 0,
                                "no_progress": 0, "did_history": [], "accept": [],
                                "hint": info.get("hint") or "",
                                "frozen": False, "updated_at": now()}
            created.append(cid)
        else:
            st["steps"][cid]["phase"] = info["phase"]
            if info.get("title"):
                st["steps"][cid]["title"] = st["steps"][cid].get("title") or info["title"]
            if info.get("hint"):
                st["steps"][cid]["hint"] = info["hint"]
        d = p["steps"] / cid
        d.mkdir(parents=True, exist_ok=True)
        sm = d / "step.md"
        if not sm.exists():
            sm.write_text(STEP_TMPL % {"id": cid, "date": now(),
                                       "status": info["phase"]}, encoding="utf-8")
    if not st.get("active_step"):
        first = sorted(rows.keys())[0]
        st["active_step"] = first
    st["phase"] = "execute"
    st["updated_at"] = now()
    backup_state(root, p["state"])
    write_json(p["state"], st)
    out("ok plan · %d steps · new=%s · active=%s" % (
        len(rows), ",".join(created) or "none", st["active_step"]))


def cmd_tick(a):
    global VERBOSE_HEADER
    VERBOSE_HEADER = bool(getattr(a, "verbose", False))
    root = require_root(a.root)
    p = paths(root)
    cfg = load_config(root)
    st = load_state(root)
    did = a.did
    if did not in DID_VALUES:
        fail("bad --did: %s (use +1 / 0 / -1 / wait)" % did, 2)

    # settle the round that just ended
    if st["last_round"]["n"] > 0:
        sid = st.get("active_step")
        s = st["steps"].get(sid)
        if s is not None:
            s["turns"] += 1
            s["did_history"].append(did)
            if did == "+1":
                s["no_progress"] = 0
            elif did == "wait":
                s["no_progress"] = 0
            else:
                s["no_progress"] += 1
            s["updated_at"] = now()

    if a.step:
        if a.step not in st["steps"]:
            fail("unknown step: %s" % a.step, 2)
        st["active_step"] = a.step

    st["last_round"] = {"n": st["last_round"]["n"] + 1, "did": did,
                        "summary": a.summary or ""}

    sid = st.get("active_step")
    s = st["steps"].get(sid, {"turns": 0, "no_progress": 0, "phase": "-", "did_history": []})
    hist = s.get("did_history", [])
    last_did = hist[-2] if len(hist) >= 2 else None
    risk, advice = assess(s, cfg, did, last_did)
    st["risk"] = risk
    st["updated_at"] = now()
    backup_state(root, p["state"])
    write_json(p["state"], st)
    logline(root, "tick n=%d did=%s step=%s risk=%s %s" % (
        st["last_round"]["n"], did, sid, risk or "-", a.summary or ""))
    header(root, st, cfg, risk, advice)
    if a.json_out:
        out(json.dumps({"step": sid, "phase": s.get("phase"), "turns": s.get("turns"),
                        "risk": risk, "advice": advice}, ensure_ascii=False))
    sys.exit(4 if risk in ("stalled", "overrun", "backtrack-review") else 0)


def cmd_status(a):
    global VERBOSE_HEADER
    VERBOSE_HEADER = bool(a.verbose)
    root = require_root(a.root)
    cfg = load_config(root)
    st = load_state(root)
    header(root, st, cfg, st.get("risk") if st.get("risk") != "none" else None,
           "上次判定的风险未清除")
    if a.verbose:
        out("")
        out("| 步骤 | 阶段 | 轮次 | 停滞 | 验收 | 状态 |")
        out("|:---|:---|--:|--:|--:|:---|")
        for cid in sorted(st["steps"]):
            s = st["steps"][cid]
            d, t = step_progress(root, cid)
            out("| %s | %s | %d | %d | %s | %s |" % (
                cid, s["phase"], s["turns"], s["no_progress"],
                ("%d/%d" % (d, t)) if t else "-",
                "frozen" if s.get("frozen") else ""))


def cmd_resume(a):
    """新开一个会话时的单次调用：状态头 + 环境 + 距上次多久（防漏 tick）。"""
    global VERBOSE_HEADER
    VERBOSE_HEADER = True
    root = require_root(a.root)
    p = paths(root)
    cfg = load_config(root)
    st = load_state(root)
    header(root, st, cfg, st.get("risk") if st.get("risk") not in (None, "none") else None,
           "上次判定的风险未清除")
    env = read_json(p["spec"] / "env.json", None)
    out("")
    cur_tier = python_tier(sys.executable)
    if env:
        r = env.get("running", {})
        out("环境：python %s [%s]（登记 %s）" % (r.get("version", "?"), r.get("tier", "?"),
                                          (env.get("detected_at") or "?")[:16]))
    else:
        out("环境：未登记（跑一次 sp.sh env）")
    out("当前：python %s [%s]" % ("%d.%d.%d" % sys.version_info[:3], cur_tier))
    if cur_tier == "C-sandbox":
        out("! 当前解释器在沙箱临时目录，不要用它装依赖")
    try:
        delta = (datetime.now() - datetime.strptime(st["updated_at"], "%Y-%m-%d %H:%M")).total_seconds() / 60
        if delta > cfg["watchdog"]["tick_stale_minutes"]:
            out("! 距上次 tick 已 %d 分钟：中间可能有未被记录的回合，轮次与验收以实际为准" % delta)
        else:
            out("上次：%d 分钟前" % delta if delta >= 1 else "上次：刚刚")
    except Exception:
        pass


def cmd_step(a):
    root = require_root(a.root)
    p = paths(root)
    st = load_state(root)
    if a.phase and a.phase not in PHASES:
        fail("bad phase: %s" % a.phase, 2)
    if a.step not in st["steps"]:
        st["steps"][a.step] = {"title": a.title or "", "phase": "draft", "turns": 0,
                               "no_progress": 0, "did_history": [], "accept": [],
                               "frozen": False, "updated_at": now()}
    s = st["steps"][a.step]
    if a.title:
        s["title"] = a.title
    if a.phase:
        s["phase"] = a.phase
        st["active_step"] = a.step
    s["updated_at"] = now()
    st["updated_at"] = now()
    backup_state(root, p["state"])
    write_json(p["state"], st)
    out("ok step %s · phase=%s" % (a.step, s["phase"]))
    out("reminder: 同步 plan.md 步骤总表 与 steps/%s/step.md 的 status（三向一致）" % a.step)


def cmd_decision(a):
    root = require_root(a.root)
    p = paths(root)
    st = load_state(root)
    n = st["counts"]["decisions"] + 1
    trigger = a.trigger or "-"
    sid = a.step or st.get("active_step") or "-"
    row = "\n## D-%02d · %s\n\n- 步骤：%s\n- 触发器：%s\n- 轮次：%d\n- 内容：%s\n" % (
        n, now(), sid, trigger, st["last_round"]["n"], a.text)
    with open(p["decisions"], "a", encoding="utf-8") as f:
        f.write(row)
    st["counts"]["decisions"] = n
    st["pending_sync"] = list(set(st.get("pending_sync", []) + ["plan.md §决策索引"]))
    st["updated_at"] = now()
    backup_state(root, p["state"])
    write_json(p["state"], st)
    out("ok decision D-%02d · 已落盘 decisions.md · 待同步 plan.md §决策索引" % n)


def cmd_change(a):
    root = require_root(a.root)
    p = paths(root)
    st = load_state(root)
    n = st["counts"]["changes"] + 1
    sid = a.step or st.get("active_step") or "-"
    with open(p["changes"], "a", encoding="utf-8") as f:
        f.write("- [%s] %s · 轮 %d · %s\n" % (sid, now(), st["last_round"]["n"], a.text))
    st["counts"]["changes"] = n
    st["updated_at"] = now()
    write_json(p["state"], st)
    out("ok change #%d · 已记入 changes.md（无理由，仅 diff 摘要）" % n)


def cmd_accept(a):
    root = require_root(a.root)
    p = paths(root)
    st = load_state(root)
    sm = p["steps"] / a.step / "step.md"
    items = checklist(sm)
    if not items:
        out("no-items %s" % sm)
        return
    if a.item is not None:
        if a.item < 1 or a.item > len(items):
            fail("bad --item %d (1..%d)" % (a.item, len(items)), 2)
        lines = Path(sm).read_text(encoding="utf-8").splitlines()
        seen = 0
        for i, line in enumerate(lines):
            if re.match(r"\s*- \[( |x)\]\s*", line):
                seen += 1
                if seen == a.item:
                    lines[i] = re.sub(r"- \[ \]", "- [x]", line, count=1)
        Path(sm).write_text("\n".join(lines) + "\n", encoding="utf-8")
        items = checklist(sm)
        st["steps"][a.step]["updated_at"] = now()
        st["pending_sync"] = list(set(st.get("pending_sync", []) + ["plan.md §步骤总表"]))
        write_json(p["state"], st)
    done = sum(1 for d, _ in items if d)
    out("accept %s · %d/%d 通过" % (a.step, done, len(items)))
    for i, (d, t) in enumerate(items, 1):
        if not d:
            out("  open %d: %s" % (i, t))
    if done == len(items):
        out("all-passed → 建议：sp.py step %s --phase verify 然后 done" % a.step)


def cmd_sync(a):
    root = require_root(a.root)
    p = paths(root)
    st = load_state(root)
    plan = parse_plan_steps(p["plan"])
    bad = []
    for cid in sorted(set(list(plan.keys()) + list(st["steps"].keys()))):
        a1 = plan.get(cid, {}).get("phase", "missing")
        a3 = st["steps"].get(cid, {}).get("phase", "missing")
        sm = p["steps"] / cid / "step.md"
        a2 = parse_front(sm).get("status", "missing")
        vals = {a1, a2, a3}
        if len(vals) != 1:
            bad.append("%s: plan=%s step.md=%s state=%s" % (cid, a1, a2, a3))
        fr = parse_front(sm)
        if fr.get("pending_sync", "无") not in ("无", "-", "", None):
            bad.append("%s: 待同步主文档 → %s" % (cid, fr["pending_sync"]))
    if bad:
        out("conflict %d" % len(bad))
        for b in bad:
            out("  " + b)
        sys.exit(2)
    if a.ack and st.get("pending_sync"):
        cleared = st["pending_sync"]
        st["pending_sync"] = []
        backup_state(root, p["state"])
        write_json(p["state"], st)
        out("ack · 已清空 pending_sync（%s）—— 确认主文档索引已手工同步" % ", ".join(cleared))
    out("ok sync · 三向一致 · %d steps" % len(st["steps"]))


def cmd_lint(a):
    root = require_root(a.root)
    cfg = load_config(root)
    p = paths(root)
    st = load_state(root)
    hard, soft = [], []
    skip = {".git", "node_modules", "__pycache__"}
    for cur, dirs, files in os.walk(root):
        cur_p = Path(cur)
        rel_root = cur_p.relative_to(root)
        dirs[:] = [d for d in dirs if d not in skip]
        depth = len(rel_root.parts)
        for d in dirs:
            ok, why = name_ok(d, cfg, is_dir=True)
            if not ok:
                soft.append("dir  %s/ (%s)" % ((rel_root / d).as_posix(), why))
            if depth + 1 > cfg["max_depth"] and not str(rel_root).startswith(SPEC_DIR + "/"):
                hard.append("deep %s/" % (rel_root / d).as_posix())
        for f in files:
            ok, why = name_ok(f, cfg, is_dir=False)
            if not ok:
                soft.append("file %s (%s)" % ((rel_root / f).as_posix(), why))
    strict = cfg["naming"]["strict_existing"]
    issues = len(hard) + (len(soft) if strict else 0)
    st["last_lint_issues"] = issues
    write_json(p["state"], st)
    if hard:
        out("lint HARD %d" % len(hard))
        for b in hard[:30]:
            out("  " + b)
    if soft:
        out("lint soft %d (非 snake_case，%s)" % (
            len(soft), "strict 模式视为违规" if strict else "存量容忍，AI 新建请用 touch 校验"))
        if strict or a.verbose:
            for b in soft[:30]:
                out("  " + b)
    if issues:
        sys.exit(2)
    out("ok lint · no blocking issue%s" % (" · %d tolerated" % len(soft) if soft else ""))


def cmd_touch(a):
    root = require_root(a.root)
    cfg = load_config(root)
    ok, msg = check_path(root, a.path, cfg, a.kind)
    if not ok:
        fail(msg, 2)
    out("ok %s" % msg)


def cmd_archive(a):
    root = require_root(a.root)
    p = paths(root)
    st = load_state(root)
    s = st["steps"].get(a.step)
    if s is None:
        fail("unknown step %s" % a.step, 2)
    s["frozen"] = True
    s["phase"] = "done"
    s["updated_at"] = now()
    st["updated_at"] = now()
    write_json(p["state"], st)
    out("ok archive %s · 就地冻结（路径不变，引用不悬挂）" % a.step)


def user_registry_path():
    return Path.home() / ".spec-pact" / "env.json"


SANDBOX_MARKERS = ("\\temp\\", "\\tmp\\", "sandbox", "\\appdata\\local\\temp", "/tmp/")
AGENT_MANAGED_MARKERS = ("\\.workbuddy\\", "/.workbuddy/", "\\.cursor\\", "/.cursor/",
                         "\\.claude\\", "/.claude/", "\\.codex\\", "/.codex/",
                         "\\pyenv\\", "/pyenv/", "\\.local\\share\\uv\\", "/.local/share/uv/",
                         "pipx\\cache", "/pipx/", "\\.npm\\", "/.npm/_npx")
SYSTEM_MARKERS = ("c:\\python", "c:\\program files\\python", ":\\windows\\",
                  "/usr/bin/", "/usr/local/bin/", "/opt/homebrew/bin/", "/opt/conda")


def python_tier(path):
    low = str(path).lower().replace("/", "\\")
    if any(k in low for k in SANDBOX_MARKERS):
        return "C-sandbox"
    if any(k in low for k in AGENT_MANAGED_MARKERS):
        return "B-agent-managed"
    if any(k in low for k in SYSTEM_MARKERS):
        return "A-system"
    return "B-agent-managed"


def probe_installed_pythons():
    # system installs that are simply not on PATH (the "agent re-downloads python" trap)
    hits = []
    roots = ["C:\\", "C:\\Program Files\\", os.environ.get("LOCALAPPDATA", "")]
    for r in roots:
        if not r:
            continue
        for pat in ("Python3*/python.exe", "Python3*/python3.exe"):
            for m in glob.glob(os.path.join(r, pat)):
                hits.append(m)
    base = os.environ.get("LOCALAPPDATA", "")
    if base:
        hits += glob.glob(os.path.join(base, "Programs", "Python", "Python3*", "python.exe"))
    seen, out_ = set(), []
    for h in hits:
        k = os.path.normcase(os.path.abspath(h))
        if k in seen or not os.path.isfile(h):
            continue
        seen.add(k)
        out_.append({"cmd": "probe", "path": h, "tier": python_tier(h)})
    return out_


def resolve_py_launcher(path):
    """py.exe 只是启动器，不是解释器本体：问它到底指向哪个 python。"""
    try:
        import subprocess
        r = subprocess.run([path, "-3", "-c", "import sys; print(sys.executable)"],
                           capture_output=True, text=True, timeout=8)
        if r.returncode == 0:
            real = (r.stdout or "").strip().splitlines()
            if real and os.path.isfile(real[-1]):
                return real[-1]
    except Exception:
        return None
    return None


def detect_pythons():
    found = []
    for n in ("python", "python3", "py"):
        p = shutil.which(n)
        if not p:
            continue
        if n == "py":
            real = resolve_py_launcher(p)
            if real:
                found.append({"cmd": "py-3", "path": real, "tier": python_tier(real)})
                continue
        found.append({"cmd": n, "path": p, "tier": python_tier(p)})
    found += probe_installed_pythons()
    seen, uniq = set(), []
    for f in found:
        k = os.path.normcase(os.path.abspath(f["path"]))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    return uniq


TIER_RANK = {"A-system": 0, "B-agent-managed": 1, "C-sandbox": 2}


def collect_env():
    """解释器分级探测。A-system 优先，B 复用不重下，C 禁止装依赖。"""
    found = detect_pythons()
    cur = sys.executable
    ranked = sorted(found, key=lambda d: TIER_RANK[d["tier"]])
    return {"ranked": ranked, "cur": cur, "cur_tier": python_tier(cur),
            "best": ranked[0] if ranked else None}


def persist_env(root, ce):
    """把探测结果写进 .spec-pact/env.json（项目级）与 ~/.spec-pact/env.json（用户级）。"""
    p = paths(root)
    reg_path = user_registry_path()
    reg = read_json(reg_path, {"deps": {}, "pythons": [], "updated_at": None})
    best = ce["best"]
    info = {
        "detected_at": now(),
        "running": {"path": ce["cur"], "version": "%d.%d.%d" % sys.version_info[:3],
                    "tier": ce["cur_tier"]},
        "candidates": ce["ranked"],
        "recommended": best["path"] if best else None,
        "user_registry": str(reg_path),
        "policy": {
            "order": ["A-system", "B-agent-managed(复用已下载的，不重新下载)", "C-sandbox(禁止)"],
            "never_download_for_sp": True,
            "dep_reuse": "先查用户级 registry，命中即复用，禁止重装",
        },
    }
    write_json(p["spec"] / "env.json", info)
    reg["pythons"] = sorted({d["path"] for d in ce["ranked"]} | {ce["cur"]}, key=str)
    reg["pythons_by_tier"] = {d["path"]: d["tier"] for d in ce["ranked"]}
    reg["updated_at"] = now()
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(reg_path, reg)
    return info, reg, reg_path


def cmd_env(a):
    root = require_root(a.root)
    reg_path = user_registry_path()
    reg = read_json(reg_path, {"deps": {}, "pythons": [], "updated_at": None})

    if a.dep:
        dep = reg["deps"].get(a.dep)
        if a.register:
            reg["deps"][a.dep] = {"path": a.register, "version": a.version or "?",
                                  "at": now(), "by": "spec-pact"}
            reg["updated_at"] = now()
            reg_path.parent.mkdir(parents=True, exist_ok=True)
            write_json(reg_path, reg)
            out("ok dep %s · 已登记 %s (用户级复用，后续项目直接命中)" % (a.dep, a.register))
            return
        if dep:
            out("reuse %s · %s · 已装于 %s（禁止重复安装）" % (a.dep, dep.get("version"), dep.get("path")))
            return
        out("missing %s · 未登记。安装后执行：sp.py env --dep %s --register <path> --version <v>" % (a.dep, a.dep))
        sys.exit(2)

    ce = collect_env()
    info, reg, reg_path = persist_env(root, ce)
    best, ranked = ce["best"], ce["ranked"]
    out("ok env · running=%s (%s) [%s]" % (ce["cur"], info["running"]["version"], ce["cur_tier"]))
    for f in ranked:
        out("  %-16s %s → %s" % (f["tier"], f["cmd"], f["path"]))
    if best and best["path"].lower() != ce["cur"].lower():
        out("! 推荐改用 %s，当前用的是 %s" % (best["path"], ce["cur_tier"]))
        out("  用法：显式用推荐解释器调用 sp.py，或 SP_PYTHON=<path> sh scripts/sp.sh ...")
    if ce["cur_tier"] == "C-sandbox":
        out("! 当前 python 位于沙箱临时目录，禁止用它安装依赖（会话结束即失效）")
    out("  registry %s · deps=%d" % (reg_path, len(reg["deps"])))


def cmd_handoff(a):
    root = require_root(a.root)
    p = paths(root)
    dest = root / "output" / ("handoff_" + fstamp())
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(p["spec"], dest / "spec_pact",
                    ignore=shutil.ignore_patterns("log"))
    lines = ["# 交接说明 · %s" % now(), "",
             "## 一、这是什么", "(见 spec_pact/plan.md)", "",
             "## 二、做到哪了", "- active: %s" % load_state(root).get("active_step"), "",
             "## 三、接下来", "(见 spec_pact/plan.md 步骤总表未 done 项)", "",
             "## 四、交付清单", "- spec_pact/（state / plan / steps / decisions / changes）", "",
             "## 五、如何接收", "放进你的根目录 → sp.py doctor → sp.py tick --did 0"]
    (dest / "handoff.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    out("ok handoff · %s" % dest)


PLAN_TMPL = """# %(task)s

> status: plan
> updated: %(date)s

## 一、任务定义

## 二、目标 / 非目标

## 三、步骤总表

| id | 名称 | 依赖 | 状态 | 验收要点 | 分文档 |
|----|------|------|------|---------|--------|
| 01_example | 示例步骤 | - | draft | 待定 | steps/01_example/step.md |

## 四、文档注册表

| 路径 | 职责 | 状态 | 最后校验 |
|------|------|------|---------|

## 五、决策索引

## 六、风险与 Plan B
"""

STEP_TMPL = """# %(id)s

> parent: ../../plan.md
> status: %(status)s
> updated: %(date)s
> upstream_check: -
> pending_sync: 无

## 目标

## 输入（含外部只读引用 id）

## 输出（落到 work/ 还是 output/，文件名）

## 执行标准

- [ ] 待填写（优先写可机械验证项）

## 执行记录

- turn 1 (+1):
"""

REFS_TMPL = """# refs · 外部只读引用登记

> 规则：外部资料一律不复制进根目录，只登记绝对路径，只读访问。

| id | 绝对路径 | 用途 | 只读 | 登记时间 | 校验(size/mtime) |
|----|---------|------|------|---------|-----------------|
"""


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="workspace root (default: nearest parent with .spec-pact)")
    ap = argparse.ArgumentParser(prog="sp.py", description="spec-pact v2 state machine")
    sub = ap.add_subparsers(dest="cmd")

    c = sub.add_parser("init", parents=[common]); c.add_argument("--task"); c.add_argument("--force", action="store_true"); c.set_defaults(fn=cmd_init)
    c = sub.add_parser("doctor", parents=[common]); c.set_defaults(fn=cmd_doctor)
    c = sub.add_parser("plan", parents=[common]); c.add_argument("--import", dest="imp", action="store_true"); c.set_defaults(fn=cmd_plan_import)
    c = sub.add_parser("tick", parents=[common])
    c.add_argument("--did", default="0", help="+1 推进 / 0 维持 / -1 回退 / wait 等用户")
    c.add_argument("--summary", default="")
    c.add_argument("--step", help="同时切换 active step")
    c.add_argument("--json", dest="json_out", action="store_true")
    c.add_argument("-v", "--verbose", action="store_true", help="状态头用竖表（含待同步 / 未过项）")
    c.set_defaults(fn=cmd_tick)
    c = sub.add_parser("status", parents=[common]); c.add_argument("-v", "--verbose", action="store_true"); c.set_defaults(fn=cmd_status)
    c = sub.add_parser("resume", parents=[common]); c.set_defaults(fn=cmd_resume)
    c = sub.add_parser("step", parents=[common]); c.add_argument("step"); c.add_argument("--phase"); c.add_argument("--title"); c.set_defaults(fn=cmd_step)
    c = sub.add_parser("decision", parents=[common]); c.add_argument("--text", required=True); c.add_argument("--trigger"); c.add_argument("--step"); c.set_defaults(fn=cmd_decision)
    c = sub.add_parser("change", parents=[common]); c.add_argument("--text", required=True); c.add_argument("--step"); c.set_defaults(fn=cmd_change)
    c = sub.add_parser("accept", parents=[common]); c.add_argument("step"); c.add_argument("--item", type=int); c.set_defaults(fn=cmd_accept)
    c = sub.add_parser("sync", parents=[common]); c.add_argument("--ack", action="store_true"); c.set_defaults(fn=cmd_sync)
    c = sub.add_parser("lint", parents=[common]); c.add_argument("-v", "--verbose", action="store_true"); c.set_defaults(fn=cmd_lint)
    c = sub.add_parser("touch", parents=[common]); c.add_argument("path"); c.add_argument("--kind", choices=["resource", "work", "output"]); c.set_defaults(fn=cmd_touch)
    c = sub.add_parser("archive", parents=[common]); c.add_argument("step"); c.set_defaults(fn=cmd_archive)
    c = sub.add_parser("handoff", parents=[common]); c.set_defaults(fn=cmd_handoff)
    c = sub.add_parser("env", parents=[common]); c.add_argument("--dep"); c.add_argument("--register"); c.add_argument("--version"); c.set_defaults(fn=cmd_env)

    a = ap.parse_args()
    if not a.cmd:
        ap.print_help()
        sys.exit(1)
    a.fn(a)


if __name__ == "__main__":
    main()
