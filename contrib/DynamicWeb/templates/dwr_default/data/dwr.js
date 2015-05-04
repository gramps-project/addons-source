// Gramps - a GTK+/GNOME based genealogy program
//
// Copyright (C) 2014 Pierre Bélissent
//
// This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
// This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
// You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


//=================================================================
//====== Indexes of the fields in the database exported from Gramps
//=================================================================

// The Gramps database is exported as Javascript Arrays
// The following indexes are indexes in these Arrays
// If you wonder why JSON is not used instead, the answer is: because. Good question nevertheless.

// I: Individual
I_NAME = 0;
I_SHORT_NAME = 1;
I_NAMES = 2;
I_GENDER = 3;
I_BIRTH_YEAR = 4;
I_BIRTH_PLACE = 5;
I_DEATH_YEAR = 6;
I_DEATH_PLACE = 7;
I_DEATH_AGE = 8;
I_EVENTS = 9;
I_ADDRS = 10;
I_NOTE = 11;
I_MEDIA = 12;
I_CITA = 13;
I_ATTR = 14;
I_URLS = 15;
I_FAMS = 16;
I_FAMC = 17;
I_ASSOC = 18;

// N: Name
N_FULL = 0;
N_TYPE = 1;
N_TITLE = 2;
N_NICK = 3;
N_CALL = 4;
N_GIVEN = 5;
N_SUFFIX = 6;
N_SURNAMES = 7;
N_FAM_NICK = 8
N_DATE = 9;
N_NOTE = 10;
N_CITA = 11;

// A: Attribute
A_TYPE = 0;
A_VALUE = 1;
A_NOTE = 2;
A_CITA = 3;

// F: Family
F_NAME = 0;
F_TYPE = 1;
F_MARR_YEAR = 2;
F_MARR_PLACE = 3;
F_EVENTS = 4;
F_NOTE = 5;
F_MEDIA = 6;
F_CITA = 7;
F_ATTR = 8;
F_SPOU = 9;
F_CHIL = 10;

// FC: Child relationship
FC_INDEX = 0;
FC_TO_FATHER = 1;
FC_TO_MOTHER = 2;
FC_NOTE = 3;
FC_CITA = 4;

// E: Event
E_TYPE = 0;
E_DATE = 1;
E_DATE_ISO = 2;
E_PLACE = 3;
E_DESCR = 4;
E_TEXT = 5;
E_MEDIA = 6;
E_CITA = 7;

// S: Source
S_TITLE = 0;
S_TEXT = 1;
S_NOTE = 2;
S_MEDIA = 3;
S_BKC = 4;
S_REPO = 5;
S_ATTR = 6;

// C: Citation
C_SOURCE = 0;
C_TEXT = 1;
C_NOTE = 2;
C_MEDIA = 3;
C_BKI = 4;
C_BKF = 5;
C_BKM = 6;
C_BKP = 7;
C_BKR = 8;

// R: Repository
R_NAME = 0;
R_TYPE = 1;
R_ADDRS = 2;
R_NOTE = 3;
R_URLS = 4;
R_BKS = 5;

// M: Media
M_TITLE = 0;
M_GRAMPS_PATH = 1;
M_PATH = 2;
M_MIME = 3;
M_DATE = 4;
M_DATE_ISO = 5;
M_NOTE = 6;
M_CITA = 7;
M_ATTR = 8;
M_THUMB = 9;
M_BKI = 10;
M_BKF = 11;
M_BKS = 12;
M_BKP = 13;

// P: Place
P_NAME = 0;
P_LOCATIONS = 1;
P_COORDS = 2;
P_NOTE = 3;
P_MEDIA = 4;
P_CITA = 5;
P_URLS = 6;
P_BKI = 7;
P_BKF = 8;

// MR: Media reference
MR_M_IDX = 0;
MR_BK_IDX = 0;
MR_THUMB = 1;
MR_RECT = 2;
MR_NOTE = 3;
MR_CITA = 4;

// RR: Repository reference
RR_R_IDX = 0;
RR_S_IDX = 0;
RR_MEDIA_TYPE = 1;
RR_CALL_NUMBER = 2;
RR_NOTE = 3;

// U: URL
U_TYPE = 0;
U_URI = 1;
U_DESCR = 2;

// AC: Association
AC_PERSON = 0;
AC_RELATIONSHIP = 1;
AC_NOTE = 2;
AC_CITA = 3;

// AD: Address
AD_DATE = 0;
AD_DATE_ISO = 1;
AD_LOCATION = 2;
AD_NOTE = 3;
AD_CITA = 4;

// LOC: Location (for places and addresses)
LOC_STREET = 0;
LOC_LOCALITY = 1;
LOC_PARISH = 2;
LOC_CITY = 3;
LOC_STATE = 4;
LOC_COUNTY = 5;
LOC_ZIP = 6;
LOC_COUNTRY = 7;
LOC_PHONE = 8;

// SN: Surname
SN_SURNAME = 0;
SN_PERSONS = 1;

// Initialize empty arrays by default
// Depending on generation options, not all the lists are generated

if (typeof(I) == 'undefined') I = []
if (typeof(F) == 'undefined') F = []
if (typeof(S) == 'undefined') S = []
if (typeof(R) == 'undefined') R = []
if (typeof(M) == 'undefined') M = []
if (typeof(P) == 'undefined') P = []
if (typeof(SN) == 'undefined') SN = []


//=================================================================
//======================================================= Constants
//=================================================================

// Type of the page
PAGE_INDI = 1;
PAGE_FAM = 2;
PAGE_SOURCE = 3;
PAGE_MEDIA = 4;
PAGE_PLACE = 5;
PAGE_REPO = 6;
PAGE_SEARCH = 7;
PAGE_SVG_TREE = 10;
PAGE_SVG_TREE_FULL = 11


//=================================================================
//==================================================== Localisation
//=================================================================

function _(text)
{
	if (__[text]) return(__[text]);
	return(text);
}


//=================================================================
//=========================================================== Liens
//=================================================================

function indiHref(idx)
{
	// Get the person page address
	
	idx = (typeof(idx) !== 'undefined') ? idx : search.Idx;
	return('person.html?' + BuildSearchString({
		Idx: idx,
		mapExpanded: false // Reset map
	}));
}

function indiRef(idx)
{
	// Go to the person page
	
	window.location.href = indiHref(idx);
	return(false);
}

function famHref(fdx)
{
	// Get the family page address
	
	fdx = (typeof(fdx) !== 'undefined') ? fdx : search.Fdx;
	return('family.html?' + BuildSearchString({
		Fdx: fdx,
		mapExpanded: false // Reset map
	}));
}

function mediaHref(mdx, m_list)
{
	// Get the media page address
	
	mdx = (typeof(mdx) !== 'undefined') ? mdx : search.Mdx;
	m_list = (typeof(m_list) !== 'undefined') ? m_list : [];
	var lt = '';
	if (search.Mdx >= 0 && ArbreType == PAGE_MEDIA)
	{
		m_list = search.ImgList;
	}
	return('media.html?' + BuildSearchString({
		Mdx: mdx,
		ImgList: m_list
	}));
}

function mediaRef(mdx)
{
	// Go to the media page
	
	window.location.href = mediaHref(mdx);
	return(false);
}

function m_list_from_mr(mr_list)
{
	// Build a list of the media referenced in the list of media reference structure
	// This list is used for numbering media in the pagination (see "printMedia")
	
	var m_list = [];
	for (var j = 0; j < mr_list.length; j++)
		m_list[j] = mr_list[j][MR_M_IDX];
	return(m_list);
}

function sourceHref(sdx)
{
	// Get the source page address
	
	sdx = (typeof(sdx) !== 'undefined') ? sdx : search.Sdx;
	return('source.html?' + BuildSearchString({
		Sdx: sdx
	}));
}

function sourceRef(sdx)
{
	// Go to the source page
	
	window.location.href = sourceHref(pdx);
	return(false);
}

function searchHref()
{
	// Get the search page address
	
	return('search.html?' + BuildSearchString());
}

function svgHref(idx, expand)
{
	// Go to the SVG tree page

	if (typeof(idx) == 'undefined') idx = search.Idx;
	var page;
	if (typeof(expand) == 'undefined')
	{
		// Get the current page
		var url = window.location.href;
		// this removes the anchor at the end, if there is one
		url = url.substring(0, (url.indexOf('#') == -1) ? url.length : url.indexOf('#'));
		// this removes the query after the file name, if there is one
		url = url.substring(0, (url.indexOf('?') == -1) ? url.length : url.indexOf('?'));
		// The file name is everything before the last slash in the path
		page = url.substring(url.lastIndexOf('/') + 1, url.length);
	}
	else if (expand)
	{
		page = 'tree_svg_full.html';
	}
	else
	{
		page = 'tree_svg.html';
	}
	return(page + '?' + BuildSearchString({
		Idx: idx,
	}));
}

function svgRef(idx, expand)
{
	// Go to the SVG tree page

	window.location.href = svgHref(idx, expand);
	return(false);
}

function placeHref(pdx)
{
	// Get to the place page address
	
	pdx = (typeof(pdx) !== 'undefined') ? pdx : search.Pdx;
	return('place.html?' + BuildSearchString({
		Pdx: pdx,
		mapExpanded: false // Reset map
	}));
}

function placeRef(pdx)
{
	// Go to the place page
	
	window.location.href = placeHref(pdx);
	return(false);
}

function repoHref(rdx)
{
	// Get to the repository page address
	
	rdx = (typeof(rdx) !== 'undefined') ? rdx : search.Rdx;
	return('repository.html?' + BuildSearchString({
		Rdx: rdx,
		mapExpanded: false // Reset map
	}));
}

function repoRef(rdx)
{
	// Go to the repository page
	
	window.location.href = repoHref(rdx);
	return(false);
}


//=================================================================
//======================================================= Implexes
//=================================================================

// List of the persons index 'idx' of table 'I', that appear several times in the ancestors or descendants of the center person
var implexes = [];


function searchImplex(idx)
{
	// Recursively search for implexes in ancestors and descendants of person 'idx'
	// The search is limited to search.Asc ascending generations and search.Dsc descending generations
	
	implexes = [];
	searchImplexAsc(idx, search.Asc, []);
	searchImplexDsc(idx, search.Dsc, []);
}


function searchImplexAsc(idx, lev, found)
{
	// Recursively search for implexes in ancestors of person 'idx',
	// limited to "lev" generations.
	// "found" contains all the persons found in the tree traversal
	
	if (($.inArray(idx, found) >= 0) && ($.inArray(idx, implexes) < 0))
	{
		implexes.push(idx);
		return;
	}
	found.push(idx);
	if (lev <= 0) return;
	for (var x_fam = 0; x_fam < I[idx][I_FAMC].length; x_fam++)
	{
		var fam = F[I[idx][I_FAMC][x_fam][FC_INDEX]];
		for (var x_spou = 0; x_spou < fam[F_SPOU].length; x_spou++)
			searchImplexAsc(fam[F_SPOU][x_spou], lev - 1, found);
	}
}


function searchImplexDsc(idx, lev, found)
{
	// Recursively search for implexes in descendants of person 'idx',
	// limited to "lev" generations.
	// "found" contains all the persons found in the tree traversal
	
	if (($.inArray(idx, found) >= 0) && ($.inArray(idx, implexes) < 0))
	{
		implexes.push(idx);
	}
	found.push(idx);
	if (lev <= 0) return;
	for (var x_fam = 0; x_fam < I[idx][I_FAMS].length; x_fam++)
	{
		var fam = F[I[idx][I_FAMS][x_fam]];
		if (!isImplex(idx))
			for (var x_chil = 0; x_chil < fam[F_CHIL].length; x_chil++)
				searchImplexDsc(fam[F_CHIL][x_chil][FC_INDEX], lev - 1, found);
		for (var x_spou = 0; x_spou < fam[F_CHIL].length; x_spou++)
			if (idx != fam[F_SPOU][x_spou])
				searchImplexDsc(fam[F_SPOU][x_spou], -1, found);
	}
}


