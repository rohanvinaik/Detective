#!/usr/bin/env python3
"""Convert KNOWABILITY.md -> a two-column IEEEtran submission .tex (tectonic-buildable)."""

import re

SRC = "/Users/rohanvinaik/tools/Detective/docs/theory/operator_completeness/KNOWABILITY.md"
OUT = "/Users/rohanvinaik/tools/Detective/docs/theory/operator_completeness/submission/knowability_ieee.tex"

raw = open(SRC).read().splitlines()

# ---- strip YAML frontmatter ----
if raw[0].strip() == "---":
    end = next(i for i in range(1, len(raw)) if raw[i].strip() == "---")
    raw = raw[end + 1 :]

# ---- citation phrases -> \cite (longest first); applied to text spans only ----
# Every author-year phrase renders as the authors' names followed by the numbered citation, in prose,
# parentheses and tables alike. collapse_cites() handles any bare \cite left inside parentheses.
CITES = [
    ("Kaminski, Ammann & Offutt 2013", r"Kaminski, Ammann and Offutt~\cite{kaminski2013}"),
    ("DeMillo, Lipton & Sayward 1978", r"DeMillo, Lipton and Sayward~\cite{demillo1978}"),
    ("Vera-Pérez et al. (2019)", r"Vera-P\'{e}rez et al.~\cite{veraperez2019}"),
    ("Vera-Pérez et al. 2018", r"Vera-P\'{e}rez et al.~\cite{descartes2018}"),
    ("Niedermayr et al. (2016)", r"Niedermayr et al.~\cite{niedermayr2016}"),
    ("Goldman & Kearns (1995)", r"Goldman and Kearns~\cite{goldman1995}"),
    ("Goldman & Kearns 1995", r"Goldman and Kearns~\cite{goldman1995}"),
    ("de Moura & Ullrich 2021", r"de Moura and Ullrich~\cite{lean4}"),
    ("mathlib Community 2020", r"the mathlib Community~\cite{mathlib}"),
    ("Shin & Bae (2016)", r"Shin and Bae~\cite{shin2016}"),
    ("Shin & Bae 2016", r"Shin and Bae~\cite{shin2016}"),
    ("Offutt et al. (1996)", r"Offutt et al.~\cite{offutt1996}"),
    ("Offutt et al. 1996", r"Offutt et al.~\cite{offutt1996}"),
    ("Ammann et al. 2014", r"Ammann et al.~\cite{ammann2014}"),
    ("Kurtz et al. 2015", r"Kurtz et al.~\cite{kurtz2015}"),
    ("Budd & Angluin 1982", r"Budd and Angluin~\cite{budd1982}"),
    ("Alshahwan & Harman 2014", r"Alshahwan and Harman~\cite{alshahwan2014}"),
    ("Schuler & Zeller", r"Schuler and Zeller~\cite{schuler2013}"),
    ("Just et al. 2012", r"Just et al.~\cite{just2012}"),
    ("Howden 1982", r"Howden~\cite{howden1982}"),
    ("Presburger 1929", r"Presburger~\cite{presburger1929}"),
    ("Wah's", r"Wah's~\cite{wah2003}"),
]


def collapse_cites(s):
    """Drop parentheses around bare citations.

    '(\\cite{a})' -> '~\\cite{a}', and '(\\cite{a}; \\cite{b})' -> '~\\cite{a,b}'.
    """

    def _merge(m):
        keys = re.findall(r"\\cite\{([^}]+)\}", m.group(1))
        return r"~\cite{" + ",".join(keys) + "}"

    s = re.sub(r"\s*\(((?:\\cite\{[^}]+\}(?:;\s*)?)+)\)", _merge, s)
    return s


def smart_quotes(s):
    """Straight double quotes in prose -> TeX quotes. Code spans are masked by the caller."""
    return re.sub(r'"([^"]+)"', r"``\1''", s)


