# -------------------------------------------------------------------------
#
# Copyright 2018-2025  Thomas S. Poindexter <tpoindex@gmail.com>
#
# MIT LICENSE
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the “Software”), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
# AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# -------------------------------------------------------------------------
register(
    REPORT,
    id="descendantspacetree",
    name=_("Descendant Space Tree"),
    category=CATEGORY_WEB,
    status=STABLE,
    fname="DescendantSpaceTree.py",
    reportclass="DescendantSpaceTreeReport",
    optionclass="DescendantSpaceTreeOptions",
    report_modes=[REPORT_MODE_GUI, REPORT_MODE_CLI],
    authors=["Tom Poindexter"],
    authors_email=["tpoindex@gmail.com"],
    description=_(
        "Generates a web page with an interactive "
        "graph of descendants represented "
        "as a Space Tree for efficient viewing, even "
        "with many descendants or generations."
    ),
    version="1.0.0",
    gramps_target_version="6.0",
)
