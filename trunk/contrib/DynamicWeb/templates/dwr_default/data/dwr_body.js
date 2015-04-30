// Gramps - a GTK+/GNOME based genealogy program
//
// Copyright (C) 2014 Pierre Bélissent
//
// This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
// This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
// You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

// This script is part of the GRAMPS dynamic web report
// See 'dynamicweb.py'
//
// This script performs the following treatments:
//
//  - Build the document body structure:
//    The body contains the following sections (div):!
//       header: the header note given as parameter in GRAMPS
//       menu: The page menu
//          This menu contains a form for: search input, number of generations inputs
//          This menu is optional (depends on the body class "dwr-menuless")
//       body-page: The contents of the page
//          the body-page could contain a search form
//       footer: the footer note given as parameter in GRAMPS
//
//  - Manage the URL search string:
//    The URL search string is used to pass parameters to the page
//
//  - Manage the menu form, and the search form embedded form


//=================================================================
//============================================================ Body
//=================================================================

// Wait for the document to be ready
$(document).ready(function(){
	BodyDecorate();
});

function BodyDecorate()
{
	// Build the page structure: menu, header, footer

	// Parse the URL search string
	ParseSearchString();
	
	// Check if the current page needs a menu
	var menuless = false;
	if ($('.dwr-menuless').length > 0) menuless = true;
	
	// Build the div for the body content
	$('body').wrapInner('<div id="body-page" class="container"></div>');
	
	// Buid menu if any
	if (!menuless)
	{
		BuildMenu();
	}
	
	// Manage search form events if any
	if (!menuless || searchEmbedded)
	{
		$('#dwr-search-txt').val(search.Txt);
		$('#dwr-search2-txt').val(search.Txt);
	}
	
	// Text for the header
	if (HEADER != '') $('body').prepend(
		'<div id="dwr-header">' +
		HEADER +
		'</div>');
		
	// Text for the footer
	if ((FOOTER + COPYRIGHT) != '') $('body').append(
		'<div id="dwr-footer" class="panel-footer">' +
		FOOTER + COPYRIGHT +
		'</div>');
}


function BodyContentsMaxSize()
{
	// Return the available size for the body contents (in 'body_page_inner' div),
	// without any scrollbar needed to show all the contents.
	// The size is return as an object with 'width' and 'height' attributes
	var w = $(window).width();
	var h = $(window).height();
	if ($('#dwr-header').is(':visible')) h -= $('#dwr-header').outerHeight(true);
	if ($('#dwr-footer').is(':visible')) h -= $('#dwr-footer').outerHeight(true);
	if ($('#dwr-menu').is(':visible')) h -= $('#dwr-menu').outerHeight(true);
	var size = {'width': w, 'height': h}
	size = innerDivNetSize(size, $('body'));
	size = innerDivNetSize(size, $('#body-page'));
	return(size);
}


function innerDivNetSize(size, div)
{
	// Return the available size for the contents of "div",
	// based on a given size "size" for the div "div".
	var w = size.width;
	var h = size.height;
	if (div && div.length > 0)
	{
		var m = div.margin();
		var p = div.padding();
		var b = div.border();
		w -= p.left + b.left + m.left + p.right + b.right + m.right;
		h -= p.top + b.top + m.top + p.bottom + b.bottom + m.bottom;
	}
	return({'width': w, 'height': h});
}


//=================================================================
//=================================================== Search string
//=================================================================

// The parameters used for all the pages are given below
// The ParseSearchString function updates the variables below from the URL search string
// The BuildSearchString function builds the URL search string from the variables below

var search = {
	//Txt; // Test of the search input form (in the navbar or embedded in the page)
	//Asc; // Number of ascending generations
	//Dsc; // Number of descending generations
	//Idx; // Index of the current person (in table "I")
	//Fdx; // Index of the current family (in table "F")
	//Mdx; // Index of the current media object (in table "M")
	//Sdx; // Index of the current source (in table "S")
	//Pdx; // Index of the current place (in table "P")
	//Rdx; // Index of the current repository (in table "R")
	//SNdx; // Index of the current surname (in table "SN")
	//SvgType; // Type of SVG graph used (the number is the index in graphsInitialize)
	//ImgList; // List of media index (in table "M") for the slideshow
	//mapExpanded; // Whether the map should be expanded to full screen
};


// Does the page contain an embedded search input ?
var searchEmbedded = false;

// Was the URL search string parsed ?
var searchInitialized = false;


function ParseSearchString()
{
	// Parse the URL search string
	if (searchInitialized) return;
	searchInitialized = true;
	search.Txt = GetURLParameter('stxt', '');
	search.Idx = GetURLParameter('idx', -1);
	search.Fdx = GetURLParameter('fdx', -1);
	search.Mdx = GetURLParameter('mdx', -1);
	search.Sdx = GetURLParameter('sdx', -1);
	search.Pdx = GetURLParameter('pdx', -1);
	search.Rdx = GetURLParameter('rdx', -1);
	search.SNdx = GetURLParameter('sndx', -1);
	search.Asc = GetURLParameter('sasc', 4);
	search.Dsc = GetURLParameter('sdsc', 4);
	search.SvgType = GetURLParameter('svgtype', SVG_TREE_TYPE);
	search.ImgList = GetURLParameter('simg', []);
	if (search.Mdx != -1 && search.ImgList.length == 0) search.ImgList = [search.Mdx];
	search.mapExpanded = GetURLParameter('mexp', false);
}