# ---- bare unicode -> LaTeX (mode-safe via \ensuremath) ; applied to whole line last ----
UNI = [
    ("–", "--"),
    ("—", "---"),
    ("§", r"\S "),
    ("é", r"\'{e}"),
    ("ω", r"\ensuremath{\omega}"),
    ("Π", r"\ensuremath{\Pi}"),
    ("∩", r"\ensuremath{\cap}"),
    ("≠", r"\ensuremath{\neq}"),
    ("≡", r"\ensuremath{\equiv}"),
    ("→", r"\ensuremath{\to}"),
    ("↔", r"\ensuremath{\leftrightarrow}"),
    ("⊆", r"\ensuremath{\subseteq}"),
    ("∅", r"\ensuremath{\varnothing}"),
    ("∀", r"\ensuremath{\forall}"),
    ("∃", r"\ensuremath{\exists}"),
    ("≤", r"\ensuremath{\le}"),
    ("≥", r"\ensuremath{\ge}"),
    ("×", r"\ensuremath{\times}"),
    ("γ", r"\ensuremath{\gamma}"),
    ("Γ", r"\ensuremath{\Gamma}"),
    ("μ", r"\ensuremath{\mu}"),
    ("σ", r"\ensuremath{\sigma}"),
    ("∈", r"\ensuremath{\in}"),
    ("∖", r"\ensuremath{\setminus}"),
    ("∪", r"\ensuremath{\cup}"),
    ("⟺", r"\ensuremath{\iff}"),
    ("“", "``"),
    ("”", "''"),
    ("‘", "`"),
    ("’", "'"),
    ("…", r"\ldots{}"),
]

# first header cell -> (float environment, caption, label)
TABLES = {
    "Work": (
        "table*",
        "Prior results compared on four questions.",
        "tab:compare",
        r"L{2.9cm}L{3.9cm}L{3.2cm}L{3.0cm}L{2.8cm}",
    ),
    "Library": (
        "table",
        r"Covered functions pseudo-tested under the uniform constant mutation, by oracle (\S 9.5). "
        r"Parenthesized: the subset whose constant preserves the return type.",
        "tab:pseudo",
        r"lL{1.3cm}L{1.6cm}L{1.9cm}",
    ),
    "Paper": (
        "table*",
        "Theorem ledger: how each claim is established.",
        "tab:ledger",
        r"L{1.9cm}L{5.4cm}L{1.7cm}L{6.9cm}",
    ),
}

ENVMAP = {
    "Definition": "definition",
    "Theorem": "theorem",
    "Proposition": "proposition",
    "Corollary": "corollary",
    "Remark": "remark",
    "Example": "example",
    "Lemma": "lemma",
}

THM_RE = re.compile(r"^\*\*(" + "|".join(ENVMAP) + r") ([0-9][0-9A-Za-z.]*) \(([^)]*)\)\.\*\* ?(.*)$")
THM_NT_RE = re.compile(r"^\*\*(" + "|".join(ENVMAP) + r") ([0-9][0-9A-Za-z.]*)\.\*\* ?(.*)$")


def esc(s):
    # escape LaTeX specials that appear as literal text (not our own markup)
    s = s.replace("\\%", "\x00PCT\x00")  # not expected; guard
    s = re.sub(r"(?<!\\)%", r"\\%", s)
    s = re.sub(r"(?<!\\)&", r"\\&", s)
    s = re.sub(r"(?<!\\)#", r"\\#", s)
    s = s.replace("_", r"\_")
    s = s.replace("\x00PCT\x00", "\\%")
    return s


def esc_code(s):
    """Escape a code span for \\texttt: LaTeX specials, plus braces, which would vanish as a group."""
    return esc(s).replace("{", r"\{").replace("}", r"\}")


