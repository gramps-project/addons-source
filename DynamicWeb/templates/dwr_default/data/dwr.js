// Gramps - a GTK+/GNOME based genealogy program
//
// Copyright (C) 2014 Pierre Bélissent
//
// This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
// This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
// You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


//=================================================================
//=================================== Database exported from Gramps
//=================================================================

// Initialize empty arrays by default
// Depending on generation options, not all the lists are generated

if (typeof(I) == 'undefined') I = []
if (typeof(F) == 'undefined') F = []
if (typeof(S) == 'undefined') S = []
if (typeof(R) == 'undefined') R = []
if (typeof(M) == 'undefined') M = []
if (typeof(P) == 'undefined') P = []
if (typeof(SN) == 'undefined') SN = []


// Events fallbacks

EVENTS_BIRTH = [_('Birth'), _('Baptism'), _('Christening')];
EVENTS_MARR = [_('Marriage'), _('Engagement'), _('Alternate Marriage')];
EVENTS_DEATH = [_('Death'), _('Burial'), _('Cremation'), _('Cause Of Death')];


// Number of entries in the tables
A_LENGTH_MENU = [[10, 50, 100, 500, 1000, -1], [10, 50, 100, 500, 1000, _('all')]]


//=================================================================
//======================================================= Constants
//=================================================================

// Type of the page
var i = 1;
PAGE_INDI = i++;
PAGE_FAM = i++;
PAGE_SOURCE = i++;
PAGE_MEDIA = i++;
PAGE_PLACE = i++;
PAGE_REPO = i++;
PAGE_SEARCH = i++;
PAGE_CONF = i++;
PAGE_SVG_TREE = i++;
PAGE_SVG_TREE_FULL = i++;
PAGE_SVG_TREE_CONF = i++;
PAGE_SVG_TREE_SAVE = i++;
PAGE_STATISTICS = i++;


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
		MapExpanded: false // Reset map
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
		MapExpanded: false // Reset map
	}));
}

function famRef(fdx)
{
	// Go to the Family page
	
	window.location.href = famHref(fdx);
	return(false);
}

function mediaHref(mdx, m_list)
{
	// Get the media page address
	
	mdx = (typeof(mdx) !== 'undefined') ? mdx : search.Mdx;
	m_list = (typeof(m_list) !== 'undefined') ? m_list : [];
	var lt = '';
	if (search.Mdx >= 0 && PageContents == PAGE_MEDIA)
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
		m_list[j] = mr_list[j].m_idx;
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
	// Get the SVG tree page

	if (typeof(idx) == 'undefined') idx = search.Idx;
	if (typeof(expand) == 'undefined') expand = search.SvgExpanded;
	var page;
	if (expand)
	{
		page = 'tree_svg_full.html';
	}
	else
	{
		page = 'tree_svg.html';
	}
	return(page + '?' + BuildSearchString({
		Idx: idx,
		SvgExpanded: expand,
	}));
}

function svgRef(idx, expand)
{
	// Go to the SVG tree page
	window.location.href = svgHref(idx, expand);
	return(false);
}

function svgConfRef()
{
	// Go to the SVG tree configuration page
	window.location.href = 'tree_svg_conf.html?' + BuildSearchString();
	return(false);
}

function svgSaveRef()
{
	// Go to the SVG tree save-as page
	window.location.href = 'tree_svg_save.html?' + BuildSearchString();
	return(false);
}

function placeHref(pdx)
{
	// Get to the place page address
	
	pdx = (typeof(pdx) !== 'undefined') ? pdx : search.Pdx;
	return('place.html?' + BuildSearchString({
		Pdx: pdx,
		MapExpanded: false // Reset map
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
		MapExpanded: false // Reset map
	}));
}

function repoRef(rdx)
{
	// Go to the repository page
	
	window.location.href = repoHref(rdx);
	return(false);
}


//=================================================================
//====================================================== Duplicates
//=================================================================

// List of the persons index 'idx' of table 'I', that appear several times in the ancestors or descendants of the center person
var duplicates = [];


function searchDuplicate(idx)
{
	// Recursively search for duplicates in ancestors and descendants of person 'idx'
	// The search is limited to search.Asc ascending generations and search.Dsc descending generations
	
	duplicates = [];
	searchDuplicateAsc(idx, search.Asc, []);
	searchDuplicateDsc(idx, search.Dsc, []);
}


function searchDuplicateAsc(idx, lev, found)
{
	// Recursively search for duplicates in ancestors of person 'idx',
	// limited to "lev" generations.
	// "found" contains all the persons found in the tree traversal
	
	if (($.inArray(idx, found) >= 0) && ($.inArray(idx, duplicates) < 0))
	{
		duplicates.push(idx);
		return;
	}
	found.push(idx);
	if (lev <= 0) return;
	for (var x_fam = 0; x_fam < I[idx].famc.length; x_fam++)
	{
		var fam = F[I[idx].famc[x_fam].index];
		for (var x_spou = 0; x_spou < fam.spou.length; x_spou++)
			searchDuplicateAsc(fam.spou[x_spou], lev - 1, found);
	}
}


function searchDuplicateDsc(idx, lev, found)
{
	// Recursively search for duplicates in descendants of person 'idx',
	// limited to "lev" generations.
	// "found" contains all the persons found in the tree traversal
	
	if (($.inArray(idx, found) >= 0) && ($.inArray(idx, duplicates) < 0))
	{
		duplicates.push(idx);
	}
	found.push(idx);
	if (lev <= 0) return;
	for (var x_fam = 0; x_fam < I[idx].fams.length; x_fam++)
	{
		var fam = F[I[idx].fams[x_fam]];
		if (!isDuplicate(idx))
			for (var x_chil = 0; x_chil < fam.chil.length; x_chil++)
				searchDuplicateDsc(fam.chil[x_chil].index, lev - 1, found);
		for (var x_spou = 0; x_spou < fam.chil.length; x_spou++)
			if (idx != fam.spou[x_spou])
				searchDuplicateDsc(fam.spou[x_spou], -1, found);
	}
}


function isDuplicate(idx)
{
	return($.inArray(idx, duplicates) >= 0);
}


//=================================================================
//================================= Text for individuals / families
//=================================================================

function indiLinked(idx, citations)
{
	citations = (typeof(citations) !== 'undefined') ? citations : true;
	var txt = I[idx].name + ' (' + I[idx].birth_year + '-' + I[idx].death_year + ')';
	txt += gidBadge(I[idx]);
	if (citations) txt += citaLinks(I[idx].cita);
	if (idx != search.Idx || PageContents != PAGE_INDI)
		txt = '<a href="' + indiHref(idx) + '">' + txt + '</a>';
	return(txt);
}

function gidBadge(o)
{
	var txt = '';
	if (!search.HideGid) txt = ' <span class="dwr-gid badge">' + o.gid + '</span>';
	return(txt);
}

GENDERS_TEXT = {
	'M': _('Male'),
	'F': _('Female'),
	'U': _('Unknown')
};
GENDERS_TEXT_ORDER = [
	GENDERS_TEXT['M'],
	GENDERS_TEXT['F'],
	GENDERS_TEXT['U']
];

function indiDetails(i)
{
	var txt = '';
	var x_name;
	txt += '<table class="table table-condensed table-bordered dwr-table-flat">';
	// txt += '<table class="dt-table dwr-table-flat">';
	for (x_name = 0; x_name < i.names.length; x_name++)
	{
		var name = i.names[x_name];
		var name_full = name.full;
		if (name.date != '') name_full += ' (' + name.date + ')';
		if (name.cita.length > 0) name_full += citaLinks(name.cita);
		txt += '<tr><td class="dwr-attr-title">' + name.type + '</td><td colspan="2" class="dwr-attr-value">' + name_full + '</td></tr>';
		if (name.nick != '') txt += '<tr><td class="empty"></td><td class="dwr-attr-title">' + _('Nick Name') + '</td><td class="dwr-attr-value">' + name.nick + '</td></tr>';
		if (name.call != '') txt += '<tr><td class="empty"></td><td class="dwr-attr-title">' + _('Call Name') + '</td><td class="dwr-attr-value">' + name.call + '</td></tr>';
		if (name.fam_nick != '') txt += '<tr><td class="empty"></td><td class="dwr-attr-title">' + _('Family Nick Name') + '</td><td class="dwr-attr-value">' + name.fam_nick + '</td></tr>';
		if (name.note != '') txt += '<tr><td class="empty"></td><td class="dwr-attr-title">' + _('Notes') + '</td><td class="dwr-attr-value">' + notePara(name.note, '<p class="dwr-attr-value">') + '</td></tr>';
	}
	txt += '<tr><td class="dwr-attr-title">' + _('Gender') + '</td><td colspan="2" class="dwr-attr-value">' + GENDERS_TEXT[i.gender] + '</td></tr>';
	if (i.death_age != '') txt += '<tr><td class="dwr-attr-title">' + _('Age at death') + '</td><td colspan="2" class="dwr-attr-value">' + i.death_age + '</td></tr>';
	txt += '</table>';
	return(txt);
}


function famLinked(fdx, citations)
{
	citations = (typeof(citations) !== 'undefined') ? citations : true;
	var txt =F[fdx].name;
	txt += gidBadge(F[fdx]);
	if (citations) txt += citaLinks(F[fdx].cita);
	if (INC_FAMILIES && (fdx != search.Fdx || PageContents != PAGE_FAM))
		txt = '<a href="' + famHref(fdx) + '">' + txt + '</a>';
	return(txt);
}


function noteSection(note)
{
	if (note == '') return([]);
	return([{
		title: _('Notes'),
		text: notePara(note, '<p>')
	}]);
}


function mediaSection(media)
{
	if (media.length == 0) return([]);
	return([{
		title: _('Media'),
		text: mediaLinks(media),
		panelclass: 'dwr-panel-media'
	}]);
}


