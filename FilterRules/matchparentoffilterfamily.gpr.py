"""
Filter rule to match parents of family filter.
"""
register(
    RULE,
    id="MatchParentOfFilterFamily",
    name=_("Parents of family filter"),
    description=_("Matches parent of family filter"),
    version = '0.0.3',
    authors=["jjdup"],
    authors_email=["jeremi+gramps@dupin.fdn.fr"],
    gramps_target_version="6.1",
    status=STABLE,
    fname="matchparentoffilterfamily.py",
    ruleclass="MatchesParentOfFilterFamily",  # must be rule class name
    namespace="Person",  # one of the primary object classes
    help_url="Addon:Rule_expansions",
)