function isImplex(idx)
{
	return($.inArray(idx, implexes) >= 0);
}


//=================================================================
//================================= Text for individuals / families
//=================================================================

function indiShortLinked(idx)
{
	return('<a href="' + indiHref(idx) + '">' + I[idx][I_SHORT_NAME] + '</a>');
}


function indiLinked(idx, citations)
{
	citations = (typeof(citations) !== 'undefined') ? citations : true;
	var txt = I[idx][I_NAME] + ' (' + I[idx][I_BIRTH_YEAR] + '-' + I[idx][I_DEATH_YEAR] + ')';
	if (citations) txt += ' ' + citaLinks(I[idx][I_CITA]);
	if (idx != search.Idx || ArbreType != PAGE_INDI)
		txt = '<a href="' + indiHref(idx) + '">' + txt + '</a>';
	return(txt);
}


function indiDetails(i)
{
	var genders = {
		'M': _('Male'),
		'F': _('Female'),
		'U': _('Unknown')
	};
	var txt = '';
	var x_name;
	txt += '<table class="table table-condensed table-bordered dwr-table-flat">';
	// txt += '<table class="dt-table dwr-table-flat">';
	for (x_name = 0; x_name < i[I_NAMES].length; x_name++)
	{
		var name = i[I_NAMES][x_name];
		var name_full = name[N_FULL];
		if (name[N_DATE] != '') name_full += ' (' + name[N_DATE] + ')';
		if (name[N_CITA].length > 0) name_full += ' ' + citaLinks(name[N_CITA]);
		txt += '<tr><td><p class="dwr-attr-title">' + name[N_TYPE] + '</p></td><td colspan="2"><p class="dwr-attr-value">' + name_full + '</p></td></tr>';
		if (name[N_NICK] != '') txt += '<tr><td class="empty"></td><td><p class="dwr-attr-title">' + _('Nick Name') + '</p></td><td><p class="dwr-attr-value">' + name[N_NICK] + '</p></td></tr>';
		if (name[N_CALL] != '') txt += '<tr><td class="empty"></td><td><p class="dwr-attr-title">' + _('Call Name') + '</p></td><td><p class="dwr-attr-value">' + name[N_CALL] + '</p></td></tr>';
		if (name[N_FAM_NICK] != '') txt += '<tr><td class="empty"></td><td><p class="dwr-attr-title">' + _('Family Nick Name') + '</p></td><td><p class="dwr-attr-value">' + name[N_FAM_NICK] + '</p></td></tr>';
		if (name[N_NOTE] != '') txt += '<tr><td class="empty"></td><td><p class="dwr-attr-title">' + _('Notes') + '</p></td><td>' + notePara(name[N_NOTE], '<p class="dwr-attr-value">') + '</td></tr>';
	}
	txt += '<tr><td><p class="dwr-attr-title">' + _('Gender') + '</p></td><td colspan="2"><p class="dwr-attr-value">' + genders[i[I_GENDER]] + '</p></td></tr>';
	if (i[I_DEATH_AGE] != '') txt += '<tr><td><p class="dwr-attr-title">' + _('Age at Death') + '</p></td><td colspan="2"><p class="dwr-attr-value">' + i[I_DEATH_AGE] + '</p></td></tr>';
	txt += '</table>';
	return(txt);
}


function famLinked(fdx, citations)
{
	citations = (typeof(citations) !== 'undefined') ? citations : true;
	var txt =F[fdx][F_NAME];
	if (citations) txt += ' ' + citaLinks(F[fdx][F_CITA]);
	if (INC_FAMILIES && (fdx != search.Fdx || ArbreType != PAGE_FAM))
		txt = '<a href="' + famHref(fdx) + '">' + txt + '</a>';
	return(txt);
}


function noteSection(note, level)
{
	level = (typeof(level) !== 'undefined') ? level : 5;
	var txt = '';
	if (note != '')
	{
		txt += printTitle(level, _('Notes') + ':');
		txt += notePara(note, '<p>');
		txt += printTitleEnd();
	}
	return(txt);
}


function mediaSection(media, level)
{
	level = (typeof(level) !== 'undefined') ? level : 5;
	var txt = '';
	if (media.length > 0)
	{
		txt += printTitle(level, _('Media') + ':', 'dwr-panel-media');
		txt += mediaLinks(media);
		txt += printTitleEnd();
	}
	return(txt);
}


function eventTable(events, idx, fdx)
{
	var j;
	var txt = '';
	if (events.length > 0)
	{
		txt += printTitle(5, _('Events'), '', true);
		txt += printTitleTable();
		txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
		// txt += '<table class="dt-table events">';
		txt += '<thead><tr>';
		txt += '<th><p class="dwr-attr-header">' + _('Event') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Date') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Place') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Description') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Notes') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Media') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Sources') + '</p></th>';
		txt += '</tr></thead><tbody>';
		for (j = 0; j < events.length; j++)
		{
			var e = events[j];
			txt += '<tr>';
			txt += '<td><p class="dwr-attr-title">' + e[E_TYPE] + '</p></td>';
			txt += '<td><p class="dwr-attr-value">' + e[E_DATE] + '</p></td>';
			txt += '<td><p class="dwr-attr-value">' + placeLink(e[E_PLACE], idx, fdx, e) + '</p></td>';
			txt += '<td><p class="dwr-attr-value">' + e[E_DESCR] + '</p></td>';
			txt += '<td>' + notePara(e[E_TEXT], '<p class="dwr-attr-value">') + '</td>';
			txt += '<td><p class="dwr-attr-value">' + mediaLinks(e[E_MEDIA]) + '</p></td>';
			txt += '<td><p class="dwr-attr-value">' + citaLinks(e[E_CITA]) + '</p></td>';
			txt += '</tr>';
		}
		txt += '</tbody></table>';
		txt += printTitleEnd();
	}
	return(txt);
}


function locationString(loc)
{
	var loc2 = [];
	for (var x_loc = 0; x_loc < loc.length; x_loc++)
		if (loc[x_loc] != '') loc2.push(loc[x_loc]);
	return(loc2.join(', '));
}


function addrsTable(addrs)
{
	var x_addr;
	var txt = '';
	if (addrs.length > 0)
	{
		txt += printTitle(5, _('Addresses'), '', true);
		txt += printTitleTable();
		txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
		// txt += '<table class="dt-table addrs">';
		txt += '<thead><tr>';
		txt += '<th><p class="dwr-attr-header">' + _('Address') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Date') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Notes') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Sources') + '</p></th>';
		txt += '</tr></thead><tbody>';
		for (x_addr = 0; x_addr < addrs.length; x_addr++)
		{
			var addr = addrs[x_addr];
			txt += '<tr>';
			txt += '<td><p class="dwr-attr-value">' + locationString(addr[AD_LOCATION]) + '</p></td>';
			txt += '<td><p class="dwr-attr-value">' + addr[AD_DATE] + '</p></td>';
			txt += '<td>' + notePara(addr[AD_NOTE], '<p class="dwr-attr-value">') + '</td>';
			txt += '<td><p class="dwr-attr-value">' + citaLinks(addr[AD_CITA]) + '</p></td>';
			txt += '</tr>';
		}
		txt += '</tbody></table>';
		txt += printTitleEnd();
	}
	return(txt);
}


function attrsTable(attrs)
{
	var x_attr;
	var txt = '';
	if (attrs.length > 0)
	{
		txt += printTitle(5, _('Attributes'), '', true);
		txt += printTitleTable();
		txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
		// txt += '<table class="dt-table attrs">';
		txt += '<thead><tr>';
		txt += '<th><p class="dwr-attr-header">' + _('Attribute') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Value') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Notes') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Sources') + '</p></th>';
		txt += '</tr></thead><tbody>';
		for (x_attr = 0; x_attr < attrs.length; x_attr++)
		{
			var a = attrs[x_attr];
			txt += '<tr>';
			txt += '<td><p class="dwr-attr-title">' + a[A_TYPE] + '</p></td>';
			txt += '<td><p class="dwr-attr-value">' + a[A_VALUE] + '</p></td>';
			txt += '<td>' + notePara(a[A_NOTE], '<p class="dwr-attr-value">') + '</td>';
			txt += '<td><p class="dwr-attr-value">' + citaLinks(a[A_CITA]) + '</p></td>';
			txt += '</tr>';
		}
		txt += '</tbody></table>';
		txt += printTitleEnd();
	}
	return(txt);
}


function urlsTable(urls)
{
	var x_url;
	var txt = '';
	if (urls.length > 0)
	{
		txt += printTitle(5, _('Web Links'), '', true);
		txt += printTitleTable();
		txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
		// txt += '<table class="dt-table urls">';
		txt += '<thead><tr>';
		txt += '<th><p class="dwr-attr-header">' + _('Link') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Description') + '</p></th>';
		txt += '</tr></thead><tbody>';
		for (x_url = 0; x_url < urls.length; x_url++)
		{
			var url = urls[x_url];
			txt += '<tr>';
			txt += '<td><p class="dwr-attr-value"><a href="' + url[U_URI] + '">' + url[U_URI] + '</a></p></td>';
			txt += '<td><p class="dwr-attr-value">' + url[U_DESCR] + '</p></td>';
			txt += '</tr>';
		}
		txt += '</tbody></table>';
		txt += printTitleEnd();
	}
	return(txt);
}


function assocsTable(assocs)
{
	var x_assoc;
	var txt = '';
	if (assocs.length > 0)
	{
		txt += printTitle(5, _('Associations'), '', true);
		txt += printTitleTable();
		txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
		// txt += '<table class="dt-table assocs">';
		txt += '<thead><tr>';
		txt += '<th><p class="dwr-attr-header">' + _('Person') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Relationship') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Notes') + '</p></th>';
		txt += '<th><p class="dwr-attr-header">' + _('Sources') + '</p></th>';
		txt += '</tr></thead><tbody>';
		for (x_assoc = 0; x_assoc < assocs.length; x_assoc++)
		{
			var assoc = assocs[x_assoc];
			txt += '<tr>';
			txt += '<td><p class="dwr-attr-value">' + indiLinked(assoc[AC_PERSON], false) + '</p></td>';
			txt += '<td><p class="dwr-attr-value">' + assoc[AC_RELATIONSHIP] + '</p></td>';
			txt += '<td>' + notePara(assoc[AC_NOTE], '<p class="dwr-attr-value">') + '</td>';
			txt += '<td><p class="dwr-attr-value">' + citaLinks(assoc[AC_CITA]) + '</p></td>';
			txt += '</tr>';
		}
		txt += '</tbody></table>';
		txt += printTitleEnd();
	}
	return(txt);
}


function notePara(note, p)
{
	if (note.indexOf('<div>') == -1 && note.indexOf('<p>') == -1)
		note = p + note + '</p>';
	return(note);
}

var pageSources = [];
var pageCitations = [];
var pageCitationsBullets = [];

function citaLinks(cita)
{
	var txt = '';
	var j, k;
	for (j = 0; j < cita.length; j++)
	{
		var c = C[cita[j]];
		var sdx = c[C_SOURCE];
		var title = S[sdx][S_TITLE];
		if (title != '') title=' title="' + title + '"';
		// Check if source is already referenced
		var x1 = $.inArray(sdx, pageSources);
		if (x1 == -1)
		{
			x1 = pageSources.length;
			pageSources[x1] = sdx;
			pageCitations[x1] = [];
		}
		var x2 = pageCitations[x1].length;
		// Check if citation already exists
		var c_m = mediaLinks(c[C_MEDIA])
		for (k = 0; k < pageCitations[x1].length; k++)
		{
			var c2 = C[pageCitations[x1][k]];
			var c2_m = mediaLinks(c2[C_MEDIA])
			if (c2[C_TEXT] == c[C_TEXT] &&
				c2[C_NOTE] == c[C_NOTE] &&
				c2_m == c_m)
			{
				x2 = k;
				break;
			}
		}
		pageCitations[x1][x2] = cita[j];
		// Reference text
		txt += ' <a class="dwr-citation label label-primary" href="#cita_' + sdx + '"' + title + '>' + x1 + ',' + x2 + '</a> ';
	}
	return(txt);
}