function eventTable(events, idx, fdx)
{
	if (events.length == 0) return([]);
	var contents = {};
	contents.title = _('Events');
	var txt = '';
	txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
	// txt += '<table class="dt-table events">';
	txt += '<thead><tr>';
	txt += '<th class="dwr-attr-header">' + _('Event') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Date') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Place') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Notes') + '</th>';
	txt += '</tr></thead><tbody>';
	for (var j = 0; j < events.length; j++)
	{
		var e = events[j];
		txt += '<tr>';
		txt += '<td class="dwr-attr-title">' + e.type + citaLinks(e.cita) + '</td>';
		txt += '<td class="dwr-attr-value">' + e.date + '</td>';
		txt += '<td class="dwr-attr-value">' + placeLink(e.place, idx, fdx, e) + '</td>';
		var notes = [];
		if (e.descr != '') notes.push('<span class="dwr-attr-header">' + _('Description') + '</span>:<br>' + e.descr);
		if (e.text != '') notes.push('<span class="dwr-attr-header">' + _('Notes') + '</span>:<br>' + notePara(e.text, '<p>'));
		var mlinks = mediaLinks(e.media);
		if (mlinks != '') notes.push('<span class="dwr-attr-header">' + _('Media') + '</span>:<br>' + mlinks);
		// Get participants
		participants = '';
		for (var i = 0; i < e.part_person.length; i += 1)
		{
			var p_idx = e.part_person[i];
			if (p_idx != idx) participants += '<br>' + indiLinked(p_idx, false);
		}
		for (var i = 0; i < e.part_family.length; i += 1)
		{
			var p_fdx = e.part_family[i];
			if (p_fdx != fdx) participants += '<br>' + indiLinked(p_fdx, false);
		}
		if (participants != '') notes.push('<span class="dwr-attr-header">' + _('Other participants') + '</span>:' + participants);
		// Build notes from notes + description + media + participants + etc.
		txt += '<td class="dwr-attr-value">' + notes.join('<p>') + '</td>';
		txt += '</tr>';
	}
	txt += '</tbody></table>';
	contents.text = txt;
	return([contents]);
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
	if (addrs.length == 0) return([]);
	var contents = {};
	contents.title = _('Addresses');
	var txt = '';
	txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
	// txt += '<table class="dt-table addrs">';
	txt += '<thead><tr>';
	txt += '<th class="dwr-attr-header">' + _('Address') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Date') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Notes') + '</th>';
	txt += '</tr></thead><tbody>';
	for (var x_addr = 0; x_addr < addrs.length; x_addr++)
	{
		var addr = addrs[x_addr];
		txt += '<tr>';
		txt += '<td class="dwr-attr-value">' + locationString(addr.location) + citaLinks(addr.cita) + '</td>';
		txt += '<td class="dwr-attr-value">' + addr.date + '</td>';
		txt += '<td class="dwr-attr-value">' + notePara(addr.note, '<p>') + '</td>';
		txt += '</tr>';
	}
	txt += '</tbody></table>';
	contents.text = txt;
	return([contents]);
}


function attrsTable(attrs)
{
	if (attrs.length == 0) return([]);
	var contents = {};
	contents.title = _('Attributes');
	var txt = '';
	txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
	// txt += '<table class="dt-table attrs">';
	txt += '<thead><tr>';
	txt += '<th class="dwr-attr-header">' + _('Attribute') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Value') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Notes') + '</th>';
	txt += '</tr></thead><tbody>';
	for (var x_attr = 0; x_attr < attrs.length; x_attr++)
	{
		var a = attrs[x_attr];
		txt += '<tr>';
		txt += '<td class="dwr-attr-title">' + a.type + citaLinks(a.cita) + '</td>';
		txt += '<td class="dwr-attr-value">' + a.value + '</td>';
		txt += '<td class="dwr-attr-value">' + notePara(a.note, '<p>') + '</td>';
		txt += '</tr>';
	}
	txt += '</tbody></table>';
	contents.text = txt;
	return([contents]);
}


function urlsTable(urls)
{
	if (urls.length == 0) return([]);
	var contents = {};
	contents.title = _('Web Links');
	var txt = '';
	txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
	// txt += '<table class="dt-table urls">';
	txt += '<thead><tr>';
	txt += '<th class="dwr-attr-header">' + _('Link') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Description') + '</th>';
	txt += '</tr></thead><tbody>';
	for (var x_url = 0; x_url < urls.length; x_url++)
	{
		var url = urls[x_url];
		txt += '<tr>';
		txt += '<td class="dwr-attr-value"><a href="' + url.uri + '">' + url.uri + '</a></td>';
		txt += '<td class="dwr-attr-value">' + url.descr + '</td>';
		txt += '</tr>';
	}
	txt += '</tbody></table>';
	contents.text = txt;
	return([contents]);
}


