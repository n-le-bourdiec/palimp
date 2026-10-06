"""Generate the three README diagrams for palimp, light and dark variants."""
from html import escape

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

THEMES = {
    "light": dict(
        text="#1f2328", muted="#59636e", box="#f6f8fa", stroke="#d1d9e0",
        accent="#0969da", accent_bg="#ddf4ff", line="#59636e", frame="#8c959f",
        warn_bg="#fff8c5", warn="#9a6700",
    ),
    "dark": dict(
        text="#e6edf3", muted="#9198a1", box="#151b23", stroke="#3d444d",
        accent="#4493f8", accent_bg="#0d2d55", line="#9198a1", frame="#656c76",
        warn_bg="#272115", warn="#d29922",
    ),
}


class SVG:
    def __init__(self, w, h, t, title):
        self.w, self.h, self.t, self.parts = w, h, t, []
        self.title = title

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill=None, stroke=None, dash=False, rx=10, sw=1.2):
        t = self.t
        d = ' stroke-dasharray="6 4"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                 f'fill="{fill or t["box"]}" stroke="{stroke or t["stroke"]}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=12.5, weight=400, color=None, anchor="start"):
        c = color or self.t["text"]
        self.add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
                 f'fill="{c}" text-anchor="{anchor}">{escape(s)}</text>')

    def lines(self, x, y, items, size=12, color=None, gap=16, anchor="start", weight=400):
        for i, s in enumerate(items):
            self.text(x, y + i * gap, s, size=size, color=color, anchor=anchor, weight=weight)

    def arrow(self, pts, color=None, dash=False, label=None, lx=None, ly=None, lanchor="middle"):
        c = color or self.t["line"]
        d = ' stroke-dasharray="5 4"' if dash else ""
        p = " ".join(f"{a},{b}" for a, b in pts)
        mid = "acc" if color == self.t["accent"] else "def"
        self.add(f'<polyline points="{p}" fill="none" stroke="{c}" stroke-width="1.5"{d} '
                 f'marker-end="url(#ah-{mid})"/>')
        if label:
            self.text(lx, ly, label, size=11.5, color=self.t["muted"], anchor=lanchor)

    def render(self):
        t = self.t
        defs = (
            '<defs>'
            f'<marker id="ah-def" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{t["line"]}"/></marker>'
            f'<marker id="ah-acc" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{t["accent"]}"/></marker>'
            '</defs>'
        )
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'width="{self.w}" height="{self.h}" font-family="{FONT}" role="img" aria-label="{escape(self.title)}">'
                f'<title>{escape(self.title)}</title>{defs}' + "".join(self.parts) + "</svg>")


