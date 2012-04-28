#
# Lines of Descendency Report - a plugin for Gramps, the GTK+/GNOME based
#                               genealogy program.
#
# This program is released under the MIT License.
# Cf. http://www.opensource.org/licenses/mit-license.php.
#
# Copyright (c) 2010, 2012 lcc <lcc.mailaddress@gmail.com>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
register(REPORT,
        id = 'LinesOfDescendency',
        name = _('Lines of Descendency Report'),
        description = _('Prints out all descendency lines '
            'from a given ancestor to a given descendent in text.'),
        version = '1.1.11',
        gramps_target_version = '3.5',
        status = STABLE,
        fname = 'lines-of-descendency.py',
        authors = ['lcc'],
        authors_email = ['lcc.mailaddress@gmail.com'],
        category = CATEGORY_TEXT,
        reportclass = 'LinesOfDescendency',
        optionclass = 'LODOptions',
        report_modes = [REPORT_MODE_GUI, REPORT_MODE_CLI]
        )