def inline_text(s):
    # mask code spans first, so quotes and citation phrases inside them stay literal
    code = []

    def _cmask(m):
        code.append(m.group(1))
        return f"\x01{len(code) - 1}\x01"

    s = re.sub(r"`([^`]+)`", _cmask, s)
    for phrase, rep in CITES:
        s = s.replace(phrase, rep)
    s = collapse_cites(s)
    s = smart_quotes(s)
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\\emph{\1}", s)
    s = re.sub("\x01(\\d+)\x01", lambda m: r"\texttt{" + esc_code(code[int(m.group(1))]) + "}", s)
    return s


def process_inline(line):
    # mask math spans so text transforms (bold/emph that may SPAN a math span) don't corrupt them
    math = []

    def _mask(m):
        math.append(m.group(0))
        return f"\x00{len(math) - 1}\x00"

    masked = re.sub(r"\$\$.+?\$\$|\$[^$]*\$", _mask, line)
    masked = inline_text(masked)
    for u, r in UNI:
        masked = masked.replace(u, r)

    def _unmask(m):
        seg = math[int(m.group(1))]
        if seg.startswith("$$"):
            return r"\[" + uni_only(seg[2:-2]) + r"\]"
        return uni_only(seg)

    return re.sub("\x00(\\d+)\x00", _unmask, masked)


def uni_only(line):
    for u, r in UNI:
        line = line.replace(u, r)
    return line


# ---- title / subtitle / abstract ----
title = subtitle = ""
abstract = []
i = 0
while i < len(raw):
    ln = raw[i]
    if ln.startswith("# "):
        title = ln[2:].strip()
    elif ln.startswith("## ") and not re.match(r"## \d", ln) and not title == "" and subtitle == "":
        subtitle = ln[3:].strip()
    elif ln.strip() == "### Abstract":
        i += 1
        while i < len(raw) and not raw[i].startswith("## "):
            if raw[i].strip() and raw[i].strip() != "---":
                abstract.append(raw[i])
            i += 1
        break
    i += 1
abstract_tex = process_inline(" ".join(a.strip() for a in abstract))

# ---- body: from first "## 1." onward ----
start = next(i for i, ln in enumerate(raw) if re.match(r"## 1\.", ln))
body = raw[start:]

out = []
n = len(body)
i = 0


def render_with_lists(lines):
    """Render a theorem body, turning embedded '1. ...' items (with indented continuations) into enumerate."""
    parts, text, items = [], [], []
    for ln in lines:
        if re.match(r"^\s*\d+\.\s", ln):
            if text:
                parts.append(process_inline(" ".join(x.strip() for x in text)))
                text = []
            items.append(re.sub(r"^\s*\d+\.\s", "", ln))
        elif items and ln.startswith("   ") and ln.strip():
            items[-1] += " " + ln.strip()
        else:
            if items:
                parts.append(enumerate_tex(items))
                items = []
            text.append(ln)
    if items:
        parts.append(enumerate_tex(items))
    if text:
        parts.append(process_inline(" ".join(x.strip() for x in text)))
    return "\n".join(parts)


def enumerate_tex(items):
    return "\n".join(
        [r"\begin{enumerate}"]
        + [r"\item " + process_inline(it.strip()) for it in items]
        + [r"\end{enumerate}"]
    )


def flush_para(buf):
    if buf:
        out.append(process_inline(" ".join(x.strip() for x in buf)))
        out.append("")
        buf.clear()


