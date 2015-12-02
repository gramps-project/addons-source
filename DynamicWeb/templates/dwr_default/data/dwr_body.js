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
//	- Build the document body structure:
//	  The body contains the following sections (div):!
//		 header: the header note given as parameter in GRAMPS
//		 menu: The page menu
//			This menu contains a form for: search input, number of generations inputs
//			This menu is optional (depends on the body class "dwr-menuless")
//		 body-page: The contents of the page
//			the body-page could contain a search form
//		 footer: the footer note given as parameter in GRAMPS
//
//	- Manage the URL search string:
//	  The URL search string is used to pass parameters to the page
//
//	- Manage the menu form, and the search form embedded form


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
	if (search.SvgExpanded) menuless = true;
	if (search.MapExpanded) menuless = true;
	
	// Build the div for the body content
	$('body').wrapInner('<div id="body-page" class="container"></div>');
	
	// Build menu if any
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
		
	// Bootstrap responsive design detection
	// $('body').append(
		// '<div class="device-xs visible-xs-block"></div>' +
		// '<div class="device-sm visible-sm-block"></div>' +
		// '<div class="device-md visible-md-block"></div>' +
		// '<div class="device-lg visible-lg-block"></div>'
	// );
}


// function isBreakpoint(alias)
// {
	// Bootstrap responsive design detection
	// return $('.device-' + alias).is(':visible');
