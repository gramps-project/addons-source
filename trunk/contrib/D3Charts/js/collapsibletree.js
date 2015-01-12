var m = [20, 50, 20, 100],
 w = 4000 - m[1] - m[3],
 h = 4000 - m[0] - m[2],
 i = 0,
 root,
 strAdjust = 25,
 rectHeight = 15,
 rectWidths = [0];

var tree = d3.layout.tree()
 .size([h, w]);

var diagonal = d3.svg.diagonal().projection(function (d) {
  return [d.y, d.x];
 });

var vis = d3.select("#chart").append("svg:svg")
 .attr("width", w + m[1] + m[3])
 .attr("height", h + m[0] + m[2])
 .append("svg:g")
 .attr("transform", "translate(" + m[3] + "," + m[0] + ")");

d3.json("json/collapsibletree.json", function(json) {
 var testString = document.getElementById("testString");

 root = json;
 root.x0 = h / 2;
 root.y0 = 0;

 function toggleAll(d) {
  if (d.children) {
   d.children.forEach(toggleAll);
   toggle(d);
  }
 }

 if (root.children) {
  // Initialize the display to show a few nodes.
  root.children.forEach(toggleAll);

  if (root.children[0]) {
   toggle(root.children[0]);

   if (root.children[0].children) {
    if (root.children[0].children[0]) {
     toggle(root.children[0].children[0]);

     if (root.children[0].children[0].children) {
      if (root.children[0].children[0].children[0]) {
       toggle(root.children[0].children[0].children[0]);
      }
      if (root.children[0].children[0].children[1]) {
       toggle(root.children[0].children[0].children[1]);
      }
     }
    }
    if (root.children[0].children[1]) {
     toggle(root.children[0].children[1]);

     if (root.children[0].children[1].children) {
      if (root.children[0].children[1].children[0]) {
       toggle(root.children[0].children[1].children[0]);
      }
      if (root.children[0].children[1].children[1]) {
       toggle(root.children[0].children[1].children[1]);
      }
     }
    }
   }
  }

  if (root.children[1]) {
   toggle(root.children[1]);

   if (root.children[1].children) {
    if (root.children[1].children[0]) {
     toggle(root.children[1].children[0]);
     if (root.children[1].children[0].children) {
      if (root.children[1].children[0].children[0]) {
       toggle(root.children[1].children[0].children[0]);
      }
      if (root.children[1].children[0].children[1]) {
       toggle(root.children[1].children[0].children[1]);
      }
     }
    }

    if (root.children[1].children[1]) {
     toggle(root.children[1].children[1]);

     if (root.children[1].children[1].children) {
      if (root.children[1].children[1].children[0]) {
       toggle(root.children[1].children[1].children[0]);
      }
      if (root.children[1].children[1].children[1]) {
       toggle(root.children[1].children[1].children[1]);
      }
     }
    }
   }
  }
 }

 var calcRectWidths = function (level, n) {
  testString.innerHTML = n.name;
  strHeight = (testString.clientHeight + strAdjust);
  strWidth = (testString.clientWidth + strAdjust);

  if (rectWidths[level] < strWidth) {
   rectWidths[level] = strWidth;
  }

  if (n.children && n.children.length > 0) {
   if (rectWidths.length <= (level + 1)) {
    rectWidths.push(0);
   }
   n.children.forEach (function (d) {
     calcRectWidths(level+1, d);
   });
  }
  if (n._children && n._children.length > 0) {
   if (rectWidths.length <= (level + 1)) {
    rectWidths.push(0);
   }
   n._children.forEach (function (d) {
     calcRectWidths(level+1, d);
   });
  }
 };
 calcRectWidths(0, root);

 update(root);
});

