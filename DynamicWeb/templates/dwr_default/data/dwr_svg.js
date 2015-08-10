// Gramps - a GTK+/GNOME based genealogy program
//
// Copyright (C) 2014 Pierre B�lissent
// See also https://github.com/andrewseddon/raphael-zpd/blob/master/raphael-zpd.js for parts of code from Raphael-ZPD
//
// This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
// This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
// You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


var nbGenAsc; // Number of ancestry generations to print
var nbGenDsc; // Number of descedants generations to print
var nbGenAscFound; // Number of ancestry generations found in the tree
var nbGenDscFound; // Number of descedants generations found in the tree

var depNum = 1; // First number used for the SOSA notation
var DimX, DimY; // Size of the viewport in pixels

var rayons, rayonsAsc, rayonsDsc; // Size of the circle for each generation
var nbPeopleAsc; // Number of people for each generation (ancestry)
var nbPeopleDsc; // Number of people for each generation (descendants)
var minSizeAsc; // Minimal size of the elements (number of sub-elements), for each generation (ancestry)
var minSizeDsc; // Minimal size of the elements (number of sub-elements), for each generation (descendants)
var reuseIdx, reusePred, reuseSucc, reuseNum, reuseN;
var reuseX;

var txtRatioMax = 10.0; // Maximal width / height ratio for the text boxes
var txtRatioMin = 1.0; // Minimal width / height ratio for the text boxes
var linkRatio = 0.2; // Ratio between space reserved for the links  and the box width
var fontFactorX = 1.8, fontFactorY = 1.0;
var coordX = 10000.0, coordY = 10000.0;
var margeX = 200.0, margeY = 200.0;
var svgStroke = 1e10; // Width of the box strokes
var svgStrokeRatio = 10.0; // Minimal ratio box size / stroke
var svgDivMinHeight = 200; // Minimal graph height
var maxAge = 0;
var minPeriod = 1e10;
var maxPeriod = -1e10;


var hemiA = 0; // Overflow angle for half-circle and quadrant graphs

var tpid = 0;
var curNumStr;

var x0, y0, w0, h0; // Coordinates of the top-left corner of the SVG graph, + width and height
var x1, y1, w1, h1; // Coordinates of the top-left corner of the SVG sheet, + width and height
var maxTextWidth; // Maximum width of the textboxes

var viewBoxX, viewBoxY, viewBoxW, viewBoxH; // Screen viewbox (top-left corner, width and height)
var viewScale; // Scale factor between SVG coordinates and screen coordinates

var iTxt = '';

// Each person is printed with a text SVG element, over a box (path).
// The same person could appear several times in the graph (duplicates)
// The elements ID used to print a person are in the form:
//    - SVGTREE_P_<number> : box for the person (it is an SVG path)
//    - SVGTREE_T_<number> : text for the person (it is an SVG text)

// List giving the SVG element used to print a person, in the form
//    - person index (in table 'I')
//    - family index (in table 'F') when printing spouses (null in other cases)
//    - level (0 = center person, 1 = 1st generation, etc.)
//    - list of SVG elements connected to this element (children/parents)
//    - list of SVG elements connected to this element (spouses)
//    - size of the element (number of sub-elements)
//    - list of commands for the element creation (strings)
//    - box for the person (it is an SVG path)
var svgParents, svgChildren, svgElts;
SVGELT_IDX = 0;
SVGELT_FDX = 1;
SVGELT_FDX_CHILD = 2;
SVGELT_LEV = 3;
SVGELT_NEXT = 4;
SVGELT_NEXT_SPOU = 5;
SVGELT_NB = 6;
SVGELT_CMD = 7;
SVGELT_P = 8;

SVGIDX_SEPARATOR = -99; // Arbitrary number, used as person index (SVGELT_IDX) for separators
SVG_SEPARATOR_SIZE = 0.3 // Separator size compared to person box size

SVG_GENDER_K = 0.9;


//==============================================================================
//==============================================================================
// Pointers to all graph types and shapes
//==============================================================================
//==============================================================================

var CoordRatio;
var CoordXr;
var CoordYr;

SVG_SHAPE_VERTICAL_TB = 0;
SVG_SHAPE_VERTICAL_BT = 1;
SVG_SHAPE_HORIZONTAL_LR = 2;
SVG_SHAPE_HORIZONTAL_RL = 3;
SVG_SHAPE_FULL_CIRCLE = 4;
SVG_SHAPE_HALF_CIRCLE = 5;
SVG_SHAPE_QUADRANT = 6;

var graphsBuild =
[
	[
		buildAscTreeV,
		buildAscTreeV,
		buildAscTreeH,
		buildAscTreeH,
		buildAsc,
		buildAscHemi,
		buildAscQadr
	],
	[
		buildDscTreeV,
		buildDscTreeV,
		buildDscTreeH,
		buildDscTreeH,
		buildDsc,
		buildDscHemi,
		buildDscQadr
	],
	[
		buildDscTreeVSpou,
		buildDscTreeVSpou,
		buildDscTreeHSpou,
		buildDscTreeHSpou,
		buildDscSpou,
		buildDscHemiSpou,
		buildDscQadrSpou
	],
	[
		buildBothTreeV,
		buildBothTreeV,
		buildBothTreeH,
		buildBothTreeH,
		buildBoth,
		buildBoth,
		buildBoth
	],
	[
		buildBothTreeVSpou,
		buildBothTreeVSpou,
		buildBothTreeHSpou,
		buildBothTreeHSpou,
		buildBothSpou,
		buildBothSpou,
		buildBothSpou
	]
];

var graphsInitialize =
[
	[
		initAscTreeV,
		initAscTreeV,
		initAscTreeH,
		initAscTreeH,
		initAsc,
		initAscHemi,
		initAscQadr
	],
	[
		initDscTreeV,
		initDscTreeV,
		initDscTreeH,
		initDscTreeH,
		initDsc,
		initDscHemi,
		initDscQadr
	],
	[
		initDscTreeVSpou,
		initDscTreeVSpou,
		initDscTreeHSpou,
		initDscTreeHSpou,
		initDscSpou,
		initDscHemiSpou,
		initDscQadrSpou
	],
	[
		initBothTreeV,
		initBothTreeV,
		initBothTreeH,
		initBothTreeH,
		initBoth,
		initBoth,
		initBoth
	],
	[
		initBothTreeVSpou,
		initBothTreeVSpou,
		initBothTreeHSpou,
		initBothTreeHSpou,
		initBothSpou,
		initBothSpou,
		initBothSpou
	]
];


//==============================================================================
//==============================================================================
// Document creation
//==============================================================================
//==============================================================================

var svgPaper, svgRoot;


function SvgCreate()
{
	nbGenAsc = search.Asc + 1;
	nbGenDsc = search.Dsc + 1;
	nbGenAscFound = 0;
	nbGenDscFound = 0;
	maxAge = 0;
	minPeriod = 1e10;
	maxPeriod = -1e10;
	$(window).load(SvgInit);
	var html = '';
	if (!search.SvgExpanded)
		html += '<div id="svg-panel" class="panel panel-default dwr-panel-tree"><div class="panel-body">';
	html += '<div id="svg-drawing" class="' + (search.SvgExpanded ? 'svg-drawing-expand' : 'svg-drawing') + '">';
	// Buttons div
	html += '<div id="svg-buttons">';
	html += '<div class="btn-group-vertical" role="group">';
	html += '<button id="svg-expand" type="button" class="btn btn-default" title="' + (search.SvgExpanded ? _('Restore') : _('Expand')) + '">';
	html += '<span class="glyphicon ' + (search.SvgExpanded ? 'glyphicon-resize-small' : 'glyphicon-resize-full') + '"></span>';
	html += '</button>';
	html += '<button id="svg-zoom-in" type="button" class="btn btn-default" title="' + _('Zoom in') + '">';
	html += '<span class="glyphicon glyphicon-zoom-in"></span>';
	html += '</button>';
	html += '<button id="svg-zoom-out" type="button" class="btn btn-default" title="' + _('Zoom out') + '">';
	html += '<span class="glyphicon glyphicon-zoom-out"></span>';
	html += '</button>';
	html += '<button id="svg-config" type="button" class="btn btn-default" title="' + _('Configuration') + '">';
	html += '<span class="glyphicon glyphicon-cog"></span>';
	html += '</button>';
	html += '<button id="svg-saveas" type="button" class="btn btn-default" title="' + _('Save tree as file') + '">';
	html += '<span class="glyphicon glyphicon-save"></span>';
	html += '</button>';
	html += '</div>';
	html += '</div>';
	// Floating popup div
	html += '<div id="svg-popup" class="svg-popup">';
	html += '</div>';
	html += '</div>'; // svg-drawing
	if (!search.SvgExpanded)
		html += '</div></div>'; // panel
	return(html);
}


function SvgInit()
{
	// Initialize graph dimensions
	CalcBoundingBox();
	graphsInitialize[search.SvgType][search.SvgShape]();
	CalcViewBox();
	svgPaper = new Raphael('svg-drawing', DimX, DimY);
	$(svgPaper.canvas).attr('xmlns:xlink', "http://www.w3.org/1999/xlink");
	svgPaper.setViewBox(0, 0, viewBoxW, viewBoxH, true);
	svgRoot = svgPaper.canvas;
	// Compute the stroke-width depending on graph size
	svgStroke = Math.min(svgStroke, 0.5 / viewScale);
	// Floating popup
	SvgPopupHide();
	$('#svg-popup').mousemove(SvgPopupMove);
	// Prepare the SVG group that will be used for scrolling/zooming
	var g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
	g.id = 'viewport';
	svgRoot.appendChild(g);
	svgPaper.canvas = g;
	var s = 'matrix(' + viewScale + ',0,0,' + viewScale + ',' + (-viewBoxX) + ',' + (-viewBoxY) + ')';
	g.setAttribute('transform', s);
	// Manage buttons
	$('#svg-zoom-in').click(SvgZoomIn);
	$('#svg-zoom-out').click(SvgZoomOut);
	$('#svg-expand').click(SvgToggleExpand);
	svgPaper.canvas = g;
	// Config button
	$('#svg-config').click(SvgConfig);
	$('#svg-saveas').click(SvgSaveAs);
	// Setup event handlers
	$(window).mouseup(SvgMouseUpWindow)
		.mousedown(SvgMouseDownWindow)
		.mousemove(SvgMouseMoveWindow)
		.resize(SvgResize);
	$(svgRoot).mousewheel(SvgMouseWheel)
		.attr('unselectable', 'on')
		.css('user-select', 'none')
		.on('selectstart', false)
		.mousedown(SvgMouseDown)
		.mousemove(SvgMouseMoveHover)
		.mouseout(SvgMouseOut);
	// Build the graph
	graphsBuild[search.SvgType][search.SvgShape]();
	SvgCreateElts(0);
	// Context menu
	context.init({
		fadeSpeed: 100,
		before: SvgContextBefore,
		compress: true
	});
	svgContextMenuItems = [
		// {
			// text: (search.SvgExpanded) ? _('Restore') : _('Expand'),
			// href: svgHref(search.Idx, !search.SvgExpanded)
		// },
		// {text: _('Zoom in'), href: 'javascript:SvgZoomIn();'},
		// {text: _('Zoom out'), href: 'javascript:SvgZoomOut();'}
	];
	context.attach('#svg-drawing', svgContextMenuItems);
}


//==============================================================================
//==============================================================================
// Configuration page
//==============================================================================
//==============================================================================

