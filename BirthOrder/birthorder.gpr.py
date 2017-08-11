#------------------------------------------------------------------------
#
# Birth Order
#
#------------------------------------------------------------------------

register(TOOL,
id    = 'birthorder',
name  = _("Sort Children in Birth order"),
description =  _("Looks through families, looking for children that are not "
                 "in birth order.  User can accept individual suggestions to "
                 "correct, edit the birth order manually, accept all those "
                 "families that have all children with proper birth dates, or "
                 "accept all."),
version = '0.0.4',
gramps_target_version = '5.0',
status = STABLE,
fname = 'birthorder.py',
authors = ["Paul R. Culley"],
authors_email = ["paulr2787@gmail.com"],
category = TOOL_DBPROC,
toolclass = 'BirthOrder',
optionclass = 'BirthOrderOptions',
tool_modes = [TOOL_MODE_GUI]
  )