function update(source) {
 var strHeight = 0,
  strWidth = 0,
  duration = d3.event && d3.event.altKey ? 1000 : 500,
  totalPersons = 0,
  newHeight = 0,
  newWidth = 0,
  heightItems = 0,
  totalPersons = 0,
  levelWidth = [1];

 var calcDepthVisible = function (level, n) {
  // Dynamically determien height/width of canvas based on
  // Depth currently displayed
  totalPersons = totalPersons + 1;
  if (n.children && n.children.length > 0) {
   if (levelWidth.length <= (level + 1)) {
    levelWidth.push(0);
   }
   levelWidth[level+1] += n.children.length;

   n.children.forEach( function (d) {
    calcDepthVisible(level+1, d);
   });
  }
 };

 calcDepthVisible(0, root);
 switch (levelWidth.length) {
  case 0 :
   heightItems = 3;
   break;
  case 1 :
   heightItems = 3;
   break;
  case 2:
   heightItems = 3;
   break;
  case 3:
   heightItems = 7;
   break;
  case 4:
   heightItems = 15;
   break;
  case 5:
   heightItems = 25;
   break;
  default:
   heightItems = levelWidth.length * 5;
   break;
 }

 if (totalPersons < heightItems) {
  heightItems = totalPersons;
 }

 newWidth = levelWidth.length * 150;

 if (newWidth > ($(window).width()-170)) {
  newWidth = $(window).width()-170;
 }

 newHeight = heightItems * 50;
 if (newHeight < 180) {
  newHeight = 180;
 }
 tree.size([newHeight, newWidth]);

 // Compute the new tree layout.
 var nodes = tree.nodes(root).reverse();

 // Update the nodes
 var node = vis.selectAll("g.node").data(nodes, function(d) {
      return d.id || (d.id = ++i);
  });

 // Enter any new nodes at the parents previous position.
 var nodeEnter = node.enter().append("svg:g")
  .attr("class", "node")
  .attr("transform", function(d) {
    return "translate(" + source.y0 + "," + source.x0 + ")";
   })
  .on("click", function(d) { toggle(d); update(d); });

 nodeEnter.append("svg:rect")
  .attr("width", function(d) {
    return rectWidths[d.depth];
   })
  .attr("height", rectHeight*2)
  .attr("x", function(d) {
    return (-rectWidths[d.depth]/2);
   })
  .attr("y", -rectHeight)
  .style("fill", function(d) {
    if (d.gender == "male") {
     return d._children ? "#B4C4D9" : "#ffffff";
    } else if (d.gender == "female") {
     return d._children ? "#F0D5D7" : "#ffffff";
    } else {
     return d._children ? "lightsteelblue" : "#fff";
    }
   });

 nodeEnter.append("svg:image")
  .attr("xlink:href", function (d) {
    return d.gender == "male" ?
     "images/male.png" : "images/female.png";
   })
  .attr("height", 12)
  .attr("width", 12)
  .attr("y", -rectHeight + 4)
  .attr("x", function(d) {
    return ((-rectWidths[d.depth]/2)+2);
   });

 nodeEnter.append("svg:text")
  .attr("x", function(d) { return +5; })
  .attr("dy", "-.12em")
  .attr("text-anchor", "middle")
  .call(wrap)
  .style("fill-opacity", 1e-6);

 // Transition nodes to their new position.
 var nodeUpdate = node.transition()
  .duration(duration)
  .attr("transform", function(d) {
    return "translate(" + d.y + "," + d.x + ")";
   });

 nodeUpdate.select("rect")
  .attr("width", function(d) {
    return rectWidths[d.depth];
   })
  .attr("height", rectHeight*2)
  .attr("x", function(d) {
    return (-rectWidths[d.depth]/2);
   })
  .attr("y", -rectHeight)
  .style("fill", function(d) {
    if (d.gender == "male") {
     return d._children ? "#B4C4D9" : "#ffffff";
    } else if (d.gender == "female") {
     return d._children ? "#F0D5D7" : "#ffffff";
    } else {
     return d._children ? "lightsteelblue" : "#fff";
    }
   });

 nodeUpdate.select("text")
  .style("fill-opacity", 1);

 // Transition exiting nodes to the parents new position.
 var nodeExit = node.exit().transition()
  .duration(duration)
  .attr("transform", function(d) {
    return "translate(" + source.y + "," + source.x + ")";
   })
  .remove();

 nodeExit.select("rect")
  .attr("width", function(d) {
    return rectWidths[d.depth];
   })
  .attr("height", rectHeight*2)
  .attr("x", function(d) {
    return (-rectWidths[d.depth]/2);
   })
  .attr("y", -rectHeight);

 nodeExit.select("text")
  .style("fill-opacity", 1e-6);

 // Update the links
 var link = vis.selectAll("path.link")
  .data(tree.links(nodes), function(d) { return d.target.id; });

 // Enter any new links at the parents previous position.
 link.enter().insert("svg:path", "g")
  .attr("class", "link")
  .attr("d", function(d) {
 var o = {x: source.x0, y: source.y0};
    return diagonal({source: o, target: o});
   })
  .transition()
  .duration(duration)
  .attr("d", diagonal);

 // Transition links to their new position.
 link.transition()
  .duration(duration)
  .attr("d", diagonal);

 // Transition exiting nodes to the parents new position.
 link.exit().transition()
  .duration(duration)
  .attr("d", function(d) {
    var o = {x: source.x, y: source.y};
    return diagonal({source: o, target: o});
   })
  .remove();

 // Stash the old positions for transition.
 nodes.forEach(function(d) {
  d.x0 = d.x;
  d.y0 = d.y;
 });
}

function wrap(text) {
 text.each(function () {
  var txt = d3.select(this),
   line1 = txt[0][0].__data__.name,
   line2 = "(" + txt[0][0].__data__.born + " - " + txt[0][0].__data__.died + ")",
   y = text.attr("y"),
   x = text.attr("x"),
   dy = parseFloat(text.attr("dy")),
   tspan = txt.text(null).append("tspan").attr("x", x).attr("y", y).attr("dy", dy + "em");

   tspan.text(line1);
   tspan = txt.append("tspan").attr("x", x).attr("y", y).attr("dy", 1*1.1+dy+"em").text(line2);
  
 });
}

// Toggle children.
function toggle(d) {
 if (d.children) {
  d._children = d.children;
  d.children = null;
 } else {
  d.children = d._children;
  d._children = null;
 }
}
