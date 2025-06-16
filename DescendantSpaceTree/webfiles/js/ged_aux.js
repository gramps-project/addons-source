/* wire up autocomplete */
var ged_autoComplete = new autoComplete({
    selector: 'input[name="q"]',
    minChars: 3,
    source: function(term, suggest) {
        term = term.toLowerCase();
        var matches = [];
        for (i = 0; i < ged_names.length; i++) {
            if (~ged_names[i].toLowerCase().indexOf(term)) matches.push(ged_names[i]);
        }
        suggest(matches);
    },
    renderItem: function (item, search){
        //item = item.replace(/@.*@$/, '');
        search = search.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        var re = new RegExp("(" + search.split(' ').join('|') + ")", "gi");
        return '<div class="autocomplete-suggestion" data-val="' + item + '">' + item.replace(re, "<b>$1</b>") + '</div>';
    },
    onSelect: function(event, term, item) {
        id = term.substr(term.indexOf("@"));
        if (id.match(/^@.*@$/)) {
            nav_goto(id);
            var elems = document.querySelectorAll('input[name="q"]');
            if (elems.length == 1) {
                elems[0].value = "";
            }
            // clear the search input
            this.selector.value = "";
        } else {
            console.log(" could not extract id from: " + item);
        }
    }
});

/* nav*/
function nav_goto(id) {
    st.onClick(id,
         {Move:{ offsetX: st.canvas.translateOffsetX, offsetY: st.canvas.translateOffsetY}});
}

/* set the chartname */
var chartname = document.getElementById('chartname');
chartname.innerHTML = " ___DESCENDANTS_OF___ " + ged_name;

/* destroy and rebuild infovis canvas on browser resize or fullscreen */
function doResize() {
    document.getElementById("infovis").textContent = '';
    init();
}
window.onresize = doResize;