function printCitations()
{
	if (pageSources.length == 0) return('');
	var txt = '';
	var j, k;
	// Print output
	txt += '<ol>';
	for (j = 0; j < pageSources.length; j++)
	{
		var sdx = pageSources[j];
		txt += '<li><a name="cita_' + sdx + '" href="' + sourceHref(sdx) + '">';
		txt += sourName(sdx) + '</a>';
		var txts = '';
		pageCitationsBullets[j] = [];
		for (k = 0; k < pageCitations[j].length; k++)
		{
			var cdx = pageCitations[j][k];
			var c = C[cdx];
			var txtc = c[C_TEXT] + c[C_NOTE] + mediaLinks(c[C_MEDIA])
			if (txtc != '')
			{
				txts += '<li>' + txtc + '</li>';
				pageCitationsBullets[j][k] = (j + 1) + citationBullet(k);
			}
			else
			{
				pageCitationsBullets[j][k] = (j + 1) + '';
			}
		}
		if (txts != '') txt += '<ol style="list-style-type: lower-alpha">' + txts + '</ol>';
		txt += '</li>';
	}
	txt += '</ol>';
	return(txt);
}

function handleCitations()
{
	// Replace references text by the list index
	$('.dwr-citation').each(function(i, e) {
		var txt = $(this).text();
		var x = txt.split(',');
		$(this).text(pageCitationsBullets[x[0]][x[1]]);
	});
}

function citationBullet(x2)
{
	var num = '';
	num = String.fromCharCode('a'.charCodeAt(0) + (x2 % 26)) + num;
	x2 = Math.floor(x2 / 26);
	if (x2 > 0) num = String.fromCharCode('a'.charCodeAt(0) + (x2 % 27) - 1) + num;
	x2 = Math.floor(x2 / 27);
	if (x2 > 0) num = String.fromCharCode('a'.charCodeAt(0) + (x2 % 27) - 1) + num;
	x2 = Math.floor(x2 / 27);
	if (x2 > 0) num = String.fromCharCode('a'.charCodeAt(0) + (x2 % 27) - 1) + num;
	x2 = Math.floor(x2 / 27);
	if (x2 > 0) num = String.fromCharCode('a'.charCodeAt(0) + (x2 % 27) - 1) + num;
	x2 = Math.floor(x2 / 27);
	if (x2 > 0) num = String.fromCharCode('a'.charCodeAt(0) + (x2 % 27) - 1) + num;
	x2 = Math.floor(x2 / 27);
	return(num);
}

function sourName(sdx)
{
	if (S[sdx][S_TITLE] != '') return(S[sdx][S_TITLE]);
	return(_('Source') + ' ' + sdx);
}


function mediaName(mdx)
{
	var txt = '';
	var m = M[mdx];
	if (m[M_TITLE] != '') return(m[M_TITLE]);
	return(m[M_GRAMPS_PATH]);
}


// List of places referenced in the page with for each one:
//    - the place index in table "P"
//    - the referencing person index in table "I", -1 if none
//    - the referencing family index in table "F", -1 if none
//    - the referencing event, if any
var pagePlaces = [];
PP_PDX = 0;
PP_IDX = 1;
PP_FDX = 2;
PP_EVENT = 3;


function placeLink(pdx, idx, fdx, event)
{
	if (typeof(idx) == 'undefined') idx = -1;
	if (typeof(fdx) == 'undefined') fdx = -1;
	if (typeof(event) == 'undefined') event = null;
	if (pdx == -1) return('');
	pagePlaces.push([pdx, idx, fdx, event]);
	if (!INC_PLACES) return(P[pdx][P_NAME]);
	if (ArbreType == PAGE_PLACE && pdx == search.Pdx) return(P[pdx][P_NAME]);
	return('<a href="' + placeHref(pdx) + '">' + P[pdx][P_NAME] + '</a>');
}


function repoLink(rdx)
{
	if (rdx == -1) return('');
	if (ArbreType == PAGE_REPO && rdx == search.Rdx) return(R[rdx][R_NAME]);
	return('<a href="' + repoHref(rdx) + '">' + R[rdx][R_NAME] + '</a>');
}


//=================================================================
//========================================================== Titles
//=================================================================

var titlesCollapsible = []; // Stack of titles property: is the title collapsible ?
var titlesTable = []; // Stack of titles property: is the title containing a table ?
var titlesNumber = 0;


function printTitle(level, title, panelclass, table, collapsible)
{
	if (typeof(table) == 'undefined') table = false;
	if (typeof(panelclass) == 'undefined') panelclass = '';
	if (typeof(collapsible) == 'undefined') collapsible = (level >= 1);
	table = table && collapsible;
	var html = '';
	titlesNumber += 1;
	var id = 'section_' + titlesNumber;
	titlesCollapsible.push(collapsible);
	titlesTable.push(table);
	if (collapsible)
	{
		html += '<div class="panel panel-default ' + panelclass + '">';
		html += '<div class="panel-heading dwr-collapsible" data-toggle="collapse" data-target="#' + id + '">';
		html += '<h' + level + ' class="panel-title">' + title + '</h' + level + '>';
		html += '</div>';
		html += '<div id="' + id + '" class="panel-collapse collapse in ' + (table ? 'dwr-panel-table' : 'dwr-panel') + '">';
		if (!table) html += '<div class="panel-body">';
	}
	else
	{
		html += '<h' + level + '>' + title + '</h' + level + '>';
	}
	return(html);
}


function printTitleTable()
{
	var table = titlesTable[titlesTable.length - 1];
	titlesTable[titlesTable.length - 1] = true;
	return(table ? '' : '</div>');
}


function printTitleEnd()
{
	collapsible = titlesCollapsible.pop();
	table = titlesTable.pop();
	var txt = '';
	if (collapsible) txt = '</div></div></div>';
	if (table) txt = '</div></div>';
	return(txt);
}


function handleTitles()
{
	// Enable Bootstrap tooltips and popovers
	$('.panel-heading').click(function(event) {
		// Prevent title collapse when the click is not on the title
		var target = $(event.target);
		if (!target.is('.panel-heading') && !target.is('.panel-title'))
		{
			event.stopImmediatePropagation();
		}
	});
	$('[data-toggle=tooltip]').tooltip();
	$('[data-toggle=popover]').popover();
}


//=================================================================
//====================================================== Individual
//=================================================================

function printIndi(idx)
{
	var j, k;
	var html = '';
	html += '<h2 class="page-header">' + I[idx][I_NAME] + ' ' + citaLinks(I[idx][I_CITA]) + '</h2>';
	html += indiDetails(I[idx]);
	html += eventTable(I[idx][I_EVENTS], idx, -1);
	html += addrsTable(I[idx][I_ADDRS]);
	html += attrsTable(I[idx][I_ATTR]);
	html += urlsTable(I[idx][I_URLS]);
	html += assocsTable(I[idx][I_ASSOC]);
	html += mediaSection(I[idx][I_MEDIA]);
	html += noteSection(I[idx][I_NOTE]);
	html += printTitle(4, _('Ancestors') + ':');
	var famc_list = $.map(I[idx][I_FAMC], function (fc) {return(fc[FC_INDEX]);});
	if (INDEX_SHOW_ALL_SIBLINGS)
	{
		for (j = 0; j < I[idx][I_FAMC].length; j++)
		{
			var fdx = I[idx][I_FAMC][j][FC_INDEX];
			for (k = 0; k < F[fdx][F_SPOU].length; k++)
			{
				var spou = I[F[fdx][F_SPOU][k]];
				for (var x_fams = 0; x_fams < spou[I_FAMS].length; x_fams++)
				{
					var fams = spou[I_FAMS][x_fams];
					if ($.inArray(fams, famc_list) < 0) famc_list.push(fams);
				}
			}
		}
	}
	for (j = 0; j < famc_list.length; j++)
	{
		var fdx = famc_list[j];
		html += printTitle(5, _('Parents') + ': ' + famLinked(fdx));
		for (k = 0; k < F[fdx][F_SPOU].length; k++)
		{
			html += '<p class="dwr-ref">' + indiLinked(F[fdx][F_SPOU][k]) + '</p>';
		}
		if (F[fdx][F_SPOU].length == 0) html += ('<p class="dwr-ref">' + _('None.'));
		html += printTitleEnd();

		html += printTitle(5, _('Siblings') + ':');
		if (F[fdx][F_CHIL].length > 0)
		{
			html += '<ol class="dwr-ref">';
			for (k = 0; k < F[fdx][F_CHIL].length; k++)
			{
				html += '<li class="dwr-ref">';
				html += printChildRef(F[fdx][F_CHIL][k]);
				html += '</li>';
			}
			html += '</ol>';
		}
		else
		{
			html += ('<p class="dwr-ref">' + _('None.'));
		}
		html += printTitleEnd();
	}
	if (famc_list.length == 0) html += ('<p class="dwr-ref">' + _('None.'));
	html += printTitleEnd();
	html += printTitle(4, _('Descendants') + ':');
	for (j = 0; j < I[idx][I_FAMS].length; j++)
	{
		var fdx = I[idx][I_FAMS][j];
		var spouses = [];
		var sep = '';
		for (k = 0; k < F[fdx][F_SPOU].length; k++)
		{
			var spou = F[fdx][F_SPOU][k]
			if (spou != idx)
			{
				spouses.push(spou);
				sep = ', ';
			}
		}
		html += printTitle(5, famLinked(fdx));
		for (k = 0; k < spouses.length; k++)
		{
			html += '<p class="dwr-ref">' + indiLinked(spouses[k]) + '</p>';
		}
		html += eventTable(F[fdx][F_EVENTS], -1, fdx);
		html += attrsTable(F[fdx][F_ATTR]);
		html += mediaSection(F[fdx][F_MEDIA]);
		html += noteSection(F[fdx][F_NOTE]);
		html += printTitle(5, _('Children') + ':');
		html += '<ol class="dwr-ref">';
		for (k = 0; k < F[fdx][F_CHIL].length; k++)
		{
			html += '<li class="dwr-ref">';
			html += printChildRef(F[fdx][F_CHIL][k]);
			html += '</li>';
		}
		html += '</ol>';
		if (F[fdx][F_CHIL].length == 0) html += '<p class="dwr-ref">' + _('None.') + '</p>';
		html += printTitleEnd();
		html += printTitleEnd();
	}
	if (I[idx][I_FAMS].length == 0) html += ('<p class="dwr-ref">' + _('None.') + '</p>');
	html += printTitleEnd();
	// Citations and source references
	var ctxt = printCitations();
	if (ctxt != '')
	{
		html += printTitle(5, _('Sources') + ':');
		html += ctxt;
		html += printTitleEnd();
	}
	return(html);
}


function printChildRef(fc)
{
	var txt = '';
	txt += indiLinked(fc[FC_INDEX]);
	txt += ' ' + citaLinks(fc[FC_CITA]);
	if (fc[FC_NOTE] != '') txt += '<p><b>' + _('Notes') + ':</b></p>' + notePara(fc[FC_NOTE], '</p>');
	rel = fc[FC_TO_FATHER];
	title = _('Relationship to Father');
	if (rel != '' && rel != _('Birth')) txt += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + title + ': </span>' + rel + '</p>';
	rel = fc[FC_TO_MOTHER];
	title = _('Relationship to Mother');
	if (rel != '' && rel != _('Birth')) txt += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + title + ': </span>' + rel + '</p>';
	return(txt);
}


//=================================================================
//========================================================== Family
//=================================================================

