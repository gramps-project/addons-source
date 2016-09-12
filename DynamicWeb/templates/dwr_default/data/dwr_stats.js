// Gramps - a GTK+/GNOME based genealogy program
//
// Copyright (C) 2014 Pierre Bélissent
//
// This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
// This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
// You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


//=================================================================
//====================================================== Statistics
//=================================================================


function chartSort(a, b)
{
	return((a > b) ? 1 : ((b > a) ? -1 : 0 ));
}

function placeSort(a, b)
{
	a = a.split(',');
	b = b.split(',');
	a.reverse();
	b.reverse();
	a =  a.join(',');
	b =  b.join(',');
	return((a > b) ? 1 : ((b > a) ? -1 : 0 ));
}

function invalidData(d)
{
	return(d == null || (typeof(d) != 'string' && isNaN(d)) || typeof(d) == 'undefined' || d == '');
}

function extractorNumberField(table, name, field)
{
	return({
		name: name,
		numeric: true,
		fval: function(idx) {
			var val = parseFloat(table[idx][field]);
			if (invalidData(val)) return([]);
			return([val]);
		},
		fsort: chartSort
	});
}

function extractorStringField(table, name, field, fsort)
{
	if (typeof(fsort) == 'undefined') fsort = chartSort;
	return({
		name: name,
		numeric: false,
		fval: function(idx) {
			var val = "" + table[idx][field];
			if (invalidData(val)) return([]);
			return([val]);
		},
		fsort: fsort
	});
}

function extractorListField(table, name, field, numeric, age)
{
	return({
		name: name,
		numeric: numeric,
		fval: function(idx) {
			vals = [];
			for (var i = 0; i < table[idx][field].length; i += 1)
			{
				var val = table[idx][field][i];
				if (!invalidData(val) && (!age || val != 0)) vals.push(val);
			}
			return(vals);
		},
		fsort: chartSort
	});
}

function extractorDateField(table, name, field)
{
	return({
		name: name,
		numeric: true,
		fval: function(idx) {
			var val = parseFloat(table[idx][field]);
			if (invalidData(val) || val == 0) return([]);
			return([val]);
		},
		fsort: chartSort
	});
}

function extractorAgeField(table, name, field)
{
	return({
		name: name,
		numeric: true,
		fval: function(idx) {
			var val = parseFloat(table[idx][field]);
			if (invalidData(val)) return([]);
			return([val]);
		},
		fsort: chartSort
	});
}

function extractorDayofyearField(table, name, field)
{
	return({
		name: name,
		numeric: true,
		fval: function(idx) {
			var val = parseFloat(table[idx][field]);
			if (invalidData(val)) return([]);
			return([val]);
		},
		fsort: chartSort
	});
}

function extractorMonthField(table, name, field)
{
	return({
		name: name,
		numeric: true,
		fval: function(idx) {
			var val = parseInt(table[idx][field]);
			if (invalidData(val)) return([]);
			return([val]);
		},
		fsort: chartSort
	});
}

var STATISTICS_DATA;
var STATISTICS_CHART_TYPES;
var STATISTICS_FUNCTIONS;

function initStatistics()
{
	STATISTICS_DATA = [
		{
			name: _('Individuals'),
			table: I,
			fref: indiRef,
			extractors: [
				extractorStringField(I, _('Name'), 'name'),
				extractorStringField(I, _('Surname'), 'chart_surnames'),
				extractorStringField(I, _('Gramps ID'), 'gid'),
				extractorStringField(I, _('Gender'), 'chart_gender', function(a, b) {
					var k1 = $.inArray(a, GENDERS_TEXT_ORDER);
					var k2 = $.inArray(b, GENDERS_TEXT_ORDER);
					return(k1 - k2);
				}),
				extractorDateField(I, _('Birth date'), 'birth_sdn'),
				extractorMonthField(I, _('Birth month'), 'birth_month'),
				extractorDayofyearField(I, _('Birth day of year'), 'birth_dayofyear'),
				extractorDateField(I, _('Death date'), 'death_sdn'),
				extractorMonthField(I, _('Death month'), 'death_month'),
				extractorDayofyearField(I, _('Death day of year'), 'death_dayofyear'),
				extractorAgeField(I, _('Age at death'), 'chart_age_death'),
				extractorListField(I, _('Age at marriage'), 'chart_age_marr', false, true),
				extractorAgeField(I, _('Age when first child born'), 'chart_age_child_first'),
				extractorAgeField(I, _('Age when last child born'), 'chart_age_child_last'),
				extractorNumberField(I, _('Number of children'), 'chart_nb_child'),
				extractorNumberField(I, _('Number of relationships'), 'chart_nb_fams'),
				extractorListField(I, _('Number of children per family'), 'chart_nb_child_fams', true, false),
				extractorStringField(I, _('Birth place'), 'birth_place', placeSort),
				extractorStringField(I, _('Death place'), 'death_place', placeSort)
			]
		},
		{
			name: _('Families'),
			table: F,
			fref: famRef,
			extractors: [
				extractorStringField(F, _('Name'), 'name'),
				extractorStringField(F, _('Spouses surnames'), 'chart_surnames'),
				extractorStringField(F, _('Gramps ID'), 'gid'),
				extractorDateField(F, _('Marriage date'), 'marr_sdn'),
				extractorMonthField(F, _('Marriage month'), 'marr_month'),
				extractorDayofyearField(F, _('Marriage day of year'), 'marr_dayofyear'),
				extractorNumberField(F, _('Number of children'), 'chart_nb_child'),
				extractorStringField(F, _('Marriage place'), 'marr_place', placeSort),
				extractorListField(F, _('Spouses age at marriage'), 'chart_spou_age_marr', false, true),
				extractorAgeField(F, _('Father\'s age at marriage'), 'chart_spou1_age_marr'),
				extractorAgeField(F, _('Mother\'s age at marriage'), 'chart_spou2_age_marr')
			]
		}
	];

	STATISTICS_FUNCTIONS = [
		{
			name: _('None'),
			needs_numeric: false,
			numeric: false,
			compute: chartFunctionNone
		},
		{
			name: _('Count'),
			needs_numeric: false,
			numeric: true,
			compute: chartFunctionCount
		},
		{
			name: _('Sum'),
			needs_numeric: true,
			numeric: true,
			compute: chartFunctionNumericWrapper(function(values) {
				var sum = 0;
				for (var i = 0; i < values.length; i += 1) sum += values[i];
				return(sum);
			})
		},
		{
			name: _('Average'),
			needs_numeric: true,
			numeric: true,
			compute: chartFunctionNumericWrapper(function(values) {
				var sum = 0;
				for (var i = 0; i < values.length; i += 1) sum += values[i];
				return(1.0 * sum / values.length);
			})
		}
	];

	STATISTICS_CHART_TYPES = [
		{
			name: _('Pie chart'),
			fbuild: printStatisticsPie,
			enabled: {w: false, x: true, y: false, z: false},
			needed: {w: false, x: true, y: false, z: false}
		},
		{
			name: _('Donut chart'),
			fbuild: printStatisticsDonut,
			enabled: {w: false, x: true, y: false, z: false},
			needed: {w: false, x: true, y: false, z: false}
		},
		{
			name: _('Bar chart'),
			fbuild: printStatisticsBar,
			enabled: {w: true, x: true, y: false, z: false},
			needed: {w: false, x: true, y: false, z: false}
		},
		{
			name: _('Line chart'),
			fbuild: printStatisticsLine,
			enabled: {w: true, x: true, y: false, z: false},
			needed: {w: false, x: true, y: false, z: false}
		},
		{
			name: _('Scatter chart'),
			fbuild: printStatisticsScatter,
			enabled: {w: true, x: true, y: true, z: false},
			needed: {w: false, x: true, y: true, z: false}
		},
		{
			name: _('Bubble chart'),
			fbuild: printStatisticsBubble,
			enabled: {w: true, x: true, y: true, z: true},
			needed: {w: false, x: true, y: true, z: true}
		}
	];
}

