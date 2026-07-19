"""
Filter rule to match person of event filter with role.
"""
register(
    RULE,
    id="MatchEventFilterRole",
    name=_("People from event with role"),
    description=_("Matches people of event filter with role"),
    version = '0.0.3',
    authors=["jjdup"],
    authors_email=["jeremi+gramps@dupin.fdn.fr"],
    gramps_target_version="6.1",
    status=STABLE,
    fname="matcheventfilterrole.py",
    ruleclass="MatchesEventFilterRole",  # must be rule class name
    namespace="Person",  # one of the primary object classes
    help_url="Addon:Rule_expansions",
)