function SvgConfPage()
{
	var html = '';
	// Graph type selector floating div
	html += '<div id="svg-drawing-type" class="panel panel-default svg-drawing-type">';
	html += '<div class="panel-body">';
	html += '<form role="form">';
	html += '<div class="row">';
	html += '<div class="col-xs-12 col-sm-6">';
	html += '<div class="form-group">';
	html += '<label for="svg-type">' + _('SVG tree graph type') + '</label>';
	html += '<select name="svg-type" id="svg-type" class="form-control" size="1" title="' + _('Select the type of graph') + '">';
	for (i = 0; i < SVG_TREE_TYPES_NAMES.length; i++)
	{
		html += '<option value="' + i + '"' + ((search.SvgType == i) ? ' selected' : '') + '>' + SVG_TREE_TYPES_NAMES[i] + '</option>';
	}
	html += '</select>';
	html += '</div>'; // form-group
	html += '</div>'; // col-xs-*
	html += '<div class="col-xs-12 col-sm-6">';
	html += '<div class="form-group">';
	html += '<label for="svg-shape">' + _('SVG tree graph shape') + '</label>';
	html += '<select name="svg-shape" id="svg-shape" class="form-control" size="1" title="' + _('Select the shape of graph') + '">';
	for (i = 0; i < SVG_TREE_SHAPES_NAMES.length; i++)
	{
		html += '<option value="' + i + '"' + ((search.SvgShape == i) ? ' selected' : '') + '>' + SVG_TREE_SHAPES_NAMES[i] + '</option>';
	}
	html += '</select>';
	html += '</div>'; // form-group
	html += '</div>'; // col-xs-*
	html += '</div>'; // row
	html += '<div class="row">';
	html += '<div class="col-xs-12 col-sm-6">';
	html += '<div class="form-group">';
	html += '<label for="svg-distrib-asc">' + _('SVG tree parents distribution') + '</label>';
	html += '<select name="svg-distrib-asc" id="svg-distrib-asc" class="form-control" size="1" title="' + _('Select the parents distribution (fan charts only)') + '">';
	for (i = 0; i < SVG_TREE_DISTRIB_ASC_NAMES.length; i++)
	{
		html += '<option value="' + i + '"' + ((search.SvgDistribAsc == i) ? ' selected' : '') + '>' + SVG_TREE_DISTRIB_ASC_NAMES[i] + '</option>';
	}
	html += '</select>';
	html += '</div>'; // form-group
	html += '</div>'; // col-xs-*
	html += '<div class="col-xs-12 col-sm-6">';
	html += '<div class="form-group">';
	html += '<label for="svg-distrib-dsc">' + _('SVG tree children distribution') + '</label>';
	html += '<select name="svg-distrib-dsc" id="svg-distrib-dsc" class="form-control" size="1" title="' + _('Select the children distribution (fan charts only)') + '">';
	for (i = 0; i < SVG_TREE_DISTRIB_DSC_NAMES.length; i++)
	{
		html += '<option value="' + i + '"' + ((search.SvgDistribDsc == i) ? ' selected' : '') + '>' + SVG_TREE_DISTRIB_DSC_NAMES[i] + '</option>';
	}
	html += '</select>';
	html += '</div>'; // form-group
	html += '</div>'; // col-xs-*
	html += '</div>'; // row
	html += '<div class="row">';
	html += '<div class="col-xs-12 col-sm-4">';
	html += '<div class="form-group">';
	html += '<label for="svg-background">' + _('Background') + '</label>';
	html += '<select name="svg-background" id="svg-background" class="form-control" size="1" title="' + _('Select the background color scheme') + '">';
	for (i = 0; i < SVG_TREE_BACKGROUND_NAMES.length; i++)
	{
		html += '<option value="' + i + '"' + ((search.SvgBackground == i) ? ' selected' : '') + '>' + SVG_TREE_BACKGROUND_NAMES[i] + '</option>';
	}
	html += '</select>';
	html += '</div>'; // form-group
	html += '</div>'; // col-xs-*
	html += '<div class="col-xs-6 col-sm-4">';
	html += '<div class="form-group">';
	html += '<label for="svg-asc">' + _('Ancestors') + '</label>';
	html += '<select id="svg-asc" class="form-control svg-gens" size="1" title="' + _('Select the number of ascending generations') + '">';
	for (i = 0; i < NB_GENERATIONS_MAX; i++)
	{
		html += '<option value="' + i + '"' + ((search.Asc == i) ? ' selected' : '') + '>' + i + '</option>';
	}
	html += '</select>';
	html += '</div>'; // form-group
	html += '</div>'; // col-xs-*
	html += '<div class="col-xs-6 col-sm-4">';
	html += '<div class="form-group">';
	html += '<label for="svg-dsc">' + _('Descendants') + '</label>';
	html += '<select id="svg-dsc" class="form-control svg-gens" size="1" title="' + _('Select the number of descending generations') + '">';
	for (i = 0; i < NB_GENERATIONS_MAX; i++)
	{
		html += '<option value="' + i + '"' + ((search.Dsc == i) ? ' selected' : '') + '>' + i + '</option>';
	}
	html += '</select>';
	html += '</div>'; // form-group
	html += '</div>'; // col-xs-*
	html += '</div>'; // row
	html += '<div class="row">';
	html += '<div class="col-xs-6 col-sm-4">';
	html += '<div class="checkbox">';
	html += '<label>';
	html += '<input type="checkbox" name="svg-dup" id="svg-dup" ' + (search.SvgDup ? 'checked' : '') + ' title="' + _('Whether to use a special color for the persons that appear several times in the SVG tree') + '"/>';
	html += _('Show duplicates') + '</label>';
	html += '</div>'; // checkbox
	html += '</div>'; // col-xs-*
	html += '</div>'; // row
	html += '<div class="text-center">';
	html += '<button id="svg-config-ok" type="button" class="btn btn-primary"> <span class="glyphicon glyphicon-ok"></span> ' + _('OK') + ' </button>';
	html += '</div>';
	html += '</form>';
	html += '</div>'; // panel-body
	html += '</div>'; // svg-drawing-type

	// Help panel
	html += '<div class="panel panel-default">';
	html += '<div class="panel-heading">';
	html += '<span class="glyphicon glyphicon-question-sign"></span> ' + _('Graph help');
	html += '</div>'; // panel-heading
	html += '<div class="panel-body">';
	html += _('<p>Click on a person to center the graph on this person.<br>When clicking on the center person, the person page is shown.<p>The type of graph could be selected in the list (on the top left side of the graph)<p>The number of ascending end descending generations could also be adjusted.<p>Use the mouse wheel or the buttons to zoom in and out.<p>The graph could also be shown full-screen.');
	html += '</div>'; // panel-body
	html += '</div>'; // panel

	// Events
	$(window).load(function() {
		$('#svg-config-ok').click(SvgConfSubmit);
	});

	return(html);
}

function SvgConfSubmit()
{
	search.SvgType = $('#svg-type').val();
	search.SvgShape = $('#svg-shape').val();
	search.SvgDistribAsc = $('#svg-distrib-asc').val();
	search.SvgDistribDsc = $('#svg-distrib-dsc').val();
	search.SvgBackground = $('#svg-background').val();
	search.Asc = $('#svg-asc').val();
	search.Dsc = $('#svg-dsc').val();
	search.SvgDup = $('#svg-dup').is(':checked');
	return(svgRef());
}


//==============================================================================
//==============================================================================
// Save page
//==============================================================================
//==============================================================================

function SvgSavePage()
{
	var html = '';
	html +=
		'<div id="svg-loader" class="text-center">' +
		'<h1>' + _('Preparing file ...') + '</h1>' +
		'</div>';
	html += SvgCreate();

	$(window).load(function() {
		$('body').css('overflow', 'hidden');
	});

	return(html);
}

function SvgSaveText()
{
	$('#svg-loader').html(
		'<h1>' + _('File ready') + '</h1>' +
		_('<p>This page provides the SVG raw code.<br>Copy the contents into a text editor and save as an SVG file.<br>Make sure that the text editor encoding is UTF-8.</p>') +
		'<p class="text-centered"><button id="svg-save-ok" type="button" class="btn btn-primary"> <span class="glyphicon glyphicon-ok"></span> ' + _('OK') + ' </button></p>'
		);
	$('#svg-save-ok').click(SvgSaveOk)
}

function SvgSaveOk()
{
	if ($('#svg-loader').length == 0) return;
	var xml = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>';
	xml += '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"\n';
	xml += 'style=\'' + CssDefaultProperties() + '\'\n';
	xml += ' width="' + $('svg').attr('width') + '"';
	xml += ' height="' + $('svg').attr('height') + '"';
	xml += ' viewBox="' + $('svg')[0].getAttribute('viewBox') + '"';
	xml += ' version="' + $('svg').attr('version') + '"';
	xml += ' preserveAspectRatio="' + $('svg')[0].getAttribute('preserveAspectRatio') + '"';
	xml += '>';
	xml += '<style type="text/css">\n';
	xml += '<![CDATA[\n';
	xml += CssProperties('.svg-tree');
	xml += CssProperties('.svg-text');
	xml += CssProperties('.svg-line');
	xml += ']]>\n';
	xml += '</style>\n';
	xml += removeLinks($('svg').html());
	xml += '</svg>';
	$('body').addClass('svg-save-text');
	$('body').text(formatXml(xml));
	$('body').css('overflow', 'auto');
	return(false);
}

function removeLinks(xml)
{
	xml = xml.replace(/(?:<a [^>]*>|<a>|<\/a [^>]*>|<\/a>)/g, '');
	return xml;
}

function CssProperties(selectorText)
{
	var css_text = selectorText + ' {\n';
	for (var s = 0 ; s < document.styleSheets.length; s++)
	{
		var cssRules = document.styleSheets[s].cssRules ||
			document.styleSheets[s].rules || []; // IE support
		for (var c = 0; c < cssRules.length; c++)
		{
			if (cssRules[c].selectorText === selectorText)
			{
				css_text += cssRules[c].style.cssText;
			}
		}
	}
	css_text += '}\n';
	return(css_text);
}

function CssDefaultProperties()
{
	var css_text = '';
	var style = $('svg')[0].style;
	for (var propertyName in style)
	{
		if (propertyName != propertyName.toLowerCase()) continue;
		if (propertyName.indexOf("webkit") != -1) continue;
		if (typeof(propertyName) == 'string' && isNaN(parseInt(propertyName)))
		{
			val = style[propertyName];
			if (typeof(val) == 'string')
			{
				val = '' + $('svg').css(propertyName);
				if (val != '' && val.indexOf("'") == -1)
					css_text += ' ' + propertyName + ':' + val + ';';
			}
		}
	}
	return(css_text);
}

