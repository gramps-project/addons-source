register(
    GENERAL,
    id="Fast Relationship Graph",
    name=_("Fast Relationship Graph"),
    description=_(
        "Fast relationship search (relationship(), all_relationships(), "
        "relationship_path(), all_relationship_paths(), relationships_to()), "
        "as a standalone library -- no SQL, no changes to gramps-core. "
        "Fixes the same exponential-under-pedigree-collapse search bug "
        "submitted upstream as gramps-project/gramps PR #2526, via a new, "
        "independent class rather than any change to RelationshipCalculator: "
        "nothing in gramps-core is modified. Import "
        "FastRelationshipGraph.fast_relationship_graph.FastRelationshipGraph "
        "directly; this addon does not run anything automatically."
    ),
    version="0.1.0",
    gramps_target_version="6.0",
    status=STABLE,
    fname="fast_relationship_graph.py",
    load_on_reg=False,
    authors=["Doug Blank"],
    authors_email=["doug.blank@gmail.com"],
    maintainers=["Doug Blank"],
    maintainers_email=["doug.blank@gmail.com"],
)