def how_it_works(t):
    s = SVG(1180, 560, t, "How palimp works: inherited firewall artifacts go through format readers, "
            "evidence collectors and an assessment, and come out as a report, owner questionnaires "
            "and a cleanup list, all on your machine.")
    # frame
    s.rect(16, 16, 1148, 528, fill="none", stroke=t["frame"], dash=True, rx=16)
    s.text(36, 44, "Runs on your machine  ·  read-only  ·  zero network egress", size=13, weight=600, color=t["muted"])

    # inputs
    s.text(44, 92, "Inherited artifacts", size=14, weight=600)
    inputs = ["Junos config (set format)", "Commit history + rollbacks", "Session logs (RT_FLOW)",
              "Hit counts", "Tickets export (CSV, optional)"]
    ys = []
    for i, name in enumerate(inputs):
        y = 108 + i * 56
        s.rect(44, y, 212, 44)
        s.text(58, y + 27, name, size=12.5)
        ys.append(y + 22)

    # readers
    s.rect(296, 190, 140, 110)
    s.text(366, 228, "Format readers", size=14, weight=600, anchor="middle")
    s.lines(366, 252, ["detect each layout,", "count unknown lines"], size=11.5, color=t["muted"], anchor="middle")
    for y in ys:
        s.arrow([(256, y), (276, y), (276, 245), (294, 245)])

    # collectors
    s.rect(476, 118, 216, 270)
    s.text(584, 146, "Evidence collectors", size=14, weight=600, anchor="middle")
    tiers = [("T1 direct", "descriptions, commits, tickets"),
             ("T2 behavioral", "logs, hit counts: seen or blind"),
             ("T3 structural", "objects, history, sibling rules"),
             ("T4 contextual", "well-known ports and apps")]
    for i, (a, b) in enumerate(tiers):
        y = 162 + i * 54
        s.rect(490, y, 188, 46, fill=t["box"], stroke=t["stroke"], rx=8)
        s.text(502, y + 19, a, size=12, weight=600)
        s.text(502, y + 36, b, size=11.5, color=t["muted"])
    s.arrow([(436, 245), (474, 245)])

    # assessment
    s.rect(732, 140, 196, 210, fill=t["accent_bg"], stroke=t["accent"], sw=1.6)
    s.text(830, 168, "Assessment", size=14, weight=600, anchor="middle")
    s.lines(746, 194, ["Verdict: keep, verify or", "removal candidate", "Confidence: HIGH, MEDIUM", "or LOW, owner to ask,", "conflicts flagged"], size=12, gap=17)
    s.rect(744, 286, 172, 48, fill=t["box"], stroke=t["accent"], rx=8)
    s.lines(830, 306, ["Never removal from", "missing traffic alone"], size=11.5, gap=15,
            color=t["accent"], anchor="middle", weight=600)
    s.arrow([(692, 245), (730, 245)])

    # outputs
    s.text(960, 132, "Outputs", size=14, weight=600)
    outs = [("Owner questionnaires", "one email per person"),
            ("Firewall team cleanup", "deactivated rules"),
            ("report.md + report.json", "every claim cites evidence")]
    for i, (a, b) in enumerate(outs):
        y = 148 + i * 64
        s.rect(960, y, 186, 52)
        s.text(970, y + 22, a, size=11.5, weight=600)
        s.text(970, y + 39, b, size=11, color=t["muted"])
        s.arrow([(928, 245), (944, 245), (944, y + 26), (958, y + 26)])

    # optional LLM lane
    s.rect(732, 420, 196, 76, dash=True)
    s.lines(830, 446, ["Local LLM writer", "optional, off by default"], size=12, gap=18, anchor="middle")
    s.text(830, 482, "Ollama on localhost only", size=11, color=t["muted"], anchor="middle")
    s.arrow([(830, 350), (830, 418)], dash=True)
    s.text(840, 388, "facts only", size=11, color=t["muted"])
    s.rect(960, 420, 186, 76, dash=True)
    s.lines(1053, 444, ["Validator", "uncited claims", "are dropped"], size=11.5, gap=16, anchor="middle")
    s.arrow([(928, 458), (958, 458)], dash=True)
    s.arrow([(1053, 420), (1053, 331)], dash=True)

    # legend
    s.add(f'<line x1="44" y1="470" x2="84" y2="470" stroke="{t["line"]}" stroke-width="1.5"/>')
    s.text(92, 474, "always on", size=11.5, color=t["muted"])
    s.add(f'<line x1="170" y1="470" x2="210" y2="470" stroke="{t["line"]}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    s.text(218, 474, "optional", size=11.5, color=t["muted"])
    s.text(44, 504, "Each rule ends with a probable intent, its ranked evidence, a confidence,", size=11.5, color=t["muted"])
    s.text(44, 521, "a verdict and the question to ask its owner.", size=11.5, color=t["muted"])
    return s.render()


def how_evaluated(t):
    s = SVG(1120, 470, t, "How palimp is evaluated: a seeded simulator generates firewall histories with "
            "a hidden ground truth; palimp analyzes the artifacts and an evaluation harness scores its "
            "verdicts. Held-out scenarios run only in GitHub Actions.")
    # simulator
    s.rect(30, 120, 200, 130)
    s.text(130, 150, "palimp-sim", size=14, weight=600, anchor="middle")
    s.lines(130, 174, ["seeded synthetic company,", "years of firewall history,", "admins, incidents, traps"],
            size=11.5, color=t["muted"], anchor="middle")

    # artifacts and ground truth
    s.rect(290, 80, 190, 70)
    s.text(385, 108, "Artifacts", size=13.5, weight=600, anchor="middle")
    s.text(385, 128, "what an engineer inherits", size=11.5, color=t["muted"], anchor="middle")
    s.rect(290, 220, 190, 70, fill=t["warn_bg"], stroke=t["warn"])
    s.text(385, 248, "Ground truth", size=13.5, weight=600, anchor="middle")
    s.text(385, 268, "never shown to palimp", size=11.5, color=t["warn"], anchor="middle")
    s.arrow([(230, 160), (260, 160), (260, 115), (288, 115)])
    s.arrow([(230, 210), (260, 210), (260, 255), (288, 255)])

    # palimp
    s.rect(540, 80, 170, 70, fill=t["accent_bg"], stroke=t["accent"], sw=1.6)
    s.text(625, 108, "palimp", size=14, weight=600, anchor="middle")
    s.text(625, 128, "same CLI users run", size=11.5, color=t["muted"], anchor="middle")
    s.arrow([(480, 115), (538, 115)])

    # harness
    s.rect(770, 150, 170, 80)
    s.text(855, 182, "Evaluation harness", size=13.5, weight=600, anchor="middle")
    s.text(855, 202, "compares rule by rule", size=11.5, color=t["muted"], anchor="middle")
    s.arrow([(710, 115), (740, 115), (740, 175), (768, 175)])
    s.text(746, 104, "report.json", size=11, color=t["muted"])
    s.arrow([(480, 255), (740, 255), (740, 205), (768, 205)])

    # metrics
    s.rect(970, 90, 130, 200)
    s.text(1035, 116, "Metrics", size=13.5, weight=600, anchor="middle")
    s.lines(982, 142, ["verdict accuracy", "vs best achievable", "", "live rules flagged", "for removal (target 0)",
                       "", "overconfidence", "", "vs naive baseline"], size=11, gap=15, color=t["muted"])
    s.arrow([(940, 190), (968, 190)])

    # lanes
    s.rect(30, 340, 520, 100, dash=True)
    s.text(50, 368, "Dev seeds", size=13.5, weight=600)
    s.lines(50, 390, ["Run locally by the coding agent. Seeds 0-19 tune the rules,",
                      "seeds 20-99 check for overfitting without any tuning."], size=12, gap=18, color=t["muted"])
    s.rect(580, 340, 520, 100, fill=t["accent_bg"], stroke=t["accent"])
    s.text(600, 368, "Held-out seeds", size=13.5, weight=600)
    s.lines(600, 390, ["Generated only in GitHub Actions from a secret salt the agent never sees.",
                       "Aggregate scores only, run by the project lead once per release."],
            size=12, gap=18, color=t["muted"])
    s.text(30, 40, "Independence: simulator and analyzer share no code, only the ground truth schema.",
           size=12.5, color=t["muted"])
    return s.render()


def how_built(t):
    s = SVG(1120, 400, t, "How palimp was built: a chat Claude acting as technical lead writes one-mission "
            "prompts, the project lead challenges and relays them, Claude Code develops in a fresh "
            "conversation per session, and the repository holds the project memory.")
    nodes = [
        (30, "Claude (chat)", "technical lead", ["vision and decisions,", "one-mission prompts,", "review of every report"]),
        (420, "Nathan", "project lead", ["challenges choices,", "accounts and installs,", "triggers held-out runs"]),
        (810, "Claude Code", "developer", ["fresh conversation per", "session: code, tests,", "commits, push, metrics"]),
    ]
    for x, a, b, desc in nodes:
        accent = a == "Nathan"
        s.rect(x, 60, 280, 140, fill=t["accent_bg"] if accent else t["box"],
               stroke=t["accent"] if accent else t["stroke"], sw=1.6 if accent else 1.2)
        s.text(x + 20, 92, a, size=15, weight=600)
        s.text(x + 20, 112, b, size=12, color=t["accent"] if accent else t["muted"], weight=600)
        s.lines(x + 20, 140, desc, size=12, gap=17, color=t["muted"])
    # top arrows
    s.arrow([(310, 95), (418, 95)], label="mission prompt", lx=364, ly=86)
    s.arrow([(700, 95), (808, 95)], label="pasted as is", lx=754, ly=86)
    # bottom return arrows
    s.arrow([(808, 165), (702, 165)], label="session report", lx=754, ly=185)
    s.arrow([(418, 165), (312, 165)], label="report + challenges", lx=364, ly=185)

    # repo memory
    s.rect(810, 260, 280, 110)
    s.text(830, 290, "Repository memory", size=15, weight=600)
    s.lines(830, 316, ["CLAUDE.md, HANDOFF.md,", "docs/decisions/, metrics/sessions.csv"], size=12, gap=17,
            color=t["muted"])
    s.arrow([(910, 200), (910, 258)])
    s.text(918, 234, "writes", size=11.5, color=t["muted"])
    s.arrow([(1010, 258), (1010, 202)])
    s.text(1018, 234, "read first", size=11.5, color=t["muted"])

    s.lines(30, 290, ["One mission per session, every decision recorded with its reason,",
                      "per-session tokens and API-equivalent cost measured, never estimated.",
                      "The agent may act on its own only in the safe direction (keep or verify)."],
            size=12.5, gap=20, color=t["muted"])
    s.text(30, 36, "Nobody on the project writes code by hand: the human role is direction, challenge and checks.",
           size=12.5, color=t["muted"])
    return s.render()


if __name__ == "__main__":
    for name, fn in [("how-it-works", how_it_works), ("evaluation", how_evaluated), ("how-it-was-built", how_built)]:
        for theme, t in THEMES.items():
            with open(f"{name}-{theme}.svg", "w") as f:
                f.write(fn(t))
