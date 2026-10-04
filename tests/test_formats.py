from palimp.formats.commits import parse_commits
from palimp.formats.hitcount import parse_hitcount
from palimp.formats.rt_flow import parse_rt_flow
from palimp.formats.tickets import parse_tickets

COMMITS = """\
0   2026-09-14 22:41:07 CEST by jdoe via cli
    CHG0012345 add CRM export
1   2026-09-12 10:02:55 CEST by svc-ansible via netconf
2   2026-09-10 16:30:12 CEST by admin via cli commit confirmed, rollback in 10mins
garbage
"""

HITCOUNT = """\
Logical system: root-logical-system
 Index   From zone        To zone           Name                    Policy count  Action
 1       users            servers           users-to-crm-web        184223        Permit
 2       users            servers           rule-47                 0             Permit
"""

LOG = (
    "<14>1 2026-09-14T08:12:44.311Z fw RT_FLOW - RT_FLOW_SESSION_CLOSE [junos@2636.1.1.1.2.129 "
    'reason="TCP FIN" source-address="10.0.0.1" policy-name="users-to-crm-web" elapsed-time="3"]\n'
    "<14>1 2026-09-15T08:12:44.311Z fw RT_FLOW - RT_FLOW_SESSION_CREATE [junos@2636.1.1.1.2.129 "
    'source-address="10.0.0.1" policy-name="users-to-crm-web"]\n'
    "Sep 15 08:12:44 fw RT_FLOW: RT_FLOW_SESSION_CREATE: session created 10.0.0.1/1->10.0.0.2/443\n"
)

TICKETS = """\
ticket_id,opened,summary,extra
CHG0012345,2026-09-01,"Open CRM export, urgent",x
,2026-09-02,no id,y
"""


def test_commits() -> None:
    commits, stats = parse_commits(COMMITS)
    assert [c.index for c in commits] == [0, 1, 2]
    assert commits[0].comment == "CHG0012345 add CRM export"
    assert commits[1].client == "netconf" and commits[1].comment == ""
    assert commits[2].extra == "commit confirmed, rollback in 10mins"
    assert stats.unknown == 1


def test_hitcount() -> None:
    rows, stats = parse_hitcount(HITCOUNT)
    assert [(r.name, r.count) for r in rows] == [("users-to-crm-web", 184223), ("rule-47", 0)]
    assert stats.ignored == 2 and stats.unknown == 0


def test_rt_flow_summary() -> None:
    summaries, stats = parse_rt_flow(LOG)
    summary = summaries["users-to-crm-web"]
    assert (summary.create, summary.close) == (1, 1)
    assert summary.first_seen.day == 14 and summary.last_seen.day == 15
    assert stats.unknown == 1


def test_tickets() -> None:
    tickets, stats = parse_tickets(TICKETS)
    assert tickets["CHG0012345"].summary == "Open CRM export, urgent"
    assert stats.unknown == 1