function printFam(fdx)
{
	var j, k;
	var html = '';
	html += '<h2 class="page-header">' + famLinked(fdx) + '</h2>';
	html += eventTable(F[fdx][F_EVENTS], -1, fdx);
	html += attrsTable(F[fdx][F_ATTR]);
	html += mediaSection(F[fdx][F_MEDIA]);
	html += noteSection(F[fdx][F_NOTE]);
	var spouses = F[fdx][F_SPOU];
	html += printTitle(4, _('Parents') + ':');
	for (k = 0; k < spouses.length; k++)
	{
		var idx = spouses[k];
		html += '<h4 class="dwr-ref-detailed">' + indiLinked(idx) + '</a></h4>';
		html += indiDetails(I[idx]);
		html += eventTable(I[idx][I_EVENTS], idx, -1);
		// html += attrsTable(I[idx][I_ATTR]);
		html += mediaSection(I[idx][I_MEDIA]);
		// html += noteSection(I[idx][I_NOTE]);
	}
	if (spouses.length == 0) html += ('<p class="dwr-ref">' + _('None.'));
	html += printTitleEnd();
	html += printTitle(4, _('Children') + ':');
	html += '<ol class="dwr-ref-detailed">';
	for (k = 0; k < F[fdx][F_CHIL].length; k++)
	{
		var fc = F[fdx][F_CHIL][k];
		var idx = F[fdx][F_CHIL][k][FC_INDEX];
		html += '<li class="dwr-ref-detailed">' + printChildRef(F[fdx][F_CHIL][k])
		html += indiDetails(I[idx]);
		html += eventTable(I[idx][I_EVENTS], idx, -1);
		// html += attrsTable(I[idx][I_ATTR]);
		html += mediaSection(I[idx][I_MEDIA]);
		// html += noteSection(I[idx][I_NOTE]);
		html += '</li>';
	}
	if (F[fdx][F_CHIL].length == 0) html += ('<p class="dwr-ref">' + _('None.') + '</p>');
	html += '</ol>';
	html += printTitleEnd();
	// Map
	if (MAP_FAMILY)
		html += printMap();
	// Citations and source references
	var ctxt = printCitations();
	if (ctxt != '')
	{
		html += printTitle(5, _('Sources') + ':');
		html += ctxt;
		html += printTitleEnd();
	}
	return(html);
}


//=================================================================
//=========================================================== Media
//=================================================================

function mediaLinks(media)
{
	var txt = '';
	var j;
	for (j = 0; j < media.length; j++)
	{
		var mr = media[j];
		var m = M[mr[MR_M_IDX]];
		var alt = m[M_TITLE];
		if (alt == '') alt = m[M_TITLE];
		if (alt == '') alt = m[M_GRAMPS_PATH];
		if (alt == '') alt = _('Media') + ' ' + mr[MR_M_IDX];
		txt += ' <a title="' + alt + '" class="thumbnail" href="' + mediaHref(mr[MR_M_IDX], m_list_from_mr(media)) + '">';
		txt += '<img src="' + mr[MR_THUMB] + '" alt="' + alt + '"></a> ';
	}
	return(txt);
}


function printMedia(mdx)
{
	var html = '';
	var m = M[mdx];
	var title = m[M_TITLE];
	if (title == '') title = m[M_GRAMPS_PATH];
	html += '<h2 class="page-header">' + title + ' ' + citaLinks(m[M_CITA]) + '</h2>';
	
	// Pagination buttons
	if (search.ImgList.length > 1)
	{
		var imgI = search.ImgList.indexOf(mdx);
		// html += '<div id="dwr-img-btns" class="btn-toolbar" role="toolbar">';
		// html += '<div class="btn-group" role="group">';
		html += '<ul id="dwr-img-btns" class="pagination">';
		// html += '<button id="media_button_prev" type="button" class="btn btn-default' + ((imgI == 0) ? ' disabled' : '') + '">';
		// html += '<a href="#"><span class="glyphicon glyphicon-chevron-left"></span></a>';
		// html += '</button>';
		html += '<li id="media_button_prev"' + ((imgI == 0) ? ' class="disabled"' : '') + '>';
		html += '<a href="#"><span class="glyphicon glyphicon-chevron-left"></span></a></li>';
		// html += '<button id="media_button_0" type="button" class="btn btn-default' + ((imgI == 0) ? ' active' : '') + '">';
		// html += '<a href="#">1</a>';
		// html += '</button>';
		html += '<li id="media_button_0"' + ((imgI == 0) ? ' class="active"' : '') + '>';
		html += '<a href="#">1</a></li>';
		var first_but = Math.min(imgI - 1, search.ImgList.length - 4);
		first_but = Math.max(1, first_but);
		var last_but = Math.min(first_but + 2, search.ImgList.length - 2);
		if (first_but > 1)
		{
			// html += '<button type="button" class="btn btn-default disabled">';
			// html += '<a href="#">&hellip;</a>';
			// html += '</button>';
			html += '<li id="media_button_0" class="disabled">';
			html += '<a href="#">&hellip;</a></li>';
		}
		for (var i = first_but; i <= last_but; i++)
		{
			// html += '<button id="media_button_' + i + '" type="button" class="btn btn-default' + ((imgI == i) ? ' active' : '') + '">';
			// html += '<a href="#">' + (i + 1) + '</a>';
			// html += '</button>';
			html += '<li id="media_button_' + i + '"' + ((imgI == i) ? ' class="active"' : '') + '>';
			html += '<a href="#">' + (i + 1) + '</a></li>';
		}
		if (last_but < search.ImgList.length - 2)
		{
			// html += '<button type="button" class="btn btn-default disabled">';
			// html += '<a href="#">&hellip;</a>';
			// html += '</button>';
			html += '<li id="media_button_0" class="disabled">';
			html += '<a href="#">&hellip;</a></li>';
		}
		if (search.ImgList.length > 1)
		{
			// html += '<button id="media_button_' + (search.ImgList.length - 1) + '" type="button" class="btn btn-default' + ((imgI == search.ImgList.length - 1) ? ' active' : '') + '">';
			// html += '<a href="#">' + search.ImgList.length + '</a>';
			// html += '</button>';
			html += '<li id="media_button_' + (search.ImgList.length - 1) + '"' + ((imgI == search.ImgList.length - 1) ? ' class="active"' : '') + '>';
			html += '<a href="#">' + search.ImgList.length + '</a></li>';
		}
		// html += '<button id="media_button_next" type="button" class="btn btn-default' + ((imgI == search.ImgList.length - 1) ? ' disabled' : '') + '">';
		// html += '<a href="#"><span class="glyphicon glyphicon-chevron-right"></span></a>';
		// html += '</button>';
		html += '<li id="media_button_next"' + ((imgI == search.ImgList.length - 1) ? ' class="disabled"' : '') + '>';
		html += '<a href="#"><span class="glyphicon glyphicon-chevron-right"></span></a></li>';
		// html += '</div>';
		html += '</ul>';
		// Expand button
		// html += '<div class="btn-group" role="group">';
		// html += '<button id="media_button_max" type="button" class="btn btn-default" title=' + _('Maximize') + '>';
		// html += '<a href="#"><span class="glyphicon glyphicon-fullscreen"></span></a>';
		// html += '</button>';
		// html += '</div>';
		// html += '</div>';
		// Pagination events
		$(window).load(function()
		{
			$('#media_button_prev').click(function() {return mediaButtonPageClick(-1);});
			$('#media_button_next').click(function() {return mediaButtonPageClick(1);});
			$('#media_button_max').click(function() {return mediaButtonMaxClick();});
			$('#media_button_0').click(function() {return mediaButtonPageClick(0, 0);});
			$('#media_button_' + (search.ImgList.length - 1)).click(function() {return mediaButtonPageClick(0, search.ImgList.length - 1);});
			for (var i = first_but; i <= last_but; i++)
			{
				(function(){ // This is used to create instances of local variables
					var icopy = i;
					$('#media_button_' + i).click(function() {return mediaButtonPageClick(0, icopy);});
				})();
			}
		});
	}

	// Image or link (if media is not an image)
	// html += '<div id="img_div">';
	if (m[M_MIME].indexOf('image') == 0)
	{
		html += '<p class="dwr-centered"><img id="dwr-image" src="' + m[M_PATH] + '" usemap="#imgmap"></p>';
		html += printMediaMap(mdx);
	}
	else
	{
		var name = m[M_GRAMPS_PATH];
		name = name.replace(/.*[\\\/]/, '');
		html += '<p class="dwr-centered"><a href="' + m[M_PATH] + '">' + name + '</a></p>';
	}
	// html += '</div>';
	
	// Media description
	if (m[M_DATE] != '') html += '<p><b>' + _('Date') + ': </b>' + m[M_DATE] + '</p>';
	html += noteSection(m[M_NOTE]);
	html += attrsTable(m[M_ATTR]);

	// Back references
	var bk_txt = printBackRefs(BKREF_TYPE_MEDIA, m[M_BKI], m[M_BKF], m[M_BKS], [], m[M_BKP], []);
	if (bk_txt != '')
	{
		html += printTitle(5, _('References') + ':');
		html += bk_txt;
		html += printTitleEnd();
	}

	// Citations and source references
	var ctxt = printCitations();
	if (ctxt != '')
		html += printTitle(5, _('Sources') + ':');
		html += ctxt;
		html += printTitleEnd();
	
	// Compute map coordinates from image size
	$(window).load(function() {
		mediaMapCoords();
		$('#dwr-image').load(mediaMapCoords);
	});
	
	return(html);
}


function mediaButtonPageClick(page_delta, page)
{
	var imgI = search.ImgList.indexOf(search.Mdx);
	if (typeof(page) == 'undefined') page = imgI;
	var i = page + page_delta;
	i = (i + search.ImgList.length) % search.ImgList.length;
	window.location.href = mediaHref(search.ImgList[i]);
	return(false);
}


function mediaButtonMaxClick()
{
	window.location.href = M[search.Mdx][M_PATH];
	return(false);
}


function mediaMapCoords()
{
	var img = $('#dwr-image');
	var img_w0 = img.width();
	var img_h0 = img.height();
	$('area').each(function(j) {
		c = $(this).attr('coords');
		rect = c.split(',');
		rect_img = [img_w0, img_h0, img_w0, img_h0];
		for (var k = 0; k < 4; k++)
		{
			rect[k] = parseInt(rect[k]);
			rect[k] = Math.round(rect[k] * rect_img[k] / 10000.0);
		}
		$(this).attr('coords', rect.join(','));
	});
}


function printMediaMap(mdx)
{
	var html = '';
	var j, k;
	var m = M[mdx];
	html += '<map name="imgmap">';
	html += printMediaRefArea(m[M_BKI], indiHref, function(ref) {return(I[ref][I_NAME]);});
	if (INC_FAMILIES)
		html += printMediaRefArea(m[M_BKF], famHref, function(ref) {return(F[ref][F_NAME]);});
	if (INC_SOURCES)
		html += printMediaRefArea(m[M_BKS], sourceHref, sourName);
	if (INC_PLACES)
		html += printMediaRefArea(m[M_BKP], placeHref, function(ref) {return(P[ref][P_NAME]);});
	html += '</map>';
	return(html);
}

function printMediaRefArea(bk_table, fref, fname)
{
	var html = '';
	var j, k;
	for (j = 0; j < bk_table.length; j++)
	{
		var ref = bk_table[j];
		idx = ref[MR_BK_IDX];
		var rect = [];
		for (k = 0; k < 4; k++)
		{
			rect[k] = parseInt(ref[MR_RECT][k]);
			rect[k] = Math.round(rect[k] * 100);
		}
		if (!isNaN(rect[0]) && rect.join(',') != '0,0,10000,10000')
		{
			html += '<area shape="rect" coords="' + rect.join(',') + '"';
			html += ' href="' + fref(idx) + '"';
			html += ' title="' + fname(idx) + '">';
		}
	}
	return(html);
}


//=================================================================
//========================================================== Source
//=================================================================