function assocsTable(assocs)
{
	if (assocs.length == 0) return([]);
	var contents = {};
	contents.title = _('Associations');
	var txt = '';
	txt += '<table class="table table-condensed table-bordered dwr-table-panel">';
	// txt += '<table class="dt-table assocs">';
	txt += '<thead><tr>';
	txt += '<th class="dwr-attr-header">' + _('Person') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Relationship') + '</th>';
	txt += '<th class="dwr-attr-header">' + _('Notes') + '</th>';
	txt += '</tr></thead><tbody>';
	for (var x_assoc = 0; x_assoc < assocs.length; x_assoc++)
	{
		var assoc = assocs[x_assoc];
		txt += '<tr>';
		txt += '<td class="dwr-attr-value">' + indiLinked(assoc.person, false) + '</td>';
		txt += '<td class="dwr-attr-value">' + assoc.relationship + citaLinks(assoc.cita) + '</td>';
		txt += '<td class="dwr-attr-value">' + notePara(assoc.note, '<p>') + '</td>';
		txt += '</tr>';
	}
	txt += '</tbody></table>';
	contents.text = txt;
	return([contents]);
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
		var sdx = c.source;
		var title = sourName(sdx);
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
		var c_m = mediaLinks(c.media)
		for (k = 0; k < pageCitations[x1].length; k++)
		{
			var c2 = C[pageCitations[x1][k]];
			var c2_m = mediaLinks(c2.media)
			if (c2.text == c.text &&
				c2.note == c.note &&
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

function sourceSection()
{
	// Citations and source references
	var ctxt = printCitations();
	if (ctxt == '') return([]);
	return([{
		title: _('Sources'),
		text: ctxt,
		panelclass: 'dwr-sources-panel'
	}]);
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
			var txtc = c.text + c.note + mediaLinks(c.media)
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
	// Show Source tabbed pane upon click
	
	$('.dwr-citation').click(function(e) {
		$('a.dwr-sources-panel[role=tab]').tab('show');
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
	var title = '';
	if (search.SourceAuthorInTitle && S[sdx].author != '') title = S[sdx].author;
	if (S[sdx].title != '')
	{
		if (title != '') title += ': ';
		title += S[sdx].title;
	}
	if (title != '') return(title);
	return(_('Source') + ' ' + S[sdx].gid);
}


function mediaName(mdx)
{
	var txt = '';
	var m = M[mdx];
	if (m.title != '') return(m.title);
	return(m.gramps_path);
}


// List of places referenced in the page with for each one:
//    - pdx: the place index in table "P"
//    - idx: the referencing person index in table "I", -1 if none
//    - fdx: the referencing family index in table "F", -1 if none
//    - event: the referencing event, if any
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
	pagePlaces.push({pdx: pdx, idx: idx, fdx: fdx, event: event});
	if (!INC_PLACES) return(P[pdx].name);
	if (PageContents == PAGE_PLACE && pdx == search.Pdx) return(P[pdx].name);
	return('<a href="' + placeHref(pdx) + '">' + P[pdx].name + '</a>');
}


function repoLink(rdx)
{
	if (rdx == -1) return('');
	if (PageContents == PAGE_REPO && rdx == search.Rdx) return(R[rdx].name);
	return('<a href="' + repoHref(rdx) + '">' + R[rdx].name + '</a>');
}


function strToContents(title, txt)
{
	if (txt == '') return([]);
	return([{
		title: title,
		text: txt
	}]);
}


//=================================================================
//========================================================== Titles
//=================================================================

var titlesCollapsible = []; // Stack of titles property: is the title collapsible ?
var titlesTable = []; // Stack of titles property: is the title containing a table ?
var titlesNumber = 0;


function printTitle(level, contents, collapsible, is_tabbeb)
{
	if (contents.length == 0) return('');
	if (typeof(is_tabbeb) == 'undefined') is_tabbeb = false;
	if (typeof(collapsible) == 'undefined') collapsible = (level >= 1);
	is_tabbeb = is_tabbeb && collapsible && search.TabbedPanels;
	var html = '';
	if (is_tabbeb)
	{
		//  Generate nav tabs
		html += '<ul class="nav nav-tabs" role="tablist">';
		for (var i = 0; i < contents.length; i += 1)
		{
			if (typeof(contents[i].panelclass) == 'undefined') contents[i].panelclass = '';
			html += '<li role="presentation"' + ((i == 0) ? ' class="active"' : '') +
				'><a href="#section_' + (titlesNumber + i) + '" role="tab" data-toggle="tab" class="' + contents[i].panelclass + '">' +
				'<h' + level + ' class="panel-title">' +
				contents[i].title +
				'</h' + level + '>' +
				'</a></li>';
		}
		html += '</ul>';
		html += '<div class="panel panel-default dwr-tab-panel"><div class="tab-content panel-body">';
	}
	for (var i = 0; i < contents.length; i += 1)
	{
		var id = 'section_' + titlesNumber;
		titlesNumber += 1;
		is_table = (contents[i].text.indexOf('<table') == 0);
		is_table = is_table && collapsible;
		if (is_tabbeb)
		{
			html += '<div id="' + id + '" role="tabpanel" class="tab-pane' +
				(is_table ? ' dwr-panel-table' : '') +
				((i == 0) ? ' active ' : ' ') + contents[i].panelclass + '">';
			html += contents[i].text;
			html += '</div>';
		}
		else if (collapsible)
		{
			html += '<div class="panel panel-default ' + contents[i].panelclass + '">';
			html += '<div class="panel-heading dwr-collapsible" data-toggle="collapse" data-target="#' + id + '">';
			html += '<h' + level + ' class="panel-title">' + contents[i].title + '</h' + level + '>';
			html += '</div>';
			html += '<div id="' + id + '" class="panel-collapse collapse in ' + (is_table ? 'dwr-panel-table' : 'dwr-panel') + '">';
			if (is_table)
			{
				html += contents[i].text;
				html += '</div></div>';
			}
			else
			{
				html += '<div class="panel-body">';
				html += contents[i].text;
				html += '</div></div></div>';
			}
			
		}
		else
		{
			html += '<h' + level + '>' + contents[i].title + '</h' + level + '>';
			html += contents[i].text;
		}
	}
	if (is_tabbeb)
	{
		html += '</div></div>';
	}
	return(html);
}


function handleTitles()
{
	// Handle collapsible panels
	$('.panel-heading').click(function(event) {
		// Prevent title collapse when the click is not on the title
		var target = $(event.target);
		if (!target.is('.panel-heading') && !target.is('.panel-title'))
		{
			event.stopImmediatePropagation();
		}
	});
	
	// Handle Bootstrap nav tabs
	$('.nav-tabs>li>a').click(function (event) {
		var target = $(event.target);
		if (target.attr('role') != 'tab' && !target.is('.panel-title'))
		{
			event.stopImmediatePropagation();
		}
	});

	// Enable Bootstrap tooltips and popovers
	$('[data-toggle=tooltip]').tooltip();
	$('[data-toggle=popover]').popover();
	
}


function printChangeTime(record)
{
	$('#dwr-change-time').html(_('Last Modified') + ': ' + record.change_time);
	return('');
}

//=================================================================
//====================================================== Individual
//=================================================================

function printIndi(idx)
{
	var html = '';
	html += '<h2 class="page-header">' + I[idx].name + gidBadge(I[idx]) + citaLinks(I[idx].cita) + '</h2>';

	html += indiDetails(I[idx]);
	html += printTitle(3, [].concat(
		eventTable(I[idx].events, idx, -1),
		addrsTable(I[idx].addrs),
		attrsTable(I[idx].attr),
		urlsTable(I[idx].urls),
		assocsTable(I[idx].assoc),
		mediaSection(I[idx].media),
		noteSection(I[idx].note),
		[{
			title: _('Ancestors'),
			text: printIndiAncestors(idx)
		},
		{
			title: _('Descendants'),
			text: printIndiDescendants(idx)
		}],
		printMap(search.MapFamily),
		sourceSection()),
		true /*collapsible*/, true /*is_tabbeb*/);
	html += printChangeTime(I[idx]);
	return(html);
}


function printIndiAncestors(idx)
{
	var html = "";
	var famc_list = $.map(I[idx].famc, function (fc) {return(fc.index);});
	if (SHOW_ALL_SIBLINGS)
	{
		for (j = 0; j < I[idx].famc.length; j++)
		{
			var fdx = I[idx].famc[j].index;
			for (k = 0; k < F[fdx].spou.length; k++)
			{
				var spou = I[F[fdx].spou[k]];
				for (var x_fams = 0; x_fams < spou.fams.length; x_fams++)
				{
					var fams = spou.fams[x_fams];
					if ($.inArray(fams, famc_list) < 0) famc_list.push(fams);
				}
			}
		}
	}
	for (j = 0; j < famc_list.length; j++)
	{
		var fdx = famc_list[j];
		html += printTitle(4,
			[{
				title: _('Parents') + ': ' + famLinked(fdx),
				text: printIndiParents(fdx)
			},
			{
				title: _('Siblings'),
				text: printIndiSiblings(fdx)
			}]);
	}
	if (famc_list.length == 0) html += ('<p class="dwr-ref">' + _('None'));
	return(html);
}


function printIndiParents(fdx)
{
	var html = '';
	if (F[fdx].spou.length == 0)
	{
		html += ('<p class="dwr-ref">' + _('None'));
	}
	else
	{
		for (var k = 0; k < F[fdx].spou.length; k++)
		{
			html += '<p class="dwr-ref">' + indiLinked(F[fdx].spou[k]) + '</p>';
		}
	}
	return(html);
}


function printIndiSiblings(fdx)
{
	var html = '';
	if (F[fdx].chil.length > 0)
	{
		html += '<ol class="dwr-ref">';
		for (k = 0; k < F[fdx].chil.length; k++)
		{
			html += '<li class="dwr-ref">';
			html += printChildRef(F[fdx].chil[k]);
			html += '</li>';
		}
		html += '</ol>';
	}
	else
	{
		html += ('<p class="dwr-ref">' + _('None'));
	}
	return(html);
}

		
function printIndiDescendants(idx)
{
	var html = '';
	for (var j = 0; j < I[idx].fams.length; j++)
	{
		var fdx = I[idx].fams[j];
		html += printTitle(4,
			[{
				title: famLinked(fdx),
				text: printIndiSpouses(fdx, idx)
			}],
			I[idx].fams.length > 1 /*collapsible*/);
	}
	if (I[idx].fams.length == 0) html += ('<p class="dwr-ref">' + _('None') + '</p>');
	return(html);
}


function printIndiSpouses(fdx, idx)
{
	var html = '';
	var spouses = $(F[fdx].spou).not([idx]).get();
	for (var k = 0; k < spouses.length; k++)
	{
		html += '<p class="dwr-ref">' + indiLinked(spouses[k]) + '</p>';
	}
	html += printTitle(4, [].concat(
		[{
			title: _('Children'),
			text: printIndiChildren(fdx)
		}],
		eventTable(F[fdx].events, -1, fdx),
		attrsTable(F[fdx].attr),
		mediaSection(F[fdx].media),
		noteSection(F[fdx].note)),
		true /*collapsible*/, true /*is_tabbeb*/);
	return(html);
}


function printIndiChildren(fdx)
{
	var html = '';
	if (F[fdx].chil.length == 0)
	{
		html += '<p class="dwr-ref">' + _('None') + '</p>';
	}
	else
	{
		html += '<ol class="dwr-ref">';
		for (var k = 0; k < F[fdx].chil.length; k++)
		{
			html += '<li class="dwr-ref">';
			html += printChildRef(F[fdx].chil[k]);
			html += '</li>';
		}
		html += '</ol>';
	}
	return(html);
}


function printChildRef(fc)
{
	var txt = '';
	txt += indiLinked(fc.index);
	txt += citaLinks(fc.cita);
	if (fc.note != '') txt += '<p><b>' + _('Notes') + ':</b></p>' + notePara(fc.note, '</p>');
	rel = fc.to_father;
	title = _('Relationship to Father');
	if (rel != '' && rel != _('Birth')) txt += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + title + ': </span>' + rel + '</p>';
	rel = fc.to_mother;
	title = _('Relationship to Mother');
	if (rel != '' && rel != _('Birth')) txt += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + title + ': </span>' + rel + '</p>';
	return(txt);
}


//=================================================================
//========================================================== Family
//=================================================================

function printFam(fdx)
{
	var html = '';
	html += '<h2 class="page-header">' + F[fdx].name + gidBadge(F[fdx]) + citaLinks(F[fdx].cita) + '</h2>';
	html += printTitle(3, [].concat(
		eventTable(F[fdx].events, -1, fdx),
		attrsTable(F[fdx].attr),
		mediaSection(F[fdx].media),
		noteSection(F[fdx].note),
		[{
			title: _('Parents'),
			text: printFamParents(fdx)
		},
		{
			title: _('Children'),
			text: printFamChildren(fdx)
		}],
		printMap(search.MapFamily),
		sourceSection()),
		true /*collapsible*/, true /*is_tabbeb*/);
	html += printChangeTime(F[fdx]);
	return(html);
}
		
function printFamParents(fdx)
{
	var html = '';
	if (F[fdx].spou.length == 0)
	{
		html += ('<p class="dwr-ref">' + _('None'));
	}
	else
	{
		html += '<ul class="dwr-ref-detailed">';
		for (var k = 0; k < F[fdx].spou.length; k++)
		{
			var idx = F[fdx].spou[k];
			html += '<li class="dwr-ref-detailed">' + indiLinked(idx);
			html += indiDetails(I[idx]);
			html += printTitle(4, [].concat(
				eventTable(I[idx].events, idx, -1),
				// addrsTable(I[idx].addrs),
				// attrsTable(I[idx].attr),
				// urlsTable(I[idx].urls),
				// assocsTable(I[idx].assoc),
				mediaSection(I[idx].media)),
				// noteSection(I[idx].note),
				true /*collapsible*/, true /*is_tabbeb*/);
			html += '</li>';
		}
	}
	return(html);
}


function printFamChildren(fdx)
{
	var html = '';
	if (F[fdx].chil.length == 0)
	{
		html += ('<p class="dwr-ref">' + _('None') + '</p>');
	}
	else
	{
		html += '<ol class="dwr-ref-detailed">';
		for (var k = 0; k < F[fdx].chil.length; k++)
		{
			var fc = F[fdx].chil[k];
			var idx = F[fdx].chil[k].index;
			html += '<li class="dwr-ref-detailed">' + printChildRef(F[fdx].chil[k])
			html += indiDetails(I[idx]);
			html += printTitle(4, [].concat(
				eventTable(I[idx].events, idx, -1),
				// addrsTable(I[idx].addrs),
				// attrsTable(I[idx].attr),
				// urlsTable(I[idx].urls),
				// assocsTable(I[idx].assoc),
				mediaSection(I[idx].media)),
				// noteSection(I[idx].note),
				true /*collapsible*/, true /*is_tabbeb*/);
			html += '</li>';
		}
		html += '</ol>';
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
		var m = M[mr.m_idx];
		var alt = m.title;
		if (alt == '') alt = m.title;
		if (alt == '') alt = m.gramps_path;
		if (alt == '') alt = _('Media') + ' ' + mr.m_idx;
		txt += ' <a title="' + alt + '" class="thumbnail" href="' + mediaHref(mr.m_idx, m_list_from_mr(media)) + '">';
		txt += '<img src="' + mr.thumb + '" alt="' + alt + '"></a> ';
	}
	return(txt);
}

function mediaPaginationButtonHtml(id, class_, text)
{
	var html = '<li id="' + id + '"';
	if (class_ != '') html += ' class="' + class_ + '"';
	html += '><a href="#">' + text + '</a></li>';
	return(html);
}
			
function printMedia(mdx)
{
	var html = '';
	var m = M[mdx];
	var title = m.title;
	if (title == '') title = m.gramps_path;
	html += '<h2 class="page-header">' + title + gidBadge(M[mdx]) + citaLinks(m.cita) + '</h2>';
	
	// Pagination buttons
	if (search.ImgList.length > 1)
	{
		var imgI = search.ImgList.indexOf(mdx);
		html += '<ul id="dwr-img-btns" class="pagination">';
		// 'Previous' button
		html += mediaPaginationButtonHtml('media_button_prev', (imgI == 0) ? 'disabled' : '',
			'<span class="glyphicon glyphicon-chevron-left"></span>');
		// First item button
		html += mediaPaginationButtonHtml('media_button_0', (imgI == 0) ? 'active' : '', '1');
		var first_but = Math.min(imgI - 1, search.ImgList.length - 4);
		first_but = Math.max(1, first_but);
		var last_but = Math.min(first_but + 2, search.ImgList.length - 2);
		if (first_but > 1)
		{
			// Separator between first item and current item buttons
			html += mediaPaginationButtonHtml('media_button_hellip', 'disabled', '&hellip;');
		}
		// Current item buttons
		for (var i = first_but; i <= last_but; i++)
		{
			html += mediaPaginationButtonHtml('media_button_' + i, (imgI == i) ? 'active' : '', i + 1);
		}
		if (last_but < search.ImgList.length - 2)
		{
			// Separator between current item buttons and last item
			html += mediaPaginationButtonHtml('media_button_hellip', 'disabled', '&hellip;');
		}
		if (search.ImgList.length > 1)
		{
			// Last item button
			var i = search.ImgList.length - 1;
			html += mediaPaginationButtonHtml('media_button_' + i, (imgI == i) ? 'active' : '', i + 1);
		}
		// 'Next' button
		html += mediaPaginationButtonHtml('media_button_next', (imgI == search.ImgList.length - 1) ? 'disabled' : '',
			'<span class="glyphicon glyphicon-chevron-right"></span>');
		html += '</ul>';
		// Pagination events
		$(window).load(function()
		{
			// Disable <a> anchors for disabled buttons
			$('.pagination .disabled a, .pagination .active a').on('click', function(e) {e.preventDefault();});
			// Connect click events
			$('#media_button_prev:not(.disabled)').click(function() {return mediaButtonPageClick(-1);});
			$('#media_button_next:not(.disabled)').click(function() {return mediaButtonPageClick(1);});
			$('#media_button_0:not(.active)').click(function() {return mediaButtonPageClick(0, 0);});
			$('#media_button_' + (search.ImgList.length - 1) + ':not(.active)').click(function() {return mediaButtonPageClick(0, search.ImgList.length - 1);});
			for (var i = first_but; i <= last_but; i++)
			{
				(function(){ // This is used to create instances of local variables
					var icopy = i;
					$('#media_button_' + i + ':not(.active)').click(function() {return mediaButtonPageClick(0, icopy);});
				})();
			}
		});
	}

	// Image or link (if media is not an image)
	if (m.mime.indexOf('image') == 0)
	{
		html += '<div class="dwr-centered"><div id="dwr-img-div">';
		html += '<img id="dwr-image" src="' + m.path + '">';
		html += printMediaMap(mdx);
		
		// Expand button
		html += '<div id="media-buttons">';
		html += '<button id="media-button-max" type="button" class="btn btn-default" title=' + _('Maximize') + '>';
		html += '<span class="glyphicon glyphicon-fullscreen"></span>';
		html += '</button>';
		html += '</div>';

		html += '</div></div>';

		// Expand button events
		$(window).load(function()
		{
			$('#media-button-max').click(function() {return mediaButtonMaxClick();});
		});
	}
	else
	{
		var name = m.gramps_path;
		name = name.replace(/.*[\\\/]/, '');
		html += '<p class="dwr-centered"><a href="' + m.path + '">' + name + '</a></p>';
	}

	// Back references
	var bk_txt = printBackRefs(BKREF_TYPE_MEDIA, m.bki, m.bkf, m.bks, [], m.bkp, []);
	
	// Media description
	if (m.date != '') html += '<p><b>' + _('Date') + ': </b>' + m.date + '</p>';
	html += printTitle(3, [].concat(
		noteSection(m.note),
		attrsTable(m.attr),
		strToContents(_('References'), bk_txt),
		sourceSection()),
		true /*collapsible*/, true /*is_tabbeb*/);

	html += printChangeTime(m);
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
	window.location.href = M[search.Mdx].path;
	return(false);
}

function printMediaMap(mdx)
{
	var html = '';
	var j, k;
//	html += '<ul id="imgmap">';
	var m = M[mdx];
	html += printMediaRefArea(m.bki, indiHref, function(ref) {return(I[ref].name);});
	if (INC_FAMILIES)
		html += printMediaRefArea(m.bkf, famHref, function(ref) {return(F[ref].name);});
	if (INC_SOURCES)
		html += printMediaRefArea(m.bks, sourceHref, sourName);
	if (INC_PLACES)
		html += printMediaRefArea(m.bkp, placeHref, function(ref) {return(P[ref].name);});
//	html += '</ul>';
	return(html);
}

function printMediaRefArea(bk_table, fref, fname)
{
	var html = '';
	var j, k;
	for (j = 0; j < bk_table.length; j++)
	{
		var ref = bk_table[j];
		idx = ref.bk_idx;
		var rect = [];
		for (k = 0; k < 4; k++)
		{
			rect[k] = parseFloat(ref.rect[k]);
		}
		if (!isNaN(rect[0]) && rect.join(',') != '0,0,100,100')
		{
			html += '<a href="' + fref(idx) + '"';
			html += ' title="' + fname(idx) + '" class="dwr-imgmap" style="';
			html += 'left: ' + rect[0] + '%;';
			html += 'top: ' + rect[1] + '%;';
			html += 'width: ' + (rect[2] - rect[0]) + '%;';
			html += 'height: ' + (rect[3] - rect[1]) + '%;">';
			html += '</a>';
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
	if (s.title != '') html += '<h2 class="page-header">' + s.title + gidBadge(S[sdx]) + '</h2>';
	if (s.text != '') html += s.text;

	// Repositories for this source
	var bk_txt = printBackRefs(BKREF_TYPE_REPOREF, [], [], [], [], [], S[sdx].repo);

	html += printTitle(3, [].concat(
		attrsTable(s.attr),
		mediaSection(s.media),
		noteSection(s.note),
		strToContents(_('Repositories'), bk_txt),
		[{
			title: _('Citations'),
			text: printSourceCitations(s)
		}]),
		true /*collapsible*/, true /*is_tabbeb*/);
	html += printChangeTime(s);
	return(html);
}

function printSourceCitations(s)
{
	var html = '';
	if (s.bkc.length > 0)
	{
		html += '<ul class="dwr-citations">';
		var j;
		for (var j = 0; j < s.bkc.length; j++)
		{
			var c = C[s.bkc[j]]
			// html += '<li>' + _('Citation') + ': ';
			html += '<li>';
			if (c.text != '') html += notePara(c.text, '<p>');
			if (c.note != '') html += '<p><b>' + _('Notes') + ':</b></p>' + notePara(c.note, '<p>');
			if (c.media.length > 0) html += '<p>' + _('Media') + ': ' + mediaLinks(c.media) + '</p>';
			// Back references
			html += printBackRefs(BKREF_TYPE_INDEX, c.bki, c.bkf, [], c.bkm, c.bkp, c.bkr);
			html += '</li>';
		}
		html += '</ul>';
	}
	else
	{
		html += '<p>' + _('None') + '</p>';
	}
	return(html);
}


//=================================================================
//========================================================== Places
//=================================================================

function placeNames(pdx)
{
	var p = P[pdx]
	if (p.names.length == 0) return('');
	var names = []
	for (var j = 0; j < p.names.length; j++)
	{
		var txt = p.names[j].name;
		if (p.names[j].date != '') txt += ' (' + p.names[j].date + ')';
		names.push(txt);
	}
	return(names.join(', '));
}

function placeHierarchy(enclosed_by, visited)
{
	if (enclosed_by.length == 0) return('');
	var txt = '<ul>';
	for (var j = 0; j < enclosed_by.length; j++)
	{
		var pdx = enclosed_by[j].pdx;
		if ($.inArray(pdx, visited) != -1) continue;
		txt += '<li class="dwr-attr-value">';
		txt += '<a href="' + placeHref(pdx) + '">'
		txt += placeNames(pdx);
		txt += '</a>';
		if (enclosed_by[j].date != '') txt += ' (' + enclosed_by[j].date + ')';
		txt += placeHierarchy(P[pdx].enclosed_by, $.merge($.merge([], visited), [pdx]))
		txt += '</li>';
	}
	txt += '</ul>';
	return(txt);
}

function printPlace(pdx)
{
	var p = P[pdx]
	var html = '';
	placeLink(pdx);
	var name = p.name;
	if (name == '') name = locationString(p.locations);
	html += '<h2 class="page-header">' + name + gidBadge(P[pdx]) + citaLinks(p.cita) + '</h2>';
	if (p.names.length > 0)
	{
		html += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Name') + ':</span> ';
		html += placeNames(pdx);
		html += '</p>';
	}
	if (p.type != '') html += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Type') + ':</span> ' + p.type + '</p>';
	if (p.code != '') html += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Code') + ':</span> ' + p.code + '</p>';
	if (p.coords[0] != '' && p.coords[1] != '')
		html +=
			'<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Latitude') + ':</span> ' + p.coords[0] + '</p>' +
			'<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Longitude') + ':</span> ' + p.coords[1] + '</p>';
	for (var j = 0; j < p.locations.length; j++)
	{
		html += '<p class="dwr-attr-title">';
		if (j == 0) html += _('Location');
		else html += _('Alternate Name') + ' ' + j;
		html += ': </p><ul>';
		var loc = p.locations[j];
		for (var k = 0; k < loc.length; k ++)
		{
			html += '<li class="dwr-attr-value"><span class="dwr-attr-title">' + loc.type + ':</span> ' + loc.name + '</li>';
		}
		html += '</ul>';
	}
	if (p.enclosed_by.length > 0)
	{
		html += '<p class="dwr-attr-title">' + _('Enclosed By') + ':</p';
		html += placeHierarchy(p.enclosed_by, [pdx]);
	}

	// Back references
	var bk_txt = printBackRefs(BKREF_TYPE_INDEX, p.bki, p.bkf, [], [], p.bkp, []);

	html += printTitle(3, [].concat(
		urlsTable(p.urls),
		mediaSection(p.media),
		noteSection(p.note),
		printMap(search.MapPlace),
		sourceSection(),
		strToContents(_('References'), bk_txt)),
		true /*collapsible*/, true /*is_tabbeb*/);
		
	html += printChangeTime(p);
	return(html);
}


//=================================================================
//==================================================== Repositories
//=================================================================

function printRepo(rdx)
{
	var r = R[rdx]
	var html = '';
	html += '<h2 class="page-header">' + r.name + gidBadge(R[rdx]) + '</h2>';
	html += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Type') + ': </span>'
	html += r.type + '</p>';
	
	// Back references
	var bk_txt = printBackRefs(BKREF_TYPE_REPO, [], [], r.bks, [], [], []);
	if (bk_txt == '') bk_txt = _('None');

	html += printTitle(3, [].concat(
		addrsTable(r.addrs),
		urlsTable(r.urls),
		noteSection(r.note),
		strToContents(_('References'), bk_txt),
		sourceSection()),
		true /*collapsible*/, true /*is_tabbeb*/);
	html += printChangeTime(r);
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
			var text_sort = text.replace(/<[^>]*>/g, '');
			var text_filt = text_sort + " " + unorm.nfkc(text_sort);
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
				if (typeof(text_sort) == 'number')
				{
					text_sort = '000000' + text_sort;
					text_sort = text_sort.substr(text_sort.length - 7);
				}
				text_sort = text_sort.toString();
			}
			if (text_sort != '' && isNaN(parseInt(text_sort))) col_num[k] = false;
			line.push({
				'text': text,
				'sort': text_sort,
				'filter': text_filt
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
				'filter': k + '.filter',
				'sort': k + '.sort',
			},
			// 'width': '200px',
			'type': (col_num[k] ? 'num' : 'string'),
			'orderable': (columns[k].fsort !== false)
		});
	}
	
	// Print table
	indexCounter ++;
	var html = '';
	if (data_copy.length == 0)
	{
		html += '<p>' + _('None') + '</p>';
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
			$(id).DataTable({
				'order': defaultsort,
				'info': false,
				'responsive': true,
				'iDisplayLength': A_LENGTH_MENU[0][search.NbEntries],
				'aLengthMenu': A_LENGTH_MENU,
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


GENDERS_ABBREVIATION = {
	'M': _('M'),
	'F': _('F'),
	'U': _('U')
};

function printPersonsIndex(data)
{
	ParseSearchString();
	ManageSearchStringGids();
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
		ftext: function(x, col) {return(I[data[x]].name);},
		fhref: function(x) {return(indiHref(data[x]));},
		fsort: function(x, col) {return(data[x]);}
	}, {
		title: _('Gender'),
		ftext: function(x, col) {return(GENDERS_ABBREVIATION[I[data[x]].gender])}
	}];
	if (search.IndexShowBirth) columns.push({
		title: _('Birth'),
		ftext: function(x, col) {return(I[data[x]].birth_year);}
	});
	if (search.IndexShowDeath) columns.push({
		title: _('Death'),
		ftext: function(x, col) {return(I[data[x]].death_year);}
	});
	if (search.IndexShowPartner) columns.push({
		title: _('Spouses'),
		ftext: function(x, col) {
			var txt = '';
			var sep = '';
			for (var x_fams = 0; x_fams < I[data[x]].fams.length; x_fams++)
			{
				var spouses = F[I[data[x]].fams[x_fams]].spou;
				for (var x_spou = 0; x_spou < spouses.length; x_spou++)
				{
					if (spouses[x_spou] !== data[x])
					{
						txt += sep + '<a class="dwr-index" href="' + indiHref(spouses[x_spou]) + '">';
						txt += I[spouses[x_spou]].name + '</a>';
						sep = '<br>';
					}
				}
			}
			return(txt);
		},
		fsort: false
	});
	if (search.IndexShowParents) columns.push({
		title: _('Parents'),
		ftext: function(x, col) {
			var txt = '';
			var sep = '';
			for (var x_famc = 0; x_famc < I[data[x]].famc.length; x_famc++)
			{
				var parents = F[I[data[x]].famc[x_famc].index].spou;
				for (var x_spou = 0; x_spou < parents.length; x_spou++)
				{
					if (parents[x_spou] !== data[x])
					{
						txt += sep + '<a class="dwr-index" href="' + indiHref(parents[x_spou]) + '">';
						txt += I[parents[x_spou]].name + '</a>';
						sep = '<br>';
					}
				}
			}
			return(txt);
		},
		fsort: false
	});
	html += printIndex(data, [0, 'asc'], columns);
	return(html);
}

function printIndexSpouseText(fdx, col)
{
	var gender = (col == 0)? 'M' : 'F';
	for (var j = 0; j < F[fdx].spou.length; j++)
		if (I[F[fdx].spou[j]].gender == gender)
			return(I[F[fdx].spou[j]].name);
	return('');
}
function printIndexSpouseIdx(fdx, col)
{
	var gender = (col == 0)? 'M' : 'F';
	for (var j = 0; j < F[fdx].spou.length; j++)
		if (I[F[fdx].spou[j]].gender == gender)
			return(F[fdx].spou[j]);
	return(-1);
}

function printFamiliesIndex()
{
	ParseSearchString();
	ManageSearchStringGids();
	document.write(htmlFamiliesIndex());
}
function htmlFamiliesIndex(data)
{
	var html = '';
	if (typeof(data) == 'undefined')
	{
		html += '<h2 class="page-header">' + _('Families Index') + '</h2>';
		data = [];
		for (var x = 0; x < F.length; x++) data.push(x);
	}
	var columns = [{
		title: _('Father'),
		ftext: function(x, col) {return(printIndexSpouseText(data[x], col));},
		fhref: function(x) {return(famHref(data[x]));},
		fsort: function(x, col) {return(printIndexSpouseIdx(data[x], col));}
	}, {
		title: _('Mother'),
		ftext: function(x, col) {return(printIndexSpouseText(data[x], col));},
		fhref: function(x) {return(famHref(data[x]));},
		fsort: function(x, col) {return(printIndexSpouseIdx(data[x], col));}
	}];
	if (search.IndexShowMarriage) columns.push({
		title: _('Marriage'),
		ftext: function(x, col) {return(F[data[x]].marr_year);}
	});
	html += printIndex(data, [0, 'asc'], columns);
	return(html);
}


function indexBkrefName(type, referenced_object, bk_field, objects, name_prop)
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
		for (var x_cita = 0; x_cita < referenced_object.bkc.length; x_cita++)
		{
			var citation = C[referenced_object.bkc[x_cita]];
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
		if (type == BKREF_TYPE_MEDIA) x_object = bk_table[x_bk].bk_idx;
		if (type == BKREF_TYPE_SOURCE) x_object = bk_table[x_bk];
		if (type == BKREF_TYPE_REPO) x_object = bk_table[x_bk].s_idx;
		if ($.inArray(x_object, already_found) == -1)
		{
			already_found.push(x_object);
			var name = objects[x_object][name_prop];
			if (name != '')
			{
				txt += sep + '<a class="dwr-index" href="' + ref(x_object) + '">';
				txt += objects[x_object][name_prop] + '</a>';
				sep = '<br>';
			}
		}
	}
	return(txt);
}


function printMediaIndex(data)
{
	ParseSearchString();
	ManageSearchStringGids();
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
			'<img src="' + M[data[x]].thumb + '"></a>'
		);},
		fsort: false
	}, {
		title: _('Title'),
		ftext: function(x, col) {return(M[data[x]].title);},
		fhref: function(x) {return(mediaHref(data[x]));},
		fsort: function(x, col) {return(data[x]);}
	}, {
		title: _('Path'),
		ftext: function(x, col) {return(M[data[x]].gramps_path);},
		fhref: function(x) {return((M[data[x]].title == '') ? mediaHref(data[x]) : '');}
	}, {
		title: _('Date'),
		ftext: function(x, col) {return(M[data[x]].date);},
		fsort: function(x, col) {return(M[data[x]].date_sdn);}
	}];
	if (search.IndexShowBkrefType) columns.push({
		title: _('Used for person'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_MEDIA, M[data[x]], 'bki', I, 'name'));},
		fsort: false
	});
	if (search.IndexShowBkrefType && INC_FAMILIES) columns.push({
		title: _('Used for family'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_MEDIA, M[data[x]], 'bkf', F, 'name'));},
		fsort: false
	});
	if (search.IndexShowBkrefType && INC_SOURCES) columns.push({
		title: _('Used for source'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_MEDIA, M[data[x]], 'bks', S, 'title'));},
		fsort: false
	});
	if (search.IndexShowBkrefType && INC_PLACES) columns.push({
		title: _('Used for place'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_MEDIA, M[data[x]], 'bkp', P, 'name'));},
		fsort: false
	});
	html += printIndex(data, [1, 'asc'], columns);
	return(html);
}