// }


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
	//P; // Previous page
	//=========================================== Data
	//Txt; // Test of the search input form (in the navbar or embedded in the page)
	//Idx; // Index of the current person (in table "I")
	//Fdx; // Index of the current family (in table "F")
	//Mdx; // Index of the current media object (in table "M")
	//Sdx; // Index of the current source (in table "S")
	//Pdx; // Index of the current place (in table "P")
	//Rdx; // Index of the current repository (in table "R")
	//SNdx; // Index of the current surname (in table "SN")
	//Igid; // Gramps ID of the current person
	//Fgid; // Gramps ID of the current family
	//Mgid; // Gramps ID of the current media object
	//Sgid; // Gramps ID of the current source
	//Pgid; // Gramps ID of the current place
	//Rgid; // Gramps ID of the current repository
	//ImgList; // List of media index (in table "M") for the slideshow
	//MapExpanded; // Whether the map should be expanded to full screen
	//=========================================== SVG tree
	//SvgType; // Type of SVG graph used
	//SvgShape; // The SVG graph shape
	//Asc; // Number of ascending generations
	//Dsc; // Number of descending generations
	//SvgDistribAsc; // The SVG graph parents distribution
	//SvgDistribDsc; // The SVG graph children distribution
	//SvgBackground; // The SVG graph color scheme
	//SvgDup; // Show duplicates in SVG graph
	//SvgExpanded; // Whether the SVG tree should be expanded to full screen
	//=========================================== Configuration parameters
	//IndexShowBirth;
	//IndexShowDeath;
	//IndexShowMarriage;
	//IndexShowPartner;
	//IndexShowParents;
	//IndexShowBkrefType;
	//ShowAllSiblings;
	//IncEvents;
	//IncFamilies;
	//IncSources;
	//IncMedia;
	//IncPlaces;
	//IncRepositories;
	//IncNotes;
	//IncAddresses;
	//MapPlace;
	//MapFamily;
	//SourceAuthorInTitle;
	//TabbedPanels;
	//HideGid;
	//NbEntries;
	//=========================================== Chart
	//ChartTable; // Data table for the statistics chart
	//ChartType; // Type of statistics chart
	//ChartDataW; // Data extractor, Series
	//ChartDataX; // Data extractor, X axis
	//ChartDataY; // Data extractor, Y axis
	//ChartDataZ; // Data extractor, Z axis
	//ChartFunctionX; // Data function, X axis
	//ChartFunctionY; // Data function, Y axis
	//ChartFunctionZ; // Data function, Z axis
	//ChartFilter1; // Data filter 1
	//ChartFilter2; // Data filter 2
	//ChartFilter3; // Data filter 3
	//ChartFilter1Min; // Data filter range lower bound
	//ChartFilter2Min; // Data filter range lower bound
	//ChartFilter3Min; // Data filter range lower bound
	//ChartFilter1Max; // Data filter range upper bound
	//ChartFilter2Max; // Data filter range upper bound
	//ChartFilter3Max; // Data filter range upper bound
	//ChartOpacity; // Chart point opacity
	//ChartBackground; // Chart point color theme
	//ChartValW; // Data value clicked, Series
	//ChartValX; // Data value clicked, X axis
	//ChartValY; // Data value clicked, Y axis
	//ChartValZ; // Data value clicked, Z axis
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
	search.P = GetURLParameter('p', '');

	search.Txt = GetURLParameter('stxt', '');
	search.Idx = GetURLParameter('idx', -1);
	search.Fdx = GetURLParameter('fdx', -1);
	search.Mdx = GetURLParameter('mdx', -1);
	search.Sdx = GetURLParameter('sdx', -1);
	search.Pdx = GetURLParameter('pdx', -1);
	search.Rdx = GetURLParameter('rdx', -1);
	search.SNdx = GetURLParameter('sndx', -1);
	search.Igid = GetURLParameter('igid', '');
	search.Fgid = GetURLParameter('fgid', '');
	search.Mgid = GetURLParameter('mgid', '');
	search.Sgid = GetURLParameter('sgid', '');
	search.Pgid = GetURLParameter('pgid', '');
	search.Rgid = GetURLParameter('rgid', '');
	search.ImgList = GetURLParameter('simg', []);
	if (search.Mdx != -1 && search.ImgList.length == 0) search.ImgList = [search.Mdx];
	search.MapExpanded = GetURLParameter('mexp', false);

	search.Asc = GetURLParameter('sasc', 4);
	search.Dsc = GetURLParameter('sdsc', 4);
	search.SvgType = GetURLParameter('svgtype', SVG_TREE_TYPE);
	search.SvgShape = GetURLParameter('svgshape', SVG_TREE_SHAPE);
	search.SvgDistribAsc = GetURLParameter('svgdasc', SVG_TREE_DISTRIB_ASC);
	search.SvgDistribDsc = GetURLParameter('svgddsc', SVG_TREE_DISTRIB_DSC);
	search.SvgBackground = GetURLParameter('svgbk', SVG_TREE_BACKGROUND);
	search.SvgDup = GetURLParameter('svgdup', SVG_TREE_SHOW_DUP);
	search.SvgExpanded = GetURLParameter('svgx', false);

	search.IndexShowBirth = GetURLParameter('cii', INDEX_SHOW_BIRTH);
	search.IndexShowDeath = GetURLParameter('cid', INDEX_SHOW_DEATH);
	search.IndexShowMarriage = GetURLParameter('cim', INDEX_SHOW_MARRIAGE);
	search.IndexShowPartner = GetURLParameter('cis', INDEX_SHOW_PARTNER);
	search.IndexShowParents = GetURLParameter('cip', INDEX_SHOW_PARENTS);
	search.IndexShowBkrefType = GetURLParameter('cib', INDEX_SHOW_BKREF_TYPE);
	search.ShowAllSiblings = GetURLParameter('csib', SHOW_ALL_SIBLINGS);
	search.IncEvents = GetURLParameter('ce', INC_EVENTS);
	search.IncFamilies = GetURLParameter('cf', INC_FAMILIES);
	search.IncSources = GetURLParameter('cs', INC_SOURCES);
	search.IncMedia = GetURLParameter('cm', INC_MEDIA);
	search.IncPlaces = GetURLParameter('cp', INC_PLACES);
	search.IncRepositories = GetURLParameter('cr', INC_REPOSITORIES);
	search.IncNotes = GetURLParameter('cn', INC_NOTES);
	search.IncAddresses = GetURLParameter('ca', INC_ADDRESSES);
	search.MapPlace = GetURLParameter('cmp', MAP_PLACE);
	search.MapFamily = GetURLParameter('cmf', MAP_FAMILY);
	search.SourceAuthorInTitle = GetURLParameter('csa', SOURCE_AUTHOR_IN_TITLE);
	search.TabbedPanels = GetURLParameter('ctp', TABBED_PANELS);
	search.HideGid = GetURLParameter('cg', HIDE_GID);
	search.NbEntries = GetURLParameter('cne', 0);

	search.ChartTable = GetURLParameter('charttable', 0);
	search.ChartType = GetURLParameter('charttype', 0);
	search.ChartDataW = GetURLParameter('chartw', EXTRACTOR_DISABLED);
	search.ChartDataX = GetURLParameter('chartx', EXTRACTOR_DISABLED);
	search.ChartDataY = GetURLParameter('charty', EXTRACTOR_DISABLED);
	search.ChartDataZ = GetURLParameter('chartz', EXTRACTOR_DISABLED);
	search.ChartFunctionX = GetURLParameter('chartfx', FUNCTION_NONE);
	search.ChartFunctionY = GetURLParameter('chartfy', FUNCTION_NONE);
	search.ChartFunctionZ = GetURLParameter('chartfz', FUNCTION_NONE);
	search.ChartFilter1 = GetURLParameter('chartfr1', EXTRACTOR_DISABLED);
	search.ChartFilter2 = GetURLParameter('chartfr2', EXTRACTOR_DISABLED);
	search.ChartFilter3 = GetURLParameter('chartfr3', EXTRACTOR_DISABLED);
	search.ChartFilter1Min = GetURLParameter('chartfr1i', "");
	search.ChartFilter2Min = GetURLParameter('chartfr2i', "");
	search.ChartFilter3Min = GetURLParameter('chartfr3i', "");
	search.ChartFilter1Max = GetURLParameter('chartfr1a', "");
	search.ChartFilter2Max = GetURLParameter('chartfr2a', "");
	search.ChartFilter3Max = GetURLParameter('chartfr3a', "");
	search.ChartOpacity = GetURLParameter('chartopa', STATISTICS_CHART_OPACITY);
	search.ChartBackground = GetURLParameter('chartbk', CHART_BACKGROUND_GRADIENT);
	search.ChartValW = GetURLParameter('chartvw', "");
	search.ChartValX = GetURLParameter('chartvx', "");
	search.ChartValY = GetURLParameter('chartvy', "");
	search.ChartValZ = GetURLParameter('chartvz', "");
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
			var s = decodeURIComponent(sParameterName[1]);
			if (typeof(def) == 'number')
			{
				s = parseInt(s);
				if (isNaN(s)) s = def;
			}
			if (def instanceof Array) s = $.parseJSON(s);
			if (typeof(def) == 'boolean')
			{
				if ($.inArray(s, ['true', 'on']) >= 0) s = true;
				if ($.inArray(s, ['false', 'off']) >= 0) s = false;
				if (!isNaN(parseInt(s))) s = parseInt(s);
				s = s ? true : false;
			}
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
	page = window.location.href.replace(/\?.*/, '').replace(toRoot, '£££').replace(/.*£££/, '');
	if (page == 'conf.html') page = search.P;
	s = SetURLParameter(s, 'p', params.P, page, '');

	s = SetURLParameter(s, 'stxt', params.Txt, search.Txt, '');
	s = SetURLParameter(s, 'idx', params.Idx, search.Idx, -1);
	s = SetURLParameter(s, 'fdx', params.Fdx, search.Fdx, -1);
	s = SetURLParameter(s, 'mdx', params.Mdx, search.Mdx, -1);
	s = SetURLParameter(s, 'sdx', params.Sdx, search.Sdx, -1);
	s = SetURLParameter(s, 'pdx', params.Pdx, search.Pdx, -1);
	s = SetURLParameter(s, 'rdx', params.Rdx, search.Rdx, -1);
	s = SetURLParameter(s, 'sndx', params.SNdx, search.SNdx, -1);
	s = SetURLParameter(s, 'igid', params.Igid, search.Igid, '');
	s = SetURLParameter(s, 'fgid', params.Fgid, search.Fgid, '');
	s = SetURLParameter(s, 'mgid', params.Mgid, search.Mgid, '');
	s = SetURLParameter(s, 'sgid', params.Sgid, search.Sgid, '');
	s = SetURLParameter(s, 'pgid', params.Pgid, search.Pgid, '');
	s = SetURLParameter(s, 'rgid', params.Rgid, search.Rgid, '');
	s = SetURLParameter(s, 'simg', params.ImgList, search.ImgList, []);
	s = SetURLParameter(s, 'mexp', params.MapExpanded, search.MapExpanded, false);

	s = SetURLParameter(s, 'sasc', params.Asc, search.Asc, 4);
	s = SetURLParameter(s, 'sdsc', params.Dsc, search.Dsc, 4);
	s = SetURLParameter(s, 'svgtype', params.SvgType, search.SvgType, SVG_TREE_TYPE);
	s = SetURLParameter(s, 'svgshape', params.SvgShape, search.SvgShape, SVG_TREE_SHAPE);
	s = SetURLParameter(s, 'svgdasc', params.SvgDistribAsc, search.SvgDistribAsc, SVG_TREE_DISTRIB_ASC);
	s = SetURLParameter(s, 'svgddsc', params.SvgDistribDsc, search.SvgDistribDsc, SVG_TREE_DISTRIB_DSC);
	s = SetURLParameter(s, 'svgbk', params.SvgBackground, search.SvgBackground, SVG_TREE_BACKGROUND);
	s = SetURLParameter(s, 'svgdup', params.SvgDup, search.SvgDup, SVG_TREE_SHOW_DUP);
	s = SetURLParameter(s, 'svgx', params.SvgExpanded, search.SvgExpanded, false);

	s = SetURLParameter(s, 'cii', params.IndexShowBirth, search.IndexShowBirth, INDEX_SHOW_BIRTH);
	s = SetURLParameter(s, 'cid', params.IndexShowDeath, search.IndexShowDeath, INDEX_SHOW_DEATH);
	s = SetURLParameter(s, 'cim', params.IndexShowMarriage, search.IndexShowMarriage, INDEX_SHOW_MARRIAGE);
	s = SetURLParameter(s, 'cis', params.IndexShowPartner, search.IndexShowPartner, INDEX_SHOW_PARTNER);
	s = SetURLParameter(s, 'cip', params.IndexShowParents, search.IndexShowParents, INDEX_SHOW_PARENTS);
	s = SetURLParameter(s, 'cib', params.IndexShowBkrefType, search.IndexShowBkrefType, INDEX_SHOW_BKREF_TYPE);
	s = SetURLParameter(s, 'csib', params.ShowAllSiblings, search.ShowAllSiblings, SHOW_ALL_SIBLINGS);
	s = SetURLParameter(s, 'ce', params.IncEvents, search.IncEvents, INC_EVENTS);
	s = SetURLParameter(s, 'cf', params.IncFamilies, search.IncFamilies, INC_FAMILIES);
	s = SetURLParameter(s, 'cs', params.IncSources, search.IncSources, INC_SOURCES);
	s = SetURLParameter(s, 'cm', params.IncMedia, search.IncMedia, INC_MEDIA);
	s = SetURLParameter(s, 'cp', params.IncPlaces, search.IncPlaces, INC_PLACES);
	s = SetURLParameter(s, 'cr', params.IncRepositories, search.IncRepositories, INC_REPOSITORIES);
	s = SetURLParameter(s, 'cn', params.IncNotes, search.IncNotes, INC_NOTES);
	s = SetURLParameter(s, 'ca', params.IncAddresses, search.IncAddresses, INC_ADDRESSES);
	s = SetURLParameter(s, 'cmp', params.MapPlace, search.MapPlace, MAP_PLACE);
	s = SetURLParameter(s, 'cmf', params.MapFamily, search.MapFamily, MAP_FAMILY);
	s = SetURLParameter(s, 'csa', params.SourceAuthorInTitle, search.SourceAuthorInTitle, SOURCE_AUTHOR_IN_TITLE);
	s = SetURLParameter(s, 'ctp', params.TabbedPanels, search.TabbedPanels, TABBED_PANELS);
	s = SetURLParameter(s, 'cg', params.HideGid, search.HideGid, HIDE_GID);
	s = SetURLParameter(s, 'cne', params.NbEntries, search.NbEntries, 0);

	s = SetURLParameter(s, 'charttable', params.ChartTable, search.ChartTable, 0);
	s = SetURLParameter(s, 'charttype', params.ChartType, search.ChartType, 0);
	s = SetURLParameter(s, 'chartw', params.ChartDataW, search.ChartDataW, EXTRACTOR_DISABLED);
	s = SetURLParameter(s, 'chartx', params.ChartDataX, search.ChartDataX, EXTRACTOR_DISABLED);
	s = SetURLParameter(s, 'charty', params.ChartDataY, search.ChartDataY, EXTRACTOR_DISABLED);
	s = SetURLParameter(s, 'chartz', params.ChartDataZ, search.ChartDataZ, EXTRACTOR_DISABLED);
	s = SetURLParameter(s, 'chartfx', params.ChartFunctionX, search.ChartFunctionX, FUNCTION_NONE);
	s = SetURLParameter(s, 'chartfy', params.ChartFunctionY, search.ChartFunctionY, FUNCTION_NONE);
	s = SetURLParameter(s, 'chartfz', params.ChartFunctionZ, search.ChartFunctionZ, FUNCTION_NONE);
	s = SetURLParameter(s, 'chartfr1', params.ChartFilter1, search.ChartFilter1, EXTRACTOR_DISABLED);
	s = SetURLParameter(s, 'chartfr2', params.ChartFilter2, search.ChartFilter2, EXTRACTOR_DISABLED);
	s = SetURLParameter(s, 'chartfr3', params.ChartFilter3, search.ChartFilter3, EXTRACTOR_DISABLED);
	s = SetURLParameter(s, 'chartfr1i', params.ChartFilter1Min, search.ChartFilter1Min, "");
	s = SetURLParameter(s, 'chartfr2i', params.ChartFilter2Min, search.ChartFilter2Min, "");
	s = SetURLParameter(s, 'chartfr3i', params.ChartFilter3Min, search.ChartFilter3Min, "");
	s = SetURLParameter(s, 'chartfr1a', params.ChartFilter1Max, search.ChartFilter1Max, "");
	s = SetURLParameter(s, 'chartfr2a', params.ChartFilter2Max, search.ChartFilter2Max, "");
	s = SetURLParameter(s, 'chartfr3a', params.ChartFilter3Max, search.ChartFilter3Max, "");
	s = SetURLParameter(s, 'chartopa', params.ChartOpacity, search.ChartOpacity, STATISTICS_CHART_OPACITY);
	s = SetURLParameter(s, 'chartbk', params.ChartBackground, search.ChartBackground, CHART_BACKGROUND_GRADIENT);
	s = SetURLParameter(s, 'chartvw', params.ChartDataW, search.ChartValW, "");
	s = SetURLParameter(s, 'chartvx', params.ChartDataX, search.ChartValX, "");
	s = SetURLParameter(s, 'chartvy', params.ChartDataY, search.ChartValY, "");
	s = SetURLParameter(s, 'chartvz', params.ChartDataZ, search.ChartValZ, "");
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
//=================================================== Form and menu
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
	var i_current = -1;
	for (i=0; i<PAGES_TITLE.length; i++)
	{
		if (PAGES_FILE[i].indexOf(ad) >= 0)
		{
			// This menu item is the current page
			i_current = i;
		}
	}
	
	// Text for the form
	var txt_form1 = '';
	txt_form1 += '<div class="pull-right">';
	txt_form1 += '<form class="navbar-form" role="search" onsubmit="return FsearchExec(0)">';
	txt_form1 += '<div class="input-group">';
	txt_form1 += '<input id="dwr-search-txt" type="text" class="form-control" placeholder="' + _('Person to search for') + '">';
	txt_form1 += '<div class="input-group-btn">';
	txt_form1 += '<button type="submit" class="btn btn-default"><span class="glyphicon glyphicon-search"></span></button>';
	txt_form1 += '</div>';
	txt_form1 += '</div>';
	if (INC_PAGECONF)
	{
		txt_form1 += ' <button type="button" id="dwr-conf" class="btn btn-default dwr-navbar-toggle-enabled" onclick="window.location.href=\'' + (toRoot + 'conf.html?' + BuildSearchString()) + '\';"><span class="glyphicon glyphicon-cog"></span></button>';
	}
	txt_form1 += '</form>';
	txt_form1 += '</div>';
	
	// Text for the menu
	var txt_menu = '';
	txt_menu += '<nav id="dwr-menu" class="navbar navbar-default" role="navigation">';
	txt_menu += '<div class="container-fluid">';
	
	txt_menu += '<div class="navbar-header">';
	txt_menu += '<button type="button" class="navbar-toggle" data-toggle="collapse" data-target="#dwr-navbar-collapse">';
	txt_menu += '<span class="sr-only">Toggle navigation</span>';
	txt_menu += '<span class="icon-bar"></span>';
	txt_menu += '<span class="icon-bar"></span>';
	txt_menu += '<span class="icon-bar"></span>';
	txt_menu += '</button>';
	if (BRAND_TITLE)
		txt_menu += '<a class="navbar-brand" href="index.html">' + BRAND_TITLE + '</a>';
	else
		txt_menu += '<a class="navbar-brand" href="https://gramps-project.org/"><img src="data/Gramps_Logo.png"></a>';
	txt_menu += '</div>';
	
	txt_menu += '<div id="dwr-navbar-collapse" class="collapse navbar-collapse">';
	txt_menu += '<ul class="nav navbar-nav">';
	for (i=0; i<PAGES_TITLE.length; i++)
	{
		var addclass = '';
		if (i == i_current) addclass = ' class="active"';
		if (PAGES_FILE[i] == "")
		{
			txt_menu += '<li class="dropdown">';
			txt_menu += '<a href="#" class="dropdown-toggle" data-toggle="dropdown">' + _('Indexes') +' <b class="caret"></b></a>';
			txt_menu += '<ul class="dropdown-menu">';
			for (var j = 0; j < PAGES_TITLE_INDEX.length; j += 1)
			{
				txt_menu += '<li' + addclass + '><a href="' + toRoot + PAGES_FILE_INDEX[j] + '?' +  BuildSearchString() + '">' + PAGES_TITLE_INDEX[j] + '</a></li>';
			}
			txt_menu += '</ul></li>';
		}
		else
		{
			txt_menu += '<li' + addclass + '><a href="' + toRoot + PAGES_FILE[i] + '?' +  BuildSearchString() + '">' + PAGES_TITLE[i] + '</a></li>';
		}
	}
	if (INC_PAGECONF)
	{
		txt_menu += '<li class="dwr-navbar-toggle-disabled"><a href="' + toRoot + 'conf.html' + '?' +  BuildSearchString() + '">' + _('Configuration') + '</a></li>';
	}
	txt_menu += '</ul>';
	txt_menu += txt_form1;
	txt_menu += '</div>'; // .navbar-collapse
	txt_menu += '</div>'; // .container-fluid
	txt_menu += '</nav>';

	$('body').prepend(txt_menu);
}


function embedSearch()
{
	// Build the embedded search input form
	document.write(embedSearchText());
}
function embedSearchText()
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
	searchEmbedded = true;
	return(txt_form);
}