function GetURLParameter(sParam, def)
{
	// Get a value from the URL search string
	// sParam: name of the parameter
	// def: Parameter default value
	var sPageURL = window.location.search.substring(1);
	var sURLVariables = sPageURL.split('&');
	for (var i = 0; i < sURLVariables.length; i++)
	{
		var sParameterName = sURLVariables[i].split('=');
		if (sParameterName[0] == sParam)
		{
			s = decodeURIComponent(sParameterName[1]);
			if ($.inArray(s, ['true', 'on']) >= 0) s = true;
			if ($.inArray(s, ['false', 'off']) >= 0) s = false;
			if (typeof(def) == 'number')
			{
				s = parseInt(s);
				if (isNaN(s)) s = def;
			}
			if (def instanceof Array) s = $.parseJSON(s);
			if (typeof(def) == 'boolean') s = s ? true : false;
			return(s);
		}
	}
	return(def);
}


function BuildSearchString(params)
{
	// Builds the URL search string from the global parameters values ("search")
	// and from the optional parameter of the function "params"
	// "params" has the same structure as "search"
	params = (typeof(params) !== 'undefined') ? params : {};
	var s = '';
	s = SetURLParameter(s, 'stxt', params.Txt, search.Txt, '');
	s = SetURLParameter(s, 'idx', params.Idx, search.Idx, -1);
	s = SetURLParameter(s, 'fdx', params.Fdx, search.Fdx, -1);
	s = SetURLParameter(s, 'mdx', params.Mdx, search.Mdx, -1);
	s = SetURLParameter(s, 'sdx', params.Sdx, search.Sdx, -1);
	s = SetURLParameter(s, 'pdx', params.Pdx, search.Pdx, -1);
	s = SetURLParameter(s, 'rdx', params.Rdx, search.Rdx, -1);
	s = SetURLParameter(s, 'sndx', params.SNdx, search.SNdx, -1);
	s = SetURLParameter(s, 'sasc', params.Asc, search.Asc, 4);
	s = SetURLParameter(s, 'sdsc', params.Dsc, search.Dsc, 4);
	s = SetURLParameter(s, 'svgtype', params.SvgType, search.SvgType, SVG_TREE_TYPE);
	s = SetURLParameter(s, 'simg', params.ImgList, search.ImgList, []);
	s = SetURLParameter(s, 'mexp', params.mapExpanded, search.mapExpanded, false);
	
// test for search string compression: result is not satisfactory
// toto = $.base64.encode(RawDeflate.deflate(unescape(encodeURIComponent(s))));
// titi = decodeURIComponent(escape(RawDeflate.inflate($.base64.decode(toto))));
// console.log(s);
// console.log(toto);
// console.log(titi);
// console.log(titi == s);
	return(s);
}

function SetURLParameter(sString, sParam, new_val, val, def)
{
	// Update the URL search string "sString" with the parameter "sParam"
	// new_val is the new parameter value, if any
	// val is the current parameter value, if any
	// val is the default parameter value, of type: number, boolean, Array, string
	
	// Manage when values are not provided
	val = (val == null || typeof(val) == 'undefined') ? def : val;
	val = (new_val == null || typeof(new_val) == 'undefined' || new_val == def) ? val : new_val;
	// Manage each type of value
	if (typeof(def) == 'number')
	{
		val = parseInt(val);
	}
	// else if (typeof(def) == 'string')
	// {
		// val = (val == '') ? def : val;
		// val = (new_val == '') ? val : new_val;
	// }
	else if (def instanceof Array)
	{
		val = (val == null || typeof(val) == 'undefined' || val.length == 0) ? def : val;
		val = (new_val == null || typeof(new_val) == 'undefined' || new_val.length == 0) ? val : new_val;
		val = JSON.stringify(val);
		def = JSON.stringify(def);
	}
	else if (typeof(def) == 'boolean')
	{
		val = val ? 1: 0;
		def = def ? 1: 0;
	}
	// Don't modify the search string if the value = default value
	if (val == def) return(sString);
	if (sString != '') sString += '&';
	return(sString + sParam + '=' + encodeURIComponent(val.toString()));
}


function Redirect(url)
{
	// Redirects to a given url
	
	var change_page = false;
	// Get the current page URL
	this_url = window.location.href;
	// this removes the anchor at the end, if there is one
	this_url = this_url.substring(0, (this_url.indexOf('#') == -1) ? this_url.length : this_url.indexOf('#'));
	// this removes the query after the file name, if there is one
	this_url = this_url.substring(0, (this_url.indexOf('?') == -1) ? this_url.length : this_url.indexOf('?'));
	if (typeof(url) == 'undefined') url = this_url;
	window.location.href = url + '?' + BuildSearchString();
}