// Indexes for tables in above structure
TABLE_I = 0;
TABLE_F = 1;
// Indexes for extractors in above structure
var i = 0;
EXTRACTOR_DISABLED = -1;
EXTRACTOR_I_NAME = i++;
EXTRACTOR_I_SURNAME = i++;
EXTRACTOR_I_GID = i++;
EXTRACTOR_I_GENDER = i++;
EXTRACTOR_I_BIRTH_DATE = i++;
EXTRACTOR_I_BIRTH_MONTH = i++;
EXTRACTOR_I_BIRTH_DAYOFYEAR = i++;
EXTRACTOR_I_DEATH_DATE = i++;
EXTRACTOR_I_DEATH_DAY = i++;
EXTRACTOR_I_DEATH_DAYOFYEAR = i++;
EXTRACTOR_I_AGE_DEATH = i++;
EXTRACTOR_I_AGE_MARR = i++;
EXTRACTOR_I_AGE_CHILD_FIRST = i++;
EXTRACTOR_I_AGE_CHILD_LAST = i++;
EXTRACTOR_I_NB_CHILD = i++;
EXTRACTOR_I_NB_FAMS = i++;
EXTRACTOR_I_NB_CHILD_FAMS = i++;
EXTRACTOR_I_BIRTH_PLACE = i++;
EXTRACTOR_I_DEATH_PLACE = i++;
var i = 0;
EXTRACTOR_F_NAME = i++;
EXTRACTOR_F_SURNAME = i++;
EXTRACTOR_F_GID = i++;
EXTRACTOR_F_MARR_DATE = i++;
EXTRACTOR_F_MARR_MONTH = i++;
EXTRACTOR_F_MARR_DAY = i++;
EXTRACTOR_F_NB_CHILD = i++;
EXTRACTOR_F_MARR_PLACE = i++;
EXTRACTOR_F_SPOU_AGE_MARR = i++;
EXTRACTOR_F_SPOU1_AGE_MARR = i++;
EXTRACTOR_F_SPOU2_AGE_MARR = i++;

// Indexes for functions in above structure
var i = 0;
FUNCTION_NONE = i++;
FUNCTION_COUNT = i++;
FUNCTION_SUM = i++;
FUNCTION_AVERAGE = i++;

// Indexes for chart types in above structure
var i = 0;
CHART_TYPE_PIE = i++;
CHART_TYPE_DONUT = i++;
CHART_TYPE_BAR = i++;
CHART_TYPE_LINE = i++;
CHART_TYPE_SCATTER = i++;
CHART_TYPE_BUBBLE = i++;

DAYS_PER_YEAR = 365.242190517;

var turboThreshold = 1000;
var turboThresholdOverflow = false;


function gregorian_ymd(sdn)
{
	if (sdn == 0)
		return({year: NaN, month: NaN, day: NaN, dayofyear: NaN})

	var _GRG_SDN_OFFSET = 32045;
	var _GRG_DAYS_PER_5_MONTHS  = 153;
	var _GRG_DAYS_PER_4_YEARS   = 1461;
	var _GRG_DAYS_PER_400_YEARS = 146097;

	var temp = (_GRG_SDN_OFFSET + sdn) * 4 - 1

	// Calculate the century (year/100)
	var century = Math.floor(temp / _GRG_DAYS_PER_400_YEARS);

	// Calculate the year and day of year (1 <= day_of_year <= 366)
	temp = Math.floor((temp % _GRG_DAYS_PER_400_YEARS) / 4) * 4 + 3;
	year = (century * 100) + Math.floor(temp / _GRG_DAYS_PER_4_YEARS);
	dayofyear = Math.floor((temp % _GRG_DAYS_PER_4_YEARS) / 4) + 1;

	// Calculate the month and day of month
	temp = dayofyear * 5 - 3;
	month = Math.floor(temp / _GRG_DAYS_PER_5_MONTHS);
	day = Math.floor((temp % _GRG_DAYS_PER_5_MONTHS) / 5) + 1;

	// Convert to the normal beginning of the year
	if (month < 10) month += 3;
	else
	{
		year += 1;
		month -= 9;
	}

	// Adjust to the B.C./A.D. type numbering
	year -= 4800;
	if (year <= 0) year -= 1;
	return({year: year, month: month, day: day, dayofyear: dayofyear})
}

function age(d1, d2)
{
	if (d1 == 0) return(NaN);
	if (d2 == 0) return(NaN);
	return((d2 - d1) / DAYS_PER_YEAR);
}

function computeStatisticsData()
{
	// Compute data required for charts
	for (var idx = 0; idx < I.length && search.ChartTable == TABLE_I; idx += 1)
	{
		indi = I[idx];
		indi.chart_gender = GENDERS_TEXT[indi.gender];
		indi.chart_surnames = [];
		for (var n = 0; n < indi.names.length; n += 1)
			indi.chart_surnames = $.extend([], indi.names[n].surnames);
		indi.birth_month = gregorian_ymd(indi.birth_sdn).month;
		indi.death_month = gregorian_ymd(indi.death_sdn).month;
		indi.birth_dayofyear = gregorian_ymd(indi.birth_sdn).dayofyear;
		indi.death_dayofyear = gregorian_ymd(indi.death_sdn).dayofyear;
		indi.chart_age_death = age(indi.birth_sdn, indi.death_sdn);
		indi.chart_age_marr = [];
		indi.chart_nb_child = 0;
		indi.chart_nb_fams = indi.fams.length;
		indi.chart_nb_child_fams = [];
		for (var i = 0; i < indi.fams.length; i += 1)
		{
			var fam = F[indi.fams[i]];
			indi.chart_age_marr.push(age(indi.birth_sdn, fam.marr_sdn));
			indi.chart_nb_child += F[I[idx].fams[i]].chil.length;
			indi.chart_nb_child_fams.push(F[indi.fams[i]].chil.length);
		}
		if (indi.fams.length > 0)
		{
			var fam0 = F[indi.fams[0]];
			if (fam0.chil.length > 0)
				indi.chart_age_child_first = age(indi.birth_sdn, fam0.chil[0].birth_sdn);
			var fam1 = F[indi.fams[indi.fams.length - 1]];
			if (fam1.chil.length > 0)
				indi.chart_age_child_last = age(indi.birth_sdn, fam1.chil[fam1.chil.length - 1].birth_sdn);
		}
	}
	for (var fdx = 0; fdx < F.length && search.ChartTable == TABLE_F; fdx += 1)
	{
		var fam = F[fdx];
		fam.chart_surnames = [];
		fam.marr_month =gregorian_ymd(fam.marr_sdn).month;
		fam.marr_dayofyear = gregorian_ymd(fam.marr_sdn).dayofyear;
		fam.chart_spou_age_marr = [];
		for (var i = 0; i < fam.spou.length; i += 1)
		{
			var indi = I[fam.spou[i]];
			for (var n = 0; n < indi.names.length; n += 1)
				fam.chart_surnames = $.extend(fam.chart_surnames, indi.names[n].surnames);
			fam.chart_spou_age_marr.push(age(indi.birth_sdn, fam.marr_sdn));
			if (i == 0) fam.chart_spou1_age_marr = fam.chart_spou_age_marr[i];
			if (i == 1) fam.chart_spou2_age_marr = fam.chart_spou_age_marr[i];
		}
		fam.chart_nb_child = fam.chil.length;
	}
}


function chartFunctionNone(data, x0, x1, fields, funcs)
{
	var subfields = $.extend([], fields); // Deep copy
	var subfuncs = $.extend([], funcs); // Deep copy
	var field = subfields.splice(0, 1);
	var func = (subfields.length > 0) ? STATISTICS_FUNCTIONS[subfuncs.splice(0, 1)].compute : null;
	var points = [];
	var y0 = x0;
	while (y0 < x1)
	{
		// Find all identical values
		var y1 = y0;
		while (y1 < x1 && data[y1][field] == data[y0][field]) y1 += 1;
		// Compute points for lesser dimension
		var subpoints = [{indexes: []}];
		if (subfields.length > 0)
		{
			subpoints = func(data, y0, y1, subfields, subfuncs);
		}
		else
		{
			for (var i = y0; i < y1; i += 1) subpoints[0].indexes.push(data[i].indexes);
		}
		// Fill result table
		for (var i = 0; i < subpoints.length; i += 1) subpoints[i][field] = data[y0 + i][field];
		points = points.concat(subpoints);
		y0 = y1;
	}
	return(points);
};