function printSourcesIndex(data)
{
	ParseSearchString();
	ManageSearchStringGids();
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
		ftext: function(x, col) {return(S[data[x]].title);},
		fhref: function(x) {return(sourceHref(data[x]));},
		fsort: function(x, col) {return(data[x]);}
	}, {
		title: _('Author'),
		ftext: function(x, col) {return(S[data[x]].author);},
		fhref: function(x) {return(sourceHref(data[x]));},
		fsort: function(x, col) {return(data[x]);}
	}, {
		title: _('Abbreviation'),
		ftext: function(x, col) {return(S[data[x]].abbrev);},
		fhref: function(x) {return(sourceHref(data[x]));},
		fsort: function(x, col) {return(data[x]);}
	}, {
		title: _('Publication information'),
		ftext: function(x, col) {return(S[data[x]].publ);},
		fhref: function(x) {return(sourceHref(data[x]));},
		fsort: function(x, col) {return(data[x]);}
	}];
	if (search.IndexShowBkrefType) columns.push({
		title: _('Used for person'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_SOURCE, S[data[x]], 'bki', I, 'name'));},
		fsort: false
	});
	if (search.IndexShowBkrefType && INC_FAMILIES) columns.push({
		title: _('Used for family'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_SOURCE, S[data[x]], 'bkf', F, 'name'));},
		fsort: false
	});
	if (search.IndexShowBkrefType && INC_MEDIA) columns.push({
		title: _('Used for media'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_SOURCE, S[data[x]], 'bkm', M, 'title'));},
		fsort: false
	});
	if (search.IndexShowBkrefType && INC_PLACES) columns.push({
		title: _('Used for place'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_SOURCE, S[data[x]], 'bkp', P, 'name'));},
		fsort: false
	});
	html += printIndex(data, [0, 'asc'], columns);
	return(html);
}


