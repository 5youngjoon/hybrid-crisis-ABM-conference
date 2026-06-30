#!/usr/bin/env python3
"""
extract_literals.py
===================

Static scan for v.1.88 model, "How a Hybrid Crisis ABM's Parameters Were Found and Decided."
"""

import argparse, csv, os, re, sys
from collections import Counter

# --------------------------------------------------------------------------- #
# 1-2. read interface and code
# --------------------------------------------------------------------------- #
def read_model(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    m = re.search(r"<code>(.*?)</code>", text, flags=re.S)
    if m:
        code = (m.group(1).replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&"))
        widgets = re.findall(r"<(slider|switch|chooser|inputbox)\b", text)
        return code, widgets
    parts = text.split("@#$#@#$#@")
    code = parts[0] if parts else text
    widgets = []
    if len(parts) > 1:
        for blk in parts[1].split("\n\n"):
            head = blk.strip().split("\n", 1)[0].strip().upper()
            if head in {"SLIDER", "SWITCH", "CHOOSER", "INPUTBOX"}:
                widgets.append(head)
    return code, widgets

def declared_globals(code):
    # strip comments/strings first, then bracket-match each globals block, so a
    # stray "]" inside a comment (e.g. "awrp ; ... [0,1] scaled") cannot truncate
    # the capture and comment words are never miscounted as global names.
    code = strip_comments_and_strings(code)
    names = []
    for m in re.finditer(r"globals\s*\[", code, flags=re.I):
        i = m.end(); depth = 1; j = i
        while j < len(code) and depth > 0:
            if code[j] == "[": depth += 1
            elif code[j] == "]": depth -= 1
            j += 1
        names += re.findall(r"[A-Za-z_][A-Za-z0-9_\-?]*", code[i:j - 1])
    return names

def count_procedures(code):
    return len([ln for ln in code.splitlines()
                if re.match(r"^(to|to-report)\s+\S", ln.strip())])

# --------------------------------------------------------------------------- #
# 3. strip comments and strings
# --------------------------------------------------------------------------- #
def strip_comments_and_strings(code):
    out = []
    for line in code.splitlines():
        line = re.sub(r'"(?:[^"\\]|\\.)*"', " ", line)
        i = line.find(";")
        if i != -1:
            line = line[:i]
        out.append(line)
    return "\n".join(out)

# --------------------------------------------------------------------------- #
# 4. classify
# --------------------------------------------------------------------------- #
NUM = re.compile(r"(?<![A-Za-z0-9_\-.])-?\d+(?:\.\d+)?(?:[eE]-?\d+)?")

# a procedure whose NAME marks it as an outcome / measurement reporter
OUTCOME = re.compile(
    r"^(outcome-|ever-|first-|strategic-regime|current-crisis-fit|"
    r"calibration-score|.*-share$|.*-hit$|.*-fired$|.*-flag$|.*-window.*|ms-|"
    r".*-recovery-lag.*|.*-tick.*|.*-tick-report|tau-.*-leads.*|.*-decay-share|"
    r".*normalized-recovery|.*-condition-.*|.*-duration|.*-frac.*|"
    r"major-strike-this-tick.|major-action-this-tick.*|low-intensity-military.*|"
    r"ticks-since-major-strike.*|awrp-frac-recovery-threshold|no-talks-share)", re.I)
DISPLAY = re.compile(r"\bplot\b|\bpen\b|histogram|set-plot|plotxy|set-current-plot|"
                     r"set-plot-|set-default-shape|\bcolor\b|\blabel\b", re.I)
BOUND = re.compile(r"\bbound\b|\bclamp\b", re.I)            # a clamp call
SCALEOTHER = re.compile(r"floor|ceiling|normaliz|\bprecision\b", re.I)
INERT = re.compile(r"\brepeat\b|\bitem\b|\brange\b|\bn-values\b|\bsublist\b|\bposition\b|"
                   r"\bcreate-|\bfput\b|\blput\b|but-first|but-last|\bmod\b", re.I)
SET_RE = re.compile(r"\bset\s+([A-Za-z_][A-Za-z0-9_\-?]*)", re.I)
DIV0_GUARD = re.compile(r"max\s*\(\s*list\s+1\s+ticks\s*\)", re.I)

def local_role(proc_name, line):
    m = SET_RE.search(line)
    return f"{proc_name.lower()}::{(m.group(1).lower() if m else '_')}"

def proc_iter(code):
    for m in re.finditer(r"\b(to(?:-report)?)\s+([^\s\[]+)(.*?)\bend\b",
                         code, flags=re.S | re.I):
        yield m.group(2), m.group(3)

def scan(code):
    """Occurrence-level classification. On a `bound (...) LO HI` line, only the
    trailing two numbers (the limits) are scale-bound; numbers inside the
    bounded expression keep their normal behavioral/classifier label."""
    code = strip_comments_and_strings(code)
    rows, oid = [], 0
    for name, body in proc_iter(code):
        is_outcome = bool(OUTCOME.match(name))
        for line in body.splitlines():
            ms = list(NUM.finditer(line))
            if not ms:
                continue
            bound_idx = set()
            if BOUND.search(line) and len(ms) >= 2:
                bound_idx = {len(ms) - 1, len(ms) - 2}   # the two limits
            for k, m in enumerate(ms):
                if DIV0_GUARD.search(line) and m.group(0) in {"1", "1.0"}:
                    b = "inert"
                elif DISPLAY.search(line):
                    b = "display"
                elif k in bound_idx or SCALEOTHER.search(line):
                    b = "scale-bound"
                elif INERT.search(line):
                    b = "inert"
                elif is_outcome:
                    b = "classifier"
                else:
                    b = "behavioral"
                oid += 1
                rows.append({"occurrence_id": oid, "value": m.group(0),
                             "bin": b, "procedure": name,
                             "local_role": local_role(name, line),
                             "context": line.strip()[:160]})
    return rows

# --------------------------------------------------------------------------- #
CONSEQUENTIAL = {"behavioral", "classifier"}

def dedup_consequential(rows):
    seen, out = set(), []
    for r in rows:
        if r["bin"] not in CONSEQUENTIAL:
            continue
        key = (r["bin"], r["value"])
        if key not in seen:
            seen.add(key); out.append(r)
    return out

def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("--out", default=".")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    code, widgets = read_model(a.model)
    glob = declared_globals(code); nproc = count_procedures(code)
    rows = scan(code); dedup = dedup_consequential(rows)
    b = Counter(r["bin"] for r in rows)
    n_beh = len({r["value"] for r in dedup if r["bin"] == "behavioral"})
    n_cls = len({r["value"] for r in dedup if r["bin"] == "classifier"})
    flds = ["occurrence_id", "value", "bin", "procedure", "local_role", "context"]
    write_csv(os.path.join(a.out, "literals_raw.csv"), rows, flds)
    write_csv(os.path.join(a.out, "literals_dedup.csv"), dedup, flds)
    write_csv(os.path.join(a.out, "globals.csv"), [{"global": g} for g in glob], ["global"])
    write_csv(os.path.join(a.out, "widgets.csv"), [{"widget": w} for w in widgets], ["widget"])
    summary = [("interface controls", len(widgets)), ("declared globals", len(glob)),
               ("procedures", nproc), ("literal occurrences (total)", len(rows)),
               ("behavioral occurrences", b["behavioral"]),
               ("classifier occurrences", b["classifier"]),
               ("scale-bound occurrences", b["scale-bound"]),
               ("inert occurrences", b["inert"]),
               ("display occurrences", b["display"]),
               ("consequential occurrences", b["behavioral"] + b["classifier"]),
               ("distinct behavioral entries", n_beh),
               ("distinct classifier entries", n_cls),
               ("distinct consequential numeric values", n_beh + n_cls)]
    write_csv(os.path.join(a.out, "scan_summary.csv"),
              [{"quantity": q, "count": c} for q, c in summary], ["quantity", "count"])
    print("Scan complete:")
    for q, c in summary:
        print(f"  {q:<32} {c}")
    print(f"Outputs in {os.path.abspath(a.out)}")

if __name__ == "__main__":
    sys.exit(main())