function printSource(sdx)
{
	var html = '';
	var s = S[sdx];
	if (s[S_TITLE] != '') html += '<h2 class="page-header">' + s[S_TITLE] + '</h2>';
	if (s[S_TEXT] != '') html += s[S_TEXT];
	html += attrsTable(s[S_ATTR]);
	html += mediaSection(s[S_MEDIA]);
	html += noteSection(s[S_NOTE]);
	// Repositories for this source
	if (S[sdx][S_REPO].length > 0)
		html += printTitle(5, _('Repositories') + ':');
		html += printBackRefs(BKREF_TYPE_REPO, [], [], [], [], [], S[sdx][S_REPO]);
		html += printTitleEnd();
	// Citations referencing this source
	html += printTitle(5, _('Citations') + ':');
	if (s[S_BKC].length > 0)
	{
		html += '<ul class="dwr-citations">';
		var j;
		for (j = 0; j < s[S_BKC].length; j++)
		{
			c = C[s[S_BKC][j]]
			// html += '<li>' + _('Citation') + ': ';
			html += '<li>';
			if (c[C_TEXT] != '') html += notePara(c[C_TEXT], '<p>');
			if (c[C_NOTE] != '') html += '<p><b>' + _('Notes') + ':</b></p>' + notePara(c[C_NOTE], '<p>');
			if (c[C_MEDIA].length > 0) html += '<p>' + _('Media') + ': ' + mediaLinks(c[C_MEDIA]) + '</p>';
			// Back references
			html += printBackRefs(BKREF_TYPE_INDEX, c[C_BKI], c[C_BKF], [], c[C_BKM], c[C_BKP], c[C_BKR]);
			html += '</li>';
		}
		html += '</ul>';
	}
	else
	{
		html += '<p>' + _('None.') + '</p>';
	}
	html += printTitleEnd();
	return(html);
}


//=================================================================
//========================================================== Places
//=================================================================

function printPlace(pdx)
{
	var p = P[pdx]
	var html = '';
	var parts = [
		_('Street'),
		_('Locality'),
		_('City'),
		_('Church Parish'),
		_('County'),
		_('State/ Province'),
		_('Postal Code'),
		_('Country'),
		_('Latitude'),
		_('Longitude')
	];
	placeLink(pdx);
	var name = p[P_NAME];
	if (name == '') name = locationString(p[P_LOCATIONS]);
	html += '<h2 class="page-header">' + name + ' ' + citaLinks(p[P_CITA]) + '</h2>';
	var j, k;
	for (j = 0; j < p[P_LOCATIONS].length; j++)
	{
		if (p[P_LOCATIONS].length > 1)
		{
			if (j == 0) html += '<p>' + _('Location') + ': </p>';
			else html += '<p>' + _('Alternate Name') + ' ' + j + ': </p>';
		}
		var loc = p[P_LOCATIONS][j];
		loc[8] = p[P_COORDS][0];
		loc[9] = p[P_COORDS][1];
		html += '<table class="table table-condensed table-bordered dwr-table-flat">';
		for (k = 0; k < parts.length / 2; k ++)
		{
			html += '<tr><th><p class="dwr-attr-header">' + parts[k] + '</p></th>';
			html += '<td><p class="dwr-attr-value">' + loc[k] + '</p></td>';
			html += '<th><p class="dwr-attr-header">' + parts[k + parts.length / 2] + '</p></th>';
			html += '<td><p class="dwr-attr-value">' + loc[k + parts.length / 2] + '</p></td></tr>';
		}
		html += '</table>';
	}
	html += urlsTable(p[P_URLS]);
	html += mediaSection(p[P_MEDIA]);
	html += noteSection(p[P_NOTE]);
	// Map
	if (MAP_PLACE)
		html += printMap();
	// Citations and source references
	var ctxt = printCitations();
	if (ctxt != '')
		html += printTitle(5, _('Sources') + ':');
		html += ctxt;
		html += printTitleEnd();
	// Back references
	var bk_txt = printBackRefs(BKREF_TYPE_INDEX, p[P_BKI], p[P_BKF], [], [], [], []);
	if (bk_txt != '')
	{
		html += printTitle(5, _('References') + ':');
		html += bk_txt;
		html += printTitleEnd();
	}
	return(html);
}


//=================================================================
//==================================================== Repositories
//=================================================================

function printRepo(rdx)
{
	var r = R[rdx]
	var html = '';
	html += '<h2 class="page-header">' + r[R_NAME] + '</h2>';
	html += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Type') + ': </span>'
	html += r[R_TYPE] + '</p>';
	html += addrsTable(r[R_ADDRS]);
	html += urlsTable(r[R_URLS]);
	html += noteSection(r[R_NOTE]);
	// Back references
	html += printTitle(5, _('References') + ':');
	var bk_txt = printBackRefs(BKREF_TYPE_REPO, [], [], r[R_BKS], [], [], []);
	if (bk_txt == '') bk_txt = _('None.');
	html += bk_txt;
	html += printTitleEnd();
	// Citations and source references
	var ctxt = printCitations();
	if (ctxt != '')
		html += printTitle(5, _('Sources') + ':');
		html += ctxt;
		html += printTitleEnd();
	return(html);
}


//=================================================================
//=========================================================== Index
//=================================================================

indexCounter = 0;

function printIndex(data, defaultsort, columns)
{
	// var time = Date.now();
	var j, k;
	ParseSearchString();
	
	// Compute data
	// (optimization: copy data in another array in order to call functions ftext, fsort, fhref only once)
	// Also check if a column is empty
	var data_copy = Array(data.length);
	var nb_cols = columns.length;
	var col_empty = []; // is the column emtpy ?
	var col_num = []; // does the colmun contain only numbers ?
	for (j = 0; j < nb_cols; j++)
	{
		col_empty.push(true);
		col_num.push(true);
	}
	for (j = 0; j < data.length; j++)
	{
		var line = [];
		for (k = 0; k < nb_cols; k++)
		{
			var text = columns[k].ftext(j, k);
			if (typeof(text) == 'undefined') text = '';
			text = text.toString();
			var text_sort = text;
			if (text != '')
			{
				col_empty[k] = false;
				if (columns[k].fhref)
				{
					var hr = columns[k].fhref(j);
					if (hr != '') text = '<a class="dwr-index" href="' + hr + '">' + text + '</a>';
				}
			}
			if (columns[k].fsort)
			{
				text_sort = columns[k].fsort(j, k);
				if (typeof(text_sort) == 'undefined') text_sort = '';
				text_sort = text_sort.toString();
			}
			text_sort = text_sort.replace(/<[^>]*>/g, '');
			if (text_sort != '' && isNaN(parseInt(text_sort))) col_num[k] = false;
			line.push({
				'text': text,
				'sort': text_sort
			});
		}
		data_copy[j] = line;
	}

	// Remove empty columns
	var nb_cols_suppr = 0;
	for (k = 0; k < nb_cols; k++)
	{
		if (col_empty[k])
		{
			nb_cols_suppr += 1;
		}
		else if (nb_cols_suppr > 0)
		{
			columns[k - nb_cols_suppr] = columns[k];
			col_num[k - nb_cols_suppr] = col_num[k];
			if (defaultsort == k) defaultsort = k - nb_cols_suppr;
			for (j = 0; j < data_copy.length; j++)
			{
				data_copy[j][k - nb_cols_suppr] = data_copy[j][k];
			}
		}
	}
	nb_cols -= nb_cols_suppr;

	// Prepare columns definition for DataTables plugin
	var colDefs = []
	for (k=0; k < nb_cols; k++)
	{
		colDefs.push({
			'data': {
				'_': k + '.text',
				'display': k + '.text',
				'filter': k + '.sort',
				'sort': k + '.sort',
			},
			// 'width': '200px',
			'type': (col_num[k] ? 'num' : 'string')
		});
	}
	
	// Print table
	indexCounter ++;
	var html = '';
	if (data_copy.length == 0)
	{
		html += '<p>' + _('None.') + '</p>';
		return(html);
	}
	html += '<table id="dwr-index-' + indexCounter + '" class="table table-condensed table-bordered dt-table dt-responsive dwr-table-flat" width="100%">';
	html += '<thead><tr>';
	for (k=0; k < nb_cols; k++)
	{
		html += '<th class="dwr-index-title">';
		html += columns[k].title;
		html += '</th>';
	}
	html += '</tr></thead>';
	html += '<tbody>';
	html += '</tbody>';
	html += '</table>';

	// Build the DataTable, see http://www.datatables.net/
	(function(){ // This is used to create instances of local variables
		var id = '#dwr-index-' + indexCounter;
		$(document).ready(function() {
		// $("#example").DataTable();
			$(id).DataTable({
				'order': defaultsort,
				'info': false,
				'responsive': true,
				'columns': colDefs,
				'data': data_copy,
				'dom':
					'<"row"<"col-xs-12"f>>' +
					'<"row"<"col-xs-12"tr>>' +
					'<"row"<"col-xs-4"l><"col-xs-8"p>>',
				'language': {
					'emptyTable':     _('No data available in table'),
					'info':           _('Showing _START_ to _END_ of _TOTAL_ entries'),
					'infoEmpty':      _('Showing 0 to 0 of 0 entries'),
					'infoFiltered':   _('(filtered from _MAX_ total entries)'),
					'infoPostFix':    '',
					'thousands':      '',
					'lengthMenu':     _('Show _MENU_ entries'),
					'loadingRecords': _('Loading...'),
					'processing':     _('Processing...'),
					'search':         _('Search:'),
					'zeroRecords':    _('No matching records found'),
					'paginate': {
						'first':      '<span class="glyphicon glyphicon-step-backward"></span>',
						'last':       '<span class="glyphicon glyphicon-step-forward"></span>',
						'next':       '<span class="glyphicon glyphicon-chevron-right"></span>',
						'previous':   '<span class="glyphicon glyphicon-chevron-left"></span>'
					},
					'aria': {
						'sortAscending':  _(': activate to sort column ascending'),
						'sortDescending': _(': activate to sort column descending')
					}
				}
			});
		});
		$(window).load(function() {
			$(id).DataTable().columns.adjust().responsive.recalc();
		});
	})();

	return(html);
}



function printPersonsIndex(data)
{
	document.write(htmlPersonsIndex(data));
}
function htmlPersonsIndex(data)
{
	var html = '';
	if (typeof(data) == 'undefined')
	{
		html += '<h2 class="page-header">' + _('Persons Index') + '</h2>';
		data = [];
		for (var x = 0; x < I.length; x++) data.push(x);
	}
	var columns = [{
		title: _('Name'),
		ftext: function(x, col) {return(I[data[x]][I_NAME]);},
		fhref: function(x) {return(indiHref(data[x]));}
	}, {
		title: _('Gender'),
		ftext: function(x, col) {return(I[data[x]][I_GENDER]);}
	}];
	if (INDEX_SHOW_BIRTH) columns.push({
		title: _('Birth'),
		ftext: function(x, col) {return(I[data[x]][I_BIRTH_YEAR]);}
	});
	if (INDEX_SHOW_DEATH) columns.push({
		title: _('Death'),
		ftext: function(x, col) {return(I[data[x]][I_DEATH_YEAR]);}
	});
	if (INDEX_SHOW_PARTNER) columns.push({
		title: _('Spouses'),
		ftext: function(x, col) {
			var txt = '';
			var sep = '';
			for (var x_fams = 0; x_fams < I[data[x]][I_FAMS].length; x_fams++)
			{
				var spouses = F[I[data[x]][I_FAMS][x_fams]][F_SPOU];
				for (var x_spou = 0; x_spou < spouses.length; x_spou++)
				{
					if (spouses[x_spou] !== data[x])
					{
						txt += sep + '<a class="dwr-index" href="' + indiHref(spouses[x_spou]) + '">';
						txt += I[spouses[x_spou]][I_NAME] + '</a>';
						sep = '<br>';
					}
				}
			}
			return(txt);
		}
	});
	if (INDEX_SHOW_PARENTS) columns.push({
		title: _('Parents'),
		ftext: function(x, col) {
			var txt = '';
			var sep = '';
			for (var x_famc = 0; x_famc < I[data[x]][I_FAMC].length; x_famc++)
			{
				var parents = F[I[data[x]][I_FAMC][x_famc][FC_INDEX]][F_SPOU];
				for (var x_spou = 0; x_spou < parents.length; x_spou++)
				{
					if (parents[x_spou] !== data[x])
					{
						txt += sep + '<a class="dwr-index" href="' + indiHref(parents[x_spou]) + '">';
						txt += I[parents[x_spou]][I_NAME] + '</a>';
						sep = '<br>';
					}
				}
			}
			return(txt);
		}
	});
	html += printIndex(data, [0, 'asc'], columns);
	return(html);
}