function chartFunctionCount(data, x0, x1, fields, funcs)
{
	var subfields = $.extend([], fields); // Deep copy
	var subfuncs = $.extend([], funcs); // Deep copy
	var field = subfields.splice(0, 1);
	var func = (subfields.length > 0) ? STATISTICS_FUNCTIONS[subfuncs.splice(0, 1)].compute : null;
	var y0 = x0;
	var points = [];
	var y0 = x0;
	while (y0 < x1)
	{
		// Find all identical values
		var y1 = y0;
		while (y1 < x1 && data[y1][field] == data[y0][field]) y1 += 1;
		// Compute points for lesser dimension
		var subpoints = [{indexes: []}];
		if (subfields.length > 0)
		{
			subpoints = func(data, y0, y1, subfields, subfuncs);
		}
		else
		{
			for (var i = y0; i < y1; i += 1) subpoints[0].indexes.push(data[i].indexes);
		}
		// Fill result table
		for (var i = 0; i < subpoints.length; i += 1)
		{
			subpoints[i][field] = y1 - y0;
			subpoints[i][field + '_str'] = subpoints[i][field] + ' (' + data[y0][field] + ')';
		}
		points = points.concat(subpoints);
		y0 = y1;
	}
	return(points);
};

function chartFunctionNumericWrapper(fn)
{
	return function(data, x0, x1, fields, funcs) {
		var subfields = $.extend([], fields); // Deep copy
		var subfuncs = $.extend([], funcs); // Deep copy
		var field = subfields.splice(0, 1);
		var func = (subfields.length > 0) ? STATISTICS_FUNCTIONS[subfuncs.splice(0, 1)].compute : null;
		var y0 = x0;
		// Compute points for lesser dimension
		var points = [{indexes: []}];
		if (subfields.length > 0)
		{
			points = func(data, x0, x1, subfields, subfuncs);
		}
		// Compute numeric function result
		var vals = [];
		for (var i = x0; i < x1; i += 1)
		{
			vals.push(data[i][field]);
			if (subfields.length == 0) points[0].indexes.push(data[i].indexes);
		}
		var val = fn(vals);
		// Build result table
		for (var i = 0; i < points.length; i += 1) points[i][field] = val;
		return(points);
	};
}


function ChartFilter(vals, field, fsort)
{
	var filtered = [];
	for (var i = 0; i < vals.length; i += 1)
	{
		var val = vals[i];
		if (typeof(D[field_min]) == 'undefined') D[field_min] = D[field_max] = val;
		D[field_min] = (fsort(D[field_min], val) <= 0) ? D[field_min]: val;
		D[field_max] = (fsort(D[field_max], val) >= 0) ? D[field_max]: val;
		filtered.push(val);
	}
	return(filtered);
}


function returnZero()
{
	return(0);
}

function fvalZero()
{
	return([0]);
}

var D;

function getStatisticsData()
{
	initStatistics();
	computeStatisticsData();

	D = {};
	var data = [];
	var table = STATISTICS_DATA[search.ChartTable].table
	var xExtractor = STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataX].fval;
	var yEnabled = STATISTICS_CHART_TYPES[search.ChartType].enabled.y && search.ChartDataY != EXTRACTOR_DISABLED;
	var yExtractor = yEnabled ?
		STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataY].fval :
		fvalZero;
	var zEnabled = STATISTICS_CHART_TYPES[search.ChartType].enabled.z && search.ChartDataZ != EXTRACTOR_DISABLED;
	var zExtractor = zEnabled ?
		STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataZ].fval :
		fvalZero;
	var wEnabled = STATISTICS_CHART_TYPES[search.ChartType].enabled.w && search.ChartDataW != EXTRACTOR_DISABLED;
	var wExtractor = wEnabled ?
		STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataW].fval :
		fvalZero;
	var xSort = STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataX].fsort;
	var ySort = yEnabled ?
		STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataY].fsort :
		returnZero;
	var zSort = zEnabled ?
		STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataZ].fsort :
		returnZero;
	var wSort = wEnabled ?
		STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataW].fsort :
		returnZero;
	var fExtractor = [
		(search.ChartFilter1 != EXTRACTOR_DISABLED) ? STATISTICS_DATA[search.ChartTable].extractors[search.ChartFilter1].fval : null,
		(search.ChartFilter2 != EXTRACTOR_DISABLED) ? STATISTICS_DATA[search.ChartTable].extractors[search.ChartFilter2].fval : null,
		(search.ChartFilter3 != EXTRACTOR_DISABLED) ? STATISTICS_DATA[search.ChartTable].extractors[search.ChartFilter3].fval : null
	];
	var fSort = [
		(search.ChartFilter1 != EXTRACTOR_DISABLED) ? STATISTICS_DATA[search.ChartTable].extractors[search.ChartFilter1].fsort : null,
		(search.ChartFilter2 != EXTRACTOR_DISABLED) ? STATISTICS_DATA[search.ChartTable].extractors[search.ChartFilter2].fsort : null,
		(search.ChartFilter3 != EXTRACTOR_DISABLED) ? STATISTICS_DATA[search.ChartTable].extractors[search.ChartFilter3].fsort : null
	];
	var fMin = [
		search.ChartFilter1Min,
		search.ChartFilter2Min,
		search.ChartFilter3Min
	];
	var fMax = [
		search.ChartFilter1Max,
		search.ChartFilter2Max,
		search.ChartFilter3Max
	];
	for (var j = 0; j < STATISTICS_NB_FILTERS; j += 1)
	{
		if (!isNaN(parseFloat(fMin[j]))) fMin[j] = parseFloat(fMin[j])
		if (fMin[j] == "") fMin[j] = null;
		if (!isNaN(parseFloat(fMax[j]))) fMax[j] = parseFloat(fMax[j])
		if (fMax[j] == "") fMax[j] = null;
	}
	filter = function(i, fsort)
	{
		for (var j = 0; j < STATISTICS_NB_FILTERS; j += 1)
		{
			if (fExtractor[j] === null) continue;
			var vals = fExtractor[j](i);
			for (var k = 0; k < vals.length; k += 1)
			{
				var val = vals[k];
				if (fMin[j] !== null && fSort[j](val, fMin[j]) < 0) return(true);
				if (fMax[j] !== null && fSort[j](val, fMax[j]) > 0) return(true);
			}
		}
		return(false)
	}
	minmax = function(vals, field, fsort)
	{
		var field_min = field + 'Min';
		var field_max = field + 'Max';
		for (var i = 0; i < vals.length; i += 1)
		{
			var val = vals[i];
			if (typeof(D[field_min]) == 'undefined') D[field_min] = D[field_max] = val;
			D[field_min] = (fsort(D[field_min], val) <= 0) ? D[field_min]: val;
			D[field_max] = (fsort(D[field_max], val) >= 0) ? D[field_max]: val;
		}
	}
	
	// Get data
	for (var i = 0; i < table.length; i += 1)
	{
		if (filter(i)) continue;
		var w = wExtractor(i);
		minmax(w, 'w', wSort);
		for (var iw = 0; iw < w.length; iw += 1)
		{
			var x = xExtractor(i);
			minmax(x, 'x', xSort);
			for (var ix = 0; ix < x.length; ix += 1)
			{
				var y = yExtractor(i);
				minmax(y, 'y', ySort);
				for (var iy = 0; iy < y.length; iy += 1)
				{
					var z = zExtractor(i);
					minmax(z, 'z', zSort);
					for (var iz = 0; iz < z.length; iz += 1)
					{
						data.push({indexes: i, w: w[iw], x: x[ix], y: y[iy], z: z[iz]});
					}
				}
			}
		}
	}

	// Sort data
	data.sort(function (a, b) {
		var s = wSort(a.w, b.w);
		if (s != 0) return(s);
		var s = xSort(a.x, b.x);
		if (s != 0) return(s);
		var s = ySort(a.y, b.y);
		if (s != 0) return(s);
		return(zSort(a.z, b.z));
	});

	// Apply functions
	data = chartFunctionNone(data, 0, data.length, ['w', 'x', 'y', 'z'], [search.ChartFunctionX, search.ChartFunctionY, search.ChartFunctionZ]);

	// Remove duplicates
	var points = [];
	for (var i = 0; i < data.length; i += 1)
	{
		if (i == 0 || !(
			data[i].w == points[points.length - 1].w &&
			data[i].x == points[points.length - 1].x &&
			data[i].y == points[points.length - 1].y &&
			data[i].z == points[points.length - 1].z &&
			data[i].w_str == points[points.length - 1].w_str &&
			data[i].x_str == points[points.length - 1].x_str &&
			data[i].y_str == points[points.length - 1].y_str &&
			data[i].z_str == points[points.length - 1].z_str))
		{
			// Element is different as previous one
			points.push(data[i]);
		}
		else
		{
			// Element is identical to previous one, concatenate table indexes
			$.merge(points[points.length - 1].indexes, data[i].indexes);
		}
	}

	// Sort and remove duplicates in table indexes
	for (var i = 0; i < points.length; i += 1)
	{
		var unique = [];
		$.each(points[i].indexes, function(i, el){
			if($.inArray(el, unique) === -1) unique.push(el);
		});
		unique.sort(function(a, b) {
			return(chartSort(a.name, b.name));
		});
		points[i].indexes = unique;
	}

	// Get min and max
	// $.each([
		// ['w', wSort],
		// ['x', xSort],
		// ['y', ySort],
		// ['z', zSort]
	// ], function (i, v) {
		// var field = v[0];
		// var fmin = v[0] + 'Min';
		// var fmax = v[0] + 'Max';
		// var fsort = v[1];
		// for (var i = 0; i < points.length; i += 1)
		// {
			// if (i == 0)
			// {
				// D[fmin] = points[i][field];
				// D[fmax] = points[i][field];
			// }
			// D[fmin] = (fsort(D[fmin], points[i][field]) <= 0) ? D[fmin]: points[i][field];
			// D[fmax] = (fsort(D[fmax], points[i][field]) >= 0) ? D[fmax]: points[i][field];
		// }
	// }

	// Check if too many points
	turboThresholdOverflow = false;
	if (points.length >= turboThreshold)
	{
		console.log('Exceeding highcharts turboThreshold (' + points.length + ' >= ' + turboThreshold + ')');
		turboThresholdOverflow = true;
	}

	// Convert non-numeric to ordinal index
	D.strings = {}
	var x_not_num = !STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataX].numeric && ! STATISTICS_FUNCTIONS[search.ChartFunctionX].numeric;
	var y_not_num = yEnabled && !STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataY].numeric && ! STATISTICS_FUNCTIONS[search.ChartFunctionY].numeric;
	$.each([['x', x_not_num, xSort], ['y', y_not_num, ySort]], function(i, v) {
		var field = v[0];
		var not_num = v[1];
		var sort = v[2];
		if (not_num)
		{
			D.strings[field] = [];
			var rawstrings = [];
			for (var i = 0; i < points.length; i += 1)
			{
				if ($.inArray(points[i][field], rawstrings) == -1) rawstrings.push(points[i][field]);
			}
			rawstrings.sort(sort);
			for (var i = 0; i < rawstrings.length; i += 1)
				if (i == 0 || rawstrings[i] != rawstrings[i - 1]) D.strings[field].push(rawstrings[i]);
			for (var i = 0; i < points.length; i += 1)
			{
				points[i][field + '_str'] = points[i][field];
				points[i][field] = $.inArray(points[i][field], D.strings[field]);
			}
		}
	});

	// Split into series
	D.series = []
	var	wValues = [];
	for (var i = 0; i < points.length; i += 1)
	{
		if ($.inArray(points[i].w, wValues) == -1)
		{
			D.series.push({
				w: points[i].w,
				points: []
			});
			wValues.push(points[i].w);
		}
		D.series[D.series.length - 1].points.push(points[i]);
	}
}


