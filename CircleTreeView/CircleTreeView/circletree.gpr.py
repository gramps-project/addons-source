# -*- coding: utf-8 -*-
"""
Gramps Plugin Registration — Circle Tree View
Target: Gramps 6.1.x
License: GNU GPL v2 or later
"""
register(
    VIEW,
    id="circletreeview",
    name=_("Circle Tree View"),
    category=("Ancestry", _("Charts")),
    description=_(
        "Descendant tree with circular nodes, multi-spouse support, "
        "auto generation depth (max 6), SVG/PNG export"
    ),
    version="1.4.0",
    gramps_target_version="6.1",
    status=STABLE,
    fname="circletree.py",
    authors=["Vadim Verenich"],
    authors_email=["vadimverenich@gmail.com"],
    viewclass="CircleTreeView",
    stock_icon="gramps-pedigree",
)