function printIndexSpouseText(fdx, col)
{
	var gender = (col == 0)? 'M' : 'F';
	for (var j = 0; j < F[fdx][F_SPOU].length; j++)
		if (I[F[fdx][F_SPOU][j]][I_GENDER] == gender)
			return(I[F[fdx][F_SPOU][j]][I_NAME]);
	return('');
}

function printFamiliesIndex()
{
	document.write(htmlFamiliesIndex());
}
function htmlFamiliesIndex()
{
	var html = '';
	html += '<h2 class="page-header">' + _('Families Index') + '</h2>';
	var columns = [{
		title: _('Father'),
		ftext: printIndexSpouseText,
		fhref: famHref
	}, {
		title: _('Mother'),
		ftext: printIndexSpouseText,
		fhref: famHref
	}];
	if (INDEX_SHOW_MARRIAGE) columns.push({
		title: _('Marriage'),
		ftext: function(fdx, col) {return(F[fdx][F_MARR_YEAR]);}
	});
	html += printIndex(F, [0, 'asc'], columns);
	return(html);
}


function indexBkrefName(type, referenced_object, bk_field, objects, name_index)
{
	var ref = (function () {return("#")});
	if (objects === I) ref = indiHref;
	if (objects === F) ref = famHref;
	if (objects === S) ref = sourceHref;
	if (objects === M) ref = mediaHref;
	if (objects === P) ref = placeHref;
	var bk_table;
	if (type == BKREF_TYPE_SOURCE)
	{
		// Extract the list of object referencing the citations referencing the source
		var bk_table = [];
		for (var x_cita = 0; x_cita < referenced_object[S_BKC].length; x_cita++)
		{
			var citation = C[referenced_object[S_BKC][x_cita]];
			for (var x_bk = 0; x_bk < citation[bk_field].length; x_bk++) bk_table.push(citation[bk_field][x_bk]);
		}
	}
	else
	{
		bk_table = referenced_object[bk_field];
	}
	var txt = '';
	var sep = '';
	var already_found = [];
	for (var x_bk = 0; x_bk < bk_table.length; x_bk++)
	{
		var x_object;
		if (type == BKREF_TYPE_INDEX) x_object = bk_table[x_bk];
		if (type == BKREF_TYPE_MEDIA) x_object = bk_table[x_bk][MR_BK_IDX];
		if (type == BKREF_TYPE_SOURCE) x_object = bk_table[x_bk];
		if (type == BKREF_TYPE_REPO) x_object = bk_table[x_bk][RR_S_IDX];
		if ($.inArray(x_object, already_found) == -1)
		{
			already_found.push(x_object);
			var name = objects[x_object][name_index];
			if (name != '')
			{
				txt += sep + '<a class="dwr-index" href="' + ref(x_object) + '">';
				txt += objects[x_object][name_index] + '</a>';
				sep = '<br>';
			}
		}
	}
	return(txt);
}


function printMediaIndex(data)
{
	document.write(htmlMediaIndex(data));
}
function htmlMediaIndex(data)
{
	var html = '';
	if (typeof(data) == 'undefined')
	{
		html += '<h2 class="page-header">' + _('Media Index') + '</h2>';
		data = [];
		for (var x = 0; x < M.length; x++) data.push(x);
	}
	var columns = [{
		title: '',
		ftext: function(x, col) {return(
			'<a class="thumbnail" href="' + mediaHref(data[x], []) + '">' +
			'<img src="' + M[data[x]][M_THUMB] + '"></a>'
		);},
	}, {
		title: _('Title'),
		ftext: function(x, col) {return(M[data[x]][M_TITLE]);},
		fhref: function(x) {return(mediaHref(data[x]));}
	}, {
		title: _('Path'),
		ftext: function(x, col) {return(M[data[x]][M_GRAMPS_PATH]);},
		fhref: function(x) {return((M[data[x]][M_TITLE] == '') ? mediaHref(data[x]) : '');}
	}, {
		title: _('Date'),
		ftext: function(x, col) {return(M[data[x]][M_DATE]);},
		fsort: function(x, col) {return(M[data[x]][M_DATE_ISO]);}
	}];
	if (INDEX_SHOW_BKREF_TYPE) columns.push({
		title: _('Used for person'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_MEDIA, M[data[x]], M_BKI, I, I_NAME));}
	});
	if (INDEX_SHOW_BKREF_TYPE && INC_FAMILIES) columns.push({
		title: _('Used for family'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_MEDIA, M[data[x]], M_BKF, F, F_NAME));}
	});
	if (INDEX_SHOW_BKREF_TYPE && INC_SOURCES) columns.push({
		title: _('Used for source'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_MEDIA, M[data[x]], M_BKS, S, S_TITLE));}
	});
	if (INDEX_SHOW_BKREF_TYPE && INC_PLACES) columns.push({
		title: _('Used for place'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_MEDIA, M[data[x]], M_BKP, P, P_NAME));}
	});
	html += printIndex(data, [0, 'asc'], columns);
	return(html);
}


function printSourcesIndex(data)
{
	document.write(htmlSourcesIndex(data));
}
function htmlSourcesIndex(data)
{
	var html = '';
	if (typeof(data) == 'undefined')
	{
		html += '<h2 class="page-header">' + _('Sources Index') + '</h2>';
		data = [];
		for (var x = 0; x < S.length; x++) data.push(x);
	}
	var columns = [{
		title: _('Title'),
		ftext: function(x, col) {return(sourName(data[x]));},
		fhref: function(x) {return(sourceHref(data[x]));}
	}];
	if (INDEX_SHOW_BKREF_TYPE) columns.push({
		title: _('Used for person'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_SOURCE, S[data[x]], C_BKI, I, I_NAME));}
	});
	if (INDEX_SHOW_BKREF_TYPE && INC_FAMILIES) columns.push({
		title: _('Used for family'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_SOURCE, S[data[x]], C_BKF, F, F_NAME));}
	});
	if (INDEX_SHOW_BKREF_TYPE && INC_MEDIA) columns.push({
		title: _('Used for media'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_SOURCE, S[data[x]], C_BKM, S, S_TITLE));}
	});
	if (INDEX_SHOW_BKREF_TYPE && INC_PLACES) columns.push({
		title: _('Used for place'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_SOURCE, S[data[x]], C_BKP, P, P_NAME));}
	});
	html += printIndex(data, [0, 'asc'], columns);
	return(html);
}


function printPlacesIndexColText(pdx, col)
{
	if (P[pdx][P_LOCATIONS].length == 0) return('');
	return(P[pdx][P_LOCATIONS][0][8 - col]);
}

function printPlacesIndexColCoord(pdx, col)
{
	var c = P[pdx][P_COORDS][col - 9];
	if (c == '') return('');
	c = Number(c);
	var txt = '000' + Math.abs(c).toFixed(4);
	txt = txt.substr(txt.length - 8);
	txt = ((c < 0)? '-' : '+') + txt;
	return(txt);
}

function printPlacesIndex(data)
{
	document.write(htmlPlacesIndex(data));
}
function htmlPlacesIndex(data)
{
	var html = '';
	if (typeof(data) == 'undefined')
	{
		html += '<h2 class="page-header">' + _('Places Index') + '</h2>';
		data = [];
		for (var x = 0; x < P.length; x++) data.push(x);
	}
	var columns = [{
		title: _('Name'),
		ftext: function(x, col) {return(P[data[x]][P_NAME]);},
		fhref: function(x) {return(placeHref(data[x]));}
	}, {
		title: _('Country'),
		ftext: printPlacesIndexColText
	}, {
		title: _('Postal Code'),
		ftext: printPlacesIndexColText
	}, {
		title: _('State/ Province'),
		ftext: printPlacesIndexColText
	}, {
		title: _('County'),
		ftext: printPlacesIndexColText
	// }, {
		// title: _('Church Parish'),
		// ftext: printPlacesIndexColText
	}, {
		title: _('City'),
		ftext: printPlacesIndexColText
	// }, {
		// title: _('Locality'),
		// ftext: printPlacesIndexColText
	// }, {
		// title: _('Street'),
		// ftext: printPlacesIndexColText
	}, {
		title: _('Latitude'),
		ftext: function(x, col) {
			if (P[data[x]][P_COORDS][0] == '') return('');
			return(Number(P[data[x]][P_COORDS][0]));
		}
	}, {
		title: _('Longitude'),
		ftext: function(x, col) {
			if (P[data[x]][P_COORDS][1] == '') return('');
			return(Number(P[data[x]][P_COORDS][1]));
		}
	}];
	if (INDEX_SHOW_BKREF_TYPE) columns.push({
		title: _('Used for person'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_INDEX, P[data[x]], P_BKI, I, I_NAME));}
	});
	if (INDEX_SHOW_BKREF_TYPE && INC_FAMILIES) columns.push({
		title: _('Used for family'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_INDEX, P[data[x]], P_BKF, F, F_NAME));}
	});
	html += printIndex(data, [0, 'asc'], columns);
	return(html);
}



function printAddressesIndex()
{
	document.write(htmlAddressesIndex());
}
function htmlAddressesIndex()
{
	// Build addresses table
	var adtable = [];
	var empty_loc = [];
	var empty_url = ['', ''];
	for (var x_i = 0; x_i < I.length; x_i++)
	{
		var i = I[x_i];
		for (var x_ad = 0; x_ad < i[I_ADDRS].length; x_ad++)
			adtable.push([x_i, i[I_ADDRS][x_ad][AD_LOCATION], empty_url])
		for (var x_url = 0; x_url < i[I_URLS].length; x_url++)
			adtable.push([x_i, empty_loc, i[I_URLS][x_url]])
	}
	// Print table
	var html = '';
	html += '<h2 class="page-header">' + _('Addresses') + '</h2>';
	var columns = [{
		title: _('Person'),
		ftext: function(x_ad, col) {return(I[adtable[x_ad][0]][I_NAME]);},
		fhref: function(x_ad) {return(indiHref(adtable[x_ad][0]));}
	}, {
		title: _('Address'),
		ftext: function(x_ad, col) {return(locationString(adtable[x_ad][1]));},
	}, {
		title: _('Web Link'),
		ftext: function(x_ad, col) {return(adtable[x_ad][2][2] || adtable[x_ad][2][1]);},
		fhref: function(x_ad) {return(adtable[x_ad][2][1]);}
	}];
	html += printIndex(adtable, [0, 'asc'], columns);
	return(html);
}



function printReposIndex()
{
	document.write(htmlReposIndex());
}
function htmlReposIndex()
{
	var html = '';
	html += '<h2 class="page-header">' + _('Repositories') + '</h2>';
	var columns = [{
		title: _('Repository'),
		ftext: function(rdx, col) {return(R[rdx][R_NAME]);},
		fhref: repoHref
	}, {
		title: _('Type'),
		ftext: function(rdx, col) {return(R[rdx][R_TYPE]);},
	}, {
		title: _('Addresses'),
		ftext: function(rdx, col) {
			return(($.map(R[rdx][R_ADDRS], locationString)).join('<br>'));
		},
	}, {
		title: _('Web Links'),
		ftext: function(rdx, col) {
			return(($.map(R[rdx][R_URLS], function(url) {
				return('<a class="dwr-index" href="' + url[1] + '">' + (url[2] || url[1]) + '</a>');
			})).join('<br>'));
		},
	}];
	if (INDEX_SHOW_BKREF_TYPE && INC_SOURCES) columns.push({
		title: _('Used for source'),
		ftext: function(rdx, col) {return(indexBkrefName(BKREF_TYPE_REPO, R[rdx], R_BKS, S, S_TITLE));}
	});
	html += printIndex(R, [0, 'asc'], columns);
	return(html);
}