function printStatistics()
{
	ParseSearchString();
	var html = '';
	html += '<h1>' + _('Statistics Charts') + '</h1>';

	// Collect data
	getStatisticsData();
	if (D.series.length > 100)
	{
		document.write('<div class="alert alert-danger" role="alert"><p>Error in the chart configuration' +
			'<p class="dwr-centered"><a href="statistics_conf.html?' + BuildSearchString() + '">' +
			'<button type="button" class="btn btn-default">' +
			_('Configure') + '</button></a>' +
			'</div>');
		return;
	}
	if (D.series.length == 0)
	{
		document.write('<div class="alert alert-danger" role="alert"><p>' + _('No matching data') +
			'<p class="dwr-centered"><a href="statistics_conf.html?' + BuildSearchString() + '">' +
			'<button type="button" class="btn btn-default">' +
			_('Configure') + '</button></a>' +
			'</div>');
		return;
	}

	// Build chart
	var chart = STATISTICS_CHART_TYPES[search.ChartType].fbuild(D);

	// Draw chart
	html += '<div id="dwr-chart-container">';
	html += '<div id="dwr-chart" class="highchart-container"></div>';
	html += '<div id="dwr-chart-buttons">';
	html += '<div class="btn-group" role="group">';
	html += '<button id="dwr-chart-config" type="button" class="btn btn-default" title="' + _('Configuration') + '">';
	html += '<span class="glyphicon glyphicon-cog"></span>';
	html += '</button>';
	html += '<button id="dwr-chart-expand" type="button" class="btn btn-default" title="' + (isChartExpanded ? _('Restore') : _('Maximize')) + '">';
	html += '<span class="glyphicon glyphicon-fullscreen"></span>';
	html += '</button>';
	html += '</div>';
	html += '</div>';
	html += '</div>';
	$(document).ready(function() {
		$('#dwr-chart-config').click(function() {
			window.location.href = 'statistics_conf.html?' + BuildSearchString();
			return(false);
		});
		$('#dwr-chart-expand').click(function() {
			window.location.href = (isChartExpanded ? 'statistics.html': 'statistics_full.html') + '?' + BuildSearchString();
			return(false);
		});
		$('#dwr-chart').highcharts(chart);
	});
	document.write(html);
}

var isChartExpanded = false;

function printStatisticsExpand()
{
	isChartExpanded = true;
	printStatistics();
	$(document).ready(function() {
		$('body').addClass('dwr-fullscreen');
		$('body').children().css('display', 'none');
		$('body').prepend($('#dwr-chart-buttons'));
		$('body').prepend($('#dwr-chart'));
		$('#dwr-chart').addClass('dwr-expanded');
		$(window).resize(chartResize);
		chartResize();
	});
}

function chartResize()
{
	var div = $('.dwr-expanded');
	if (div.length != 1) return(true);
	var w = $(window).width();
	var h = $(window).height();
	div.width(w);
	div.height(h);
	var highchart = $('#dwr-chart').highcharts();
	highchart.setSize(w, h, false);
	highchart.reflow();
	return(true);
}


function printStatisticsDefaultChart()
{
	var title = STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataX].name;
	if (search.ChartDataY != EXTRACTOR_DISABLED)
		title = STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataY].name;
	var chart = {
		chart: {},
		title: {
			text: title
		},
		credits: {
			enabled: false
		},
		legend: {
			enabled: false
		},
		tooltip: {
			headerFormat: '',
			pointFormatter: pointFormatter
		},
		plotOptions: {},
		xAxis: {
			title: {},
			labels: {}
		},
		yAxis: {
			title: {},
			labels: {}
		},
		series: []
	}
	if (turboThresholdOverflow) chart.tooltip.enabled = false;
	return(chart);
}


STATISTICS_GENDER_COLORS = [
	GRAMPS_PREFERENCES['color-gender-male-death'],
	GRAMPS_PREFERENCES['color-gender-female-death'],
	GRAMPS_PREFERENCES['color-gender-unknown-death']
];

function chartColor(i, nb)
{
	var color = "#888";
	if (search.ChartBackground == CHART_BACKGROUND_GENDER)
	{
		color = STATISTICS_GENDER_COLORS[i % STATISTICS_GENDER_COLORS.length];
	}
	if (search.ChartBackground == CHART_BACKGROUND_GRADIENT)
	{
		color = SvgColorGrad(0, nb - 1, i);
	}
	if (search.ChartBackground == CHART_BACKGROUND_SINGLE)
	{
		color = SVG_TREE_COLOR1;
	}
	if (search.ChartBackground == CHART_BACKGROUND_WHITE)
	{
		color = SVG_TREE_COLOR_SCHEME0[i % SVG_TREE_COLOR_SCHEME0.length];
	}
	if (search.ChartBackground == CHART_BACKGROUND_SCHEME1)
	{
		color = SVG_TREE_COLOR_SCHEME1[i % SVG_TREE_COLOR_SCHEME1.length];
	}
	if (search.ChartBackground == CHART_BACKGROUND_SCHEME2)
	{
		color = SVG_TREE_COLOR_SCHEME2[i % SVG_TREE_COLOR_SCHEME2.length];
	}
	// Opacity
	var rgb = Raphael.getRGB(color);
	return("rgba(" + rgb.r + "," + rgb.g + "," + rgb.b + "," + (search.ChartOpacity / 100.0) + ")");
}


