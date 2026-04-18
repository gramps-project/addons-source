"""
Filter rule to match event of person filter with role.
"""
register(
    RULE,
    id="MatchPersonFilterRole",
    name=_("Events from people with role"),
    description=_("Matches event of people filter with role"),
    version = '0.0.2',
    authors=[""],
    authors_email=[""],
    gramps_target_version="6.1",
    status=STABLE,
    fname="matchpersonfilterrole.py",
    ruleclass="MatchesPersonFilterRole",  # must be rule class name
    namespace="Event",  # one of the primary object classes
    help_url="Addon:Rule_expansions",
)