//=================================================================
//================================================== Surnames index
//=================================================================

function printSurnameIndex()
{
	ParseSearchString();
	if (search.SNdx >= 0)
	{
		if (SN[search.SNdx][1].length == 0)
		{
			document.write('<p>' + _('No matching surname.') + '</p>');
		}
		else if (SN[search.SNdx][1].length == 1)
		{
			indiRef(SN[search.SNdx][1][0]);
		}
		else
		{
			document.write('<h2 class="page-header">', ((SN[search.SNdx][SN_SURNAME].length > 0) ? SN[search.SNdx][SN_SURNAME] : '<i>' + _('Without surname') + '</i>'), '</h2>');
			document.write(htmlPersonsIndex(SN[search.SNdx][SN_PERSONS]));
		}
	}
	else
	{
		printSurnamesIndex();
	}
}

function surnameString(sndx, surname, number)
{
	if (surname == '') surname = _('Without surname');
	return(
		'<span class="dwr-nowrap"><a href="surname.html?' + BuildSearchString({SNdx: sndx}) + '">' +
		surname + '</a> <span class="badge">' + number + '</span></span> ');
}

function printSurnamesIndex()
{
	ParseSearchString();
	document.write(
		'<h2 class="page-header">' +
		_('Surnames Index') +
		' <small><a href="surnames2.html?' + BuildSearchString() + '">' +
		_('(sort by quantity)') +
		'</a></small>' +
		'</h2>');

	// Build the surnames titles and texts
	var titles = [];
	var texts = [];
	for (i = 0; i < SN.length; i++)
	{
		if (SN[i][SN_SURNAME].length > 0)
		{
			var letter = SN[i][SN_SURNAME].latinize().substring(0, 1).toUpperCase();
			if ($.inArray(letter, titles) == -1)
			{
				// New initial for the surname
				titles.push(letter);
				texts[letter] = '';
			}
			texts[letter] += surnameString(i, SN[i][SN_SURNAME], SN[i][SN_PERSONS].length);
		}
		else
		{
			// Empty surname
			titles.push('');
			texts[''] = surnameString(i, SN[i][SN_SURNAME], SN[i][SN_PERSONS].length);
		}
	}
	// Print surnames as bootstrap collapsible panels
	for (i = 0; i < titles.length; i++)
	{
		var letter = titles[i];
		var txt = '';
		txt += '<div class="panel panel-default">';
		if (letter != '')
		{
			txt += '<div class="panel-heading dwr-collapsible collapsed" data-toggle="collapse" data-target="#panel_surname_' + i + '">';
			txt += '<h5 class="panel-title">' + letter + '</h5>';
			txt += '</div>';
			txt += '<div id="panel_surname_' + i + '" class="panel-collapse collapse">';
			txt += '<div class="panel-body">';
			txt += texts[letter];
			txt += '</div>';
			txt += '</div>';
		}
		else
		{
			txt += '<div id="panel_surname_' + i + '" class="panel-collapse collapse in">';
			txt += '<div class="panel-body">';
			txt += texts[letter];
			txt += '</div>';
			txt += '</div>';
		}
		txt += '</div>';
		document.write(txt);
	}
}

function printSurnamesIndex2()
{
	ParseSearchString();
	document.write(
		'<h2 class="page-header">' +
		_('Surnames Index') +
		' <small><a href="surnames.html?' + BuildSearchString() + '">' +
		_('(sort by name)') +
		'</a></small>' +
		'</h2>');

	// Build the surnames data
	var surnames = [];
	for (i = 0; i < SN.length; i++)
	{
		surnames.push({
			number: SN[i][SN_PERSONS].length,
			name: SN[i][SN_SURNAME],
			sndx: i
		});
	}
	surnames.sort(function(a, b) {return(b.number - a.number)});
	
	// Print surnames as bootstrap collapsible panels
	for (i = 0; i < surnames.length; i++)
	{
		var surname = surnames[i];
		document.write(surnameString(surname.sndx, surname.name, surname.number));
	}
}


//=================================================================
//================================================= Back references
//=================================================================

BKREF_TYPE_INDEX = 0;
BKREF_TYPE_MEDIA = 1;
BKREF_TYPE_SOURCE = 2;
BKREF_TYPE_REPO = 3;

function printBackRefs(type, bki, bkf, bks, bkm, bkp, bkr)
{
	var html = '';
	html += printBackRef(type, bki, indiHref, function(ref) {return(I[ref][I_NAME]);});
	if (INC_FAMILIES)
		html += printBackRef(type, bkf, famHref, function(ref) {return(F[ref][F_NAME]);});
	if (INC_SOURCES)
		html += printBackRef(type, bks, sourceHref, sourName);
	if (INC_MEDIA)
		html += printBackRef(type, bkm, mediaHref, mediaName);
	if (INC_PLACES)
		html += printBackRef(type, bkp, placeHref, function(ref) {return(P[ref][P_NAME]);});
	if (INC_REPOSITORIES)
		html += printBackRef(type, bkr, repoHref, function(ref) {return(R[ref][R_NAME]);});
	if (html == '') return('');
	return('<ul class="dwr-backrefs">' + html + '</ul>');
}

function printBackRef(type, bk_table, fref, fname)
{
	var html = '';
	var j;
	for (j = 0; j < bk_table.length; j++)
	{
		var ref = bk_table[j];
		var txt = '';
		if (type == BKREF_TYPE_INDEX)
		{
			// This is a citation, person or family back reference
			txt = '<a href="' + fref(ref) + '">' + fname(ref) + '</a>';
		}
		else if (type == BKREF_TYPE_MEDIA)
		{
			// This is a media back reference
			txt = '<a href="' + fref(ref[MR_BK_IDX]) + '">' + fname(ref[MR_BK_IDX]) + '</a>';
			txt += ' ' + citaLinks(ref[MR_CITA]);
			if (ref[MR_NOTE] != '')
			{
				txt = '<div>' + txt;
				txt += notePara(ref[MR_NOTE], '<p>');
				txt += '</div>';
			}
		}
		else if (type == BKREF_TYPE_REPO)
		{
			// This is a media back reference
			txt = '<a href="' + fref(ref[RR_R_IDX]) + '">' + fname(ref[RR_R_IDX]) + '</a>';
			if (ref[RR_MEDIA_TYPE] != '')
				txt += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Media Type') + ': </span>' + ref[RR_MEDIA_TYPE] + '</p>';
			if (ref[RR_CALL_NUMBER] != '')
				txt += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Call Number') + ': </span>' + ref[RR_CALL_NUMBER] + '</p>';
			if (ref[RR_NOTE] != '')
			{
				txt = '<div>' + txt;
				txt += notePara(ref[RR_NOTE], '<p>');
				txt += '</div>';
			}
		}
		html += '<li>' + txt + '</li>';
	}
	return(html);
}


//=================================================================
//============================================================ Maps
//=================================================================

var mapObject;


function printMap()
{
	var html = '';
	// Check if there is at least 1 place with coordinates defined
	var found = false;
	for (var j = 0; j < pagePlaces.length; j++)
	{
		var pdx = pagePlaces[j][PP_PDX];
		if (P[pdx][P_COORDS].join('') != '') found = true;
	}
	if (!found) return('');
	// Schedule the differed update of the map
	$(window).load(mapUpdate)
	// Build HTML
	html += printTitle(5, _('Map') +
		' <a tabindex="0" data-toggle="popover" data-placement="bottom" title="" data-trigger="focus" data-content="' +
		_('Click on the map to show it fullscreen') +
		'"><span class="glyphicon glyphicon-question-sign"></span></a>',
		'dwr-panel-map');
	html += '<div id="gmap_canvas">';
	html += '</div>';
	html += printTitleEnd();
	if (search.mapExpanded)
	{
		$('body').toggleClass('dwr-fullscreen');
		$('body > div').css('display', 'none');
	}
	return(html);
}


