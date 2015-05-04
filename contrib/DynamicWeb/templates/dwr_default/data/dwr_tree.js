// Gramps - a GTK+/GNOME based genealogy program
//
// Copyright (C) 2014 Pierre Bélissent
//
// This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
// This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
// You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

// This script is part of the Gramps dynamic web report
// See "dynamicweb.py"
//
// This script performs the following treatments:
//
//  - Build the document body structure:
//    The body contains the following sections (div):!
//       header: the header note given as parameter in Gramps
//       menu: The page menu
//          This menu contains a form for: search input, number of generations inputs
//          This menu is optional (depends on the body class 'menuless')
//       body-page: The contents of the page
//          the body-page could contain a search form
//       footer: the footer note given as parameter in Gramps
//
//  - Manage the search string:
//    The URL search string is used to pass parameters to the page
//
//  - Manage the menu form, and the search form embedded form


//=================================================================
//==================================================== Arbre rapide
//=================================================================

var levMax;


function tdClass(lev)
{
	return("simpletree gen" + lev);
}


function tdIshort(idx, lev, tree, style)
{
	tree = (typeof(tree) !== 'undefined') ? tree : true;
	style = (typeof(style) !== 'undefined') ? style : true;
	var page = (tree) ? "tree" : "indi";
	txt = "<a class='simpletree_link' href='javascript:" + page + "Ref(" + idx + ")'>" + I[idx][I_SHORT_NAME];
	var cl = "in0";
	var fz = 12;
	if (idx == search.Idx)
	{
		cl = "in1";
		fz = 16;
		txt += " <span class='simpletree_details'>(" + _('details') + ")</span>";
	}
	txt += "</a>";
	var td =
		"<td" + (style ? " class='simpletree gen" + (levMax-parseInt(lev)) +
		(isImplex(idx) ? " implex" : "") +
		((I[idx][I_GENDER] == "M") ? " male" : ((I[idx][I_GENDER] == "F") ? " female" : " unknown")) +
		"'" : "") + ">" +
		"<p class='" + cl + "' + style='font-size:" + fz + "px;'>" + txt + "</td>";
	return(td);
}

function ascendants(idx, lev)
{
	var txt = "<table border='0' cellspacing='0' cellpadding='0'>";
	var i, j;
	if (lev > 1)
	{
		txt += "<tr align='center' valign='bottom'>";
		for (i = 0; i < I[idx][I_FAMC].length; i++)
		{
			for (j = 0; j < F[I[idx][I_FAMC][i][FC_INDEX]][F_SPOU].length; j++)
			{
				txt += "<td>" + ascendants(F[I[idx][I_FAMC][i][FC_INDEX]][F_SPOU][j], lev - 1) + "</td>";
			}
		}
		txt += "</tr>\n";
	}
	txt += "<tr align='center'>";
	for (i = 0; i < I[idx][I_FAMC].length; i++)
	{
		for (j = 0; j < F[I[idx][I_FAMC][i][FC_INDEX]][F_SPOU].length; j++)
		{
			txt += tdIshort(F[I[idx][I_FAMC][i][FC_INDEX]][F_SPOU][j], lev-1);
		}
	}
	txt += "</tr></table>\n";
	return(txt);
}


function descendants(idx, lev)
{
	var i, j, txt = "";
	if (I[idx][I_FAMS].length > 1) txt += "<table border='0' cellspacing='0' cellpadding='0'><tr align='center' valign='top'>\n";
	for (i = 0; i < I[idx][I_FAMS].length; i++)
	{
		if (I[idx][I_FAMS].length > 1) txt += "<td>";
		txt += "<table border='0' cellspacing='0' cellpadding='0'>";
		var spouses = [];
		for (j = 0; j < F[I[idx][I_FAMS][i]][F_SPOU].length; j++)
		{
			if (F[I[idx][I_FAMS][i]][F_SPOU][j] != idx)
			{
				spouses.push(F[I[idx][I_FAMS][i]][F_SPOU][j]);
			}
		}
		if ((lev == levMax) || (spouses.length > 0))
		{
			txt += "<tr align='center'>";
			var cs = F[I[idx][I_FAMS][i]][F_CHIL].length;
			txt += "<td class='" + tdClass(levMax - parseInt(lev)) + "'" + ((cs > 1) ? (" colspan='" + cs + "'") : "") + ">";
			txt += "<table border='0' cellspacing='0' cellpadding='0'>";
			txt += "<tr align='center'>";
			if (spouses.length == 0)
			{
				txt += "<td><p class='in0'>?</p></td>";
			}
			for (j = 0; j < spouses.length; j++)
			{
				txt += tdIshort(spouses[j], lev, true, false);
			}
			txt += "</tr></table></td></tr>";
		}
		txt += "<tr align='center'>";
		for (j = 0; j < F[I[idx][I_FAMS][i]][F_CHIL].length; j++)
		{
			txt += tdIshort(F[I[idx][I_FAMS][i]][F_CHIL][j][FC_INDEX], lev - 1);
		}
		txt += "</tr>";
		if (lev > 1)
		{
			txt += "<tr align='center' valign='top'>";
			for (j = 0; j < F[I[idx][I_FAMS][i]][F_CHIL].length; j++)
			{
				txt += "<td>";
				txt += descendants(F[I[idx][I_FAMS][i]][F_CHIL][j][FC_INDEX], lev - 1);
				txt += "</td>";
			}
			txt += "</tr>";
		}
		txt += "</table>";
		if (I[idx][I_FAMS].length > 1) txt += "</td>";
	}
	if (I[idx][I_FAMS].length > 1) txt += "</tr></table>";
	return(txt);
}


function treeBuild(idx)
{
	var html = "";
	var levAsc = $("#FsearchAsc").val();
	var levDesc = $("#FsearchDsc").val();
	html += ("<table border='0' cellspacing='0' cellpadding='0'>");
	levMax = levAsc;
	if (levAsc > 0)
		html += ("<tr align='center' valign='bottom'><td>" + ascendants(idx, levAsc) + "</td></tr>\n");
	html += ("<tr align='center'>" + tdIshort(idx, levAsc, false));
	var fr = [];
	var i,j;
	for (i = 0; i < I[idx][I_FAMC].length; i++)
	{
		for (j = 0; j < F[I[idx][I_FAMC][i][FC_INDEX]][F_CHIL].length; j++)
		{
			if (F[I[idx][I_FAMC][i][FC_INDEX]][F_CHIL][j][FC_INDEX] != idx)
			{
				fr.push(F[I[idx][I_FAMC][i][FC_INDEX]][F_CHIL][j][FC_INDEX]);
			}
		}
	}
	if (fr.length > 0)
	{
		html += (
			"<td><table border='0' cellspacing='0' cellpadding='0'>" +
			"<tr><td><p class='in0'>" + _('Siblings') + ":</td></tr>\n");
		for (j = 0; j < fr.length; j++)
		{
			html += ("<tr>" + tdIshort(fr[j], levMax) + "</tr>\n");
		}
		html += ("</table></td>\n");
	}
	html += ("</tr>\n");
	levMax = levDesc;
	if (levDesc > 0)
		html += ("<tr align='center' valign='top'><td>" + descendants(idx,levDesc) + "</td></tr>\n");
	html += ("</table>");
	return(html);
}

