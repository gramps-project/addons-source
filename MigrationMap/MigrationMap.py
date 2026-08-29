#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Brian Caudill
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
Migration Map tool.

Collects every dated event whose place has coordinates, then writes a
self-contained HTML page with an animated Leaflet map: press play and each
person's moves draw themselves across the map as the years advance, with a
pulsing frontier on the moves happening "now" and a running readout of who is
moving where. Pairs with the Geocode Places tool, which fills in the
coordinates this relies on.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import os
import html
import json
import pathlib
import tempfile
import webbrowser

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.utils.place import conv_lat_lon
from gramps.gen.plug.menu import BooleanOption, StringOption
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# HTML template (Leaflet; data spliced in at the marked tokens)
#
# -------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
 integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
<style>
 html,body{margin:0;height:100%;font-family:-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:#10130f}
 #map{position:absolute;top:0;left:0;right:0;bottom:128px;background:#10130f}
 .title{position:absolute;top:12px;left:50px;z-index:1000;background:rgba(20,24,18,.93);color:#eef3e8;
   padding:9px 15px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.35);max-width:340px}
 .title h1{margin:0 0 3px;font-size:1rem}
 .title p{margin:0;font-size:.72rem;opacity:.9;line-height:1.4}
 .readout{position:absolute;top:12px;right:12px;z-index:1000;background:rgba(20,24,18,.93);color:#eef3e8;
   padding:9px 15px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.35);min-width:230px;text-align:right}
 .readout .yr{font-size:1.6rem;font-weight:800;line-height:1.05}
 .readout .era{font-size:.72rem;opacity:.85;margin-top:2px}
 .readout .ev{font-size:.78rem;margin-top:7px;border-top:1px solid rgba(238,243,232,.25);
   padding-top:6px;text-align:left;line-height:1.4;min-height:48px}
 .readout .ev b{color:#ffd98a}
 .dock{position:absolute;left:0;right:0;bottom:0;height:128px;z-index:1000;
   background:linear-gradient(180deg,#1a1f15 0%,#10130f 100%);color:#eef3e8;
   box-shadow:0 -2px 12px rgba(0,0,0,.4);padding:10px 26px 14px;box-sizing:border-box}
 .controls{display:flex;align-items:center;gap:10px;margin-bottom:4px}
 .controls button{font-weight:700;font-size:.82rem;cursor:pointer;background:#eef3e8;color:#2a2420;
   border:none;border-radius:8px;padding:7px 13px}
 .controls button:hover{background:#fff}
 .controls .hint{font-size:.71rem;opacity:.7;margin-left:auto}
 .track{position:relative;height:74px;padding:0 11px}
 .ticks{position:absolute;left:11px;right:11px;top:0;height:34px;pointer-events:none}
 .tick{position:absolute;transform:translateX(-50%);text-align:center}
 .tick .bar{width:2px;height:8px;background:#a7b88f;margin:0 auto;opacity:.8}
 .tick .lbl{font-size:.63rem;color:#dce8cf}
 input[type=range].scrub{-webkit-appearance:none;appearance:none;width:100%;height:8px;border-radius:6px;
   background:#3a4430;outline:none;margin:40px 0 0}
 input[type=range].scrub::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:22px;height:22px;
   border-radius:50%;background:#ffd98a;border:3px solid #1a1f15;cursor:grab;box-shadow:0 1px 6px rgba(0,0,0,.5)}
 input[type=range].scrub::-moz-range-thumb{width:22px;height:22px;border-radius:50%;background:#ffd98a;border:3px solid #1a1f15;cursor:grab}
 .leaflet-popup-content{font-size:.86rem;line-height:1.45}
 .frontier{width:14px;height:14px;border-radius:50%;background:#ffd98a;border:2px solid #1a1f15;
   animation:pulse 1.5s infinite}
 @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(255,217,138,.7)}70%{box-shadow:0 0 0 15px rgba(255,217,138,0)}100%{box-shadow:0 0 0 0 rgba(255,217,138,0)}}
 .legend{background:rgba(255,255,255,.95);padding:7px 10px;border-radius:9px;font-size:.72rem;line-height:1.5;color:#2a2420;max-width:220px}
 .legend i{width:16px;height:0;border-top:3px solid #000;display:inline-block;margin-right:6px;vertical-align:4px}
</style></head>
<body>
<div class="title">
 <h1>__TITLE__</h1>
 <p>Press <b>&#9654;</b> or drag the gold handle to watch each person's moves
 <b>draw themselves across the years</b>. Pulsing dots are moves happening that year.</p>
</div>
<div class="readout">
 <div class="yr" id="yr">—</div>
 <div class="era" id="era"></div>
 <div class="ev" id="ev">Drag the timeline or press play…</div>
</div>
<div id="map"></div>
<div class="dock">
 <div class="controls">
  <button id="play">▶ Play</button>
  <button id="reset">⏮ Restart</button>
  <span class="hint">Drag the gold handle to scrub through time.</span>
 </div>
 <div class="track"><div class="ticks" id="ticks"></div>
  <input type="range" class="scrub" id="scrub" min="0" max="1000" step="1" value="0"></div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
 integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
var EVENTS = __DATA__;
var DRAWPATHS = __PATHS__;
var PALETTE = ["#e6550d","#3182bd","#31a354","#756bb1","#e377c2","#17becf",
               "#bcbd22","#8c564b","#d62728","#1f9e89"];
var OTHER = "#8a8a8a";

// Colour by surname: the most common surnames get distinct colours.
var counts = {};
EVENTS.forEach(function(e){ counts[e.s] = (counts[e.s]||0)+1; });
var ranked = Object.keys(counts).sort(function(a,b){ return counts[b]-counts[a]; });
var colorOf = {};
ranked.forEach(function(s,i){ colorOf[s] = i < PALETTE.length ? PALETTE[i] : OTHER; });

var map = L.map('map', {worldCopyJump:true}).setView([39,-98], 4);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
   {maxZoom:19, attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
if (EVENTS.length) map.fitBounds(EVENTS.map(function(e){return [e.lat,e.lon];}), {padding:[35,35]});

// group into per-person tracks, sorted by year
var tracks = {};
EVENTS.forEach(function(e){
   if(!tracks[e.p]) tracks[e.p] = {name:e.name, s:e.s, pts:[]};
   tracks[e.p].pts.push(e);
});
Object.keys(tracks).forEach(function(k){ tracks[k].pts.sort(function(a,b){return a.year-b.year;}); });

var ys = EVENTS.map(function(e){return e.year;});
var minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
var span = Math.max(1, maxY - minY);

function esc(s){ return s; }  // text already escaped server-side
function popup(e){
   return "<b>"+e.name+"</b><br><span style='color:#777;font-weight:700'>"+e.etype+
          " &middot; "+e.year+"</span><br>"+e.place;
}

// Pre-create one polyline + one marker per event, updated in place each frame.
var layers = {};
Object.keys(tracks).forEach(function(pid){
   var t = tracks[pid], col = colorOf[t.s] || OTHER;
   var line = DRAWPATHS ? L.polyline([], {color:col, weight:2, opacity:.5, lineJoin:'round'}).addTo(map) : null;
   var markers = t.pts.map(function(e){
      return L.circleMarker([e.lat,e.lon],
         {radius:3, color:col, weight:1, fillColor:col, fillOpacity:.6}).bindPopup(popup(e));
   });
   layers[pid] = {t:t, col:col, line:line, markers:markers, vis:[]};
});

function drawnPath(pts, yF){
   if(pts.length < 2 || yF <= pts[0].year) return [];
   var out = [[pts[0].lat, pts[0].lon]];
   for(var i=1;i<pts.length;i++){
      var a=pts[i-1], b=pts[i];
      if(yF >= b.year){ out.push([b.lat,b.lon]); }
      else { var f=(yF-a.year)/Math.max(1,(b.year-a.year));
             out.push([a.lat+(b.lat-a.lat)*f, a.lon+(b.lon-a.lon)*f]); break; }
   }
   return out;
}

var frontier = L.layerGroup().addTo(map);
var yrEl=document.getElementById('yr'), eraEl=document.getElementById('era'),
    evEl=document.getElementById('ev'), scrub=document.getElementById('scrub');
var lastYear = null;

function update(p){
   var yF = minY + p*span;
   var iy = Math.floor(yF + 0.5);
   // paths grow every frame (cheap)
   if(DRAWPATHS){
      Object.keys(layers).forEach(function(pid){
         layers[pid].line.setLatLngs(drawnPath(layers[pid].t.pts, yF));
      });
   }
   scrub.style.background = "linear-gradient(90deg,#d99a1c 0%,#e9b84a "+(p*100)+
      "%,#3a4430 "+(p*100)+"%,#3a4430 100%)";
   if(iy === lastYear) return;   // marker/readout work only on year change
   lastYear = iy;
   yrEl.textContent = iy;
   eraEl.textContent = (Math.floor(iy/10)*10) + "s";
   frontier.clearLayers();
   var moving = [], located = 0;
   Object.keys(layers).forEach(function(pid){
      var L0 = layers[pid];
      L0.t.pts.forEach(function(e,i){
         var on = e.year <= iy;
         var m = L0.markers[i], has = map.hasLayer(m);
         if(on && !has){ m.addTo(map); located++; }
         else if(!on && has){ map.removeLayer(m); }
         else if(on){ located++; }
         if(e.year === iy){
            moving.push(e);
            frontier.addLayer(L.marker([e.lat,e.lon],
               {icon:L.divIcon({className:'',html:"<div class='frontier'></div>",
                iconSize:[14,14], iconAnchor:[7,7]}), zIndexOffset:900}));
         }
      });
   });
   if(moving.length){
      moving.sort(function(a,b){ return a.name<b.name?-1:1; });
      var lines = moving.slice(0,4).map(function(e){
         return "<b>"+e.name+"</b> — "+e.etype+", "+e.place; }).join("<br>");
      if(moving.length>4) lines += "<br>+"+(moving.length-4)+" more";
      evEl.innerHTML = lines;
   } else {
      evEl.innerHTML = "<span style='opacity:.6'>"+located+" people located so far</span>";
   }
}

// decade ticks
var ticks = document.getElementById('ticks');
for(var d = Math.ceil(minY/20)*20; d <= maxY; d += 20){
   var el = document.createElement('div'); el.className='tick';
   el.style.left = ((d-minY)/span*100)+"%";
   el.innerHTML = "<div class='bar'></div><div class='lbl'>"+d+"</div>";
   ticks.appendChild(el);
}

// legend (top surnames)
var lg = L.control({position:'bottomleft'});
lg.onAdd = function(){
   var d = L.DomUtil.create('div','legend');
   var rows = ranked.slice(0, PALETTE.length).map(function(s){
      return "<i style='border-color:"+colorOf[s]+"'></i>"+(s||"(no surname)");
   }).join("<br>");
   d.innerHTML = "<b style='display:block;margin-bottom:3px'>Surnames</b>"+rows;
   return d;
};
lg.addTo(map);

var timer = null, playBtn = document.getElementById('play');
function stop(){ if(timer){clearInterval(timer);timer=null;} playBtn.textContent="▶ Play"; }
function play(){ stop(); if(+scrub.value>=1000) scrub.value=0; playBtn.textContent="⏸ Pause";
   timer=setInterval(function(){ var v=+scrub.value+2;
      if(v>=1000){ scrub.value=1000; update(1); stop(); return; }
      scrub.value=v; update(v/1000); }, 70); }
playBtn.onclick = function(){ timer ? stop() : play(); };
document.getElementById('reset').onclick = function(){ stop(); scrub.value=0; lastYear=null; update(0); };
scrub.addEventListener('input', function(){ stop(); update(+scrub.value/1000); });

update(0);
setTimeout(play, 800);
</script></body></html>
"""


# -------------------------------------------------------------------------
#
# MigrationMapOptions
#
# -------------------------------------------------------------------------
class MigrationMapOptions(MenuToolOptions):
    """
    Options for the Migration Map tool.
    """

    def add_menu_options(self, menu):
        """
        Add the tool options.
        """
        category = _("Options")

        draw_paths = BooleanOption(_("Draw migration paths"), True)
        draw_paths.set_help(
            _("Connect each person's locations in time order with a line that "
              "grows as the animation plays.")
        )
        menu.add_option(category, "draw_paths", draw_paths)

        output = StringOption(_("Output HTML file (blank = temp file)"), "")
        output.set_help(_("Where to write the map; left blank uses a temp file."))
        menu.add_option(category, "output", output)


# -------------------------------------------------------------------------
#
# MigrationMapWindow
#
# -------------------------------------------------------------------------
class MigrationMapWindow(PluginWindows.ToolManagedWindowBatch):
    """
    Tool window that builds and opens the animated migration map.
    """

    def get_title(self):
        """
        Return the tool window title.
        """
        return _("Migration Map")

    def initial_frame(self):
        """
        Return the name of the options frame.
        """
        return _("Options")

    def collect_events(self):
        """
        Return a list of dated, geocoded event dicts for every person.
        """
        events = []
        self.progress.set_pass(
            _("Collecting located events..."), self.db.get_number_of_people()
        )
        for person in self.db.iter_people():
            self.progress.step()
            name = person.get_primary_name().get_name()
            surname = person.get_primary_name().get_surname()
            pid = person.get_gramps_id()
            for eref in person.get_event_ref_list():
                event = self.db.get_event_from_handle(eref.ref)
                if event is None:
                    continue
                handle = event.get_place_handle()
                if not handle:
                    continue
                place = self.db.get_place_from_handle(handle)
                if place is None:
                    continue
                lat = (place.get_latitude() or "").strip()
                lon = (place.get_longitude() or "").strip()
                if not lat or not lon:
                    continue
                dlat, dlon = conv_lat_lon(lat, lon, "D.D8")
                if not dlat or not dlon:
                    continue
                year = event.get_date_object().get_year()
                if not year:
                    continue
                # Escape free-text fields: rendered as HTML in the Leaflet popup.
                events.append(
                    {
                        "p": pid,
                        "name": html.escape(name),
                        "s": html.escape(surname),
                        "year": year,
                        "lat": float(dlat),
                        "lon": float(dlon),
                        "place": html.escape(place_displayer.display(self.db, place)),
                        "etype": html.escape(str(event.get_type())),
                    }
                )
        return events

    def run(self):
        """
        Build the animated map and open it in the browser.
        """
        opts = self.options.handler.options_dict
        events = self.collect_events()

        self.add_results_frame(_("Results"))
        if not events:
            self.results_write(
                _(
                    "No dated events with coordinates were found. Add place "
                    "coordinates first (for example with the Geocode Places "
                    "tool), then run this again.\n"
                )
            )
            return

        title = html.escape(_("Migration Map - %s") % self.db.get_dbname())
        page = (
            HTML.replace("__DATA__", json.dumps(events))
            .replace("__PATHS__", "true" if opts["draw_paths"] else "false")
            .replace("__TITLE__", title)
        )

        output = (opts["output"] or "").strip()
        if not output:
            output = os.path.join(tempfile.gettempdir(), "gramps_migration_map.html")
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(page)

        years = [event["year"] for event in events]
        people = len({event["p"] for event in events})
        self.results_write(
            _("Mapped %(events)d located events for %(people)d people, "
              "%(start)d-%(end)d.\n")
            % {"events": len(events), "people": people,
               "start": min(years), "end": max(years)}
        )
        self.results_write(_("Opening: %s\n") % output)
        webbrowser.open(pathlib.Path(output).as_uri())
