
"""
Person filter rule including all persons reachable from the active/selected person, except those in the given filter.

This allows to cut partial trees, e.g. exclude everything learned about my spouse but have all non-relatives in my half of the tree.
"""

# https://github.com/gramps-project/gramps/blob/master/gramps/gen/plug/_pluginreg.py
register(RULE,
  id    = 'ExcludeSubtree',
  name  = _("All people, starting at <person>, except those in/behind <filter>"),
  description = _("Matches people who are reachable starting from <person> "
      "except those in <filter>."),
  version = '0.5',
  authors = ["Jonathan Biegert"],
  authors_email = ["azrdev@gmail.com"],
  gramps_target_version = '6.0',
  status = BETA,
  fname = "excludesubtree.py",
  ruleclass = 'ExcludeSubtree',  # must be rule class name
  namespace = 'Person',  # one of the primary object classes
)