function formatXml(xml)
{
	var reg = /(>)\s*(<)(\/*)/g;
	var wsexp = / *(.*) +\n/g;
	var contexp = /(<.+>)(.+\n)/g;
	xml = xml.replace(reg, '$1\n$2$3').replace(wsexp, '$1\n').replace(contexp, '$1\n$2');
	var pad = 0;
	var formatted = '';
	var lines = xml.split('\n');
	var indent = 0;
	var lastType = 'other';
	// 4 types of tags - single, closing, opening, other (text, doctype, comment) - 4*4 = 16 transitions
	var transitions = {
		'single->single'    : 0,
		'single->closing'   : -1,
		'single->opening'   : 0,
		'single->other'     : 0,
		'closing->single'   : 0,
		'closing->closing'  : -1,
		'closing->opening'  : 0,
		'closing->other'    : 0,
		'opening->single'   : 1,
		'opening->closing'  : 0,
		'opening->opening'  : 1,
		'opening->other'    : 1,
		'other->single'     : 0,
		'other->closing'    : -1,
		'other->opening'    : 0,
		'other->other'      : 0
	};

	for (var i=0; i < lines.length; i++) {
		var ln = lines[i];
		var single = Boolean(ln.match(/<.+\/>/)); // is this line a single tag? ex. <br />
		var closing = Boolean(ln.match(/<\/.+>/)); // is this a closing tag? ex. </a>
		var opening = Boolean(ln.match(/<[^!].*>/)); // is this even a tag (that's not <!something>)
		var type = single ? 'single' : closing ? 'closing' : opening ? 'opening' : 'other';
		var fromTo = lastType + '->' + type;
		lastType = type;
		var padding = '';

		indent += transitions[fromTo];
		for (var j = 0; j < indent; j++) {
			padding += '    ';
		}

		formatted += padding + ln + '\n';
	}

	return formatted;
};


//==============================================================================
//==============================================================================
// Tree size and styles
//==============================================================================
//==============================================================================

function CalcBoundingBox()
{
	if ($('.svg-drawing-expand').length == 0)
	{
		var w = $('#svg-drawing').innerWidth();
		var h = $('#svg-drawing').innerHeight();
		var dim = innerDivNetSize(BodyContentsMaxSize(), $('#svg-panel'));
		dim = innerDivNetSize(dim, $('#svg-drawing'));
		if (!w || w < svgDivMinHeight) w = dim.width;
		DimX = Math.max(svgDivMinHeight, w);
		DimY = Math.max(svgDivMinHeight, h, dim.height);
	}
	else
	{
		DimX = Math.max(svgDivMinHeight, $(window).width());
		DimY = Math.max(svgDivMinHeight, $(window).height());
	}
	// console.log($('#svg-drawing').width(), $('#svg-drawing').height(), DimX, DimY);
}


function CalcViewBox()
{
	viewScale = Math.min(DimX / w0, DimY / h0);
	x1 = x0 - (DimX / viewScale - w0) / 2;
	y1 = y0 - (DimY / viewScale - h0) / 2;
	w1 = DimX / viewScale;
	h1 = DimY / viewScale;
	// console.log(x0, y0, w0, h0, x1, y1, w1, h1);
	viewBoxX = Math.round(x1 * viewScale);
	viewBoxY = Math.round(y1 * viewScale);
	viewBoxW = DimX;
	viewBoxH = DimY;
}


function SvgCreateElts(n)
{
	// Difers the SVG element creation
	var incr = 50;
	for (var x_elt = n; (x_elt < n + incr) && (x_elt < svgElts.length); x_elt++)
	{
		for (var i = 0; i < svgElts[x_elt][SVGELT_CMD].length; i++)
		{
			// console.log(svgElts[x_elt][SVGELT_CMD][i]);
			eval(svgElts[x_elt][SVGELT_CMD][i]);
		}
	}
	if (svgElts.length > n + incr)
	{
		setTimeout(function()
		{
			SvgCreateElts(n + incr);
		}, 200);
	}
	else
	{
		SvgSaveText();
	}
}


function SvgSetStyle(p, text, x_elt, lev)
{
	var elt = svgElts[x_elt];
	// Get the class of the person box and text
	var fill = "#FFFFFF";
	var stroke = "#000000";
	var dark = 1.0;
	if (search.SvgBackground == 0) // BACKGROUND_GENDER
	{
		var g = 'unknown';
		if (I[elt[SVGELT_IDX]][I_GENDER] == 'M') g = 'male';
		if (I[elt[SVGELT_IDX]][I_GENDER] == 'F') g = 'female';
		var d = 'alive';
		if (I[elt[SVGELT_IDX]][I_DEATH_YEAR] != "") d = 'death';
		fill = GRAMPS_PREFERENCES['color-gender-' + g + '-' + d];
	}
	if (typeof(lev) != 'undefined' && search.SvgBackground == 1) // BACKGROUND_GRAD_GEN
	{
		fill = SvgColorGrad(0, Math.max(nbGenAscFound, nbGenDscFound) - 1, lev);
		dark = SVG_GENDER_K;
	}
	if ( // BACKGROUND_GRAD_AGE, BACKGROUND_GRAD_PERIOD
		(search.SvgBackground == 2) ||
		(search.SvgBackground == 4))
	{
		var b = parseInt(I[elt[SVGELT_IDX]][I_BIRTH_YEAR]);
		var d = parseInt(I[elt[SVGELT_IDX]][I_DEATH_YEAR]);
		var x;
		var m;
		if ((search.SvgBackground == 2) && !isNaN(b) && !isNaN(d))
		{
			fill = SvgColorGrad(0, maxAge, d - b);
		}
		if ((search.SvgBackground == 4) && (minPeriod <= maxPeriod))
		{
			if (!isNaN(b) && !isNaN(d))
				fill = SvgColorGrad(minPeriod, maxPeriod, (d + b) / 2.0);
			else if (!isNaN(b))
				fill = SvgColorGrad(minPeriod, maxPeriod, b);
			else if (!isNaN(d))
				fill = SvgColorGrad(minPeriod, maxPeriod, d);
		}
		dark = SVG_GENDER_K;
	}
	if (search.SvgBackground == 3) // BACKGROUND_SINGLE_COLOR
	{
		fill = SVG_TREE_COLOR1;
	}
	if (search.SvgBackground == 5) // BACKGROUND_WHITE
	{
		fill = SVG_TREE_COLOR_SCHEME0[lev % SVG_TREE_COLOR_SCHEME0.length];
		dark = SVG_GENDER_K;
	}
	if (search.SvgBackground == 6) // BACKGROUND_SCHEME1
	{
		fill = SVG_TREE_COLOR_SCHEME1[lev % SVG_TREE_COLOR_SCHEME1.length];
		dark = SVG_GENDER_K;
	}
	if (search.SvgBackground == 7) // BACKGROUND_SCHEME2
	{
		fill = SVG_TREE_COLOR_SCHEME2[lev % SVG_TREE_COLOR_SCHEME2.length];
		dark = SVG_GENDER_K;
	}
	if (search.SvgDup && isDuplicate(elt[SVGELT_IDX]))
	{
		fill = SVG_TREE_COLOR_DUP;
	}
	if ((elt[SVGELT_IDX] < 0) || (I[elt[SVGELT_IDX]][I_GENDER] == 'F')) dark = 1.0;
	var fill_hsb = Raphael.rgb2hsb(Raphael.getRGB(fill));
	var fill_rgb = Raphael.hsb2rgb({
		h: fill_hsb.h,
		s: fill_hsb.s,
		b: fill_hsb.b * dark
	});
	fill = Raphael.rgb(fill_rgb.r, fill_rgb.g, fill_rgb.b);
	// Get hyperlink address
	var href = svgHref(elt[SVGELT_IDX]);
	// Set box attributes
	p.node.setAttribute('class', 'svg-tree');
	p.node.setAttribute('fill', fill);
	p.node.setAttribute('stroke-width', svgStroke);
	p.node.id = 'SVGTREE_P_' + x_elt;
	// p.attr("href", href);
	elt[SVGELT_P] = p;
	if (text)
	{
		// Set box text attributes
		text.node.setAttribute('class', 'svg-text');
		text.node.id = 'SVGTREE_T_' + x_elt;
	}
}


function SvgColorGrad(mini, maxi, value)
{
	var x = value - mini;
	var m = maxi - mini;
	if (x < 0) x = 0;
	if (x >= m) x = m;
	x = (m == 0) ? 0 : 1.0 * x / m;
	// Compute color gradient
	var cstart = Raphael.rgb2hsb(Raphael.getRGB(SVG_TREE_COLOR1));
	var cend = Raphael.rgb2hsb(Raphael.getRGB(SVG_TREE_COLOR2));
	var rgb = Raphael.hsb2rgb({
		h: (1.0 + cstart.h + x * ((1.0 + cend.h - cstart.h) % 1.0)) % 1.0,
		s: (1-x) * cstart.s + x * cend.s,
		b: (1-x) * cstart.b + x * cend.b
	});
	return(Raphael.rgb(rgb.r, rgb.g, rgb.b));
}


//==============================================================================
//==============================================================================
//=========================================== Mouse events
//==============================================================================
//==============================================================================

var clickOrigin = null; // Click position when moving / zooming
var svgMoving = false; // The graph is being moved
var tfMoveZoom = null; // move/zoom transform matrix
var hoverBox = -1; // SVG element index (in table svgElts) where is the mouse
var leftButtonDown = false; // Mouse left button position


function SvgGetElt(node)
{
	while (node.id != 'svg-drawing')
	{
		if (node.id.indexOf('SVGTREE_') == 0)
			return(parseInt(node.id.replace(/SVGTREE_[A-Z_]+/, '')));
		node = node.parentNode;
	}
	return(-1);
}


function SvgMouseDownWindow(event)
{
	if (event.button > 0) return(true);
	leftButtonDown = true;
	return(true);
}

function SvgMouseDown(event)
{
	if (event.button > 0) return(true);
	clickOrigin = getEventPoint(event);
	svgMoving = false;
	var g = svgRoot.getElementById('viewport');
	tfMoveZoom = g.getCTM().inverse();
	var elt = SvgGetElt(event.target);
	if (elt >= 0)
	{
		SvgMouseEventEnter(elt);
	}
	return(false);
}

function SvgMouseUpWindow(event)
{
	if (event.button > 0) return(true);
	leftButtonDown = false;
	if (hoverBox >= 0)
	{
		var elt = SvgGetElt(event.target);
		if (elt == hoverBox)
		{
			var idx = svgElts[hoverBox][SVGELT_IDX];
			if (idx >= 0)
			{
				// Get hyperlink address
				svgRef(svgElts[hoverBox][SVGELT_IDX]);
				return(false);
			}
		}
	}
	clickOrigin = null;
	svgMoving = false;
	tfMoveZoom = null;
	return(true);
}

function SvgToggleExpand(elt)
{
	search.SvgExpanded = !($('#svg-drawing').hasClass('svg-drawing-expand'));
	svgRef();
}

function SvgConfig(elt)
{
	svgConfRef();
}

function SvgSaveAs(elt)
{
	svgSaveRef();
}

function SvgMouseMoveWindow(event)
{
	if (clickOrigin)
	{
		var p = getEventPoint(event);
		var d = Math.sqrt((p.x - clickOrigin.x) * (p.x - clickOrigin.x) + (p.y - clickOrigin.y) * (p.y - clickOrigin.y));
		if (d > 10 || svgMoving)
		{
			svgMoving = true;
			var p2 = p.matrixTransform(tfMoveZoom);
			var o2 = clickOrigin.matrixTransform(tfMoveZoom);
			// console.log(p.x, clickOrigin.x, p2.x, o2.x);
			SvgSetGraphCtm(tfMoveZoom.inverse().translate(p2.x - o2.x, p2.y - o2.y));
			SvgMouseEventExit();
			SvgPopupHide();
			return(false);
		}
	}
	if (svgMoving)
	{
		event.stopImmediatePropagation();
		return(false);
	}
	return(true);
}

function SvgMouseMoveHover(event)
{
	if (!svgMoving && !leftButtonDown)
	{
		var elt = SvgGetElt(event.target);
		if (elt >= 0)
		{
			if (elt != hoverBox)
			{
				SvgMouseEventExit();
				SvgPopupHide();
				SvgMouseEventEnter(elt);
			}
			SvgPopupShow(elt, event);
		}
		else if (hoverBox >= 0)
		{
			SvgMouseEventExit();
			SvgPopupHide();
		}
	}
	return(true);
}

function SvgMouseOut(event)
{
	var e = event.toElement || event.relatedTarget;
	if ($(e).attr('id') == 'svg-popup' ||
		e == svgRoot ||
		(e && (e.parentNode == svgRoot ||
		(e.parentNode && (e.parentNode.parentNode == svgRoot ||
		(e.parentNode.parentNode && (e.parentNode.parentNode.parentNode == svgRoot))))))) return(true);
	SvgMouseEventExit();
	SvgPopupHide();
	return(true);
}

function SvgMouseEventExit()
{
	if (hoverBox >= 0)
	{
		var p = svgElts[hoverBox][SVGELT_P];
		if (p)
		{
			p.node.setAttribute('stroke-width', svgStroke);
			p.node.setAttribute('class', 'svg-tree');
			// $('#SVGTREE_P_' + hoverBox).removeClass('svg-tree-hover');
		}
	}
	hoverBox = -1;
}

function SvgMouseEventEnter(elt)
{
	if (elt >= 0 && elt != hoverBox)
	{
		hoverBox = -1;
		var p = svgElts[elt][SVGELT_P];
		if (p)
		{
			hoverBox = elt;
			p.node.setAttribute('stroke-width', svgStroke * 2.0);
			p.node.setAttribute('class', 'svg-tree svg-tree-hover');
			// $('#SVGTREE_P_' + hoverBox).addClass('svg-tree-hover');
		}
	}
}

function SvgMouseWheel(event)
{
	if (event.preventDefault) event.preventDefault();
    var p = getEventPoint(event);
	// See jquery-mousewheel plugin
	// console.log(event.deltaX, event.deltaY, event.deltaFactor);
	SvgZoom(event.deltaY, p);
	// Zoom factor: 0.97/1.03
	return(false);
}

function SvgZoom(delta, p)
{
	// Use center if p not defined
	if (typeof(p) == 'undefined')
	{
		p = svgRoot.createSVGPoint();
		p.x = DimX / 2;
		p.y = DimY / 2;
	}
	// Zoom factor: 0.97/1.03
	var z = Math.pow(1 + Math.sign(delta) * .1, Math.abs(delta));
    var g = svgRoot.getElementById('viewport');
	var ctm = g.getCTM().inverse();
	var scale = ctm.a;
	if ((delta < 0) && (z / scale < DimX / w1))
		z = DimX / w1 * scale; // Minimal zoom
	if ((delta > 0) && (z / scale > 1.0))
		z = 1.0 * scale; // Maximal zoom
	p = p.matrixTransform(ctm);
	// Compute new scale matrix in current mouse position
	var k = svgRoot.createSVGMatrix().translate(p.x, p.y).scale(z).translate(-p.x, -p.y);
	SvgSetGraphCtm(g.getCTM().multiply(k));
	// Update the matrix used for moving
	if (tfMoveZoom) tfMoveZoom = k.inverse().multiply(tfMoveZoom);
}

function SvgZoomIn()
{
	SvgZoom(1);
	return(false);
}

function SvgZoomOut()
{
	SvgZoom(-1);
	return(false);
}

function SvgResize()
{
	// Do not resize when not full size
	if ($('.svg-drawing-expand').length == 0) return;
	// Compute new size
	var _DimX = DimX;
	var _DimY = DimY;
	var _viewBoxX = viewBoxX;
	var _viewBoxY = viewBoxY;
	var _viewBoxW = viewBoxW;
	var _viewBoxH = viewBoxH;
	var _viewScale = viewScale;
	CalcBoundingBox();
	CalcViewBox();
	viewScale = _viewScale;
	if ((_DimX == DimX) && (_DimY == DimY)) return(true);
	// Change viewport size
	var g = svgPaper.canvas
	svgPaper.canvas = svgRoot;
	svgPaper.setSize(DimX, DimY);
	svgPaper.setViewBox(0, 0, viewBoxW, viewBoxH);
	svgPaper.canvas = g;
	// Move buttons
	var gbut1 = $('#buttons_group_1');
	if (gbut1.length > 0)
	{
		gbut1 = gbut1[0];
		var m = gbut1.getCTM();
		m = m.translate(DimX - _DimX, DimY - _DimY);
		// console.log('matrix(' + m.a + ',' + m.b + ',' + m.c + ',' + m.d + ',' + m.e + ',' + m.f + ') '+DimX+', '+DimY+' / '+_DimX+', '+_DimY);
		gbut1.setAttribute('transform', 'matrix(' + m.a + ',' + m.b + ',' + m.c + ',' + m.d + ',' + m.e + ',' + m.f + ')');
	}
	var gbut2 = $('#buttons_group_2');
	if (gbut2.length > 0)
	{
		gbut2 = gbut2[0];
		var m = gbut2.getCTM();
		m = m.translate(DimX - _DimX, 0)
		gbut2.setAttribute('transform', 'matrix(' + m.a + ',' + m.b + ',' + m.c + ',' + m.d + ',' + m.e + ',' + m.f + ')');
	}
	// Translate graph
	var g = svgRoot.getElementById('viewport');
	// var s = g.getCTM().translate((DimX - _DimX) / 2.0, (DimY - _DimY) / 2.0);
	var s = g.getCTM();
	s.e += (DimX - _DimX) / 2.0;
	s.f += (DimY - _DimY) / 2.0;
	// console.log((DimX - _DimX) / 2.0, (s.translate((DimX - _DimX) / 2.0, (DimY - _DimY) / 2.0)).e-s.e);
	SvgSetGraphCtm(s);
	return(false);
}

function getEventPoint(event)
{
	var p = svgRoot.createSVGPoint();
	var posX = $(svgRoot).offset().left;
	var posY = $(svgRoot).offset().top;
	p.x = event.pageX - posX;
	p.y = event.pageY - posY;
	// console.log(p.x, p.y);
	// p.x = event.clientX;
	// p.y = event.clientY;
	return p;
}


function SvgSetGraphCtm(matrix)
{
	var g = svgRoot.getElementById('viewport');
	// Limit matrix to bounding rect
	// console.log(matrix.a * x1 + matrix.e, matrix.a * (x1 + w1) + matrix.e - DimX);
	matrix.e -= Math.max(0, matrix.a * x1 + matrix.e);
	matrix.e -= Math.min(0, matrix.a * (x1 + w1) + matrix.e - DimX);
	matrix.f -= Math.max(0, matrix.a * y1 + matrix.f);
	matrix.f -= Math.min(0, matrix.a * (y1 + h1) + matrix.f - DimY);
	// Limit matrix to graph area
	if (matrix.a * x0 + matrix.e > 0)
		matrix.e -= Math.min(matrix.a * x0 + matrix.e, Math.max(0, matrix.a * (x0 + x0 + w0) / 2 + matrix.e - DimX / 2));
	if (matrix.a * (x0 + w0) + matrix.e < DimX)
		matrix.e -= Math.max(matrix.a * (x0 + w0) + matrix.e - DimX, Math.min(0, matrix.a * (x0 + x0 + w0) / 2 + matrix.e - DimX / 2));
	if (matrix.a * y0 + matrix.f > 0)
		matrix.f -= Math.min(matrix.a * y0 + matrix.f, Math.max(0, matrix.a * (y0 + y0 + h0) / 2 + matrix.f - DimY / 2));
	if (matrix.a * (y0 + h0) + matrix.f < DimY)
		matrix.f -= Math.max(matrix.a * (y0 + h0) + matrix.f - DimY, Math.min(0, matrix.a * (y0 + y0 + h0) / 2 + matrix.f - DimY / 2));
	// Set transform
	var s = 'matrix(' + matrix.a + ',' + matrix.b + ',' + matrix.c + ',' + matrix.d + ',' + matrix.e + ',' + matrix.f + ')';
	g.setAttribute('transform', s);
}


//==============================================================================
//==============================================================================
// Popup for each person
//==============================================================================
//==============================================================================


svgPopupIdx = -1;

function SvgPopupHide()
{
	$('#svg-popup').hide();
}

function SvgPopupShow(elt, event)
{
	var idx = svgElts[elt][SVGELT_IDX];
	if (idx < 0)
	{
		SvgPopupHide();
		return;
	}
	var fdx = (typeof(svgElts[elt][SVGELT_FDX]) == 'undefined') ? -1 : svgElts[elt][SVGELT_FDX];
	$('#svg-popup').show();
	if (idx != svgPopupIdx)
	{
		var html = '<p>' + I[idx][I_NAME];
		html += '<br>* ' + I[idx][I_BIRTH_YEAR];
		if (I[idx][I_BIRTH_PLACE] != "") html += ' (' + I[idx][I_BIRTH_PLACE] + ')';
		if (fdx >= 0)
		{
			html += '<br>x ' + F[fdx][F_MARR_YEAR];
			if (F[fdx][F_MARR_PLACE] != "") html += ' (' + F[fdx][F_MARR_PLACE] + ')';
		}
		if (I[idx][I_DEATH_YEAR] != "")
		{
			html += '<br>+ ' + I[idx][I_DEATH_YEAR];
			if (I[idx][I_DEATH_PLACE] != "") html += ' (' + I[idx][I_DEATH_PLACE] + ')';
		}
		html += '</p>';
		$('#svg-popup').html(html);
		svgPopupIdx = idx;
	}
	SvgPopupMove(event);
}

function SvgPopupMove(event)
{
	var p = getEventPoint(event);
	var m = 10;
	p.x += m;
	p.y += m;
	if (p.x > DimX / 2) p.x -= $('#svg-popup').outerWidth(true) + 2 * m;
	if (p.y > DimY / 2) p.y -= $('#svg-popup').outerHeight(true) + 2 * m;
	$('#svg-popup').css('left', p.x);
	$('#svg-popup').css('top', p.y);
	return(true);
}


//==============================================================================
//==============================================================================
// Context menu
//==============================================================================
//==============================================================================

function SvgContextBefore($menu, event)
{
	var data = [];
	var elt = SvgGetElt(event.target);
	if (elt >= 0)
	{
		var idx = svgElts[elt][SVGELT_IDX];
		if (idx >= 0)
		{
			// Person menu items
			data = data.concat([
				{text: I[idx][I_NAME], href: svgHref(idx)},
				{text: _('Person page'), href: indiHref(idx)}
			]);
			var j, k, subm;
			// Spouses menu items
			subm = [];
			for (j = 0; j < I[idx][I_FAMS].length; j++)
			{
				var fdx = I[idx][I_FAMS][j];
				for (k = 0; k < F[fdx][F_SPOU].length; k++)
				{
					if (F[fdx][F_SPOU][k] == idx) continue;
					subm.push({
						text: I[F[fdx][F_SPOU][k]][I_NAME],
						href: svgHref(F[fdx][F_SPOU][k])
					});
				}
			}
			if (subm.length > 0) data.push({
				text: _('Spouses'),
				subMenu: subm
			});
			// Siblings menu items
			subm = [];
			for (j = 0; j < I[idx][I_FAMC].length; j++)
			{
				var fdx = I[idx][I_FAMC][j][FC_INDEX];
				for (k = 0; k < F[fdx][F_CHIL].length; k++)
				{
					if (F[fdx][F_CHIL][k][FC_INDEX] == idx) continue;
					subm.push({
						text: I[F[fdx][F_CHIL][k][FC_INDEX]][I_NAME],
						href: svgHref(F[fdx][F_CHIL][k][FC_INDEX])
					});
				}
			}
			if (subm.length > 0) data.push({
				text: _('Siblings'),
				subMenu: subm
			});
			// Children menu items
			subm = [];
			for (j = 0; j < I[idx][I_FAMS].length; j++)
			{
				var fdx = I[idx][I_FAMS][j];
				for (k = 0; k < F[fdx][F_CHIL].length; k++)
				{
					subm.push({
						text: I[F[fdx][F_CHIL][k][FC_INDEX]][I_NAME],
						href: svgHref(F[fdx][F_CHIL][k][FC_INDEX])
					});
				}
			}
			if (subm.length > 0) data.push({
				text: _('Children'),
				subMenu: subm
			});
			// Parents menu items
			subm = [];
			for (j = 0; j < I[idx][I_FAMC].length; j++)
			{
				var fdx = I[idx][I_FAMC][j][FC_INDEX];
				for (k = 0; k < F[fdx][F_SPOU].length; k++)
				{
					subm.push({
						text: I[F[fdx][F_SPOU][k]][I_NAME],
						href: svgHref(F[fdx][F_SPOU][k])
					});
				}
			}
			if (subm.length > 0) data.push({
				text: _('Parents'),
				subMenu: subm
			});
		}
	}
	// if (data.length > 0) data = data.concat([{divider: true}]);
	// data = data.concat(svgContextMenuItems);
	if (data.length == 0) return(true);
	context.rebuild('#svg-drawing', data);
}


//==============================================================================
//==============================================================================
// Access to data
//==============================================================================
//==============================================================================

function getFams(idx)
{
	return(I[idx][I_FAMS]);
}
function getFamc(idx)
{
	indexes = [];
	for (var x = 0; x < I[idx][I_FAMC].length; x++)
		indexes.push(I[idx][I_FAMC][x][FC_INDEX]);
	return(indexes);
}
function getSpou(fdx)
{
	var indexes = F[fdx][F_SPOU];
	for (var x = 0; x < indexes.length; x++)
	{
		var idx = indexes[x];
		UpdateDates(idx);
	}
	return(indexes);
}
function getChil(fdx)
{
	indexes = [];
	for (var x = 0; x < F[fdx][F_CHIL].length; x++)
	{
		var idx = F[fdx][F_CHIL][x][FC_INDEX];
		UpdateDates(idx);
		indexes.push(idx);
	}
	return(indexes);
}

function UpdateDates(idx)
{
	var b = parseInt(I[idx][I_BIRTH_YEAR]);
	var d = parseInt(I[idx][I_DEATH_YEAR]);
	var a = d - b;
	if (!isNaN(a)) maxAge = Math.max(maxAge, a);
	if (!isNaN(b)) minPeriod = Math.min(minPeriod, b);
	if (!isNaN(d)) maxPeriod = Math.max(maxPeriod, d);
}


//==============================================================================
//==============================================================================
//=========================================== Calcul du nombre d'ascendants
//==============================================================================
//==============================================================================

function calcAsc(idx, lev)
{
	var i;
	nbPeopleAsc = [];
	minSizeAsc = [];
	for (i = 0; i <= nbGenAsc; i++)
	{
		nbPeopleAsc[i] = 0;
		minSizeAsc[i] = 1e33;
	}
	svgParents = [];
	calcAscSub(idx, lev);
}

function calcAscSub(idx, lev)
{
	var elt = [];
	elt[SVGELT_IDX] = idx;
	elt[SVGELT_LEV] = lev;
	elt[SVGELT_NEXT] = [];
	elt[SVGELT_NEXT_SPOU] = [];
	elt[SVGELT_CMD] = [];
	svgParents.push(elt);
	nbGenAscFound = Math.max(nbGenAscFound, lev + 1);
	var i, j;
	elt[SVGELT_NB] = 0;
	if (lev < nbGenAsc - 1)
	{
		for (i = 0; i < getFamc(idx).length; i++)
		{
			for (j = 0; j < getSpou(getFamc(idx)[i]).length; j++)
			{
				elt[SVGELT_NEXT].push(svgParents.length);
				var elt_next = calcAscSub(getSpou(getFamc(idx)[i])[j], lev + 1);
				elt[SVGELT_NB] += elt_next[SVGELT_NB];
			}
		}
	}
	svgAddSeparatorAsc(elt);
	elt[SVGELT_NB] = Math.max(elt[SVGELT_NB], 1);
	nbPeopleAsc[lev] += elt[SVGELT_NB];
	minSizeAsc[lev] = Math.min(minSizeAsc[lev], elt[SVGELT_NB]);
	return(elt);
}


function svgAddSeparatorAsc(root)
{
	svgAddSeparator(svgParents, nbPeopleAsc, root);
}


function svgAddSeparator(elts, nbTable, root)
{
	// Check the type of the tree (circles don't have separators)
	if ($.inArray(search.SvgShape, [SVG_SHAPE_FULL_CIRCLE, SVG_SHAPE_HALF_CIRCLE, SVG_SHAPE_QUADRANT]) >= 0) return;
	// Check if 'root' has at least 2 generations below it
	var needSep = false;
	for (var i = 0; i < root[SVGELT_NEXT].length; i++)
	{
		var x_next = root[SVGELT_NEXT][i];
		var child = elts[x_next];
		if (child[SVGELT_NEXT].length > 0)
		{
			needSep = true;
			break;
		}
	}
	if (!needSep) return;
	// Add a separator between each person below 'root'
	var elt = [];
	elt[SVGELT_IDX] = SVGIDX_SEPARATOR;
	elt[SVGELT_LEV] = root[SVGELT_LEV] + 1;
	elt[SVGELT_NEXT] = [];
	elt[SVGELT_NEXT_SPOU] = [];
	elt[SVGELT_CMD] = [];
	elt[SVGELT_NB] = SVG_SEPARATOR_SIZE;
	var next = [];
	for (var i = 0; i < root[SVGELT_NEXT].length; i++)
	{
		next.push(elts.length);
		next.push(root[SVGELT_NEXT][i]);
	}
	next.push(elts.length);
	// Update data
	elts.push(elt);
	var sepSize = SVG_SEPARATOR_SIZE * (root[SVGELT_NEXT].length + 1);
	nbTable[root[SVGELT_LEV] + 1] += sepSize;
	root[SVGELT_NB] += sepSize;
	root[SVGELT_NEXT] = next;
}


//==============================================================================
//==============================================================================
//=========================================== Calcul des descendants
//==============================================================================
//==============================================================================


function calcDsc(idx, lev, print_spouses)
{
	var i;
	nbPeopleDsc = [];
	minSizeDsc = [];
	for (i = 0; i <= nbGenDsc; i++)
	{
		nbPeopleDsc[i] = 0;
		minSizeDsc[i] = 1e33;
	}
	svgChildren = [];
	// nbFams = [];
	if (search.SvgDistribDsc == 0 || $.inArray(search.SvgShape, [SVG_SHAPE_FULL_CIRCLE, SVG_SHAPE_HALF_CIRCLE, SVG_SHAPE_QUADRANT]) < 0)
		return calcDscPropSub(idx, lev, print_spouses);
	else
		return calcDscSub(idx, lev, 1.0, print_spouses);
}

function calcDscPropSub(idx, lev, print_spouses)
{
	var elt = [];
	elt[SVGELT_IDX] = idx;
	elt[SVGELT_LEV] = lev;
	elt[SVGELT_NEXT] = [];
	elt[SVGELT_NEXT_SPOU] = [];
	elt[SVGELT_CMD] = [];
	svgChildren.push(elt);
	nbGenDscFound = Math.max(nbGenDscFound, lev + 1);
	elt[SVGELT_NB] = 0;
	if (lev < nbGenDsc - 1)
	{
		for (var f = 0; f < getFams(idx).length; f++)
		{
			var nb_spou = 0;
			var nb_chil = 0;
			var next = [];
			var next_spou = [];
			var fdx = getFams(idx)[f];
			if (print_spouses)
			{
				for (var i = 0; i < getSpou(fdx).length; i++)
				{
					if (idx != getSpou(fdx)[i])
					{
						next_spou.push(svgChildren.length);
						calcDscSubSpou(getSpou(fdx)[i], fdx, lev, print_spouses);
						nb_spou += 1;
					}
				}
				if (nb_spou == 0)
				{
					// No spouse, create a fictive spouse to reserve space
					next_spou.push(svgChildren.length);
					calcDscSubSpou(-1, fdx, lev, print_spouses);
					nb_spou = 1;
				}
			}
			for (var i = 0; i < getChil(fdx).length; i++)
			{
				next.push(svgChildren.length);
				var elt_next = calcDscPropSub(getChil(fdx)[i], lev + 1, print_spouses);
				elt_next[SVGELT_FDX_CHILD] = fdx;
				nb_chil += elt_next[SVGELT_NB];
			}
			var nbmax = Math.max(nb_spou, nb_chil);
			for (var i = 0; i < next.length; i++)
				svgChildren[next[i]][SVGELT_NB] *= 1.0 * nbmax / nb_chil;
			for (var i = 0; i < next_spou.length; i++)
				svgChildren[next_spou[i]][SVGELT_NB] *= 1.0 * nbmax / nb_spou;
			elt[SVGELT_NB] += nbmax;
			$.merge(elt[SVGELT_NEXT], next);
			$.merge(elt[SVGELT_NEXT_SPOU], next_spou);
		}
	}
	svgAddSeparatorDsc(elt);
	elt[SVGELT_NB] = Math.max(elt[SVGELT_NB], 1);
	nbPeopleDsc[lev] += elt[SVGELT_NB];
	minSizeDsc[lev] = Math.min(minSizeDsc[lev], elt[SVGELT_NB]);
	return(elt);
}

function calcDscSub(idx, lev, nb, print_spouses)
{
	var elt = [];
	elt[SVGELT_IDX] = idx;
	elt[SVGELT_LEV] = lev;
	elt[SVGELT_NEXT] = [];
	elt[SVGELT_NEXT_SPOU] = [];
	elt[SVGELT_CMD] = [];
	elt[SVGELT_NB] = nb;
	svgChildren.push(elt);
	nbGenDscFound = Math.max(nbGenDscFound, lev + 1);
	var nb_chil = 0;
	for (var f = 0; f < getFams(idx).length; f++)
	{
		var fdx = getFams(idx)[f];
		nb_chil += getChil(fdx).length;
	}
	if (lev < nbGenDsc - 1)
	{
		for (var f = 0; f < getFams(idx).length; f++)
		{
			var nb_spou = 0;
			var next = [];
			var next_spou = [];
			var fdx = getFams(idx)[f];
			if (print_spouses)
			{
				for (var i = 0; i < getSpou(fdx).length; i++)
				{
					if (idx != getSpou(fdx)[i])
					{
						next_spou.push(svgChildren.length);
						calcDscSubSpou(getSpou(fdx)[i], fdx, lev, print_spouses);
						nb_spou += 1;
					}
				}
				if (nb_spou == 0)
				{
					// No spouse, create a fictive spouse to reserve space
					next_spou.push(svgChildren.length);
					calcDscSubSpou(-1, fdx, lev, print_spouses);
					nb_spou = 1;
				}
			}
			for (var i = 0; i < getChil(fdx).length; i++)
			{
				next.push(svgChildren.length);
				var nbc = nb / nb_chil;
				if (print_spouses) nbc = nb / getFams(idx).length / getChil(fdx).length;
				var elt_next = calcDscSub(getChil(fdx)[i], lev + 1, nbc, print_spouses);
				elt_next[SVGELT_FDX_CHILD] = fdx;
			}
			for (var i = 0; i < next_spou.length; i++)
				svgChildren[next_spou[i]][SVGELT_NB] = nb / getFams(idx).length / nb_spou;
			$.merge(elt[SVGELT_NEXT], next);
			$.merge(elt[SVGELT_NEXT_SPOU], next_spou);
		}
	}
	svgAddSeparatorDsc(elt);
	nbPeopleDsc[lev] = 1.0;
	minSizeDsc[lev] = Math.min(minSizeDsc[lev], elt[SVGELT_NB]);
	return(elt);
}

function calcDscSubSpou(idx, fdx, lev, print_spouses)
{
	var elt = [];
	elt[SVGELT_IDX] = idx;
	elt[SVGELT_FDX] = fdx;
	elt[SVGELT_LEV] = lev;
	elt[SVGELT_NEXT] = [];
	elt[SVGELT_NEXT_SPOU] = [];
	elt[SVGELT_CMD] = [];
	svgChildren.push(elt);
	elt[SVGELT_NB] = 1;
	nbGenDscFound = Math.min(nbGenDsc, Math.max(nbGenDscFound, lev + 2));
	return(elt);
}


function svgAddSeparatorDsc(root)
{
	svgAddSeparator(svgChildren, nbPeopleDsc, root);
}


//==============================================================================
//==============================================================================
//=========================================== Calcul des rayons
//==============================================================================
//==============================================================================

// These functions compute the width of the circles for each generation

function calcRayons(nb_gen)
{
	var i;
	rayons = [];
	rayons[0] = 0.5;
	for (i = 1; i < nb_gen; i++)
	{
		var p = Math.pow(2, i);
		rayons[i] = 2 * Math.PI * rayons[i-1] * txtRatioMax / p;
		if (rayons[i] > 1.0) rayons[i] = 1.0;
		rayons[i] += rayons[i-1];
	}
	for (i = 0; i < nb_gen; i++)
	{
		rayons[i] /= rayons[nb_gen-1];
	}
}


function calcRayonsPropAsc()
{
	calcRayonsPropSub(svgParents[0], nbPeopleAsc, nbGenAscFound, null);
}

function calcRayonsDsc(idx, print_spouses)
{
	calcRayonsPropSub(svgChildren[0], nbPeopleDsc, nbGenDscFound, print_spouses);
}

function calcRayonsPropBoth(idx, print_spouses)
{
	calcRayonsPropSub(svgParents[0], nbPeopleAsc, nbGenAscFound, null);
	rayonsAsc = rayons;
	calcRayonsPropSub(svgChildren[0], nbPeopleDsc, nbGenDscFound, print_spouses);
	rayonsDsc = rayons;
	rayons = null;
	var nb_gen = Math.max(nbGenAscFound, nbGenDscFound);
	for (var i = 0 ; i < nb_gen; i++)
	{
		var r_dsc = rayonsDsc[i];
		if (i >= nbGenAscFound) rayonsAsc[i] = rayonsDsc[i];
		else if (i >= nbGenDscFound) rayonsDsc[i] = rayonsAsc[i];
		else if (rayonsAsc[i] < r_dsc) rayonsDsc[i] = rayonsAsc[i];
		else rayonsAsc[i] = rayonsDsc[i];
	}
	if (print_spouses)
	{
		var offset = 0;
		for (var i = 0 ; i < nbGenAscFound; i++)
		{
			if (i < nbGenAscFound - 1) offset = (rayonsAsc[i + 1] - rayonsAsc[i]) / 2;
			else if (i < nbGenDscFound - 1) offset = (rayonsDsc[i + 1] - rayonsDsc[i]) / 2;
			rayonsAsc[i] += offset;
		}
		var ratio = Math.min(1.0, 1.0 / rayonsAsc[nbGenAscFound - 1]);
		for (var i = 0 ; i < nb_gen; i++)
		{
			rayonsAsc[i] *= ratio;
			rayonsDsc[i] *= ratio;
		}
	}
}

function calcRayonsPropSub(center_elt, nb_people, nb_gen, print_spouses)
{
	var ofst = 0;
	if (search.SvgShape == SVG_SHAPE_QUADRANT)
	{
		nb_gen += 1;
		nb_people[-1] = 1;
		ofst = -1;
	}
	var i;
	rayons = [];
	rayons[0 + ofst] = 0.5;
	for (i = 1 + ofst; i <= nb_gen + ofst; i++)
	{
		rayons[i] = 2.0 * Math.PI * rayons[i-1] * txtRatioMax * nb_people[i] / center_elt[SVGELT_NB];
		if (rayons[i] > 1) rayons[i] = 1.0;
		if (print_spouses && i == nb_gen + ofst) rayons[i] /= 2.0;
		rayons[i] += rayons[i-1];
	}
	for (i = 0 + ofst; i <= nb_gen + ofst; i++)
	{
		rayons[i] /= rayons[nb_gen + ofst];
	}
}


//==============================================================================
//==============================================================================
// ASCENDING CIRCLES
//==============================================================================
//==============================================================================

//=========================================== Roue ascendante

function initAsc()
{
	x0 = -(coordX + margeX);
	y0 = -(coordY + margeY);
	w0 = 2 * (coordX + margeX);
	h0 = 2 * (coordY + margeY);
}

function buildAsc()
{
	if (search.SvgDistribAsc ==0) return buildAscProp();
	calcAsc(search.Idx, 0);
	calcRayons(nbGenAscFound);
	svgElts = svgParents;
	calcCircleStrokeWidthAsc(2*Math.PI);
	maxTextWidth = coordX * rayons[0] * 2;
	svgElts[0][SVGELT_CMD].push('cCircle(' + [rayons[0], 0].join(', ') + ');');
	buildAscSub0(0, 0, 0, 2*Math.PI, depNum);
}

function calcCircleStrokeWidthAsc(a)
{
	// Compute the stroke-width depending on box size
	for (var i = 0; i < nbGenAscFound; i++)
	{
		svgStroke = Math.min(svgStroke, coordX * rayons[i] * a * minSizeAsc[i] / svgParents[0][SVGELT_NB] / svgStrokeRatio);
	}
	// console.log("svgStroke = " + svgStroke);
}

function buildAscSub0(x_elt, lev, a, b, num)
{
	var n = svgElts[x_elt][SVGELT_NEXT].length;
	for (var i = 0; i < n; i++)
	{
		var x_next = svgElts[x_elt][SVGELT_NEXT][i];
		var sex = I[svgElts[x_next][SVGELT_IDX]][I_GENDER];
		buildAscSub(x_next, lev+1,
			a + (b - a) / n * i,
			a + (b - a) / n * (i + 1),
			(sex == 'F') ? num * 2 + 1 : num * 2);
	}
}

function buildAscSub(x_elt, lev, a, b, num)
{
	svgElts[x_elt][SVGELT_CMD].push('secteur(' + [a, b, rayons[lev-1], rayons[lev], x_elt, lev].join(',') + ');');
	buildAscSub0(x_elt, lev, a, b, num);
}


//=========================================== Hemisphere ascendant
function initAscHemi()
{
	x0 = -(coordX + margeX);
	y0 = -(coordY + margeY);
	w0 = 2 * (coordX + margeX);
	h0 = coordY * (1 + Math.sin(hemiA)) + 2 * margeY;
}

function buildAscHemi()
{
	if (search.SvgDistribAsc ==0) return buildAscHemiProp();
	calcAsc(search.Idx, 0);
	calcRayons(nbGenAscFound);
	svgElts = svgParents;
	calcCircleStrokeWidthAsc(Math.PI + 2 * hemiA);
	maxTextWidth = coordX * rayons[0] * 2;
	svgParents[0][SVGELT_CMD].push('cCircleHemi(' + [rayons[0], -Math.PI/2 - hemiA, Math.PI/2 + hemiA, 0].join(', ') + ');');
	buildAscSub0(0, 0, -Math.PI/2 - hemiA, Math.PI/2 + hemiA, depNum);
}


//=========================================== Quadrant ascendant
function initAscQadr()
{
	var over =  Math.sin(hemiA);
	x0 = -(coordX * over + margeX);
	y0 = -(coordY + margeY);
	w0 = coordX * (1 + over) + 2 * margeX;
	h0 = coordY * (1 + over) + 2 * margeY;
}

function buildAscQadr()
{
	if (search.SvgDistribAsc ==0) return buildAscQadrProp();
	calcAsc(search.Idx, 0);
	calcRayons(nbGenAscFound + 1);
	maxTextWidth = coordX * rayons[0] * 2;
	for (var i = 0; i < rayons.length; i++) rayons[i - 1] = rayons[i];
	svgElts = svgParents;
	calcCircleStrokeWidthAsc(Math.PI / 2 + 2 * hemiA);
	buildAscSub(0, 0, -hemiA, Math.PI/2 + hemiA, depNum);
}


//==============================================================================
//==============================================================================
// ASCENDING CIRCLES - PROPORTIONAL
//==============================================================================
//==============================================================================

//=========================================== Roue ascendante proportionnelle
function buildAscProp()
{
	calcAsc(search.Idx, 0);
	calcRayonsPropAsc();
	svgElts = svgParents;
	calcCircleStrokeWidthAsc(2*Math.PI);
	maxTextWidth = coordX * rayons[0] * 2;
	svgElts[0][SVGELT_CMD].push('cCircle(' + [rayons[0], 0].join(', ') + ');');
	buildAscPropSub0(0, 0, 0, 2*Math.PI, depNum);
}

function buildAscPropSub0(x_elt, lev, a, b, num)
{
	var c = a;
	for (var i = 0; i < svgElts[x_elt][SVGELT_NEXT].length; i++)
	{
		var x_next = svgElts[x_elt][SVGELT_NEXT][i];
		var sex = I[svgElts[x_next][SVGELT_IDX]][I_GENDER];
		var da = 1.0 * (b - a) * svgElts[x_next][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		buildAscPropSub(x_next, lev + 1, c, c+da, (sex == 'F') ? num * 2 + 1 : num * 2);
		c += da;
	}
}

function buildAscPropSub(x_elt, lev, a, b, num)
{
	svgElts[x_elt][SVGELT_CMD].push('secteur(' + [a, b, rayons[lev-1], rayons[lev], x_elt, lev].join(',') + ');');
	buildAscPropSub0(x_elt, lev, a, b, num);
}

//=========================================== Hemisphere ascendant proportionnel
function buildAscHemiProp()
{
	calcAsc(search.Idx, 0);
	calcRayonsPropAsc();
	svgElts = svgParents;
	calcCircleStrokeWidthAsc(Math.PI + 2 * hemiA);
	maxTextWidth = coordX * rayons[0] * 2;
	svgParents[0][SVGELT_CMD].push('cCircleHemi(' + [rayons[0], -Math.PI/2 - hemiA, Math.PI/2 + hemiA, 0].join(', ') + ');');
	buildAscPropSub0(0, 0, -Math.PI/2 - hemiA, Math.PI/2 + hemiA, depNum);
}

//=========================================== Quadrant ascendant proportionnel
function buildAscQadrProp()
{
	calcAsc(search.Idx, 0);
	calcRayonsPropAsc();
	svgElts = svgParents;
	calcCircleStrokeWidthAsc(Math.PI / 2 + 2 * hemiA);
	maxTextWidth = coordX * rayons[0] * 2;
	buildAscPropSub(0, 0, -hemiA, Math.PI/2 + hemiA, depNum);
}

//==============================================================================
//==============================================================================
// DESCENDING CIRCLES
//==============================================================================
//==============================================================================

//=========================================== Roue descendante
function initDsc()
{
	initAsc();
}

function buildDsc()
{
	calcDsc(search.Idx, 0, false);
	calcRayonsDsc(search.Idx, false);
	svgElts = svgChildren;
	calcCircleStrokeWidthDsc(2*Math.PI);
	maxTextWidth = coordX * rayons[0] * 2;
	svgElts[0][SVGELT_CMD].push('cCircle(' + [rayons[0], 0].join(', ') + ');');
	buildDscSub0(0, 0, 0, 2*Math.PI);
}

function calcCircleStrokeWidthDsc(a)
{
	// Compute the stroke-width depending on box size
	for (var i = 0; i < nbGenDscFound; i++)
	{
		svgStroke = Math.min(svgStroke, coordX * rayons[i] * a * minSizeDsc[i] / svgChildren[0][SVGELT_NB] / svgStrokeRatio);
	}
	// console.log("svgStroke = " + svgStroke);
}

function buildDscSub0(x_elt, lev, a, b)
{
	var c = a;
	for (var i = 0; i < svgElts[x_elt][SVGELT_NEXT].length; i++)
	{
		var x_next = svgElts[x_elt][SVGELT_NEXT][i];
		var da = 1.0 * (b - a) * svgElts[x_next][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		buildDscSub(x_next, lev + 1, c, c + da);
		c += da;
	}
}

function buildDscSub(x_elt, lev, a, b)
{
	svgElts[x_elt][SVGELT_CMD].push('secteur(' + [a, b, rayons[lev-1], rayons[lev], x_elt, lev].join(',') + ');');
	buildDscSub0(x_elt, lev, a, b);
}

//=========================================== Hemisphere descendant
function initDscHemi()
{
	initAscHemi();
}

function buildDscHemi()
{
	calcDsc(search.Idx, 0, false);
	calcRayonsDsc(search.Idx, false);
	svgElts = svgChildren;
	calcCircleStrokeWidthDsc(Math.PI + 2 * hemiA);
	maxTextWidth = coordX * rayons[0] * 2;
	svgElts[0][SVGELT_CMD].push('cCircleHemi(' + [rayons[0], -Math.PI/2 - hemiA, Math.PI/2 + hemiA, 0].join(', ') + ');');
	buildDscSub0(0, 0, -Math.PI/2 - hemiA, Math.PI/2 + hemiA);
}

//=========================================== Quadrant descendant
function initDscQadr()
{
	initAscQadr();
}

function buildDscQadr()
{
	calcDsc(search.Idx, 0, false);
	calcRayonsDsc(search.Idx, false);
	svgElts = svgChildren;
	calcCircleStrokeWidthDsc(Math.PI / 2 + 2 * hemiA);
	maxTextWidth = coordX * rayons[0] * 2;
	buildDscSub(0, 0, -hemiA, Math.PI/2 + hemiA);
}


//==============================================================================
//==============================================================================
// DESCENDING CIRCLES - WITH SPOUSES
//==============================================================================
//==============================================================================

//=========================================== Roue descendante avec epoux
function initDscSpou()
{
	initAsc();
}

function buildDscSpou()
{
	calcDsc(search.Idx, 0, true);
	calcRayonsDsc(search.Idx, true);
	svgElts = svgChildren;
	calcCircleStrokeWidthDsc(2*Math.PI);
	maxTextWidth = coordX * rayons[0] * 2;
	svgElts[0][SVGELT_CMD].push('cCircle(' + [rayons[0], 0].join(', ') + ');');
	buildDscSpouSub0(0, 0, 0, 2*Math.PI);
}

function buildDscSpouSub0(x_elt, lev, a, b)
{
	var c = a;
	for (var i = 0; i < svgElts[x_elt][SVGELT_NEXT_SPOU].length; i++)
	{
		var x_next = svgElts[x_elt][SVGELT_NEXT_SPOU][i];
		var da = 1.0 * (b - a) * svgElts[x_next][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		buildDscSpouSub1(x_next, lev, c, c + da);
		c += da;
	}
	c = a;
	for (var i = 0; i < svgElts[x_elt][SVGELT_NEXT].length; i++)
	{
		var x_next = svgElts[x_elt][SVGELT_NEXT][i];
		var da = 1.0 * (b - a) * svgElts[x_next][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		buildDscSpouSub2(x_next, lev + 1, c, c + da);
		c += da;
	}
}

function buildDscSpouSub1(x_elt, lev, a, b)
{
	// Print spouse
	svgElts[x_elt][SVGELT_CMD].push('secteur(' + [a, b, rayons[lev], (rayons[lev+1]+rayons[lev])/2, x_elt, lev].join(',') + ');');
}

function buildDscSpouSub2(x_elt, lev, a, b)
{
	// Print child
	svgElts[x_elt][SVGELT_CMD].push('secteur(' + [a, b, (rayons[lev]+rayons[lev-1])/2, rayons[lev], x_elt, lev].join(',') + ');');
	buildDscSpouSub0(x_elt, lev, a, b);
}


//=========================================== Hemisphere descendant avec epoux
function initDscHemiSpou()
{
	initAscHemi();
}

function buildDscHemiSpou()
{
	calcDsc(search.Idx, 0, true);
	calcRayonsDsc(search.Idx, true);
	svgElts = svgChildren;
	calcCircleStrokeWidthDsc(Math.PI + 2 * hemiA);
	maxTextWidth = coordX * rayons[0] * 2;
	svgElts[0][SVGELT_CMD].push('cCircleHemi(' + [rayons[0], -Math.PI/2 - hemiA, Math.PI/2 + hemiA, 0].join(', ') + ');');
	buildDscSpouSub0(0, 0, -Math.PI/2 - hemiA, Math.PI/2 + hemiA);
}


//=========================================== Quadrant descendant avec epoux
function initDscQadrSpou()
{
	initAscQadr();
}

function buildDscQadrSpou()
{
	calcDsc(search.Idx, 0, true);
	calcRayonsDsc(search.Idx, true);
	svgElts = svgChildren;
	calcCircleStrokeWidthDsc(Math.PI / 2 + 2 * hemiA);
	maxTextWidth = coordX * rayons[0] * 2;
	buildDscSpouSub2(0, 0, -hemiA, Math.PI/2 + hemiA);
}


//==============================================================================
//==============================================================================
// ASCENDING AND DESCENDING CIRCLES
//==============================================================================
//==============================================================================

//=========================================== Roue ascendante+descendante

function buildBothSub(print_spouses)
{
	calcAsc(search.Idx, 0);
	calcDsc(search.Idx, 0, print_spouses);
	calcRayonsPropBoth(search.Idx, print_spouses);
	mergeSVGelts();
	var center1 = svgParents[0];
	var center2 = svgChildren[0];
	// Ascendants
	svgElts[0] = center1;
	maxTextWidth = coordX * rayonsAsc[0] * 2;
	rayons = rayonsAsc;
	calcCircleStrokeWidthAsc(Math.PI);
	if (search.SvgDistribAsc == 0) buildAscPropSub0(0, 0, -Math.PI/2, Math.PI/2, depNum);
	else buildAscSub0(0, 0, -Math.PI/2, Math.PI/2, depNum);
	// Descendants
	svgElts[0] = center2;
	maxTextWidth = coordX * rayonsDsc[0] * 2;
	rayons = rayonsDsc;
	calcCircleStrokeWidthDsc(Math.PI);
	if (print_spouses) buildDscSpouSub0(0, 0, Math.PI/2, 3*Math.PI/2);
	else buildDscSub0(0, 0, Math.PI/2, 3*Math.PI/2);
	// Texte central
	svgElts[0][SVGELT_CMD].push('cCircleBoth(' + [rayonsAsc[0], rayonsDsc[0], 0].join(', ') + ');');
}

function mergeSVGelts()
{
	// Merge svgParents and svgChildren
	var shift = svgParents.length;
	svgElts = svgParents;
	for (var x_elt = 0; x_elt < svgChildren.length; x_elt++)
	{
		elt = svgChildren[x_elt];
		fields = [SVGELT_NEXT, SVGELT_NEXT_SPOU];
		for (var x_field = 0; x_field < 2; x_field++)
		{
			var field = fields[x_field];
			for (var i = 0; i < elt[field].length; i++) elt[field][i] += shift - 1;
		}
		if (x_elt > 0) svgElts.push(elt);
	}
}

function initBoth()
{
	initAsc();
}
function buildBoth()
{
	buildBothSub(false);
}

function initBothSpou()
{
	initAsc();
}
function buildBothSpou()
{
	buildBothSub(true);
}


//==============================================================================
//==============================================================================
// TREE - HORIZONTAL
//==============================================================================
//==============================================================================

//=========================================== Arbre ascendant
function initAscTreeH()
{
	calcAsc(search.Idx, 0);
	svgElts = svgParents;
	var box_width = Math.min(coordX / nbGenAscFound, coordY / svgElts[0][SVGELT_NB] * txtRatioMax);
	var box_height = box_width / txtRatioMax;
	maxTextWidth = box_width;
	x0 = -margeX;
	y0 = -margeY;
	w0 = box_width * nbGenAscFound + box_width * (nbGenAscFound - 1) * linkRatio + 2.0 * margeX;
	h0 = box_height * svgElts[0][SVGELT_NB] + 2.0 * margeY;
	// Compute the stroke-width depending on box size
	svgStroke = Math.min(svgStroke, box_height / svgStrokeRatio);
}

function buildAscTreeH()
{
	buildAscTreeHSub(0, 0, svgElts[0][SVGELT_NB], depNum, nbGenAscFound, 0);
}

function buildAscTreeHSub(x_elt, a, b, num, nb_gens, offsetx, child_x, child_y)
{
	if (svgElts[x_elt][SVGELT_IDX] == SVGIDX_SEPARATOR) return;
	var lev = svgElts[x_elt][SVGELT_LEV];
	var box_width = Math.min(coordX / nb_gens, coordY / svgElts[0][SVGELT_NB] * txtRatioMax);
	var box_height = Math.min(box_width / txtRatioMin, minSizeAsc[lev] * box_width / txtRatioMax);
	var x = box_width * (1.0 + linkRatio) * (lev + offsetx);
	var y = (a + b) / 2.0 * box_width / txtRatioMax;
	svgElts[x_elt][SVGELT_CMD].push('rectangle(' + buildTreeHRect(x, y - box_height / 2.0, box_width, box_height, x_elt, lev).join(',') + ');');
	if (typeof(child_x) == 'number')
	{
		// Draw links
		svgElts[x_elt][SVGELT_CMD].push('line(' + buildTreeHLine(child_x, child_y, x, y).join(',') + ');');
	}
	var c = a;
	for (var i = 0; i < svgElts[x_elt][SVGELT_NEXT].length; i++)
	{
		var x_next = svgElts[x_elt][SVGELT_NEXT][i];
		var da = 1.0 * (b - a) * svgElts[x_next][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		if (svgElts[x_next][SVGELT_IDX] != SVGIDX_SEPARATOR)
		{
			var sex = I[svgElts[x_next][SVGELT_IDX]][I_GENDER];
			buildAscTreeHSub(x_next, c, c + da, (sex == 'F') ? num * 2 + 1 : num * 2, nb_gens, offsetx, x + box_width, y);
		}
		c += da;
	}
}

function buildTreeHRect(x, y, w, h, x_elt, lev)
{
	if (search.SvgShape != 3)
	{
		x = w0 - 2.0 * margeX - x - w;
	}
	return([x, y, w, h, x_elt, lev]);
}

function buildTreeHLine(x1, y1, x2, y2)
{
	if (search.SvgShape != 3)
	{
		x1 = w0 - 2.0 * margeX - x1;
		x2 = w0 - 2.0 * margeX - x2;
	}
	return([x1, y1, x2, y2]);
}


//=========================================== Arbre descendant
function initDscTreeH()
{
	calcDsc(search.Idx, 0, false);
	svgElts = svgChildren;
	var box_width = Math.min(coordX / nbGenDscFound, coordY / svgElts[0][SVGELT_NB] * txtRatioMax);
	var box_height = box_width / txtRatioMax;
	maxTextWidth = box_width;
	x0 = -margeX;
	y0 = -margeY;
	w0 = box_width * nbGenDscFound + box_width * (nbGenDscFound - 1) * linkRatio + 2.0 * margeX;
	h0 = box_height * svgElts[0][SVGELT_NB] + 2.0 * margeY;
	// Compute the stroke-width depending on box size
	svgStroke = Math.min(svgStroke, box_height / svgStrokeRatio);
}

function buildDscTreeH()
{
	buildDscTreeHSub(0, 0, svgElts[0][SVGELT_NB], nbGenDscFound, nbGenDscFound - 1, true);
}

function buildDscTreeHSub(x_elt, a, b, nb_gens, offsetx, print_center, parent_x, parent_y)
{
	if (svgElts[x_elt][SVGELT_IDX] == SVGIDX_SEPARATOR) return;
	var lev = svgElts[x_elt][SVGELT_LEV];
	var box_width = Math.min(coordX / nb_gens, coordY / svgElts[0][SVGELT_NB] * txtRatioMax);
	var box_height = Math.min(box_width / txtRatioMin, minSizeDsc[lev] * box_width / txtRatioMax);
	var x = box_width * (1.0 + linkRatio) * (offsetx - lev);
	var y = (a + b) / 2.0 * box_width / txtRatioMax;
	if (print_center || lev > 0)
		svgElts[x_elt][SVGELT_CMD].push('rectangle(' + buildTreeHRect(x, y - box_height / 2.0, box_width, box_height, x_elt, lev).join(',') + ');');
	if (typeof(parent_x) == 'number')
	{
		// Draw links
		svgElts[x_elt][SVGELT_CMD].push('line(' + buildTreeHLine(parent_x, parent_y, x + box_width, y).join(',') + ');');
	}
	var c = a;
	for (var i = 0; i < svgElts[x_elt][SVGELT_NEXT].length; i++)
	{
		var x_next = svgElts[x_elt][SVGELT_NEXT][i];
		var da = 1.0 * (b - a) * svgElts[x_next][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		buildDscTreeHSub(x_next, c, c + da, nb_gens, offsetx, print_center, x, y);
		c += da;
	}
}

//=========================================== Arbre descendant avec epoux
function initDscTreeHSpou()
{
	calcDsc(search.Idx, 0, true);
	svgElts = svgChildren;
	var nb_gens = nbGenDscFound * 2 - 1;
	var box_width = Math.min(coordX / nb_gens, coordY / svgElts[0][SVGELT_NB] * txtRatioMax);
	var box_height = box_width / txtRatioMax;
	maxTextWidth = box_width;
	x0 = -margeX;
	y0 = -margeY;
	w0 = box_width * nb_gens + box_width * (nb_gens - 1) * linkRatio + 2.0 * margeX;
	h0 = box_height * svgElts[0][SVGELT_NB] + 2.0 * margeY;
	// Compute the stroke-width depending on box size
	svgStroke = Math.min(svgStroke, box_height / svgStrokeRatio);
}

function buildDscTreeHSpou()
{
	var nb_gens = nbGenDscFound * 2 - 1;
	buildDscTreeHSpouSub(0, 0, svgElts[0][SVGELT_NB], nb_gens, nb_gens - 1, true);
}

function buildDscTreeHSpouSub(x_elt, a, b, nb_gens, offsetx, print_center, parent_x, parent_y)
{
	if (svgElts[x_elt][SVGELT_IDX] == SVGIDX_SEPARATOR) return;
	var lev = svgElts[x_elt][SVGELT_LEV];
	var box_width = Math.min(coordX / nb_gens, coordY / svgElts[0][SVGELT_NB] * txtRatioMax);
	var box_height = Math.min(box_width / txtRatioMin, minSizeDsc[lev] * box_width / txtRatioMax);
	var x = box_width * (1.0 + linkRatio) * (offsetx - lev * 2);
	var y = (a + b) / 2.0 * box_width / txtRatioMax;
	if (print_center || lev > 0)
		svgElts[x_elt][SVGELT_CMD].push('rectangle(' + buildTreeHRect(x, y - box_height / 2.0, box_width, box_height, x_elt, lev).join(',') + ');');
	if (typeof(parent_x) == 'number')
	{
		// Draw links
		svgElts[x_elt][SVGELT_CMD].push('line(' + buildTreeHLine(parent_x, parent_y, x + box_width, y).join(',') + ');');
	}
	var c_spou = a;
	var i_chil = 0;
	var x_spou = x - box_width * (1.0 + linkRatio);
	var box_height_spou = Math.min(box_width / txtRatioMin, minSizeDsc[lev + 1] * box_width / txtRatioMax);
	for (var i_spou = 0; i_spou < svgElts[x_elt][SVGELT_NEXT_SPOU].length; i_spou++)
	{
		var x_next_spou = svgElts[x_elt][SVGELT_NEXT_SPOU][i_spou];
		var da_spou = 1.0 * (b - a) * svgElts[x_next_spou][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		var y_spou = (c_spou + da_spou / 2.0) * box_width / txtRatioMax;
		var p_x = x - box_width;
		var p_y = y;
		if (svgElts[x_next_spou][SVGELT_IDX] >= 0)
		{
			p_x = x_spou;
			p_y = y_spou;
			svgElts[x_next_spou][SVGELT_CMD].push('rectangle(' + buildTreeHRect(x_spou, y_spou - box_height_spou / 2.0, box_width, box_height_spou, x_next_spou, lev).join(',') + ');');
			svgElts[x_next_spou][SVGELT_CMD].push('line(' + buildTreeHLine(x, y, x_spou + box_width, y_spou).join(',') + ');');
		}
		var c_chil = c_spou;
		while (i_chil < svgElts[x_elt][SVGELT_NEXT].length)
		{
			var x_next_chil = svgElts[x_elt][SVGELT_NEXT][i_chil];
			if (svgElts[x_next_chil][SVGELT_FDX_CHILD] != svgElts[x_next_spou][SVGELT_FDX] && svgElts[x_next_chil][SVGELT_IDX] != SVGIDX_SEPARATOR) break;
			var da = 1.0 * (b - a) * svgElts[x_next_chil][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
			buildDscTreeHSpouSub(x_next_chil, c_chil, c_chil + da, nb_gens, offsetx, print_center, p_x, p_y);
			c_chil += da;
			i_chil += 1;
		}
		c_spou += da_spou;
	}
}


//=========================================== Arbre ascendant+descendant

function initBothTreeHSub(print_spouses)
{
	calcAsc(search.Idx, 0);
	calcDsc(search.Idx, 0, print_spouses);
	var maxN = Math.max(svgParents[0][SVGELT_NB], svgChildren[0][SVGELT_NB]);
	var ratio = 1.0 * maxN / svgParents[0][SVGELT_NB];
	for (var i = 0; i < svgParents.length; i++) svgParents[i][SVGELT_NB] *= ratio;
	for (var i = 0; i <= nbGenAsc; i++) minSizeAsc[i] *= ratio;
	ratio = 1.0 * maxN / svgChildren[0][SVGELT_NB];
	for (var i = 0; i < svgChildren.length; i++) svgChildren[i][SVGELT_NB] *= ratio;
	for (var i = 0; i <= nbGenDsc; i++) minSizeDsc[i] *= ratio;
	mergeSVGelts();
	var nb_gens = nbGenAscFound + (print_spouses ? (nbGenDscFound * 2 - 1) : nbGenDscFound) - 1;
	var box_width = Math.min(coordX / nb_gens, coordY / svgElts[0][SVGELT_NB] * txtRatioMax);
	var box_height = box_width / txtRatioMax;
	maxTextWidth = box_width;
	x0 = -margeX;
	y0 = -margeY;
	w0 = box_width * nb_gens + box_width * (nb_gens - 1) * linkRatio + 2.0 * margeX;
	h0 = box_height * svgElts[0][SVGELT_NB] + 2.0 * margeY;
	// Compute the stroke-width depending on box size
	svgStroke = Math.min(svgStroke, box_height / svgStrokeRatio);
}

function buildBothTreeHSub(print_spouses)
{
	var center1 = svgParents[0];
	var center2 = svgChildren[0];
	var nb_gens = nbGenAscFound + (print_spouses ? (nbGenDscFound * 2 - 1) : nbGenDscFound) - 1;
	// Ascendants
	svgElts[0] = center1;
	buildAscTreeHSub(0, 0, svgElts[0][SVGELT_NB], depNum, nb_gens, nb_gens - nbGenAscFound);
	// Descendants
	svgElts[0] = center2;
	if (print_spouses) buildDscTreeHSpouSub(0, 0, svgElts[0][SVGELT_NB], nb_gens, nb_gens - nbGenAscFound, false);
	else buildDscTreeHSub(0, 0, svgElts[0][SVGELT_NB], nb_gens, nb_gens - nbGenAscFound, false);
	// Texte central
	svgElts[0] = center1;
}

function initBothTreeH()
{
	initBothTreeHSub(false);
}
function buildBothTreeH()
{
	buildBothTreeHSub(false);
}

function initBothTreeHSpou()
{
	initBothTreeHSub(true);
}
function buildBothTreeHSpou()
{
	buildBothTreeHSub(true);
}


//==============================================================================
//==============================================================================
// TREE - VERTICAL
//==============================================================================
//==============================================================================

//=========================================== Arbre vertical ascendant
function initAscTreeV()
{
	calcAsc(search.Idx, 0);
	svgElts = svgParents;
	var box_height = Math.min(coordY / nbGenAscFound, coordX / svgElts[0][SVGELT_NB] / txtRatioMin);
	var box_width = box_height * txtRatioMin;
	maxTextWidth = box_width;
	// Space reserved for links between boxes
	var h = box_height * nbGenAscFound + 2.0 * margeX; // total height
	linkRatio = Math.max(linkRatio,
		(coordY - h) / (nbGenAscFound - 1) / box_height
	);
	// Size of the canvas
	w0 = box_width * svgElts[0][SVGELT_NB] + 2.0 * margeX;
	h0 = box_height * nbGenAscFound + box_height * (nbGenAscFound - 1) * linkRatio + 2.0 * margeY;
	x0 = -margeX;
	y0 = -margeY;
	// Compute the stroke-width depending on box size
	svgStroke = Math.min(svgStroke, box_width / svgStrokeRatio);
}

function buildAscTreeV()
{
	buildAscTreeVSub(0, 0, svgElts[0][SVGELT_NB], depNum, nbGenAscFound, nbGenAscFound - 1);
}

function buildAscTreeVSub(x_elt, a, b, num, nb_gens, offsety, child_x, child_y)
{
	if (svgElts[x_elt][SVGELT_IDX] == SVGIDX_SEPARATOR) return;
	var lev = svgElts[x_elt][SVGELT_LEV];
	var box_height = Math.min(coordY / nb_gens, coordX / svgElts[0][SVGELT_NB] / txtRatioMin);
	var box_width = Math.min(box_height * txtRatioMax, minSizeAsc[lev] * box_height * txtRatioMin);
	var y = box_height * (1.0 + linkRatio) * (offsety - lev);
	var x = (a + b) / 2.0 * coordX / svgElts[0][SVGELT_NB];
	svgElts[x_elt][SVGELT_CMD].push('rectangle(' + buildTreeVRect(x - box_width / 2.0, y, box_width, box_height, x_elt, lev).join(',') + ');');
	if (typeof(child_x) == 'number')
	{
		// Draw links
		svgElts[x_elt][SVGELT_CMD].push('line(' + buildTreeVLine(child_x, child_y, x, y + box_height).join(',') + ');');
	}
	var c = a;
	for (var i = 0; i < svgElts[x_elt][SVGELT_NEXT].length; i++)
	{
		var x_next = svgElts[x_elt][SVGELT_NEXT][i];
		var da = 1.0 * (b - a) * svgElts[x_next][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		if (svgElts[x_next][SVGELT_IDX] != SVGIDX_SEPARATOR)
		{
			var sex = I[svgElts[x_next][SVGELT_IDX]][I_GENDER];
			buildAscTreeVSub(x_next, c, c + da, (sex == 'F') ? num * 2 + 1 : num * 2, nb_gens, offsety, x, y);
		}
		c += da;
	}
}

function buildTreeVRect(x, y, w, h, x_elt, lev)
{
	if (search.SvgShape == 1)
	{
		y = h0 - 2.0 * margeY - y - h;
	}
	return([x, y, w, h, x_elt, lev]);
}

function buildTreeVLine(x1, y1, x2, y2)
{
	if (search.SvgShape == 1)
	{
		y1 = h0 - 2.0 * margeY - y1;
		y2 = h0 - 2.0 * margeY - y2;
	}
	return([x1, y1, x2, y2]);
}

//=========================================== Arbre vertical descendant
function initDscTreeV()
{
	calcDsc(search.Idx, 0, false);
	svgElts = svgChildren;
	var box_height = Math.min(coordY / nbGenDscFound, coordX / svgElts[0][SVGELT_NB] / txtRatioMin);
	var box_width = box_height * txtRatioMin;
	maxTextWidth = box_width;
	// Space reserved for links between boxes
	var h = box_height * nbGenDscFound + 2.0 * margeY; // total height
	linkRatio = Math.max(linkRatio,
		(Math.min(coordY, coordX * DimY / DimX) - h) / (nbGenDscFound - 1) / box_height
	);
	// Size of the canvas
	w0 = box_width * svgElts[0][SVGELT_NB] + 2.0 * margeX;
	h0 = box_height * nbGenDscFound + box_height * (nbGenDscFound - 1) * linkRatio + 2.0 * margeY;
	x0 = -margeX;
	y0 = -margeY;
	// Compute the stroke-width depending on box size
	svgStroke = Math.min(svgStroke, box_width / svgStrokeRatio);
}

function buildDscTreeV()
{
	buildDscTreeVSub(0, 0, svgElts[0][SVGELT_NB], nbGenDscFound, 0, true);
}

function buildDscTreeVSub(x_elt, a, b, nb_gens, offsety, print_center, parent_x, parent_y)
{
	if (svgElts[x_elt][SVGELT_IDX] == SVGIDX_SEPARATOR) return;
	var lev = svgElts[x_elt][SVGELT_LEV];
	var box_height = Math.min(coordY / nb_gens, coordX / svgElts[0][SVGELT_NB] / txtRatioMin);
	var box_width = Math.min(box_height * txtRatioMax, minSizeDsc[lev] * box_height * txtRatioMin);
	var y = box_height * (1.0 + linkRatio) * (lev + offsety);
	var x = (a + b) / 2.0 * coordX / svgElts[0][SVGELT_NB];
	if (print_center || lev > 0)
		svgElts[x_elt][SVGELT_CMD].push('rectangle(' + buildTreeVRect(x - box_width / 2.0, y, box_width, box_height, x_elt, lev).join(',') + ');');
	if (typeof(parent_x) == 'number')
	{
		// Draw links
		svgElts[x_elt][SVGELT_CMD].push('line(' + buildTreeVLine(parent_x, parent_y, x, y).join(',') + ');');
	}
	var c = a;
	for (var i = 0; i < svgElts[x_elt][SVGELT_NEXT].length; i++)
	{
		var x_next = svgElts[x_elt][SVGELT_NEXT][i];
		var da = 1.0 * (b - a) * svgElts[x_next][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		buildDscTreeVSub(x_next, c, c + da, nb_gens, offsety, print_center, x, y + box_height);
		c += da;
	}
}

//=========================================== Arbre vertical descendant avec epoux
function initDscTreeVSpou()
{
	calcDsc(search.Idx, 0, true);
	svgElts = svgChildren;
	var nb_gens = nbGenDscFound * 2 - 1;
	var box_height = Math.min(coordY / nb_gens, coordX / svgElts[0][SVGELT_NB] / txtRatioMin);
	var box_width = box_height * txtRatioMin;
	maxTextWidth = box_width;
	// Space reserved for links between boxes
	var h = box_height * nb_gens + 2.0 * margeY; // total height
	linkRatio = Math.max(linkRatio,
		(Math.min(coordY, coordX * DimY / DimX) - h) / (nb_gens - 1) / box_height
	);
	// Size of the canvas
	w0 = box_width * svgElts[0][SVGELT_NB] + 2.0 * margeX;
	h0 = box_height * nb_gens + box_height * (nb_gens - 1) * linkRatio + 2.0 * margeY;
	x0 = -margeX;
	y0 = -margeY;
	// Compute the stroke-width depending on box size
	svgStroke = Math.min(svgStroke, box_width / svgStrokeRatio);
}

function buildDscTreeVSpou()
{
	var nb_gens = nbGenDscFound * 2 - 1;
	buildDscTreeVSpouSub(0, 0, svgElts[0][SVGELT_NB], nb_gens, 0, true);
}

function buildDscTreeVSpouSub(x_elt, a, b, nb_gens, offsety, print_center, parent_x, parent_y)
{
	if (svgElts[x_elt][SVGELT_IDX] == SVGIDX_SEPARATOR) return;
	var lev = svgElts[x_elt][SVGELT_LEV];
	var box_height = Math.min(coordY / nb_gens, coordX / svgElts[0][SVGELT_NB] / txtRatioMin);
	var box_width = Math.min(box_height * txtRatioMax, minSizeDsc[lev] * box_height * txtRatioMin);
	var y = box_height * (1.0 + linkRatio) * (lev * 2 + offsety);
	var x = (a + b) / 2.0 * coordX / svgElts[0][SVGELT_NB];
	if (print_center || lev > 0)
		svgElts[x_elt][SVGELT_CMD].push('rectangle(' + buildTreeVRect(x - box_width / 2.0, y, box_width, box_height, x_elt, lev).join(',') + ');');
	if (typeof(parent_x) == 'number')
	{
		// Draw links
		svgElts[x_elt][SVGELT_CMD].push('line(' + buildTreeVLine(parent_x, parent_y, x, y).join(',') + ');');
	}
	var c_spou = a;
	var i_chil = 0;
	var y_spou = y + box_height * (1.0 + linkRatio) + box_height;
	var box_width_spou = Math.min(box_height * txtRatioMax, minSizeDsc[lev + 1] * box_height * txtRatioMin);
	for (var i_spou = 0; i_spou < svgElts[x_elt][SVGELT_NEXT_SPOU].length; i_spou++)
	{
		var x_next_spou = svgElts[x_elt][SVGELT_NEXT_SPOU][i_spou];
		var da_spou = 1.0 * (b - a) * svgElts[x_next_spou][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
		var x_spou = (c_spou + da_spou / 2.0) * coordX / svgElts[0][SVGELT_NB];
		var p_x = x;
		var p_y = y + box_height;
		if (svgElts[x_next_spou][SVGELT_IDX] >= 0)
		{
			p_x = x_spou;
			p_y = y_spou;
			svgElts[x_next_spou][SVGELT_CMD].push('rectangle(' + buildTreeVRect(x_spou - box_width_spou / 2.0, y_spou - box_height, box_width_spou, box_height, x_next_spou, lev).join(',') + ');');
			svgElts[x_next_spou][SVGELT_CMD].push('line(' + buildTreeVLine(x, y + box_height, x_spou, y_spou - box_height).join(',') + ');');
		}
		var c_chil = c_spou;
		while (i_chil < svgElts[x_elt][SVGELT_NEXT].length)
		{
			var x_next_chil = svgElts[x_elt][SVGELT_NEXT][i_chil];
			if (svgElts[x_next_chil][SVGELT_FDX_CHILD] != svgElts[x_next_spou][SVGELT_FDX] && svgElts[x_next_chil][SVGELT_IDX] != SVGIDX_SEPARATOR) break;
			var da = 1.0 * (b - a) * svgElts[x_next_chil][SVGELT_NB] / svgElts[x_elt][SVGELT_NB];
			buildDscTreeVSpouSub(x_next_chil, c_chil, c_chil + da, nb_gens, offsety, print_center, p_x, p_y);
			c_chil += da;
			i_chil += 1;
		}
		c_spou += da_spou;
	}
}


//=========================================== Arbre vertical ascendant+descendant

function initBothTreeVSub(print_spouses)
{
	calcAsc(search.Idx, 0);
	calcDsc(search.Idx, 0, print_spouses);
	var maxN = Math.max(svgParents[0][SVGELT_NB], svgChildren[0][SVGELT_NB]);
	var ratio = 1.0 * maxN / svgParents[0][SVGELT_NB];
	for (var i = 0; i < svgParents.length; i++) svgParents[i][SVGELT_NB] *= ratio;
	for (var i = 0; i <= nbGenAsc; i++) minSizeAsc[i] *= ratio;
	ratio = 1.0 * maxN / svgChildren[0][SVGELT_NB];
	for (var i = 0; i < svgChildren.length; i++) svgChildren[i][SVGELT_NB] *= ratio;
	for (var i = 0; i <= nbGenDsc; i++) minSizeDsc[i] *= ratio;
	mergeSVGelts();
	var nb_gens = nbGenAscFound + (print_spouses ? (nbGenDscFound * 2 - 1) : nbGenDscFound) - 1;
	var box_height = Math.min(coordY / nb_gens, coordX / svgElts[0][SVGELT_NB] / txtRatioMin);
	var box_width = box_height * txtRatioMin;
	maxTextWidth = box_width;
	// Space reserved for links between boxes
	var h = box_height * nb_gens + 2.0 * margeY; // total height
	linkRatio = Math.max(linkRatio,
		(Math.min(coordY, coordX * DimY / DimX) - h) / (nb_gens - 1) / box_height
	);
	// Size of the canvas
	w0 = box_width * svgElts[0][SVGELT_NB] + 2.0 * margeX;
	h0 = box_height * nb_gens + box_height * (nb_gens - 1) * linkRatio + 2.0 * margeY;
	x0 = -margeX;
	y0 = -margeY;
	// Compute the stroke-width depending on box size
	svgStroke = Math.min(svgStroke, box_width / svgStrokeRatio);
}

function buildBothTreeVSub(print_spouses)
{
	var center1 = svgParents[0];
	var center2 = svgChildren[0];
	var nb_gens = nbGenAscFound + (print_spouses ? (nbGenDscFound * 2 - 1) : nbGenDscFound) - 1;
	var offsety = nb_gens - (print_spouses ? (nbGenDscFound * 2 - 1) : nbGenDscFound);
	// Ascendants
	svgElts[0] = center1;
	buildAscTreeVSub(0, 0, svgElts[0][SVGELT_NB], depNum, nb_gens, offsety);
	// Descendants
	svgElts[0] = center2;
	if (print_spouses) buildDscTreeVSpouSub(0, 0, svgElts[0][SVGELT_NB], nb_gens, offsety, false);
	else buildDscTreeVSub(0, 0, svgElts[0][SVGELT_NB], nb_gens, offsety, false);
	// Texte central
	svgElts[0] = center1;
}

function initBothTreeV()
{
	initBothTreeVSub(false);
}
function buildBothTreeV()
{
	buildBothTreeVSub(false);
}

function initBothTreeVSpou()
{
	initBothTreeVSub(true);
}
function buildBothTreeVSpou()
{
	buildBothTreeVSub(true);
}


//==============================================================================
//==============================================================================
// Basic drawing
//==============================================================================
//==============================================================================

//=========================================== Shapes
function cCircle(r, x_elt)
{
	var idx = svgElts[x_elt][SVGELT_IDX];
	// Create center for Circle graphs
	var p = svgPaper.circle(0, 0, r * coordX);
	// Create text
	var x = r * coordX * 0.87;
	var y = r * coordY * 0.5;
	var text = textRect(-x, -y, x, y, x_elt);
	// Build the SVG elements style
	SvgSetStyle(p, text, x_elt, 0);
}

function cCircleHemi(r, a1, a2, x_elt)
{
	var idx = svgElts[x_elt][SVGELT_IDX];
	// Create center for CircleHemi graphs
	var ap = 'M ' + (coordX * r * Math.sin(a1)) + ',' + (-coordY * r * Math.cos(a1)) +
			arcPath(r,a1,a2,1) +
			' z';
	var p = svgPaper.path(ap);
	// Create text
	var x = r * coordX * 0.87;
	var y = r * coordY * 0.5;
	var y2 = r * coordY * Math.sin(hemiA);
	var text = textRect(-x, -y, x, Math.min(y, y2), x_elt);
	// Build the SVG elements style
	SvgSetStyle(p, text, x_elt, 0);
}

function cCircleBoth(r1, r2, x_elt)
{
	var idx = svgElts[x_elt][SVGELT_IDX];
	// Create center for CircleBoth graphs
	var ap = 'M ' + (-coordX * r1) + ',' + 0 +
			arcPath(r1, -Math.PI/2, Math.PI/2, 1) +
			' L ' + (coordX * r2) + ',' + 0 +
			arcPath(r2, Math.PI/2, 3*Math.PI/2, 1) +
			' z';
	var p = svgPaper.path(ap);
	// Create text
	var x = coordX * Math.min(r1, r2) * 0.87;
	var y = coordX * Math.min(r1, r2) * 0.5;
	var text = textRect(-x, -y, x, y, x_elt);
	// Build the SVG elements style
	SvgSetStyle(p, text, x_elt, 0);
}

function line(x1, y1, x2, y2)
{
	var p = svgPaper.path(['M', x1, y1, 'L', x2, y2]);
	p.node.setAttribute('class', 'svg-line');
	p.node.setAttribute('stroke-width', svgStroke);
}

function calcTextTab(tab, n)
{
	var i, j, l = tab.length;
	if (l <= n)
	{
		var t = arrayCopy(tab);
		for (i=l; i<n; i++) t[i] = '';
		return(t);
	}
	j = 0;
	for (i = 0; i < l; i++) j = Math.max(j, tab[i].length);
	NEWSZ:for (; j<1000; j++)
	{
		var t = [];
		for (i = 0; i < n; i++) t[i] = '';
		var o = 0;
		for (i = 0; i < l; i++)
		{
			if (tab[i].length > j) continue NEWSZ;
			if (tab[i].length + t[o].length >= j)
			{
				o++;
				if (o >= n) continue NEWSZ;
				t[o] = tab[i];
			}
			else
			{
				t[o] += ' ' + tab[i];
			}
		}
		return(t);
	}
}

function calcTextTabSize(tab, n)
{
	tab = calcTextTab(tab, n);
	var i, sz = 0;
	for (i = 0; i < tab.length; i++)
	{
		sz = Math.max(sz, tab[i].length);
	}
	return(sz);
}

// function textPath(p, tab, w, h)
// {
	// return;
	// Calcul de la taille de police et des lignes
	// var fs = 0;
	// var i, fi = 0;
	// for (i = 0; i < tab.length; i++)
	// {
		// var sz = calcTextTabSize(tab, i+1);
		// var nfs = Math.round(Math.min(fontFactorX * w / sz, fontFactorY * h / (i+1)));
		// nfs = Math.min(nfs, Math.round(maxTextWidth * fontFactorX / txtRatioMax));
		// if (nfs > fs)
		// {
			// fs = nfs;
			// fi = i;
		// }
	// }
	// tab = calcTextTab(tab, fi+1);
	// Dessin
	// var ai = 'pid_' + tpid;
	// var p2 = SVGDoc.createElementNS(xmlns, 'path');
	// p2.setAttributeNS(null, 'd', p);
	// p2.setAttributeNS(null, 'id', ai);
	// SVGDefs.appendChild(p2);
	// for (i = 0; i < tab.length; i++)
	// {
		// var svgt = SVGDoc.createElementNS(xmlns, 'text');
		// svgt.setAttributeNS(null, 'font-size', fs);
		// svgt.setAttributeNS(null, 'fill', 'black');
		// svgPaper.appendChild(svgt);

		// var dy = (Math.round((0.8 - tab.length/2 + i) * 100) / 100) + 'em';
		// var dy = (Math.round((0.8 - tab.length/2 + i) * 100) / 100) * fs;
		// var q = SVGDoc.createElementNS(xmlns, 'textPath');
		// q.setAttributeNS(xlink, 'xlink:href', '#'+ai);
		// q.setAttributeNS(null, 'startOffset', '50%');

		// svgt.appendChild(q);
		// var s = SVGDoc.createElementNS(xmlns, 'tspan');
		// s.setAttributeNS(null, 'dy', dy);
		// var blanc =  SVGDoc.createTextNode('\n');
		// q.appendChild(blanc);
		// q.appendChild(s);
		// var u = SVGDoc.createTextNode(tab[i]);
		// s.appendChild(u);
		// /*
		// q.setAttributeNS(null, 'dy', dy);
		// svgt.appendChild(q);
		// var u = SVGDoc.createTextNode(tab[i]);
		// q.appendChild(u);
		// */
	// }
	// tpid++;
// }

function textLine(x, y, a, txt, w, h, x_elt)
{
	var idx = svgElts[x_elt][SVGELT_IDX];
	// Calcul de la taille de police et des lignes
	var tab = txt.split(/[ \-]+/g);
	var fs = 0;
	var i, fi = 0;
	for (i = 0; i < tab.length; i++)
	{
		var sz = calcTextTabSize(tab, i+1);
		var nfs = Math.round(Math.min(fontFactorX * w / sz, fontFactorY * h / (i+1)));
		nfs = Math.min(nfs, Math.round(maxTextWidth * fontFactorX / txtRatioMax));
		if (nfs > fs)
		{
			fs = nfs;
			fi = i;
		}
	}
	tab = calcTextTab(tab, fi+1);
	txt = tab.join('\n');
	// Dessin
	var text = svgPaper.text(x, y, txt);
	var fs0 = Math.max(10, Math.round(20 / viewScale));
	text.attr('font', '');
	text.attr('font-size', '' + fs0);
	var bbox = text.getBBox();
	var fs = Math.min(w / bbox.width, h / bbox.height);
	text.attr('font-size', fs0 * fs);
	text = chromeBugBBox(text);
	if (a != 0) text.transform('r' + a * 180 / Math.PI);
	return(text);
}

function chromeBugBBox(text)
{
	// Chrome bug workaround (https://github.com/DmitryBaranovskiy/raphael/issues/491)
	// This workaround only partially corrects the issue:
	// Chrome getBBox implementation is bugged
	if (text.getBBox().width == 0)
	{
		var tspan = text.node.getElementsByTagName('tspan')[0];
		if (tspan)
		{
			tspan.setAttribute('dy', 0);
		}
	}
	return(text);
}

function arcPath(r, a1, a2, sweep)
{
	with(Math){
	var p = '';
	var n = floor(abs(a2 - a1) * 2 / PI) + 1;
	var i;
	for (i=1; i<=n; i++)
	{
		p += ' A ' + (coordX * r) + ',' + (coordY * r) +
			' 0 0,' + sweep + ' ' +
			(coordX * r * sin(a1+(a2-a1)*i/n)) + ',' + (-coordY * r * cos(a1+(a2-a1)*i/n));
	}
	} // with(Math)
	return(p);
}

function secteur(a1, a2, r1, r2, x_elt, lev)
{
	with(Math){
	var idx = svgElts[x_elt][SVGELT_IDX];
	// Create sector
	while (a1 < 0) {a1 += 2*PI; a2 += 2*PI;}
	while (a1 > 2*PI) {a1 -= 2*PI; a2 -= 2*PI;}
	var ap1 = (coordX * r1 * sin(a1)) + ',' + (-coordY * r1 * cos(a1));
	var ap2 = (coordX * r1 * sin(a2)) + ',' + (-coordY * r1 * cos(a2));
	var ap3 = (coordX * r2 * sin(a1)) + ',' + (-coordY * r2 * cos(a1));
	var ap4 = (coordX * r2 * sin(a2)) + ',' + (-coordY * r2 * cos(a2));
	var ap = 'M ' + ap2 + arcPath(r1, a2, a1, 0) + ' L ' + ap3 + arcPath(r2, a1, a2, 1) + ' z';
	var p = svgPaper.path(ap);
	// Create text over the sector
	var txt = GetTextI(idx);
	var r = (r1 + r2) / 2;
	var a = (a1 + a2) / 2;
	var w = coordX * (r2 - r1);
	var h = coordX * r * min(abs(sin(acos(r1 / r2))), abs(a2 - a1));
	var ta = a;
	if (w < h)
	{
		var tmp = w;
		w = h;
		h = tmp;
	}
	else
	{
		ta = a + PI/2;
	}
	while (ta > 2*PI) ta -= 2*PI;
	if ((ta > PI/2) && (ta < 3*PI/2)) ta += PI;
	var text = textLine(coordX * r * sin(a), -coordY * r * cos(a), ta, txt, w, h, x_elt);
	// Build the SVG elements style
	SvgSetStyle(p, text, x_elt, lev);
	} // with(Math)
}

function rectangle(x, y, w, h, x_elt, lev)
{
	with(Math){
	var idx = svgElts[x_elt][SVGELT_IDX];
	// Create rectangle
	var p = svgPaper.rect(x, y, w, h);
	// Create text over the sector
	var txt = GetTextI(idx);
	var tw = w;
	var th = h;
	var ta = 0;
	if (w < h)
	{
		var tmp = tw;
		tw = th;
		th = tmp;
		ta = -PI/2;
	}
	var text = textLine(x + w / 2.0, y + h / 2.0, ta, txt, tw, th, x_elt);
	// Build the SVG elements style
	SvgSetStyle(p, text, x_elt, lev);
	} // with(Math)
}

function textRect(x1, y1, x2, y2, x_elt)
{
	var idx = svgElts[x_elt][SVGELT_IDX];
	var txt = GetTextI(idx);
	return textLine((x1 + x2) / 2.0, (y1 + y2) / 2.0, 0, txt, x2 - x1, y2 - y1, x_elt);
}

function GetTextI(idx)
{
	if (idx < 0) return('?');
	return(I[idx][I_SHORT_NAME]);
}