para = []
in_appendix = False
while i < n:
    ln = body[i]
    s = ln.rstrip()

    # headings
    # Section numbers are taken from the source headings, so the rendered numbers match the paper's own
    # cross-references (§9, Theorem 3.2, "### 9.5") rather than being renumbered by LaTeX.
    m = re.match(r"^##\s++(\d++)\.\s++(\S.*)$", s)
    if m:
        flush_para(para)
        out.append(r"\setcounter{section}{" + str(int(m.group(1)) - 1) + "}")
        out.append(r"\section{" + process_inline(m.group(2)) + "}")
        i += 1
        continue
    m = re.match(r"^##\s++Appendix\s++([A-Z])\.\s++(\S.*)$", s)
    if m:
        flush_para(para)
        if not in_appendix:
            out.append(r"\appendices")  # IEEEtran: headings "Appendix A: <title>"
            in_appendix = True
        out.append(r"\setcounter{section}{" + str(ord(m.group(1)) - ord("A")) + "}")
        out.append(r"\section{" + process_inline(m.group(2)) + "}")
        i += 1
        continue
    m = re.match(r"^###\s++(\d++)\.(\d++)\s++(\S.*)$", s)
    if m:
        flush_para(para)
        out.append(r"\setcounter{subsection}{" + str(int(m.group(2)) - 1) + "}")
        out.append(r"\subsection{" + process_inline(m.group(3)) + "}")
        i += 1
        continue

    # theorem-like (with title)
    m = THM_RE.match(s)
    mnt = THM_NT_RE.match(s) if not m else None
    if m or mnt:
        flush_para(para)
        if m:
            kind, num, ttl, rest = m.group(1), m.group(2), m.group(3), m.group(4)
            head = f"{num} ({ttl})"
        else:
            kind, num, rest = mnt.group(1), mnt.group(2), mnt.group(3)
            head = num
        env = ENVMAP[kind]
        # gather until blank line
        buf = [rest] if rest else []
        i += 1
        while i < n and body[i].strip() != "":
            buf.append(body[i])
            i += 1
        out.append(r"\begin{" + env + "}[" + uni_only(head) + "]")
        out.append(render_with_lists(buf))
        out.append(r"\end{" + env + "}")
        out.append("")
        continue

    # proof — gather until $\qed$ (a proof may span several paragraphs, e.g. the (<=)/(=>) halves);
    # preserve internal blank lines as paragraph breaks so the qed box lands only at the very end.
    if s.lstrip().startswith("*Proof.*"):
        flush_para(para)
        plines = [re.sub(r"^\s*\*Proof\.\*\s*", "", s)]
        done = "$\\qed$" in plines[0]
        i += 1
        while i < n and not done:
            nxt = body[i]
            if re.match(
                r"^(##\s|\*\*(Definition|Theorem|Proposition|Corollary|Remark|Example|Lemma)\s)", nxt.lstrip()
            ):
                break
            plines.append(nxt)
            if "$\\qed$" in nxt:
                done = True
            i += 1
        text = "\n".join(plines).replace("$\\qed$", "")
        paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        out.append(r"\begin{proof}")
        out.append("\n\n".join(process_inline(" ".join(p.split())) for p in paras))
        out.append(r"\end{proof}")
        out.append("")
        continue

    # display math $$ ... $$  (may be one line or span)
    if s.strip().startswith("$$"):
        flush_para(para)
        # collect until closing $$ (inclusive), could be same line
        block = s.strip()
        if block.count("$$") >= 2:
            inner = block[2 : block.rfind("$$")]
            out.append(r"\[" + uni_only(inner) + r"\]")
            out.append("")
            i += 1
            continue
        buf = [block[2:]]
        i += 1
        while i < n and "$$" not in body[i]:
            buf.append(body[i])
            i += 1
        if i < n:
            tail = body[i]
            buf.append(tail[: tail.find("$$")])
            i += 1
        out.append(r"\[" + uni_only(" ".join(buf)) + r"\]")
        out.append("")
        continue

    # table
    if s.lstrip().startswith("|"):
        flush_para(para)
        tbl = []
        while i < n and body[i].lstrip().startswith("|"):
            tbl.append(body[i].strip())
            i += 1
        # parse
        rows = []
        for r in tbl:
            if re.match(r"^\|[\s:|-]+\|?$", r):  # separator
                continue
            cells = [c.strip() for c in r.strip().strip("|").split("|")]
            rows.append(cells)
        ncol = max(len(r) for r in rows)
        # each table gets its own caption, keyed by its first header cell
        spec = TABLES.get(rows[0][0])
        if spec is None:
            raise SystemExit(f"no caption registered for table with header {rows[0]!r}")
        env, caption, label, colspec = spec
        out.append(r"\begin{" + env + r"}[!t]\centering\footnotesize")
        out.append(r"\caption{" + caption + "}")
        out.append(r"\label{" + label + "}")
        out.append(r"\begin{tabular}{" + colspec + "}")
        out.append(r"\toprule")
        for ri, r in enumerate(rows):
            r = r + [""] * (ncol - len(r))
            out.append(" & ".join(process_inline(c) for c in r) + r" \\")
            if ri == 0:
                out.append(r"\midrule")
        out.append(r"\bottomrule")
        out.append(r"\end{tabular}")
        out.append(r"\end{" + env + "}")
        out.append("")
        continue

    # numbered list
    if re.match(r"^\d+\.\s", s.lstrip()):
        flush_para(para)
        first_number = int(re.match(r"^\s*(\d+)\.", s).group(1))
        items = []
        while i < n and (
            re.match(r"^\d+\.\s", body[i].lstrip())
            or (items and body[i].startswith("   ") and body[i].strip())
        ):
            if re.match(r"^\d+\.\s", body[i].lstrip()):
                items.append(re.sub(r"^\s*\d+\.\s", "", body[i]))
            else:
                items[-1] += " " + body[i].strip()
            i += 1
        out.append(r"\begin{enumerate}")
        if first_number > 1:  # a list resumed after intervening text keeps the source numbering
            out.append(r"\setcounter{enumi}{" + str(first_number - 1) + "}")
        for it in items:
            out.append(r"\item " + process_inline(it.strip()))
        out.append(r"\end{enumerate}")
        out.append("")
        continue

    # bullet list
    if re.match(r"^-\s", s.lstrip()):
        flush_para(para)
        items = []
        # an indented, non-bullet line continues the preceding item (as in the numbered list)
        while i < n and (
            re.match(r"^-\s", body[i].lstrip()) or (items and body[i].startswith("  ") and body[i].strip())
        ):
            if re.match(r"^-\s", body[i].lstrip()):
                items.append(re.sub(r"^\s*-\s", "", body[i]))
            else:
                items[-1] += " " + body[i].strip()
            i += 1
        out.append(r"\begin{itemize}")
        for it in items:
            out.append(r"\item " + process_inline(it.strip()))
        out.append(r"\end{itemize}")
        out.append("")
        continue

    # horizontal rule / blank
    if s.strip() in ("---", ""):
        flush_para(para)
        i += 1
        continue

    # normal paragraph line
    para.append(s)
    i += 1