function pointFormatter()
{
	var txt = [];
	var p = this;
	if (!turboThresholdOverflow && p.indexes.length == 1)
		txt.push(STATISTICS_DATA[search.ChartTable].table[p.indexes[0]].name);
	$.each([
		['w', search.ChartDataW, FUNCTION_NONE],
		['x', search.ChartDataX, search.ChartFunctionX],
		['y', search.ChartDataY, search.ChartFunctionY],
		['z', search.ChartDataZ, search.ChartFunctionZ]
	], function(i, v) {
		var val = p[v[0]];
		var val_str = p[v[0] + '_str'];
		var extractor = v[1];
		var func = v[2];
		if (turboThresholdOverflow && i > 0)
		{
			val_str = D.strings[v[0]][p[i - 1]];
		}
		var val = (typeof(val_str) == 'undefined') ? val : val_str;
		if (extractor != EXTRACTOR_DISABLED)
		{
			var name = STATISTICS_DATA[search.ChartTable].extractors[extractor].name;
			if (func != FUNCTION_NONE) name += ' (' + STATISTICS_FUNCTIONS[func].name + ')';
			txt.push(name + ': ' + val);
		}
	});
	return(txt.join('<br>'));
}

function pointLink(event)
{
	var p = event.point;
	if (!turboThresholdOverflow && p.indexes.length == 1)
	{
		STATISTICS_DATA[search.ChartTable].fref(p.indexes[0]);
		return(false);
	}
	vals = {};
	$.each(['w', 'x', 'y', 'z'], function(i, v) {
		var val = p[v];
		var val_str = p[v + '_str'];
		if (turboThresholdOverflow && i > 0)
		{
			val_str = D.strings[v][p[i - 1]];
		}
		vals[v] = (typeof(val_str) == 'undefined') ? val : val_str;
	});
	search.ChartValW = "" + vals.w;
	search.ChartValX = "" + vals.x;
	search.ChartValY = "" + vals.y;
	search.ChartValZ = "" + vals.z;
	window.location.href = 'statistics_link.html?' + BuildSearchString();
}

function printStatisticsPie(D)
{
	var total = 0;
	for (var i = 0; i < D.series[0].points.length; i += 1)
	{
		total += D.series[0].points[i].x;
	}

	var chart = printStatisticsDefaultChart();
	chart.chart.type = 'pie';
	chart.plotOptions.pie = {
		events: {
			click: pointLink
		}
	};
	chart.series.push({data: []});
	for (var i = 0; i < D.series[0].points.length; i += 1)
	{
		var y = D.series[0].points[i].x;
		if (turboThresholdOverflow)
		{
			data.push(y);
		}
		else
		{
			var p = $.extend({}, D.series[0].points[i]);
			var val = (typeof(D.series[0].points[i].x_str) == 'undefined') ? D.series[0].points[i].x : D.series[0].points[i].x_str + ': ' + D.series[0].points[i].x;
			chart.series[0].data.push($.extend(p, {
				name: val + ' (' + Math.round(100 * D.series[0].points[i].x / total) + '%)',
				y: D.series[0].points[i].x,
				color: chartColor(i, D.series[0].points.length)
			}));
		}
	}
	return(chart);
}


function printStatisticsDonut(D)
{
	var chart = printStatisticsPie(D);
	chart.series[0].size = '100%';
    chart.series[0].innerSize = '65%';
	return(chart);
}


function printStatisticsLine(D)
{
	var chart = printStatisticsScatter(D);
	chart.plotOptions.line = {
		events: {
			click: pointLink
		}
	};
	return(chart);
}


function printStatisticsBar(D)
{
	var chart = printStatisticsLine(D);
	chart.plotOptions.bar = {
		events: {
			click: pointLink
		}
	};
	return(chart);
}


function printStatisticsPlots(D)
{
	var chart = printStatisticsDefaultChart();
	chart.chart.zoomType = 'xy';
	// Axis names
	chart.xAxis.title.text = STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataX].name;
	chart.yAxis.title.text = STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataY].name;
	if (search.ChartFunctionX != FUNCTION_NONE) chart.xAxis.title.text += ' (' + STATISTICS_FUNCTIONS[search.ChartFunctionX].name + ')';
	if (search.ChartFunctionY != FUNCTION_NONE) chart.yAxis.title.text += ' (' + STATISTICS_FUNCTIONS[search.ChartFunctionY].name + ')';
	chart.xAxis.labels.enabled = STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataX].numeric || STATISTICS_FUNCTIONS[search.ChartFunctionX].numeric;
	chart.yAxis.labels.enabled = STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataY].numeric || STATISTICS_FUNCTIONS[search.ChartFunctionY].numeric;
	// Categories for non-numeric data
	// if (! STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataX].numeric) chart.xAxis.categories = [];
	// if (! STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataY].numeric) chart.yAxis.categories = [];
	// Fill data
	for (var serie = 0; serie < D.series.length; serie += 1)
	{
		var data = [];
		for (var i = 0; i < D.series[serie].points.length; i += 1)
		{
			var x = (search.ChartDataX == EXTRACTOR_DISABLED) ? 0 : D.series[serie].points[i].x;
			var y = (search.ChartDataY == EXTRACTOR_DISABLED) ? 0 : D.series[serie].points[i].y;
			var z = (search.ChartDataZ == EXTRACTOR_DISABLED) ? 0 : D.series[serie].points[i].z;
			// if (! STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataX].numeric) chart.xAxis.categories.push(x);
			// if (! STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataY].numeric) chart.yAxis.categories.push(y);
			if (turboThresholdOverflow)
			{
				data.push([x, y, z]);
			}
			else
			{
				var p = $.extend({}, D.series[serie].points[i]);
				data.push($.extend(p, {x: x, y: y, z: z}));
			}
		}
		chart.series.push({
			name: (search.ChartDataW >= 0) ? D.series[serie].w : chart.yAxis.title.text,
			color: chartColor(serie, D.series.length),
			marker: {
				fillOpacity: search.ChartOpacity / 100.0
			},
			data: data
		});
	}
	return(chart);
}

function printStatisticsScatter(D)
{
	var chart = printStatisticsPlots(D);
	chart.chart.type = 'scatter';
	chart.chart.zoomType = 'xy';
	chart.plotOptions.scatter = {
		marker: {
			radius: 5,
			symbol: 'circle',
		},
		events: {
			click: pointLink
		}
	};
	return(chart);
}

function printStatisticsBubble(D)
{
	var chart = printStatisticsPlots(D);
	chart.chart.type = 'bubble';
	chart.plotOptions.bubble = {
		events: {
			click: pointLink
		}
	};
	return(chart);
}


// function pointLinkI()
// {
	// return indiRef(parseInt(this.name));
// }
// function chartPointDataI()
// {
	// idx = parseInt(this.name);
	// return(I[idx].name);
// }
// function pointLinkF()
// {
	// return famRef(parseInt(this.name));
// }
// function chartPointDataF()
// {
	// fdx = parseInt(this.name);
	// return(F[fdx].name);
// }


//=================================================================
//=================================================== Configuration
//=================================================================

STATISTICS_NB_FILTERS = 3;

function printStatisticsConfSelect(label, id, lg)
{
	if (typeof(lg) == 'undefined') lg = 3;
	var html = '';
	html += '<label id="' + id + '-lbl" for="' + id + '" class="control-label col-xs-12 col-sm-5 col-lg-' + lg + '">' + label + ': </label>';
	html += '<div class="col-xs-12 col-sm-7 col-lg-' + lg + '">';
	// html += '<div class="form-group">';
	html += '<select name="' + id + '" id="' + id + '" class="form-control" size="1">';
	html += '</select>';
	html += '</div>';
	// html += '</div>';
	return(html);
}

function printStatisticsConfInput(label, id)
{
	var html = '';
	// html += '<div class="form-group">';
	html += '<label id="' + id + '-lbl" for="' + id + '" class="control-label col-xs-12 col-sm-6 col-lg-2">' + label + ': </label>';
	html += '<div class="col-xs-12 col-sm-6 col-lg-2">';
	html += '<input type="text" name="' + id + '" id="' + id + '" class="form-control">';
	html += '</div>';
	// html += '</div>';
	return(html);
}