function printPlacesIndexColText(data, x, field)
{
	var pdx = data[x];
	if (P[pdx].locations.length == 0) return('');
	P[pdx].locations[0]
	if (typeof(P[pdx].locations[0][field]) == 'undefined') return('');
	return(P[pdx].locations[0][field]);
}

function printPlacesIndexColCoord(pdx, col)
{
	var c = P[pdx].coords[col - 9];
	if (c == '') return('');
	c = Number(c);
	var txt = '000' + Math.abs(c).toFixed(4);
	txt = txt.substr(txt.length - 8);
	txt = ((c < 0)? '-' : '+') + txt;
	return(txt);
}

function printPlacesIndex(data)
{
	ParseSearchString();
	ManageSearchStringGids();
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
		ftext: function(x, col) {return(P[data[x]].name);},
		fhref: function(x) {return(placeHref(data[x]));},
		fsort: function(x, col) {return(data[x]);}
	}, {
		title: _('Latitude'),
		ftext: function(x, col) {
			if (P[data[x]].coords[0] == '') return('');
			return(Number(P[data[x]].coords[0]));
		}
	}, {
		title: _('Longitude'),
		ftext: function(x, col) {
			if (P[data[x]].coords[1] == '') return('');
			return(Number(P[data[x]].coords[1]));
		}
	}, {
		title: _('Type'),
		ftext: function(x, col) {return(P[data[x]].type);}
	}, {
		title: _('Code'),
		ftext: function(x, col) {return(P[data[x]].code);}
	}, {
		title: STATE,
		ftext: function(x, col) {return(printPlacesIndexColText(data, x, STATE));}
	}, {
		title: COUNTRY,
		ftext: function(x, col) {return(printPlacesIndexColText(data, x, COUNTRY));}
	}, {
		title: POSTAL,
		ftext: function(x, col) {return(printPlacesIndexColText(data, x, POSTAL));}
	}];
	if (search.IndexShowBkrefType) columns.push({
		title: _('Enclosed By'),
		ftext: function(x, col) {
			return(($.map(P[data[x]].enclosed_by, function(enc) {return(placeNames(enc.pdx));})).join('<br>'));
			}
	});
	if (search.IndexShowBkrefType) columns.push({
		title: _('Used for person'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_INDEX, P[data[x]], 'bki', I, 'name'));},
		fsort: false
	});
	if (search.IndexShowBkrefType && INC_FAMILIES) columns.push({
		title: _('Used for family'),
		ftext: function(x, col) {return(indexBkrefName(BKREF_TYPE_INDEX, P[data[x]], 'bkf', F, 'name'));},
		fsort: false
	});
	html += printIndex(data, [0, 'asc'], columns);
	return(html);
}