flush_para(para)
body_tex = "\n".join(out)

# ---- bibliography: every entry is cited in KNOWABILITY.md; sorted by first author ----
BIB_ENTRIES = [
    (
        "alshahwan2014",
        r"Alshahwan, N., Harman, M.: Coverage and fault detection of the output-uniqueness test "
        r"selection criteria. In: ISSTA, pp. 181--192 (2014). "
        r"doi:10.1145/2610384.2610413",
    ),
    (
        "ammann2014",
        r"Ammann, P., Delamaro, M.E., Offutt, J.: Establishing theoretical minimal sets of mutants. "
        r"In: ICST, pp. 21--30 (2014). doi:10.1109/ICST.2014.13",
    ),
    (
        "budd1982",
        r"Budd, T.A., Angluin, D.: Two notions of correctness and their relation to testing. "
        r"Acta Informatica \textbf{18}(1), 31--45 (1982). doi:10.1007/BF00625279",
    ),
    (
        "demillo1978",
        r"DeMillo, R.A., Lipton, R.J., Sayward, F.G.: Hints on test data selection: help for the "
        r"practicing programmer. IEEE Computer \textbf{11}(4), 34--41 (1978). doi:10.1109/C-M.1978.218136",
    ),
    (
        "lean4",
        r"de Moura, L., Ullrich, S.: The Lean 4 theorem prover and programming language. In: CADE, "
        r"LNCS 12699, pp. 625--635 (2021). doi:10.1007/978-3-030-79876-5\_37",
    ),
    (
        "goldman1995",
        r"Goldman, S.A., Kearns, M.J.: On the complexity of teaching. J. Comput. Syst. Sci. "
        r"\textbf{50}(1), 20--31 (1995). doi:10.1006/jcss.1995.1003",
    ),
    (
        "howden1982",
        r"Howden, W.E.: Weak mutation testing and completeness of test sets. IEEE Trans. Softw. Eng. "
        r"\textbf{SE-8}(4), 371--379 (1982). doi:10.1109/TSE.1982.235571",
    ),
    (
        "just2012",
        r"Just, R., Kapfhammer, G.M., Schweiggert, F.: Do redundant mutants affect the effectiveness "
        r"and efficiency of mutation analysis? In: ICST, pp. 720--725 (2012). doi:10.1109/ICST.2012.162",
    ),
    (
        "kaminski2013",
        r"Kaminski, G., Ammann, P., Offutt, J.: Improving logic-based testing. J. Syst. Softw. "
        r"\textbf{86}(8), 2002--2012 (2013). doi:10.1016/j.jss.2012.08.024",
    ),
    (
        "kurtz2015",
        r"Kurtz, B., Ammann, P., Offutt, J.: Static analysis of mutant subsumption. In: ICST "
        r"Workshops (Mutation), pp. 1--10 (2015). doi:10.1109/ICSTW.2015.7107454",
    ),
    (
        "mathlib",
        r"The mathlib Community: The Lean mathematical library. In: CPP, pp. 367--381 (2020). "
        r"doi:10.1145/3372885.3373824",
    ),
    (
        "niedermayr2016",
        r"Niedermayr, R., Juergens, E., Wagner, S.: Will my tests tell me if I break this code? "
        r"In: CSED@ICSE, pp. 23--29 (2016). doi:10.1145/2896941.2896944",
    ),
    (
        "offutt1996",
        r"Offutt, A.J., Lee, A., Rothermel, G., Untch, R.H., Zapf, C.: An experimental determination "
        r"of sufficient mutant operators. ACM Trans. Softw. Eng. Methodol. \textbf{5}(2), 99--118 (1996). "
        r"doi:10.1145/227607.227610",
    ),
    (
        "presburger1929",
        r"Presburger, M.: \"{U}ber die Vollst\"{a}ndigkeit eines gewissen Systems der Arithmetik "
        r"ganzer Zahlen, in welchem die Addition als einzige Operation hervortritt. In: Comptes Rendus du I "
        r"Congr\`{e}s de Math\'{e}maticiens des Pays Slaves, pp. 92--101. Warsaw (1929)",
    ),
    (
        "schuler2013",
        r"Schuler, D., Zeller, A.: Checked coverage: an indicator for oracle quality. Softw. Test. "
        r"Verif. Reliab. \textbf{23}(7), 531--551 (2013). doi:10.1002/stvr.1497",
    ),
    (
        "shin2016",
        r"Shin, D., Bae, D.H.: A theoretical framework for understanding mutation-based testing "
        r"methods. In: ICST, pp. 299--308 (2016). doi:10.1109/ICST.2016.22",
    ),
    (
        "descartes2018",
        r"Vera-P\'{e}rez, O.L., Monperrus, M., Baudry, B.: Descartes: a PITest engine to detect "
        r"pseudo-tested methods (tool demonstration). In: ASE, pp. 908--911 (2018). "
        r"doi:10.1145/3238147.3240474",
    ),
    (
        "veraperez2019",
        r"Vera-P\'{e}rez, O.L., Danglot, B., Monperrus, M., Baudry, B.: A comprehensive study of "
        r"pseudo-tested methods. Empir. Softw. Eng. \textbf{24}(3), 1195--1225 (2019). "
        r"doi:10.1007/s10664-018-9653-2",
    ),
    (
        "wah2003",
        r"Wah, K.S.H.T.: An analysis of the coupling effect I: single test data. Sci. Comput. Program. "
        r"\textbf{48}(2--3), 119--161 (2003). doi:10.1016/S0167-6423(03)00022-4",
    ),
]
bib = (
    "\\begin{thebibliography}{99}\n\n"
    + "\n\n".join("\\bibitem{" + key + "}\n" + text for key, text in BIB_ENTRIES)
    + "\n\n"
)