//=================================================================
//============================================================ Form
//=================================================================

function FsearchExec(n)
{
	// Search input submission
	// n: 0 = search input in the navbar, 1 = search input embedded in page
	if (n == 0) search.Txt = $('#dwr-search-txt').val();
	if (n == 1) search.Txt = $('#dwr-search2-txt').val();
	search.Idx = -1;
	search.Fdx = -1;
	search.Mdx = -1;
	search.Sdx = -1;
	search.Pdx = -1;
	search.Rdx = -1;
	// Redirect to the search page
	window.location.href = searchHref();
	return(false);
}


function BuildMenu()
{
	// Get current page
	var ad = window.location.href;
	ad = ad.replace(/\?.*/, '');
	ad = ad.replace(/.*\//, '');
	var i;
	
	// Get current menu item
	menu_fallback = {
		'person.html': 'persons.html',
		'persons.html': 'person.html',
		'families.html': 'family.html',
		'family.html': 'families.html',
		'sources.html': 'source.html',
		'source.html': 'sources.html',
		'medias.html': 'media.html',
		'media.html': 'medias.html',
		'places.html': 'place.html',
		'place.html': 'places.html',
		'repositories.html': 'repository.html',
		'repository.html': 'repositories.html',
		'surnames.html': 'surname.html',
		'surname.html': 'surnames.html'
	}
	var i_current = -1;
	var i_current_fallback = -1;
	for (i=0; i<PAGES_TITLE.length; i++)
	{
		if (PAGES_FILE[i].indexOf(ad) >= 0)
		{
			// This menu item is the current page
			i_current = i;
		}
		if (menu_fallback[PAGES_FILE[i]] && menu_fallback[PAGES_FILE[i]].indexOf(ad) >= 0)
		{
			// This menu item could be the current page
			i_current_fallback = i;
		}
	}
	if (i_current == -1) i_current = i_current_fallback;
	
	// Text for the form
	var txt_form1 = '';
	txt_form1 += '<form class="navbar-form navbar-right" role="search" onsubmit="return FsearchExec(0)">';
	txt_form1 += '<div id="nav_form_search" class="input-group">';
	txt_form1 += '<input id="dwr-search-txt" type="text" class="form-control" placeholder="' + _('Person to search for') + '">';
	txt_form1 += '<div class="input-group-btn">';
	txt_form1 += '<button type="submit" class="btn btn-default"><span class="glyphicon glyphicon-search"></span></button>';
	txt_form1 += '</div>';
	txt_form1 += '</div>';
	txt_form1 += '</form> ';
	
	// Text for the menu
	var txt_menu = '';
	txt_menu += '<nav id="dwr-menu" class="navbar navbar-default">';
	txt_menu += '<div class="container-fluid">';
	
	txt_menu += '<div class="navbar-header">';
	txt_menu += '<button type="button" class="navbar-toggle collapsed" data-toggle="collapse" data-target="#navbar-collapse">';
	txt_menu += '<span class="sr-only">Toggle navigation</span>';
	txt_menu += '<span class="icon-bar"></span>';
	txt_menu += '<span class="icon-bar"></span>';
	txt_menu += '<span class="icon-bar"></span>';
	txt_menu += '</button>';
	txt_menu += txt_form1;
	txt_menu += '</div>';
	
	txt_menu += '<div class="collapse navbar-collapse" id="navbar-collapse">';
	txt_menu += '<ul class="nav navbar-nav">';
	for (i=0; i<PAGES_TITLE.length; i++)
	{
		var addclass = '';
		if (i == i_current) addclass = ' class="active"';
		txt_menu += '<li' + addclass + '><a href="' + toRoot + PAGES_FILE[i] + '?' +  BuildSearchString() + '">' + PAGES_TITLE[i] + '</a></li>';
	}
	txt_menu += '</ul>';
	txt_menu += '</div><!-- /.navbar-collapse -->';
	
	txt_menu += '</div><!-- /.container-fluid -->';
	txt_menu += '</nav>';

	$('body').prepend(txt_menu);
}


function embedSearch()
{
	// Build the embedded search input form
	var txt_form = '';
	txt_form += '<form id="embed_form_search" class="form-inline role="search" onsubmit="return FsearchExec(1)">';
	txt_form += '<div class="input-group">';
	txt_form += '<input id="dwr-search2-txt" type="text" class="form-control" placeholder="' + _('Person to search for') + '">';
	txt_form += '<div class="input-group-btn">';
	txt_form += '<button type="submit" class="btn btn-default"><span class="glyphicon glyphicon-search"></span></button>';
	txt_form += '</div>';
	txt_form += '</div>';
	txt_form += '</form>';
	document.write(txt_form);
	searchEmbedded = true;
}