function printStatisticsConf()
{
	ParseSearchString();
	initStatistics();
	var html = '';
	// Chart type selector floating div
	html += '<h1>' + _('Statistics Charts') + '</h1>';
	html += chartExampleLinks();
	html += '<div class="panel panel-default">';
	html += '<div class="panel-body">';
	html += '<form id="dwr-chart-form" role="form" class="form-horizontal">';
	html += '<div class="row">';
	html += printStatisticsConfSelect(_('Data used'), 'dwr-chart-table');
	html += printStatisticsConfSelect(_('Chart type'), 'dwr-chart-type');
	html += '</div>';
	html += '<hr id="dwr-chart-dataw-hr">';
	html += '<div class="row">';
	html += printStatisticsConfSelect(_('Data used to split into series'), 'dwr-chart-dataw');
	html += '</div>';
	html += '<hr id="dwr-chart-datax-hr">';
	html += '<div class="row">';
	html += printStatisticsConfSelect(_('X-axis data'), 'dwr-chart-datax');
	html += printStatisticsConfSelect(_('X-axis function'), 'dwr-chart-funcx');
	html += '</div>';
	html += '<hr id="dwr-chart-datay-hr">';
	html += '<div class="row">';
	html += printStatisticsConfSelect(_('Y-axis data'), 'dwr-chart-datay');
	html += printStatisticsConfSelect(_('Y-axis function'), 'dwr-chart-funcy');
	html += '</div>';
	html += '<hr id="dwr-chart-dataz-hr">';
	html += '<div class="row">';
	html += printStatisticsConfSelect(_('Z-axis data'), 'dwr-chart-dataz');
	html += printStatisticsConfSelect(_('Z-axis function'), 'dwr-chart-funcz');
	// html += '<div id="dwr-chart-dataz-alert" class="col-xs-12 hidden">';
	// html += '<p><div class="alert alert-danger">';
	// html += _('The Z-axis value has to be numeric');
	// html += '</div>';
	// html += '</div>';
	html += '</div>';
	html += '<hr>';
	for (var i = 1; i <= STATISTICS_NB_FILTERS; i += 1)
	{
		html += '<div class="row">';
		html += printStatisticsConfSelect(_('Filter') + ' ' + i, 'dwr-chart-filter' + i, 2);
		html += printStatisticsConfInput(_('Minimum'), 'dwr-chart-filter' + i + 'min');
		html += printStatisticsConfInput(_('Maximum'), 'dwr-chart-filter' + i + 'max');
		html += '</div>';
	}
	html += '<hr>';

	html += '<div class="row">';

	// html += '<div class="form-group">';
	html += '<label for="dwr-chart-background" class="control-label col-xs-12 col-sm-5 col-md-3 col-lg-2">' + _('Chart coloring') + ': </label>';
	html += '<div class="col-xs-12 col-sm-7 col-md-3 col-lg-3">';
	html += '<select name="dwr-chart-background" id="dwr-chart-background" class="form-control" size="1" title="' + _('Chart coloring') + '">';
	html += '</select>';
	html += '</div>';
	// html += '</div>';

	// html += '<div class="form-group">';
	html += '<label for="dwr-chart-opacity" class="control-label col-xs-12 col-sm-5 col-md-3 col-lg-2">' + _('Opacity') + ': </label>';
	// html += '<div class="col-xs-12 col-sm-7 col-md-3 col-lg-2">';
	html += '<div class="col-xs-12 col-sm-7 col-md-3 col-lg-2">';
	html += '<div class="input-group">';
	html += '<span class="input-group-btn">';
	html += '<button id="dwr-chart-opacity-minus" class="btn btn-default" type="button"><span class="glyphicon glyphicon-minus"></span></button>';
	html += '</span>';
	html += '<input type="text" name="dwr-chart-opacity" id="dwr-chart-opacity" class="form-control" value="' + search.ChartOpacity + '" title="' + _('Opacity') + '">';
	html += '<span class="input-group-btn">';
	html += '<button id="dwr-chart-opacity-plus" class="btn btn-default" type="button"><span class="glyphicon glyphicon-plus"></span></button>';
	html += '</span>';
	// html += '<div class="input-group-btn-vertical">';
	// html += '<button class="btn btn-default" type="button"><i class="glyphicon glyphicon-chevron-up"></i></button>';
	// html += '<button class="btn btn-default" type="button"><i class="glyphicon glyphicon-chevron-down"></i></button>';
	// html += '<button class="btn btn-default" type="button"><i class="glyphicon glyphicon-triangle-top"></i></button>';
	// html += '<button class="btn btn-default" type="button"><i class="glyphicon glyphicon-triangle-top"></i></button>';
	// html += '<button class="btn btn-default" type="button">&#x25B4;</button>';
	// html += '<button class="btn btn-default" type="button">&#x25BE;</button>';
	// html += '<button class="btn btn-default" type="button"><span class="glyphicon glyphicon-caret-up"></span></button>';
	// html += '<button class="btn btn-default" type="button"><span class="glyphicon glyphicon-caret-down"></span></button>';
	// html += '</div>';
	html += '</div>';
	html += '</div>';
	// html += '</div>';
	// html += '</div>';

	html += '<div class="hidden-xs col-sm-6 col-md-6 hidden-lg"></div>'; // filler div
	html += '<div class="checkbox col-xs-12 col-sm-6 col-md-6 col-lg-3">';
	html += '<label><input type="checkbox" value="">' + _('Enable click on chart') + '</label>';
	html += '</div>';

	html += '</div>'; //row

	html += '<hr>';
	html += '<div class="text-center">';
	html += '<button id="dwr-chart-config-ok" type="button" class="btn btn-primary"> <span class="glyphicon glyphicon-ok"></span> ' + _('OK') + ' </button>';
	html += '</div>';
	html += '</form>';
	html += '</div>'; // panel-body
	html += '</div>'; // panel

	// Events
	$(window).load(function() {
		chartConfRepopulate();
		$('#dwr-chart-config-ok').click(function() {
			chartValidateOpts();
			window.location.href = 'statistics.html?' + BuildSearchString();
			return(false);
		});
		$('#dwr-chart-form select').change(chartUpdateOpts);
		$('#dwr-chart-opacity-minus').click(function() {
			$('#dwr-chart-opacity').val(Math.max(parseInt($('#dwr-chart-opacity').val(), 10) - 1, 0));
		});
		$('#dwr-chart-opacity-plus').click(function() {
			$('#dwr-chart-opacity').val(Math.min(parseInt($('#dwr-chart-opacity').val(), 10) + 1, 100));
		});
	});

	document.write(html);
}

function chartUpdateOpts()
{
	chartValidateOpts();
	chartConfRepopulate();
	return(false);
}

