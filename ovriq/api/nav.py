"""Faelles navigationsbjaelke paa tvaers af OVRIQ-siderne."""

NAV_CSS = """
.ovnav{display:flex;gap:4px;flex-wrap:wrap;align-items:center;margin-bottom:18px;
padding-bottom:14px;border-bottom:1px solid var(--line)}
.ovnav a{padding:7px 13px;border-radius:8px;color:var(--dim);text-decoration:none;
font-size:12px;letter-spacing:1px;border:1px solid transparent;font-family:inherit}
.ovnav a:hover{color:var(--txt);border-color:var(--line)}
.ovnav a.active{color:var(--neon);border-color:var(--neon)}
.ovnav a.home{color:var(--mag);border-color:var(--mag)}
.ovnav .spacer{flex:1}
"""

def nav_html(active: str = "") -> str:
    def cls(key):
        return ' class="active"' if key == active else ''
    return (
        '<nav class="ovnav">'
        '<a class="home" href="https://ovriq.xyz">ovriq.xyz</a>'
        '<a href="/dashboard"' + cls("dashboard") + '>Marked</a>'
        '<a href="/portal"' + cls("portal") + '>Portal</a>'
        '<a href="/docs">API-docs</a>'
        '<span class="spacer"></span>'
        '<a href="https://github.com/BeMintalitet/ovriq">GitHub</a>'
        '</nav>'
    )