function printAddressesIndex()
{
	ParseSearchString();
	ManageSearchStringGids();
	document.write(htmlAddressesIndex());
}
function htmlAddressesIndex()
{
	// Build addresses table
	var adtable = [];
	var empty_loc = [];
	var empty_url = {type: '', uri: '', descr: ''};
	for (var x_i = 0; x_i < I.length; x_i++)
	{
		var i = I[x_i];
		for (var x_ad = 0; x_ad < i.addrs.length; x_ad++)
			adtable.push([x_i, i.addrs[x_ad].location, empty_url])
		for (var x_url = 0; x_url < i.urls.length; x_url++)
			adtable.push([x_i, empty_loc, i.urls[x_url]])
	}
	// Print table
	var html = '';
	html += '<h2 class="page-header">' + _('Addresses') + '</h2>';
	var columns = [{
		title: _('Person'),
		ftext: function(x_ad, col) {return(I[adtable[x_ad][0]].name);},
		fhref: function(x_ad) {return(indiHref(adtable[x_ad][0]));},
		fsort: function(x, col) {return(adtable[x_ad][0]);}
	}, {
		title: _('Address'),
		ftext: function(x_ad, col) {return(locationString(adtable[x_ad][1]));},
	}, {
		title: _('Web Link'),
		ftext: function(x_ad, col) {return(adtable[x_ad][2].descr || adtable[x_ad][2].uri);},
		fhref: function(x_ad) {return(adtable[x_ad][2].uri);}
	}];
	html += printIndex(adtable, [0, 'asc'], columns);
	return(html);
}