function chartValidateOpts()
{
	var newsearch = {};
	newsearch.ChartTable = $('#dwr-chart-table').val();
	newsearch.ChartType = $('#dwr-chart-type').val();
	newsearch.ChartDataW = $('#dwr-chart-dataw').val();
	newsearch.ChartDataX = $('#dwr-chart-datax').val();
	newsearch.ChartDataY = $('#dwr-chart-datay').val();
	newsearch.ChartDataZ = $('#dwr-chart-dataz').val();
	newsearch.ChartFunctionX = $('#dwr-chart-funcx').val();
	newsearch.ChartFunctionY = $('#dwr-chart-funcy').val();
	newsearch.ChartFunctionZ = $('#dwr-chart-funcz').val();
	newsearch.ChartFilter1 = $('#dwr-chart-filter1').val();
	newsearch.ChartFilter2 = $('#dwr-chart-filter2').val();
	newsearch.ChartFilter3 = $('#dwr-chart-filter3').val();
	newsearch.ChartFilter1Min = $('#dwr-chart-filter1min').val();
	newsearch.ChartFilter2Min = $('#dwr-chart-filter2min').val();
	newsearch.ChartFilter3Min = $('#dwr-chart-filter3min').val();
	newsearch.ChartFilter1Max = $('#dwr-chart-filter1max').val();
	newsearch.ChartFilter2Max = $('#dwr-chart-filter2max').val();
	newsearch.ChartFilter3Max = $('#dwr-chart-filter3max').val();
	newsearch.ChartOpacity = $('#dwr-chart-opacity').val();
	newsearch.ChartBackground = $('#dwr-chart-background').val();

	// Reset slectors when changing the table
	if (newsearch.ChartTable != search.ChartTable)
	{
		newsearch.ChartDataW = EXTRACTOR_DISABLED;
		newsearch.ChartDataX = EXTRACTOR_DISABLED;
		newsearch.ChartDataY = EXTRACTOR_DISABLED;
		newsearch.ChartDataZ = EXTRACTOR_DISABLED;
		search.ChartFilter1 = EXTRACTOR_DISABLED;
		search.ChartFilter2 = EXTRACTOR_DISABLED;
		search.ChartFilter3 = EXTRACTOR_DISABLED;
	}
	search = $.extend(search, newsearch);
	// Enable only the selector  allowed by the type of chart
	if (!STATISTICS_CHART_TYPES[search.ChartType].enabled.w) search.ChartDataW = EXTRACTOR_DISABLED;
	if (!STATISTICS_CHART_TYPES[search.ChartType].enabled.y) search.ChartDataY = EXTRACTOR_DISABLED;
	if (!STATISTICS_CHART_TYPES[search.ChartType].enabled.z) search.ChartDataZ = EXTRACTOR_DISABLED;
	// Disable function for disabled extractors
	if (search.ChartDataX == EXTRACTOR_DISABLED) search.ChartFunctionX = FUNCTION_NONE;
	if (search.ChartDataY == EXTRACTOR_DISABLED) search.ChartFunctionY = FUNCTION_NONE;
	if (search.ChartDataZ == EXTRACTOR_DISABLED) search.ChartFunctionZ = FUNCTION_NONE;
	// Disable filter N+1 if filter N not used
	if (search.ChartFilter1 == EXTRACTOR_DISABLED) search.ChartFilter2 = EXTRACTOR_DISABLED;
	if (search.ChartFilter2 == EXTRACTOR_DISABLED) search.ChartFilter3 = EXTRACTOR_DISABLED;
}

function chartConfRepopulate()
{
	var html = '';
	for (var i = 0; i < STATISTICS_DATA.length; i++)
	{
		html += '<option value="' + i + '"' + ((search.ChartTable == i) ? ' selected' : '') + '>' + STATISTICS_DATA[i].name + '</option>';
	}
	$('#dwr-chart-table').html(html);
	var html = '';
	for (var i = 0; i < STATISTICS_CHART_TYPES.length; i++)
	{
		html += '<option value="' + i + '"' + ((search.ChartType == i) ? ' selected' : '') + '>' + STATISTICS_CHART_TYPES[i].name + '</option>';
	}
	$('#dwr-chart-type').html(html);
	var html = '';
	for (var i = 0; i < CHART_BACKGROUND_NAMES.length; i++)
	{
		html += '<option value="' + i + '"' + ((search.ChartBackground == i) ? ' selected' : '') + '>' + CHART_BACKGROUND_NAMES[i] + '</option>';
	}
	$('#dwr-chart-background').html(html);
	$('#dwr-chart-opacity').val("" + search.ChartOpacity);
	var enabled = STATISTICS_CHART_TYPES[search.ChartType].enabled;
	var needed = STATISTICS_CHART_TYPES[search.ChartType].needed;
	$('#dwr-chart-dataw').html(
		chartConfPopulateData(search.ChartDataW, enabled.w, needed.w, true)
	);
	$('#dwr-chart-datax').html(
		chartConfPopulateData(search.ChartDataX, enabled.x, needed.x)
	);
	$('#dwr-chart-datay').html(
		chartConfPopulateData(search.ChartDataY, enabled.y, needed.y)
	);
	$('#dwr-chart-dataz').html(
		chartConfPopulateData(search.ChartDataZ, enabled.z, needed.z)
	);
	$('#dwr-chart-funcx').html(
		chartConfPopulateFunc(search.ChartFunctionX, search.ChartDataX)
	);
	$('#dwr-chart-funcy').html(
		chartConfPopulateFunc(search.ChartFunctionY, search.ChartDataY)
	);
	$('#dwr-chart-funcz').html(
		chartConfPopulateFunc(search.ChartFunctionZ, search.ChartDataZ)
	);
	// Disable select inputs with only one option
	$('#dwr-chart-form select').each(function() {
		var id = $(this).attr('id');
		var hide = ($(this).find('option').length <= 1);
		if (id.indexOf('dwr-chart-func') == 0 && $(this).find('option[value="' + FUNCTION_NONE + '"]').length == 0) hide = false
		if (id.indexOf('dwr-chart-filter') == 0) hide = false
		if (hide)
		{
			$(this).parent().hide();
			$('#' + id + '-hr').hide();
			$('#' + id + '-lbl').hide();
		}
		else
		{
			$(this).parent().show();
			$('#' + id + '-hr').show();
			$('#' + id + '-lbl').show();
		}
	});
	// Filters
	$('#dwr-chart-filter1').html(chartConfPopulateData(search.ChartFilter1, true));
	for (var i = 1; i <= STATISTICS_NB_FILTERS; i += 1)
	{
		// Populate select
		$('#dwr-chart-filter' + (i + 1)).html(chartConfPopulateData(search['ChartFilter' + (i + 1)], search['ChartFilter' + i] != EXTRACTOR_DISABLED));
		// Set text inputs values
		$('#dwr-chart-filter' + i + 'min').val(search['ChartFilter' + i + 'Min']);
		$('#dwr-chart-filter' + i + 'max').val(search['ChartFilter' + i + 'Max']);
		// Disable unused filters
		if (search['ChartFilter' + i] == EXTRACTOR_DISABLED)
		{
			$('#dwr-chart-filter' + (i + 1)).parent().hide();
			$('#dwr-chart-filter' + (i + 1) + '-lbl').hide();
		}
		else
		{
			$('#dwr-chart-filter' + (i + 1)).parent().show();
			$('#dwr-chart-filter' + (i + 1) + '-lbl').show();
		}
		// Disable min/max for unused filters
		if (search['ChartFilter' + i] == EXTRACTOR_DISABLED)
		{
			$('#dwr-chart-filter' + i + 'min').hide();
			$('#dwr-chart-filter' + i + 'max').hide();
			$('#dwr-chart-filter' + i + 'min-lbl').hide();
			$('#dwr-chart-filter' + i + 'max-lbl').hide();
		}
		else
		{
			$('#dwr-chart-filter' + i + 'min').show();
			$('#dwr-chart-filter' + i + 'max').show();
			$('#dwr-chart-filter' + i + 'min-lbl').show();
			$('#dwr-chart-filter' + i + 'max-lbl').show();
		}
	}
	// Alerts
	// if (search.ChartDataZ != EXTRACTOR_DISABLED &&
		// !STATISTICS_FUNCTIONS[search.ChartFunctionZ].numeric &&
		// !STATISTICS_DATA[search.ChartTable].extractors[search.ChartDataZ].numeric)
	// {
		// $("#dwr-chart-dataz-alert").removeClass('hidden');
	// }
	// else
	// {
		// $("#dwr-chart-dataz-alert").addClass('hidden');
	// }
}

function chartConfPopulateData(extractor, enabled, needed, no_numeric)
{
	if (typeof(no_numeric) == 'undefined') no_numeric = false;
	var html = '';
	if (!needed)
	{
	html += '<option value="' + EXTRACTOR_DISABLED + '"' + ((extractor == EXTRACTOR_DISABLED) ? ' selected' : '') + '>' + _('None') + '</option>';
	}
	if (enabled)
	{
		for (var i = 0; i < STATISTICS_DATA[search.ChartTable].extractors.length; i++)
		{
			if (no_numeric && STATISTICS_DATA[search.ChartTable].extractors[i].numeric) continue;
			html += '<option value="' + i + '"' + ((extractor == i) ? ' selected' : '') + '>' + STATISTICS_DATA[search.ChartTable].extractors[i].name + '</option>';
		}
	}
	return(html);
}