function mapUpdate()
{
	// Check if online
	if (MAP_SERVICE == 'Google' && typeof(google) == 'undefined') return;
	if (MAP_SERVICE == 'OpenStreetMap' && typeof(ol) == 'undefined') return;
	// Expand map if required
	if (search.mapExpanded)
	{
		$('body').prepend($('#gmap_canvas'));
		$('#gmap_canvas').addClass('dwr-map-expanded');
		mapResizeDivs();
		$(window).resize(mapResize);
	}
	// Get all the coordinates, SW and NE coordinates
	var mapCoords = []; // List of markers coordinates
	var mapGotit = []; // List of markers coordinates already found
	var markerPaces = []; // List of markers places index in table pagePlaces
	var south = 1e10;
	var north = -1e10;
	var west = -1e10;
	var east = 1e10;
	var osmFromProj = 'EPSG:4326';
	var osmToProj = 'EPSG:3857';
	for (var x_place = 0; x_place < pagePlaces.length; x_place++)
	{
		var pdx = pagePlaces[x_place][PP_PDX];
		var lat = Number(P[pdx][P_COORDS][0]);
		var lon = Number(P[pdx][P_COORDS][1]);
		var sc = P[pdx][P_COORDS].join('');
		// Check if coordinates are valid
		if (sc != '')
		{
			var x_marker = $.inArray(sc, mapGotit);
			// Check if coordinates are not already in the list
			if (x_marker == -1)
			{
				x_marker = mapGotit.length;
				mapGotit.push(sc);
				markerPaces[x_marker] = [];
			}
			if (MAP_SERVICE == 'Google')
			{
				mapCoords[x_marker] = new google.maps.LatLng(lat, lon);
			}
			else if (MAP_SERVICE == 'OpenStreetMap')
			{
				// mapCoords[mapCoords.length] = [lon, lat];
				mapCoords[x_marker] = ol.proj.transform([lon, lat], osmFromProj, osmToProj);
			}
			markerPaces[x_marker].push(x_place);
			south = Math.min(south, lat);
			north = Math.max(north, lat);
			west = Math.max(west, lon);
			east = Math.min(east, lon);
		}
	}
	// Compute optimal zoom
	var angleW = west - east;
	if (angleW < 0) angleW += 360;
	var zoom = 7;
	if (angleW > 0)
	{
		var GLOBE_WIDTH = 256;
		var GLOBE_HEIGHT = 256;
		var pixelW = $('#gmap_canvas').width();
		var zoomW = Math.log(pixelW * 360 / angleW / GLOBE_WIDTH) / Math.LN2;
		function latRad(lat) {
			var sin = Math.sin(lat * Math.PI / 180);
			var radX2 = Math.log((1 + sin) / (1 - sin)) / 2;
			return Math.max(Math.min(radX2, Math.PI), -Math.PI) / 2;
		}
		var angleH = latRad(north) - latRad(south);
		var pixelH = $('#gmap_canvas').height();
		var zoomH = Math.log(pixelH * Math.PI / angleH / GLOBE_HEIGHT) / Math.LN2;
		zoom = Math.floor(Math.min(zoomW, zoomH) / 1.1);
		zoom = Math.min(zoom, 15);
		zoom = Math.max(zoom, 1);
	}
	// Update map
	var osmVectorSource;
	// var osmMarkers;
	if (MAP_SERVICE == 'Google')
	{
		var centerCoord = new google.maps.LatLng((south + north) / 2, (west + east) / 2);
		var mapOptions = {
			scaleControl:    true,
			panControl:      true,
			backgroundColor: '#000000',
			draggable:       true,
			zoom:            zoom,
			center:          centerCoord,
			mapTypeId:       google.maps.MapTypeId.ROADMAP
		}
		mapObject = new google.maps.Map(document.getElementById('gmap_canvas'), mapOptions);
		// Expand event
		google.maps.event.addListener(mapObject, 'click', mapExpand);
	}
	else if (MAP_SERVICE == 'OpenStreetMap')
	{
		var centerCoord = [(west + east) / 2, (south + north) / 2];
		// map = L.map('gmap_canvas');
		// map.setView(centerCoord, zoom);
		// L.tileLayer("http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            // attribution: "© <a href='http://openstreetmap.org'>OpenStreetMap</a> contributors",
		// }).addTo(map);
		var centerCoord = ol.proj.transform([(west + east) / 2, (south + north) / 2], osmFromProj, osmToProj);
		mapObject = new ol.Map({
			target: $('#gmap_canvas')[0],
			layers: [
				new ol.layer.Tile({
					source: new ol.source.OSM()
				})
			],
			view: new ol.View({
				center: centerCoord,
				zoom: zoom
			})
		});
		osmVectorSource = new ol.source.Vector({});
		// osmMarkers = new ol.Layer.Markers('Markers');
		// Expand event
		mapObject.on('singleclick', mapExpand);
	}
	// Place markers
	for (var x_marker = 0; x_marker < mapCoords.length; x_marker++)
	{
		// Sort markerPaces by name
		markerPaces[x_marker].sort(function(a, b) {
			return(P[pagePlaces[a][PP_PDX]][P_NAME].localeCompare(P[pagePlaces[b][PP_PDX]][P_NAME]));
		});
		// Build markers data
		var mapName = '';
		var mapInfo = '';
		var previous_pdx = -1;
		var previous_ul = false;
		for (var x_place = 0; x_place < markerPaces[x_marker].length; x_place++)
		{
			var pp = pagePlaces[markerPaces[x_marker][x_place]];
			var pdx = pp[PP_PDX];
			if (pdx != previous_pdx)
			{
				if (mapName) mapName += '\n';
				mapName += P[pdx][P_NAME];
				if (previous_ul) mapInfo += '</ul>';
				mapInfo += '<p class="dwr-mapinfo"><a href="' + placeHref(pdx) + '">' + P[pdx][P_NAME] + '</a></p>';
				previous_pdx = pdx;
				previous_ul = false;
			}
			var txt = '';
			if (pp[PP_IDX] >= 0) txt += indiLinked(pp[PP_IDX], false);
			if (pp[PP_FDX] >= 0) txt += famLinked(pp[PP_FDX], false);
			if (pp[PP_EVENT]) txt += ' (' + (pp[PP_EVENT][E_TYPE] || pp[PP_EVENT][E_DESCR]) + ')';
			if (txt)
			{
				if (!previous_ul) mapInfo += '<ul class="dwr-mapinfo">';
				previous_ul = true;
				mapInfo += '<li class="dwr-mapinfo">' + txt + '</li>';
			}
		}
		if (previous_ul) mapInfo += '</ul>';
		// Print marker
		if (MAP_SERVICE == 'Google')
		{
			(function(){ // This is used to create instances of local variables
				var marker = new google.maps.Marker({
					position:  mapCoords[x_marker],
					draggable: true,
					title:     mapName,
					map:       mapObject
				});
				var infowindow = new google.maps.InfoWindow({
					content: mapInfo
				});
				google.maps.event.addListener(marker, 'click', function() {
					infowindow.open(mapObject, marker);
				});
			})();
		}
		else if (MAP_SERVICE == 'OpenStreetMap')
		{
			(function(){ // This is used to create instances of local variables
				var popupname = 'OsmPopup' + x_marker;
				// Create the OpenLayers icon
				var coord = new ol.geom.Point(mapCoords[x_marker]);
				var iconFeature = new ol.Feature({
					geometry: coord,
					name: popupname
				});
				osmVectorSource.addFeature(iconFeature);
				// Create the OpenLayers overlay div
				var popupdiv = $('#gmap_canvas').append('<div id="' + popupname + '"></div>').children().last();
				var popup = new ol.Overlay({
					element: popupdiv[0],
					positioning: 'top-center',
					stopEvent: false
				});
				mapObject.addOverlay(popup);
				// Create the bootstrap popup
				popupdiv.popover({
					'placement': 'top',
					'html': true,
					'title': mapName,
					'content': mapInfo
				});
				popupdiv.popover('hide');
			})();
		}
	}
	if (MAP_SERVICE == 'OpenStreetMap')
	{
		var iconStyle = new ol.style.Style({
			image: new ol.style.Icon(({
				anchor: [0.0, 1.0],
				anchorXUnits: 'fraction',
				anchorYUnits: 'fraction',
				src: 'data/gramps-geo-altmap.png'
			}))
		});
		var vectorLayer = new ol.layer.Vector({
			source: osmVectorSource,
			style: iconStyle
		});
		mapObject.addLayer(vectorLayer);
		mapObject.on('click', OsmClick);
		$(mapObject.getViewport()).on('mousemove', OsmMove);
	}
}


function mapExpand()
{
	search.mapExpanded = !search.mapExpanded;
	Redirect();
	return(false);
}


function mapResizeDivs()
{
	var w = $(window).width();
	var h = $(window).height();
	$('#gmap_canvas').width(w);
	$('#gmap_canvas').height(h);
}


function mapResize()
{
	if (!search.mapExpanded) return(true);
	mapResizeDivs();
	mapObject.checkResize();
	return(true);
}

function OsmClick(event)
{
	// Display OpenLayers popup on click

	// Get the popup divs
	var popupdivs = $('#gmap_canvas').find('div').filter(function(index) {
		return(this.id.indexOf('OsmPopup') == 0);
	})

	// Get the icon clicked
	var feature = mapObject.forEachFeatureAtPixel(event.pixel, function(feature, layer) {
		return feature;
	});
	var popupname = '';
	var coord;
	if (feature)
	{
		var geometry = feature.getGeometry();
		coord = geometry.getCoordinates();
		popupname = feature.get('name');
	}

	// Hide all OpenLayers popups except the for clicked icon
	var overlays = mapObject.getOverlays();
	var overlay;
	for (var i = 0; i < overlays.getLength(); i++)
	{
		if (overlays.item(i).getElement().id == popupname) overlay = overlays.item(i);
	}
	popupdivs.each(function() {
		if (this.id == popupname)
		{
			overlay.setPosition(coord);
			$(this).popover('show');
		}
		else
		{
			$(this).popover('hide');
		}
	});
}

function OsmMove(event)
{
	// Change OpenLayers mouse cursor when over marker
	var pixel = mapObject.getEventPixel(event.originalEvent);
	var hit = mapObject.forEachFeatureAtPixel(pixel, function(feature, layer) {
		return true;
	});
	if (hit)
	{
		$(mapObject.getTarget()).css('cursor', 'pointer');
	}
	else
	{
		$(mapObject.getTarget()).css('cursor', '');
	}
}


//=================================================================
//================================================== Search by name
//=================================================================

function SearchFromString(ss, data, fextract)
{
	ss = ss.latinize();
	ss = ss.replace(/[^a-zA-Z0-9]+/g, ' ');
	ss = ss.toLowerCase();
	var terms = ss.match(/[^\s]+/ig);
	var results = [];
	if (terms == null) return(results);
	for (var x = 0; x < data.length; x++)
	{
		var found = true;
		var s = fextract(x);
		s = s.latinize();
		s = s.replace(/[^a-zA-Z0-9]+/g, ' ');
		s = s.toLowerCase();
		for (var j = 0; j < terms.length; j++)
		{
			if (s.match(terms[j]) == null) found = false;
		}
		if (found) results.push(x);
		// console.log(found + ": "+ ss+"  /  "+s);
	}
	return(results);
}


function SearchObjects()
{
	var types = [
		{
			data: I,
			fextract: function(idx) {
				return(I[idx][I_NAME] + ' ' + I[idx][I_BIRTH_YEAR] + ' ' + I[idx][I_DEATH_YEAR]);
			},
			text: _('Persons found:'),
			findex: htmlPersonsIndex,
			fref: indiRef
		},
		{
			data: M,
			fextract: function(mdx) {return(M[mdx][M_TITLE] + ' ' + M[mdx][M_PATH]);},
			text: _('Media found:'),
			findex: htmlMediaIndex,
			fref: mediaRef
		},
		{
			data: S,
			fextract: function(sdx) {return(S[sdx][S_TITLE]);},
			text: _('Sources found:'),
			findex: htmlSourcesIndex,
			fref: sourceRef
		},
		{
			data: P,
			fextract: function(pdx) {return(P[pdx][P_NAME]);},
			text: _('Places found:'),
			findex: htmlPlacesIndex,
			fref: placeRef
		}
	];
	var x;
	var nb_found = 0;
	var fref;
	var index;
	var html = '';
	for (x = 0; x < types.length; x++)
	{
		var results;
		var type = types[x];
		results = SearchFromString(search.Txt, type.data, type.fextract);
		nb_found += results.length;
		if (results.length == 1 && x == 0)
		{
			// Only 1 person found, redirect to the person page
			fref = type.fref;
			index = results[0];
			break;
		}
		if (results.length > 0)
		{
			fref = type.fref;
			index = results[0];
			html += '<h4>' + type.text + '</h4>';
			html += type.findex(results);
		}
	}
	if (nb_found == 1)
	{
		fref(index);
		html = '';
	}
	else if (nb_found == 0)
	{
		html = '';
		if (search.Txt != '')
		{
			html += '<p>' + _('There is no matching name.') + '</p>';
			$('#dwr-search-txt').focus();
		}
		html += '<p>' + _('Use the search box above in order to find a person.<br>Women are listed with their maiden name.') + '</p>';
	}
	else
	{
		html = ('<p>' + _('Several matches.<br>Precise your search or choose in the lists below.') + '</p>') + html;
	}
	return(html);
}


//=================================================================
//======================================================= Affichage
//=================================================================

var ArbreType;

function arbreMain(arbreType)
{
	ArbreType = arbreType;

	ParseSearchString();

	$(document).ready(function(){
		arbreMainSub();
	});
}

function arbreMainSub()
{
	var html = '';

	if (search.Idx >= 0 && ArbreType == PAGE_SVG_TREE)
	{
		searchImplex(search.Idx);
		// SVG tree
		html += SvgCreate();
	}
	else if (search.Idx >= 0 && ArbreType == PAGE_SVG_TREE_FULL)
	{
		searchImplex(search.Idx);
		html = SvgCreate(true);
		$('body').html(html).toggleClass('dwr-fullscreen');
	}
	else if (search.Sdx >= 0 && ArbreType == PAGE_SOURCE)
	{
		// Print 1 source
		html += printSource(search.Sdx);
	}
	else if (search.Mdx >= 0 && ArbreType == PAGE_MEDIA)
	{
		// Print 1 media
		html += printMedia(search.Mdx);
	}
	else if (search.Idx >= 0 && ArbreType == PAGE_INDI)
	{
		// Print individual
		html += printIndi(search.Idx);
	}
	else if (search.Fdx >= 0 && ArbreType == PAGE_FAM)
	{
		// Print individual
		html += printFam(search.Fdx);
	}
	else if (search.Pdx >= 0 && ArbreType == PAGE_PLACE && INC_PLACES)
	{
		// Print place
		html += printPlace(search.Pdx);
	}
	else if (search.Rdx >= 0 && ArbreType == PAGE_REPO)
	{
		// Print repository
		html += printRepo(search.Rdx);
	}
	else if (ArbreType == PAGE_SEARCH)
	{		
		// Print search by name results
		html = SearchObjects();
	}
	else
	{
		// Page without index specified. Redirect to the search page
		window.location.href = searchHref();
	}

	$('#body-page').html(html);

	handleCitations();
	handleTitles();
	// $('.dt-table').DataTable();
}