function printReposIndex()
{
	ParseSearchString();
	ManageSearchStringGids();
	document.write(htmlReposIndex());
}
function htmlReposIndex()
{
	var html = '';
	html += '<h2 class="page-header">' + _('Repositories') + '</h2>';
	var columns = [{
		title: _('Repository'),
		ftext: function(rdx, col) {return(R[rdx].name);},
		fhref: repoHref,
		fsort: function(rdx, col) {return(rdx);}
	}, {
		title: _('Type'),
		ftext: function(rdx, col) {return(R[rdx].type);},
	}, {
		title: _('Addresses'),
		ftext: function(rdx, col) {
			return(($.map(R[rdx].addrs, locationString)).join('<br>'));
		},
	}, {
		title: _('Web Links'),
		ftext: function(rdx, col) {
			return(($.map(R[rdx].urls, function(url) {
				return('<a class="dwr-index" href="' + url.uri + '">' + (url.descr || url.uri) + '</a>');
			})).join('<br>'));
		},
	}];
	if (search.IndexShowBkrefType && INC_SOURCES) columns.push({
		title: _('Used for source'),
		ftext: function(rdx, col) {return(indexBkrefName(BKREF_TYPE_REPO, R[rdx], 'bks', S, 'title'));},
		fsort: false
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
	ManageSearchStringGids();
	
	if (search.SNdx >= 0)
	{
		if (SN[search.SNdx].persons.length == 0)
		{
			document.write('<p>' + _('No matching surname.') + '</p>');
		}
		else if (SN[search.SNdx].persons.length == 1)
		{
			window.location.replace(indiHref(SN[search.SNdx].persons[0]));
		}
		else
		{
			document.write(
				'<h2 class="page-header">',
				(SN[search.SNdx].surname.length > 0) ?
					SN[search.SNdx].surname :
					'<i>' + _('Without surname') + '</i>',
				'</h2>');
			document.write(htmlPersonsIndex(SN[search.SNdx].persons));
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
	ManageSearchStringGids();
	
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
		if (SN[i].surname.length > 0)
		{
			var letter = SN[i].letter;
			if ($.inArray(letter, titles) == -1)
			{
				// New initial for the surname
				titles.push(letter);
				texts[letter] = '';
			}
			texts[letter] += surnameString(i, SN[i].surname, SN[i].persons.length);
		}
		else
		{
			// Empty surname
			titles.push('');
			texts[''] = surnameString(i, SN[i].surname, SN[i].persons.length);
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
	ManageSearchStringGids();
	
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
			number: SN[i].persons.length,
			name: SN[i].surname,
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
BKREF_TYPE_REPOREF = 4;

function printBackRefs(type, bki, bkf, bks, bkm, bkp, bkr)
{
	var html = '';
	html += printBackRef(type, bki, indiHref, function(ref) {return(I[ref].name);});
	if (INC_FAMILIES)
		html += printBackRef(type, bkf, famHref, function(ref) {return(F[ref].name);});
	else
		html += printBackRef(type, bkf, null, function(ref) {return(F[ref].name);});
	if (INC_SOURCES)
		html += printBackRef(type, bks, sourceHref, sourName);
	if (INC_MEDIA)
		html += printBackRef(type, bkm, mediaHref, mediaName);
	if (INC_PLACES)
		html += printBackRef(type, bkp, placeHref, function(ref) {return(P[ref].name);});
	if (INC_REPOSITORIES)
		html += printBackRef(type, bkr, repoHref, function(ref) {return(R[ref].name);});
	if (html == '') return('');
	return('<ul class="dwr-backrefs">' + html + '</ul>');
}

function printBackRef(type, bk_table, fref, fname)
{
	my_fref = function(ref, txt) {
		if (fref == null) return(txt);
		return('<a href="' + fref(ref) + '">' + txt + '</a>');
	};
	var html = '';
	var j;
	for (j = 0; j < bk_table.length; j++)
	{
		var ref = bk_table[j];
		var txt = '';
		if (type == BKREF_TYPE_INDEX)
		{
			// This is a citation, person or family back reference
			txt = my_fref(ref, fname(ref));
		}
		else if (type == BKREF_TYPE_MEDIA)
		{
			// This is a media back reference
			txt = my_fref(ref.bk_idx, fname(ref.bk_idx));
			txt += citaLinks(ref.cita);
			if (ref.note != '')
			{
				txt = '<div>' + txt;
				txt += notePara(ref.note, '<p>');
				txt += '</div>';
			}
		}
		else if (type == BKREF_TYPE_REPO || type == BKREF_TYPE_REPOREF)
		{
			var idx = (type == BKREF_TYPE_REPO) ? ref.s_idx : ref.r_idx;
			// This is a repository back reference
			txt = my_fref(idx, fname(idx));
			if (ref.media_type != '')
				txt += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Media Type') + ': </span>' + ref.media_type + '</p>';
			if (ref.call_number != '')
				txt += '<p class="dwr-attr-value"><span class="dwr-attr-title">' + _('Call Number') + ': </span>' + ref.call_number + '</p>';
			if (ref.note != '')
			{
				txt = '<div>' + txt;
				txt += notePara(ref.note, '<p>');
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


function printMap(enabled)
{
	if (!enabled || !INC_PLACES) return([]);
	// Check if there is at least 1 place with coordinates defined
	var found = false;
	for (var j = 0; j < pagePlaces.length; j++)
	{
		var pdx = pagePlaces[j].pdx;
		if (P[pdx].coords.join('') != '') found = true;
	}
	if (!found) return([]);
	// Schedule the differed update of the map
	if (search.TabbedPanels && !search.MapExpanded)
		$(window).load(function () {
			if ($(".tab-pane.active.dwr-panel-map").length > 0)
			{
				// The map is already the active tab
				mapUpdate();
			}
			else
			{
				// Waiting for the map to be the active tab
				$('a.dwr-panel-map').on('shown.bs.tab', mapUpdate);
			}
		});
	else
	{
		$(window).load(mapUpdate);
	}
	// Build HTML
	
	 // +
			// ' <a tabindex="0" data-toggle="popover" data-placement="bottom" title="" data-trigger="focus" data-content="' +
			// _('Click on the map to show it full-screen') +
			// '"><span class="glyphicon glyphicon-question-sign"></span></a>'
			
			
	var contents = {
		title: _('Map'),
		text:'<div id="gmap_canvas"></div>',
		panelclass: 'dwr-panel-map'
	};
	if (search.MapExpanded)
	{
		$('body').toggleClass('dwr-fullscreen');
		$('body').children().css('display', 'none');
	}
	return([contents]);
}


mapUpdated = false;

function mapUpdate()
{
	if (mapUpdated) return;
	mapUpdated = true;
	// Check if online
	if (MAP_SERVICE == 'Google' && typeof(google) == 'undefined') return;
	if (MAP_SERVICE == 'OpenStreetMap' && typeof(ol) == 'undefined') return;
	// Expand map if required
	if (search.MapExpanded)
	{
		$('body').prepend($('#gmap_canvas'));
		$('#gmap_canvas').addClass('dwr-expanded');
		mapResize();
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
		var pdx = pagePlaces[x_place].pdx;
		var lat = Number(P[pdx].coords[0]);
		var lon = Number(P[pdx].coords[1]);
		var sc = P[pdx].coords.join('');
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
	};
	// Place markers
	var points = [];
	var nb_max = 0;
	GetIconProps = function(x_marker)
	{
		var point = points[x_marker];
		var nb = point.nb_birth + point.nb_marr + point.nb_death + point.nb_other;
		nb = Math.max(nb, 1);
		var src = '';
		if (point.nb_birth == nb)
			src = 'data/gramps-geo-birth.png';
		else if (point.nb_marr == nb)
			src = 'data/gramps-geo-marriage.png';
		else if (point.nb_death == nb)
			src = 'data/gramps-geo-death.png';
		else
			src = 'data/gramps-geo-mainmap.png';
		var scale = 0.5 + 1.0 * nb / Math.max(nb_max, 5);
		return({
			src: src,
			scale: scale,
			size: {w: Math.round(48 * scale), h: Math.round(48 * scale)},
			anchor: {x: Math.round(0.1 * 48 * scale), y: Math.round(0.9 * 48 * scale)}
		});
	}
	for (var x_marker = 0; x_marker < mapCoords.length; x_marker++)
	{
		// Sort markerPaces by name
		markerPaces[x_marker].sort(function(a, b) {
			return(P[pagePlaces[a].pdx].name.localeCompare(P[pagePlaces[b].pdx].name));
		});
		// Build markers data
		var point = {
			mapName: '',
			mapInfo: '',
			nb_other: 0,
			nb_birth: 0,
			nb_marr: 0,
			nb_death: 0
		};
		var previous_pdx = -1;
		var previous_ul = false;
		for (var x_place = 0; x_place < markerPaces[x_marker].length; x_place++)
		{
			var pp = pagePlaces[markerPaces[x_marker][x_place]];
			var pdx = pp.pdx;
			if (pdx != previous_pdx)
			{
				if (point.mapName) point.mapName += '\n';
				point.mapName += P[pdx].name;
				if (previous_ul) point.mapInfo += '</ul>';
				point.mapInfo += '<p class="dwr-mapinfo"><a href="' + placeHref(pdx) + '">' + P[pdx].name + '</a></p>';
				previous_pdx = pdx;
				previous_ul = false;
			}
			var txt = '';
			if (pp.idx >= 0)
			{
				txt += indiLinked(pp.idx, false);
			}
			if (pp.fdx >= 0)
			{
				txt += famLinked(pp.fdx, false);
			}
			if (pp.event) txt += ' (' + (pp.event.type || pp.event.descr) + ')';
			if (txt)
			{
				if (!previous_ul) point.mapInfo += '<ul class="dwr-mapinfo">';
				previous_ul = true;
				point.mapInfo += '<li class="dwr-mapinfo">' + txt + '</li>';
				if ($.inArray(pp.event.type, EVENTS_BIRTH) >= 0)
					point.nb_birth += 1;
				else if ($.inArray(pp.event.type, EVENTS_MARR) >= 0)
					point.nb_marr += 1;
				else if ($.inArray(pp.event.type, EVENTS_DEATH) >= 0)
					point.nb_death += 1;
				else
					point.nb_other += 1;
			}
		}
		if (previous_ul) point.mapInfo += '</ul>';
		nb_max = Math.max(nb_max, point.nb_birth + point.nb_marr + point.nb_death + point.nb_other);
		points[x_marker] = point;
		// Print marker
		if (MAP_SERVICE == 'Google')
		{
			(function(){ // This is used to create instances of local variables
				var ip = GetIconProps(x_marker);
				var marker = new google.maps.Marker({
					position:  mapCoords[x_marker],
					// draggable: true,
					title:     point.mapName,
					map:       mapObject,
					icon: {
						anchor: new google.maps.Point(ip.anchor.x, ip.anchor.y),
						scaledSize: new google.maps.Size(ip.size.w, ip.size.h),
						url: ip.src
					}
				});
				var infowindow = new google.maps.InfoWindow({
					content: point.mapInfo
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
					'title': point.mapName,
					'content': point.mapInfo
				});
				popupdiv.popover('hide');
				
				popupdiv.on('show.bs.popover', function () {
					// alert("show " + this.id);
					inhibitMapExpand = true;
				})
				popupdiv.on('hide.bs.popover', function () {
					// alert("hide " + this.id);
					inhibitMapExpand = true;
				})
			})();
		}
	}
	if (MAP_SERVICE == 'OpenStreetMap')
	{
		OsmPointStyle = function(feature, resolution)
		{
			var x_marker = parseInt(feature.p.name.replace('OsmPopup', ''));
			var ip = GetIconProps(x_marker);
			var iconStyle = new ol.style.Style({
				image: new ol.style.Icon(({
					anchor: [ip.anchor.x, ip.anchor.y],
					anchorXUnits: 'pixels',
					anchorYUnits: 'pixels',
					scale: ip.scale,
					src: ip.src
				}))
			});
			return([iconStyle]);
		};

		var vectorLayer = new ol.layer.Vector({
			source: osmVectorSource,
			style: OsmPointStyle
			// style: iconStyle
		});
		mapObject.addLayer(vectorLayer);
		mapObject.on('click', OsmClick);
		$(mapObject.getViewport()).on('mousemove', OsmMove);
	}
}


var inhibitMapExpand = false;

function mapExpand()
{
	if (inhibitMapExpand) return(false);
	search.MapExpanded = !($('body').hasClass('dwr-fullscreen'));
	Redirect();
	return(false);
}


function mapResize()
{
	var div = $('.dwr-expanded');
	if (div.length != 1) return(true);
	var w = $(window).width();
	var h = $(window).height();
	div.width(w);
	div.height(h);
	if (mapObject) mapObject.checkResize();
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

	inhibitMapExpand = false;
	popupdivs.each(function() {
		if (this.id == popupname)
		{
			overlay.setPosition(coord);
			$(this).popover('show');
		}
		else if ($(this).next('div.popover:visible').length)
		{
			$(this).popover('hide');
		}
	});
	
	return(false);
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
	ss = unorm.nfkc(ss).toLowerCase();
	var terms = ss.match(/[^\s]+/ig);
	var results = [];
	if (terms == null) return(results);
	for (var x = 0; x < data.length; x++)
	{
		var found = true;
		var s = fextract(x);
		s = unorm.nfkc(s).toLowerCase();
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
				return(I[idx].name + ' ' + I[idx].birth_year + ' ' + I[idx].death_year);
			},
			text: _('Persons'),
			findex: htmlPersonsIndex,
			fref: indiHref
		},
		{
			data: M,
			fextract: function(mdx) {return(M[mdx].title + ' ' + M[mdx].path);},
			text: _('Media'),
			findex: htmlMediaIndex,
			fref: mediaHref
		},
		{
			data: S,
			fextract: function(sdx) {return(S[sdx].title + ' ' + S[sdx].author + ' ' + S[sdx].abbrev + ' ' + S[sdx].publ);},
			text: _('Sources'),
			findex: htmlSourcesIndex,
			fref: sourceHref
		},
		{
			data: P,
			fextract: function(pdx) {return(P[pdx].name);},
			text: _('Places'),
			findex: htmlPlacesIndex,
			fref: placeHref
		}
	];
	var x;
	var nb_found = 0;
	var fref;
	var index;
	var html = '';
	var contents = [];
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
			contents.push({
				title: type.text + ' ' + results.length,
				text: type.findex(results)
			});
		}
	}
	html += printTitle(3, contents)
	if (nb_found == 1)
	{
		window.location.replace(fref(index));
		html = '';
	}
	else if (nb_found == 0)
	{
		html = '';
		if (search.Txt != '')
		{
			html += '<p>' + _('No matches found') + '</p>';
			$('#dwr-search-txt').focus();
		}
		html += '<p>' + _('Use the search box above in order to find a person.') + '</p>';
	}
	else
	{
		html = ('<p>' + _('Several matches.<br>Precise your search or choose in the lists below.') + '</p>') + html;
	}
	return(html);
}


//=================================================================
//======================================================= Gramps ID
//=================================================================

function ManageSearchStringGids()
{
	// Select between index in table or GID (mutually exclusive)
	if (search.Idx < 0) search.Idx = GidToIndex(search.Igid, I);
	if (search.Fdx < 0) search.Fdx = GidToIndex(search.Fgid, F);
	if (search.Mdx < 0) search.Mdx = GidToIndex(search.Mgid, M);
	if (search.Sdx < 0) search.Sdx = GidToIndex(search.Sgid, S);
	if (search.Pdx < 0) search.Pdx = GidToIndex(search.Pgid, P);
	if (search.Rdx < 0) search.Rdx = GidToIndex(search.Rgid, R);
	
	search.Igid = '';
	search.Fgid = '';
	search.Mgid = '';
	search.Sgid = '';
	search.Pgid = '';
	search.Rgid = '';
}

function GidToIndex(gid, table)
{
	// Change GID into index in table
	if (gid == '') return(-1);
	for(var i = 0; i < table.length; i++)
	{
		if (table[i].gid == gid) return(i);
	}
	return(-1);
}



//=================================================================
//======================================================== Calendar
//=================================================================

function printCalendar()
{
	var html = '';
	html += 'printCalendar not implemented';
	document.write(html);
}



//=================================================================
//============================================================ Home
//=================================================================

function HomePage()
{
	ParseSearchString();
	ManageSearchStringGids();

	var html = '';
	html += '<h1>' + TITLE + '</h1>';
	html += '<p>';
	var tables = [
		[SN, "surnames.html"],
        [I, "persons.html"],
        [F, "families.html"],
        [S, "sources.html"],
        [M, "medias.html"],
        [P, "places.html"],
        [R, "repositories.html"]
	];
	var sep = '';
	for (var i = 0; i < tables.length; i += 1)
	{
		var j = $.inArray(tables[i][1], PAGES_FILE_INDEX);
		if (j == -1) continue;
		html += sep
		html +=	'<a href="' + tables[i][1] + '?' + BuildSearchString() + '">';
		html +=	PAGES_TITLE_INDEX[j] + ': ' + tables[i][0].length;
		html +=	'</a>';
		sep = '<br>';
	}
	html += '<br> <p>' + embedSearchText() + '<p>';
	document.write(html);
}



//=================================================================
//========================================================== Config
//=================================================================

function ConfigPage()
{
	var html = '';
	html += '<h1>' + _('Configuration') + '</h1>';
	html += '<div class="panel panel-default">';
	html += '<div class="panel-body">';
	html += '<form id="dwr-chart-form" role="form" class="form-horizontal">';

	var configsCheck = [
//		['IncFamilies', _('Show family pages'), ''],
//		['IncSources', _('Show sources'), ''],
//		['IncMedia', _('Show images and media objects'), ''],
//		['IncPlaces', _('Show place pages'), ''],
//		['IncRepositories', _('Show repository pages'), ''],
//		['IncNotes', _('Show notes'), ''],
//		['IncAddresses', _('Show addresses'), '</div><hr><div class="row">'],
		['IndexShowBirth', _('Include a column for birth dates on the index pages'), ''],
		['IndexShowDeath', _('Include a column for death dates on the index pages'), ''],
		['IndexShowMarriage', _('Include a column for marriage dates on the index pages'), ''],
		['IndexShowPartner', _('Include a column for partners on the index pages'), ''],
		['IndexShowParents', _('Include a column for parents on the index pages'), ''],
		['IndexShowBkrefType', _('Include references in indexes'), '</div><hr><div class="row">'],
		['MapPlace', _('Include Place map on Place Pages'), ''],
		['MapFamily', _('Include a map in the individuals and family pages'), '</div><hr><div class="row">'],
		['ShowAllSiblings', _('Include half and/ or step-siblings on the individual pages'), '</div><div class="row">'],
		['SourceAuthorInTitle', _('Insert sources author in the sources title'), '</div><div class="row">'],
		['TabbedPanels', _('Use tabbed panels instead of sections'), ''],
		['HideGid', _('Suppress Gramps ID'), ''],
		['IncChangeTime', _('Show last modification time'), '']
	];
	html += '<div class="row">';
	for (var i = 0; i < configsCheck.length; i += 1)
	{
		var opt = configsCheck[i][0];
		html += '<div class="checkbox col-xs-12 col-md-6"><label>';
		html += '<input type="checkbox" id="dwr-cfg-' + opt + '"' + (search[opt] ? ' checked' : '') + '>';
		html += configsCheck[i][1] + '</label></div>';
		html += configsCheck[i][2];
	}
	html += '</div><hr>';
	var configsSelect = [
		['NbEntries', _('Number of entries in the tables'), A_LENGTH_MENU[1]]
	];
	html += '<div class="row">';
	for (var i = 0; i < configsSelect.length; i += 1)
	{
		var opt = configsSelect[i][0];
		var txts = configsSelect[i][2];
		html += '<label for="dwr-cfg-' + opt + '" class="control-label col-xs-8 col-md-4">' + configsSelect[i][1] + '</label>';
		html += '<div class="col-xs-4 col-md-2">';
		html += '<select name="dwr-cfg-' + opt + '" id="dwr-cfg-' + opt + '" class="form-control" size="1">';
		for (var j = 0; j < txts.length; j += 1)
		{
			html += '<option value="' + j + '"' + ((search[opt]== j) ? ' selected' : '') + '>' + txts[j] + '</option>';
		}
		html += '</select></div>';
	}
	html += '</div>'; //row
	html += '<hr>';
	html += '<div class="text-center">';
	html += '<button id="dwr-config-ok" type="button" class="btn btn-primary"> <span class="glyphicon glyphicon-ok"></span> ' + _('OK') + ' </button>';
	html += '</div>';

	html += '</form>';
	html += '</div>'; // panel-body
	html += '</div>'; // panel

	// Events
	$(window).load(function() {
		$('#dwr-config-ok').click(function() {
			for (var i = 0; i < configsCheck.length; i++)
			{
				var opt = configsCheck[i][0];
				search[opt] = $('#dwr-cfg-' + opt)[0].checked ? true : false;
			}
			for (var i = 0; i < configsSelect.length; i++)
			{
				var opt = configsSelect[i][0];
				search[opt] = $('#dwr-cfg-' + opt).val();
			}
			window.location.href = search.P + '?' + BuildSearchString();
			return(false);
		});
	});

	return(html);
}



//=================================================================
//============================================================ Main
//=================================================================

var PageContents;

function DwrMain(page)
{
	PageContents = page;

	ParseSearchString();
	ManageSearchStringGids();

	$(document).ready(function(){
		DwrMainRdy();
	});
}

function DwrMainRdy()
{
	var html = '';

	if ($.inArray(PageContents, [PAGE_SVG_TREE_FULL, PAGE_SVG_TREE_SAVE, PAGE_SVG_TREE_CONF]) < 0) search.SvgExpanded = false;
	if (search.Idx >= 0 && PageContents == PAGE_SVG_TREE)
	{
		searchDuplicate(search.Idx);
		html += SvgCreate();
	}
	else if (search.Idx >= 0 && PageContents == PAGE_SVG_TREE_FULL)
	{
		search.SvgExpanded = true;
		searchDuplicate(search.Idx);
		html += SvgCreate();
		$('body').html(html).toggleClass('dwr-fullscreen');
	}
	else if (search.Idx >= 0 && PageContents == PAGE_SVG_TREE_SAVE)
	{
		searchDuplicate(search.Idx);
		html += SvgSavePage();
		if (search.SvgExpanded) $('body').html(html);
	}
	else if (PageContents == PAGE_SVG_TREE_CONF)
	{
		html += SvgConfPage();
	}
	else if (search.Sdx >= 0 && PageContents == PAGE_SOURCE)
	{
		// Print 1 source
		html += printSource(search.Sdx);
	}
	else if (search.Mdx >= 0 && PageContents == PAGE_MEDIA)
	{
		// Print 1 media
		html += printMedia(search.Mdx);
	}
	else if (search.Idx >= 0 && PageContents == PAGE_INDI)
	{
		// Print individual
		html += printIndi(search.Idx);
	}
	else if (search.Fdx >= 0 && PageContents == PAGE_FAM)
	{
		// Print individual
		html += printFam(search.Fdx);
	}
	else if (search.Pdx >= 0 && PageContents == PAGE_PLACE && INC_PLACES)
	{
		// Print place
		html += printPlace(search.Pdx);
	}
	else if (search.Rdx >= 0 && PageContents == PAGE_REPO)
	{
		// Print repository
		html += printRepo(search.Rdx);
	}
	else if (PageContents == PAGE_SEARCH)
	{		
		// Print search by name results
		html = SearchObjects();
	}
	else if (PageContents == PAGE_CONF)
	{
		// Print configuration page
		html = ConfigPage();
	}
	else
	{
		// Page without index specified. Redirect to the search page
		window.location.replace(searchHref());
	}

	$('#body-page').html(html);

	handleCitations();
	handleTitles();
	// $('.dt-table').DataTable();
}