function chartConfPopulateFunc(func, extractor)
{
	var html = '';
	html += '<option value="' + FUNCTION_NONE + '"' + ((func == FUNCTION_NONE) ? ' selected' : '') + '>' + _('None') + '</option>';
	if (extractor == EXTRACTOR_DISABLED) return(html);
	for (var i = FUNCTION_NONE + 1; i < STATISTICS_FUNCTIONS.length; i++)
	{
		if (STATISTICS_FUNCTIONS[i].needs_numeric && !STATISTICS_DATA[search.ChartTable].extractors[extractor].numeric) continue;
		html += '<option value="' + i + '"' + ((func == i) ? ' selected' : '') + '>' + STATISTICS_FUNCTIONS[i].name + '</option>';
	}
	return(html);
}


//=================================================================
//====================================================== Links page
//=================================================================

function printStatisticsLinks()
{
	// Get indexes in table of selected point
	ParseSearchString();
	getStatisticsData();
	var xEnabled = true;
	var yEnabled = STATISTICS_CHART_TYPES[search.ChartType].enabled.y && search.ChartDataY != EXTRACTOR_DISABLED;
	var zEnabled = STATISTICS_CHART_TYPES[search.ChartType].enabled.z && search.ChartDataZ != EXTRACTOR_DISABLED;
	var wEnabled = STATISTICS_CHART_TYPES[search.ChartType].enabled.w && search.ChartDataW != EXTRACTOR_DISABLED;
	var indexes = [];
	for (var iw = 0; iw < D.series.length; iw += 1)
	{
		if (wEnabled && "" + D.series[iw].w != search.ChartValW + "") continue;
		for (var i = 0; i < D.series[iw].points.length; i += 1)
		{
			p = D.series[iw].points[i];
			vals = {};
			$.each(['x', 'y', 'z'], function(j, v) {
				var val = p[v];
				var val_str = p[v + '_str'];
				if (turboThresholdOverflow)
				{
					val_str = D.strings[v][p[j]];
				}
				vals[v] = (typeof(val_str) == 'undefined') ? val : val_str;
			});
			if (xEnabled && "" + vals.x != search.ChartValX + "") continue;
			if (yEnabled && "" + vals.y != search.ChartValY + "") continue;
			if (zEnabled && "" + vals.z != search.ChartValZ + "") continue;
			$.merge(indexes, p.indexes);
		}
	}
	// Print data index
	if (search.ChartTable == TABLE_I) document.write(htmlPersonsIndex(indexes));
	if (search.ChartTable == TABLE_F) document.write(htmlFamiliesIndex(indexes));
}


//=================================================================
//======================================================== Examples
//=================================================================

STATISTICS_EXAMPLE_CHARTS = [
	{
		name: _('Gender'),
		opts: {
			ChartTable: TABLE_I,
			ChartType: CHART_TYPE_PIE,
			ChartDataW: EXTRACTOR_DISABLED,
			ChartDataX: EXTRACTOR_I_GENDER,
			ChartDataY: EXTRACTOR_DISABLED,
			ChartDataZ: EXTRACTOR_DISABLED,
			ChartFunctionX: FUNCTION_COUNT,
			ChartFunctionY: FUNCTION_NONE,
			ChartFunctionZ: FUNCTION_NONE,
			ChartOpacity: 100,
			ChartBackground: CHART_BACKGROUND_GENDER
		}
	},
	{
		name: _('Surnames'),
		opts: {
			ChartTable: TABLE_I,
			ChartType: CHART_TYPE_DONUT,
			ChartDataW: EXTRACTOR_DISABLED,
			ChartDataX: EXTRACTOR_I_SURNAME,
			ChartDataY: EXTRACTOR_DISABLED,
			ChartDataZ: EXTRACTOR_DISABLED,
			ChartFunctionX: FUNCTION_COUNT,
			ChartFunctionY: FUNCTION_NONE,
			ChartFunctionZ: FUNCTION_NONE,
			ChartOpacity: 100,
			ChartBackground: CHART_BACKGROUND_GRADIENT
		}
	},
	{
		name: _('Age at marriage'),
		opts: {
			ChartTable: TABLE_I,
			ChartType: CHART_TYPE_SCATTER,
			ChartDataW: EXTRACTOR_I_GENDER,
			ChartDataX: EXTRACTOR_I_BIRTH_DATE,
			ChartDataY: EXTRACTOR_I_AGE_MARR,
			ChartDataZ: EXTRACTOR_DISABLED,
			ChartFunctionX: FUNCTION_NONE,
			ChartFunctionY: FUNCTION_NONE,
			ChartFunctionZ: FUNCTION_NONE,
			ChartOpacity: 80,
			ChartBackground: CHART_BACKGROUND_GENDER
		}
	},
	{
		name: _('Number of children per family'),
		opts: {
			ChartTable: TABLE_F,
			ChartType: CHART_TYPE_SCATTER,
			ChartDataW: EXTRACTOR_DISABLED,
			ChartDataX: EXTRACTOR_F_MARR_DATE,
			ChartDataY: EXTRACTOR_F_NB_CHILD,
			ChartDataZ: EXTRACTOR_DISABLED,
			ChartFunctionX: FUNCTION_NONE,
			ChartFunctionY: FUNCTION_NONE,
			ChartFunctionZ: FUNCTION_NONE,
			ChartOpacity: 80,
			ChartBackground: CHART_BACKGROUND_SINGLE
		}
	},
	{
		name: _('Age at death and number of deaths depending on place'),
		opts: {
			ChartTable: TABLE_I,
			ChartType: CHART_TYPE_BUBBLE,
			ChartDataW: EXTRACTOR_I_GENDER,
			ChartDataX: EXTRACTOR_I_DEATH_PLACE,
			ChartDataY: EXTRACTOR_I_AGE_DEATH,
			ChartDataZ: EXTRACTOR_I_DEATH_PLACE,
			ChartFunctionX: FUNCTION_NONE,
			ChartFunctionY: FUNCTION_AVERAGE,
			ChartFunctionZ: FUNCTION_COUNT,
			ChartOpacity: 20,
			ChartBackground: CHART_BACKGROUND_SINGLE
		}
	},
	{
		name: _('Number of children depending on parents age at marriage'),
		opts: {
			ChartTable: TABLE_F,
			ChartType: CHART_TYPE_BUBBLE,
			ChartDataW: EXTRACTOR_DISABLED,
			ChartDataX: EXTRACTOR_F_SPOU_AGE_MARR,
			ChartDataY: EXTRACTOR_F_NB_CHILD,
			ChartDataZ: EXTRACTOR_F_NB_CHILD,
			ChartFunctionX: FUNCTION_NONE,
			ChartFunctionY: FUNCTION_NONE,
			ChartFunctionZ: FUNCTION_COUNT,
			ChartOpacity: 20,
			ChartBackground: CHART_BACKGROUND_SINGLE
			// ,
			// ChartFilter1: EXTRACTOR_F_MARR_DATE,
			// ChartFilter1Min: "1700",
			// ChartFilter1Max: "1950",
			// ChartFilter2: EXTRACTOR_F_SPOU1_AGE_MARR,
			// ChartFilter2Min: "0",
			// ChartFilter2Max: "200"
		}
	}
];

function chartConfExample(i)
{
	// Update search string with example parameters
	search = $.extend(search, STATISTICS_EXAMPLE_CHARTS[i].opts);
	chartConfRepopulate();
}

function chartExampleLinks()
{
	var links = [];
	for (var i = 0; i < STATISTICS_EXAMPLE_CHARTS.length; i += 1)
	{
		// Save the search string parameters (deep copy)
		var searchOld = $.extend({}, search);
		// Update search string with example parameters
		search = $.extend(search, STATISTICS_EXAMPLE_CHARTS[i].opts);
		// Build link
		links.push(
			// '<div class="col-xs-12 col-sm-6 col-lg-4"><li>' +
			'<li>' +
			STATISTICS_EXAMPLE_CHARTS[i].name +
			' <a href="statistics.html?' + BuildSearchString() + '"><span class="badge">' + _('See chart') + '</span></a>' +
			' <a href="javascript:chartConfExample(' + i + ');"><span class="badge">' + _('Configure') + '</span></a>' +
			'</li>');
			// '</li></div>');
		// Restore search string
		search = searchOld;
	}
	// html += chartExampleLinks().join('</li><li>');
	// html += '<ul><li></li></ul>';
	return(printTitle(5, [{
		title: _('Examples'),
		text: '<ul>' + links.join('') + '</ul>'
	}], true, false));
	// return(
		// '<p>' + _('Chart examples') + ':' +
		// '<ul><div class="row">' + links.join('') + '</div></ul>');
}
