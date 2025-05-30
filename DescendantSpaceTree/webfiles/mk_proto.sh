#!

awk '

  function inline(line, open_tag, close_tag, text) {
     print "<!-- INLINED: " line " -->";
     print open_tag;
     print text;
     print close_tag;
     print "<!-- END INLINED -->";
     print "";
     next;
  }

  function readfile(f) {
     text = ""
     while ((getline line <f) > 0) {
         text = text "\n" line;
     }
     close(f)
     return text "\n";
  }

  BEGIN {
    style_tag    = "<style>";
    style_close  = "</style>";
    script_tag   = "<script language=\"javascript\">";
    script_close = "</script>";
    pico_css     = readfile("./css/pico.classless.css");
    auto_css     = readfile("./css/auto-complete.css");
    auto_js      = readfile("./js/auto-complete.js");
    jit_js       = readfile("./js/jit-yc.js");
    tree_js      = readfile("./js/tree_base.js");
    ged_js       = readfile("./js/ged.js");
    gedaux_js    = readfile("./js/ged_aux.js");
  }

  /^<link.*.\/css\/pico.classless.css.*$/   { inline($0, style_tag, style_close, pico_css) }

  /<link.*.\/css\/auto-complete.css.*/      { inline($0, style_tag, style_close, auto_css) }

  /<script.*.\/js\/auto-complete.min.js.*$/ { inline($0, script_tag, script_close, auto_js) }

  /<script.*.\/js\/jit-yc.js.*$/            { inline($0, script_tag, script_close, jit_js)  }

  /<script.*.\/js\/tree_base.js.*$/         { inline($0, script_tag, script_close, tree_js) }

  /<script.*.\/js\/ged.js.*$/               { inline($0, script_tag, script_close, ged_js) }

  /<script.*.\/js\/ged_aux.js.*$/           { inline($0, script_tag, script_close, gedaux_js) }

  { print; }

' < html/descendant_tree.html
