#!/usr/bin/env python3
"""Convert KNOWABILITY.md -> a two-column IEEEtran submission .tex (tectonic-buildable)."""

import re, sys

SRC = "/Users/rohanvinaik/tools/Detective/docs/theory/operator_completeness/KNOWABILITY.md"
OUT = "/Users/rohanvinaik/tools/Detective/docs/theory/operator_completeness/submission/knowability_ieee.tex"

raw = open(SRC).read().splitlines()

# ---- strip YAML frontmatter ----
if raw[0].strip() == "---":
    end = next(i for i in range(1, len(raw)) if raw[i].strip() == "---")
    raw = raw[end + 1 :]

# ---- citation phrases -> \cite (longest first); applied to text spans only ----
CITES = [
    ("Kaminski, Ammann & Offutt", r"\cite{kaminski}"),
    ("Vera-Pérez et al. (2018", r"\cite{veraperez2018} ("),  # keeps a following ", Descartes)"
    ("Vera-Pérez et al. 2018", r"\cite{veraperez2018}"),
    ("Niedermayr et al. (2016)", r"\cite{niedermayr2016}"),
    ("Niedermayr et al. 2016", r"\cite{niedermayr2016}"),
    ("Goldman & Kearns (1995)", r"\cite{goldman1995}"),
    ("DeMillo et al. 1978", r"\cite{demillo1978}"),
    ("Offutt et al. 1996", r"\cite{offutt1996}"),
    ("Ammann et al. 2014", r"\cite{ammann2014}"),
    ("Kurtz et al. 2015", r"\cite{kurtz2015}"),
    ("Budd & Angluin 1982", r"\cite{budd1982}"),
    ("Alshahwan & Harman", r"\cite{alshahwan}"),
    ("Schuler & Zeller", r"\cite{schuler}"),
    ("Just et al.", r"\cite{just2014}"),
    ("Wah's", r"Wah's~\cite{wah}"),
]

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


def inline_text(s):
    for phrase, rep in CITES:
        s = s.replace(phrase, rep)
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\\emph{\1}", s)
    s = re.sub(r"`([^`]+)`", r"\\texttt{\1}", s)
    return s


def process_inline(line):
    # mask math spans so text transforms (bold/emph that may SPAN a math span) don't corrupt them
    math = []

    def _mask(m):
        math.append(m.group(0))
        return "\x00%d\x00" % (len(math) - 1)

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
    l = raw[i]
    if l.startswith("# "):
        title = l[2:].strip()
    elif l.startswith("## ") and not re.match(r"## \d", l) and not title == "" and subtitle == "":
        subtitle = l[3:].strip()
    elif l.strip() == "### Abstract":
        i += 1
        while i < len(raw) and not raw[i].startswith("## "):
            if raw[i].strip() and raw[i].strip() != "---":
                abstract.append(raw[i])
            i += 1
        break
    i += 1
abstract_tex = process_inline(" ".join(a.strip() for a in abstract))

# ---- body: from first "## 1." onward ----
start = next(i for i, l in enumerate(raw) if re.match(r"## 1\.", l))
body = raw[start:]

out = []
n = len(body)
i = 0


def flush_para(buf):
    if buf:
        out.append(process_inline(" ".join(x.strip() for x in buf)))
        out.append("")
        buf.clear()


para = []
while i < n:
    l = body[i]
    s = l.rstrip()

    # headings
    m = re.match(r"^##\s+(\d+)\.\s+(.*)$", s)
    if m:
        flush_para(para)
        out.append(r"\section{%s}" % process_inline(m.group(2)))
        i += 1
        continue
    m = re.match(r"^###\s+([0-9.]+)\s+(.*)$", s)
    if m:
        flush_para(para)
        out.append(r"\subsection{%s}" % process_inline(m.group(2)))
        i += 1
        continue

    # theorem-like (with title)
    m = THM_RE.match(s)
    mnt = THM_NT_RE.match(s) if not m else None
    if m or mnt:
        flush_para(para)
        if m:
            kind, num, ttl, rest = m.group(1), m.group(2), m.group(3), m.group(4)
            head = "%s (%s)" % (num, ttl)
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
        content = process_inline(" ".join(x.strip() for x in buf))
        out.append(r"\begin{%s}[%s]" % (env, uni_only(head)))
        out.append(content)
        out.append(r"\end{%s}" % env)
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
        out.append(r"\begin{table*}[!t]\centering\footnotesize")
        out.append(r"\caption{Mechanization ledger: paper results and their Lean names.}")
        out.append(r"\label{tab:mech}")
        out.append(r"\begin{tabular}{%s}" % ("l" * ncol))
        out.append(r"\toprule")
        for ri, r in enumerate(rows):
            r = r + [""] * (ncol - len(r))
            out.append(" & ".join(process_inline(c) for c in r) + r" \\")
            if ri == 0:
                out.append(r"\midrule")
        out.append(r"\bottomrule")
        out.append(r"\end{tabular}")
        out.append(r"\end{table*}")
        out.append("")
        continue

    # numbered list
    if re.match(r"^\d+\.\s", s.lstrip()):
        flush_para(para)
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
        for it in items:
            out.append(r"\item " + process_inline(it.strip()))
        out.append(r"\end{enumerate}")
        out.append("")
        continue

    # bullet list
    if re.match(r"^-\s", s.lstrip()):
        flush_para(para)
        items = []
        while i < n and re.match(r"^-\s", body[i].lstrip()):
            items.append(re.sub(r"^\s*-\s", "", body[i]))
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

# ---- harvest bibliography from paper_lncs.tex + add 4 review-added entries ----
lncs = open(
    "/Users/rohanvinaik/tools/Detective/docs/theory/operator_completeness/submission/paper_lncs.tex"
).read()
bib = lncs[lncs.index(r"\begin{thebibliography}") : lncs.index(r"\end{thebibliography}")]
extra = r"""
\bibitem{kaminski}
Kaminski, G., Ammann, P., Offutt, J.: Improving logic-based testing. Journal of Systems and Software 86(8), 2002--2012 (2013)

\bibitem{wah}
Wah, K.S.H.T.: An analysis of the coupling effect I: single test data. Science of Computer Programming 48(2--3), 119--161 (2003)

\bibitem{alshahwan}
Alshahwan, N., Harman, M.: Coverage and fault detection of the output-uniqueness test selection criteria. In: ISSTA 2014, pp. 181--192 (2014)

\bibitem{schuler}
Schuler, D., Zeller, A.: Checked coverage: an indicator for test quality. Software Testing, Verification and Reliability 23(7), 531--551 (2013)
"""
bib = bib + extra + "\n"

PREAMBLE = r"""\documentclass[conference]{IEEEtran}
\usepackage{amsmath,amssymb}
\usepackage{amsthm}
\usepackage{booktabs}
\usepackage{placeins}
\usepackage[hidelinks]{hyperref}
\usepackage{xcolor}

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
print("wrote", OUT, "(%d lines)" % doc.count("\n"))
