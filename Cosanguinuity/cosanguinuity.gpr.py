# File: Cosanguinuity.gpr.py
register(GRAMPLET,
         id="Cosanguinuity",
         name=_("Cosanguinuity"),
         description = _("Gramplet showing pedigree collapse and relationships between partners"),
         version = '1.0.3',
         gramps_target_version="5.1",
         status = STABLE,
         fname="cosanguinuity.py",
         height = 50,
         detached_width = 400,
         detached_height = 500,
         gramplet = 'CosanguinuityGramplet',
         gramplet_title=_("Cosanguinuity"),
         help_url="5.1_Addons#Addon_List",
         navtypes=['Person']
         )
