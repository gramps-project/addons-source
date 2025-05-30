var st, labelType, useGradients, nativeTextSupport, animate;

(function() {
  var ua = navigator.userAgent,
      iStuff = ua.match(/iPhone/i) || ua.match(/iPad/i),
      typeOfCanvas = typeof HTMLCanvasElement,
      nativeCanvasSupport = (typeOfCanvas == 'object' || typeOfCanvas == 'function'),
      textSupport = nativeCanvasSupport 
        && (typeof document.createElement('canvas').getContext('2d').fillText == 'function');
  //I'm setting this based on the fact that ExCanvas provides text support for IE
  //and that as of today iPhone/iPad current text support is lame
  labelType = (!nativeCanvasSupport || (textSupport && !iStuff))? 'Native' : 'HTML';
  nativeTextSupport = labelType == 'Native';
  useGradients = nativeCanvasSupport;
  animate = !(iStuff || !nativeCanvasSupport);
})();

var Log = {
  elem: false,
  write: function(text){
    if (!this.elem) 
      this.elem = document.getElementById('log');
    this.elem.innerHTML = text;
  }
};


function init(){
    //init data
    var json = ged_data;
    
    
    //init Spacetree
    //Create a new ST instance
    st = new $jit.ST({
        //id of viz container element
        injectInto: 'infovis',

        //set duration for the animation
        duration: 400,
        //
        //set animation transition type
        transition: $jit.Trans.Quart.easeInOut,

        //set distance between node and its children
        levelDistance: 40,

        //enable panning
        Navigation: {
          enable:true,
          panning:true
        },

        //set node and edge styles
        //set overridable=true for styling individual
        //nodes or edges
        Node: {
            height: 55,
            width: 130,
            type: 'rectangle',
            color: '#aaa',
            overridable: true
        },
        
        Edge: {
            type: 'bezier',
            overridable: true
        },
        
        onBeforeCompute: function(node){
            Log.write(node.data.info);
        },
        
        onAfterCompute: function(){
        },
        
        //This method is called on DOM label creation.
        //Use this method to add event handlers and styles to
        //your node.
        onCreateLabel: function(label, node){
            label.id = node.id;            
            label.innerHTML = node.name;
            label.onclick = function(){
            	st.onClick(node.id,{Move:{ offsetX: st.canvas.translateOffsetX, offsetY: st.canvas.translateOffsetY}});
            };
            //set label styles
            var style = label.style;
            style.width = 140 + 'px';
            style.height = 34 + 'px';            
            style.cursor = 'pointer';
            style.color = '#333';
            style.fontSize = '0.66em';
            style.textAlign= 'left';
            style.paddingTop = '1px';
            style.paddingLeft = '3px';
            style.marginTop = '1px';
            style.lineHeight =  '1.1em';
        },
        
        //This method is called right before plotting
        //a node. It's useful for changing an individual node
        //style properties before plotting it.
        //The data properties prefixed with a dollar
        //sign will override the global node style properties.
        onBeforePlotNode: function(node){
            //add some color to the nodes in the path between the
            //root node and the selected node.
            if (node.selected) {
                node.data.$color = "#ff7";
            }
            else {
                delete node.data.$color;
                //if the node belongs to the last plotted level
                if(!node.anySubnode("exist")) {
                    if (node.data.info.match(/Follow Descendant Tree/)) {
                        node.data.$color = '#bbf';
                    } else {
                        //count children number
                        var count = 0;
                        node.eachSubnode(function(n) { count++; });
                        //assign a node color based on
                        //how many children it has
                        var color_idx = count > 10 ? 10 : count;
                        node.data.$color = ['#bbb','#fef1f6','#fee1ed','#fed7e6','#fdc9de','#fdbad5','#fdaacb','#fc9cc2','#fc92bc','#fc83b3','#fc73aa'][color_idx];                   
                    }
                }
            }
        },
        
        //This method is called right before plotting
        //an edge. It's useful for changing an individual edge
        //style properties before plotting it.
        //Edge data proprties prefixed with a dollar sign will
        //override the Edge global style properties.
        onBeforePlotLine: function(adj){
            if (adj.nodeFrom.selected && adj.nodeTo.selected) {
                adj.data.$color = "#eed";
                adj.data.$lineWidth = 3;
            }
            else {
                delete adj.data.$color;
                delete adj.data.$lineWidth;
            }
        }
    });

    //load json data
    st.loadJSON(json);

    //compute node positions and layout
    st.compute();

    //optional: make a translation of the tree
    st.geom.translate(new $jit.Complex(-200, 0), "current");

    //emulate a click on the root node.
    st.onClick(st.root);

}