# every cited key must have an entry, and every entry must be cited
_cited = {k for grp in re.findall(r"\\cite\{([^}]+)\}", body_tex) for k in grp.split(",")}
_listed = {key for key, _ in BIB_ENTRIES}
if _cited != _listed:
    raise SystemExit(
        f"citation mismatch: cited-not-listed={sorted(_cited - _listed)} "
        f"listed-not-cited={sorted(_listed - _cited)}"
    )

PREAMBLE = r"""\documentclass[conference]{IEEEtran}
\usepackage{amsmath,amssymb}
\usepackage{amsthm}
\usepackage{booktabs}
\usepackage{array}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\usepackage{cite}
\usepackage{placeins}
\usepackage[hidelinks]{hyperref}
\usepackage{xcolor}
%% Tectonic runs XeTeX, which has no TU-encoded Times (ptm): without this, LaTeX silently falls back
%% to an upright regular face and every bold, italic and typewriter span renders as plain roman.
\usepackage{fontspec}
\setmainfont{texgyretermes}[Extension=.otf, UprightFont=*-regular, BoldFont=*-bold,
  ItalicFont=*-italic, BoldItalicFont=*-bolditalic]
\setmonofont{lmmono10-regular.otf}[BoldFont=lmmonolt10-bold.otf]

%% arabic section numbers, so the headings match the paper's own references (\S 3, Theorem 3.2)
\renewcommand{\thesection}{\arabic{section}}
\renewcommand{\thesubsection}{\thesection.\arabic{subsection}}
\renewcommand{\thesectiondis}{\thesection.}
\renewcommand{\thesubsectiondis}{\thesubsection}

\newcommand{\Mov}{\mathrm{Mov}}
\newcommand{\Det}{\mathrm{Det}}
\newcommand{\DetW}{\mathrm{Det}_{\omega}}
\newcommand{\Foot}{\mathrm{Foot}}
\newcommand{\score}{\mathrm{score}}
\newcommand{\TR}{\mathcal{T}(R)}
\providecommand{\qed}{}

\newtheoremstyle{run}{\topsep}{\topsep}{}{}{\bfseries}{.}{ }{\thmname{#1}\thmnote{ #3}}
\theoremstyle{run}
\newtheorem*{definition}{Definition}
\newtheorem*{theorem}{Theorem}
\newtheorem*{proposition}{Proposition}
\newtheorem*{corollary}{Corollary}
\newtheorem*{lemma}{Lemma}
\newtheorem*{remark}{Remark}
\newtheorem*{example}{Example}

\begin{document}
\title{%(title)s}
\author{\IEEEauthorblockN{Anonymous Author(s)}\IEEEauthorblockA{Affiliation}}
\maketitle
\begin{abstract}
%(abstract)s
\end{abstract}
\begin{IEEEkeywords}
Mutation testing, test adequacy, operator completeness, extreme mutation, interactive theorem proving.
\end{IEEEkeywords}

"""

doc = PREAMBLE % {"title": uni_only(esc(title)), "abstract": abstract_tex}
doc += body_tex
doc += "\n\n" + r"\FloatBarrier" + "\n\n" + bib + r"\end{thebibliography}" + "\n\\end{document}\n"

open(OUT, "w").write(doc)
n_lines = doc.count("\n")
print("wrote", OUT, f"({n_lines} lines)")
