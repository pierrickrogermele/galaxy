require(["utils/utils","mvc/ui/icon-button","libs/farbtastic",],function(b,a){b.cssLoadFile("static/style/circster.css")});define(["libs/underscore","libs/d3","viz/visualization","utils/config"],function(h,m,j,c){var n=Backbone.Model.extend({is_visible:function(r,o){var p=r.getBoundingClientRect(),q=$("svg")[0].getBoundingClientRect();if(p.right<0||p.left>q.right||p.bottom<0||p.top>q.bottom){return false}return true}});var i={drawTicks:function(s,r,w,q,o){var v=s.append("g").selectAll("g").data(r).enter().append("g").selectAll("g").data(w).enter().append("g").attr("class","tick").attr("transform",function(x){return"rotate("+(x.angle*180/Math.PI-90)+")translate("+x.radius+",0)"});var u=[],t=[],p=function(x){return x.angle>Math.PI?"end":null};if(o){u=[0,0,0,-4];t=[4,0,"",".35em"];p=null}else{u=[1,0,4,0];t=[0,4,".35em",""]}v.append("line").attr("x1",u[0]).attr("y1",u[1]).attr("x2",u[2]).attr("y1",u[3]).style("stroke","#000");return v.append("text").attr("x",t[0]).attr("y",t[1]).attr("dx",t[2]).attr("dy",t[3]).attr("text-anchor",p).attr("transform",q).text(function(x){return x.label})},formatNum:function(p,o){if(o===undefined){o=2}if(p===null){return null}var r=null;if(Math.abs(p)<1){r=p.toPrecision(o)}else{var q=Math.round(p.toPrecision(o));p=Math.abs(p);if(p<1000){r=q}else{if(p<1000000){r=Math.round((q/1000).toPrecision(3)).toFixed(0)+"K"}else{if(p<1000000000){r=Math.round((q/1000000).toPrecision(3)).toFixed(0)+"M"}}}}return r}};var d=Backbone.Model.extend({});var a=Backbone.View.extend({className:"circster",initialize:function(o){this.genome=o.genome;this.label_arc_height=50;this.scale=1;this.circular_views=null;this.chords_views=null;this.model.get("drawables").on("add",this.add_track,this);this.model.get("drawables").on("remove",this.remove_track,this);var p=this.model.get("config");p.get("arc_dataset_height").on("change:value",this.update_track_bounds,this);p.get("track_gap").on("change:value",this.update_track_bounds,this)},get_circular_tracks:function(){return this.model.get("drawables").filter(function(o){return o.get("track_type")!=="DiagonalHeatmapTrack"})},get_chord_tracks:function(){return this.model.get("drawables").filter(function(o){return o.get("track_type")==="DiagonalHeatmapTrack"})},get_tracks_bounds:function(){var q=this.get_circular_tracks(),s=this.model.get("config").get_value("arc_dataset_height"),r=this.model.get("config").get_value("track_gap"),o=Math.min(this.$el.width(),this.$el.height())-20,u=o/2-q.length*(s+r)+r-this.label_arc_height,t=m.range(u,o/2,s+r);var p=this;return h.map(t,function(v){return[v,v+s]})},render:function(){var x=this,o=x.$el.width(),w=x.$el.height(),t=this.get_circular_tracks(),r=this.get_chord_tracks(),q=x.model.get("config").get_value("total_gap"),s=this.get_tracks_bounds(),p=m.select(x.$el[0]).append("svg").attr("width",o).attr("height",w).attr("pointer-events","all").append("svg:g").call(m.behavior.zoom().on("zoom",function(){var y=m.event.scale;p.attr("transform","translate("+m.event.translate+") scale("+y+")");if(x.scale!==y){if(x.zoom_drag_timeout){clearTimeout(x.zoom_drag_timeout)}x.zoom_drag_timeout=setTimeout(function(){},400)}})).attr("transform","translate("+o/2+","+w/2+")").append("svg:g").attr("class","tracks");this.circular_views=t.map(function(z,A){var y=new e({el:p.append("g")[0],track:z,radius_bounds:s[A],genome:x.genome,total_gap:q});y.render();return y});this.chords_views=r.map(function(z){var y=new k({el:p.append("g")[0],track:z,radius_bounds:s[0],genome:x.genome,total_gap:q});y.render();return y});var v=this.circular_views[this.circular_views.length-1].radius_bounds[1],u=[v,v+this.label_arc_height];this.label_track_view=new b({el:p.append("g")[0],track:new d(),radius_bounds:u,genome:x.genome,total_gap:q});this.label_track_view.render()},add_track:function(u){var p=this.model.get("config").get_value("total_gap");if(u.get("track_type")==="DiagonalHeatmapTrack"){var q=this.circular_views[0].radius_bounds,t=new k({el:m.select("g.tracks").append("g")[0],track:u,radius_bounds:q,genome:this.genome,total_gap:p});t.render();this.chords_views.push(t)}else{var s=this.get_tracks_bounds();h.each(this.circular_views,function(v,w){v.update_radius_bounds(s[w])});h.each(this.chords_views,function(v){v.update_radius_bounds(s[0])});var r=this.circular_views.length,o=new e({el:m.select("g.tracks").append("g")[0],track:u,radius_bounds:s[r],genome:this.genome,total_gap:p});o.render();this.circular_views.push(o)}},remove_track:function(p,r,q){var o=this.circular_views[q.index];this.circular_views.splice(q.index,1);o.$el.remove();var s=this.get_tracks_bounds();h.each(this.circular_views,function(t,u){t.update_radius_bounds(s[u])})},update_track_bounds:function(){var o=this.get_tracks_bounds();h.each(this.circular_views,function(p,q){p.update_radius_bounds(o[q])});h.each(this.chords_views,function(p){p.update_radius_bounds(o[0])})}});var l=Backbone.View.extend({tagName:"g",initialize:function(o){this.bg_stroke="#ddd";this.loading_bg_fill="#ffc";this.bg_fill="#ddd";this.total_gap=o.total_gap;this.track=o.track;this.radius_bounds=o.radius_bounds;this.genome=o.genome;this.chroms_layout=this._chroms_layout();this.data_bounds=[];this.scale=1;this.parent_elt=m.select(this.$el[0])},get_fill_color:function(){var o=this.track.get("config").get_value("block_color");if(!o){o=this.track.get("config").get_value("color")}return o},render:function(){var s=this.parent_elt;var r=this.chroms_layout,u=m.svg.arc().innerRadius(this.radius_bounds[0]).outerRadius(this.radius_bounds[1]),o=s.selectAll("g").data(r).enter().append("svg:g"),q=o.append("path").attr("d",u).attr("class","chrom-background").style("stroke",this.bg_stroke).style("fill",this.loading_bg_fill);q.append("title").text(function(w){return w.data.chrom});var p=this,t=p.track.get("data_manager"),v=(t?t.data_is_ready():true);$.when(v).then(function(){$.when(p._render_data(s)).then(function(){q.style("fill",p.bg_fill);p.render_labels()})})},render_labels:function(){},update_radius_bounds:function(p){this.radius_bounds=p;var o=m.svg.arc().innerRadius(this.radius_bounds[0]).outerRadius(this.radius_bounds[1]);this.parent_elt.selectAll("g>path.chrom-background").transition().duration(1000).attr("d",o);this._transition_chrom_data();this._transition_labels()},update_scale:function(r){var q=this.scale;this.scale=r;if(r<=q){return}var p=this,o=new n();this.parent_elt.selectAll("path.chrom-data").filter(function(t,s){return o.is_visible(this)}).each(function(y,u){var x=m.select(this),t=x.attr("chrom"),w=p.genome.get_chrom_region(t),v=p.track.get("data_manager"),s;if(!v.can_get_more_detailed_data(w)){return}s=p.track.get("data_manager").get_more_detailed_data(w,"Coverage",0,r);$.when(s).then(function(B){x.remove();p._update_data_bounds();var A=h.find(p.chroms_layout,function(C){return C.data.chrom===t});var z=p.get_fill_color();p._render_chrom_data(p.parent_elt,A,B).style("stroke",z).style("fill",z)})});return p},_transition_chrom_data:function(){var p=this.track,r=this.chroms_layout,o=this.parent_elt.selectAll("g>path.chrom-data"),s=o[0].length;if(s>0){var q=this;$.when(p.get("data_manager").get_genome_wide_data(this.genome)).then(function(v){var u=h.reject(h.map(v,function(w,x){var y=null,z=q._get_path_function(r[x],w);if(z){y=z(w.data)}return y}),function(w){return w===null});var t=p.get("config").get_value("color");o.each(function(x,w){m.select(this).transition().duration(1000).style("stroke",t).style("fill",t).attr("d",u[w])})})}},_transition_labels:function(){},_update_data_bounds:function(p){var o=this.data_bounds;this.data_bounds=p||this.get_data_bounds(this.track.get("data_manager").get_genome_wide_data(this.genome));this._transition_chrom_data()},_render_data:function(r){var q=this,p=this.chroms_layout,o=this.track,s=$.Deferred();$.when(o.get("data_manager").get_genome_wide_data(this.genome)).then(function(u){q.data_bounds=q.get_data_bounds(u);o.get("config").set_value("min_value",q.data_bounds[0],{silent:true});o.get("config").set_value("max_value",q.data_bounds[1],{silent:true});layout_and_data=h.zip(p,u),chroms_data_layout=h.map(layout_and_data,function(v){var w=v[0],x=v[1];return q._render_chrom_data(r,w,x)});var t=q.get_fill_color();q.parent_elt.selectAll("path.chrom-data").style("stroke",t).style("fill",t);s.resolve(r)});return s},_render_chrom_data:function(o,p,q){},_get_path_function:function(p,o){},_chroms_layout:function(){var p=this.genome.get_chroms_info(),r=m.layout.pie().value(function(t){return t.len}).sort(null),s=r(p),o=2*Math.PI*this.total_gap/p.length,q=h.map(s,function(v,u){var t=v.endAngle-o;v.endAngle=(t>v.startAngle?t:v.startAngle);return v});return q}});var b=l.extend({initialize:function(o){l.prototype.initialize.call(this,o);this.innerRadius=this.radius_bounds[0];this.radius_bounds[0]=this.radius_bounds[1];this.bg_stroke="#fff";this.bg_fill="#fff";this.min_arc_len=0.05},_render_data:function(q){var p=this,o=q.selectAll("g");o.selectAll("path").attr("id",function(u){return"label-"+u.data.chrom});o.append("svg:text").filter(function(u){return u.endAngle-u.startAngle>p.min_arc_len}).attr("text-anchor","middle").append("svg:textPath").attr("class","chrom-label").attr("xlink:href",function(u){return"#label-"+u.data.chrom}).attr("startOffset","25%").text(function(u){return u.data.chrom});var r=function(w){var u=(w.endAngle-w.startAngle)/w.value,v=m.range(0,w.value,25000000).map(function(x,y){return{radius:p.innerRadius,angle:x*u+w.startAngle,label:y===0?0:(y%3?null:p.formatNum(x))}});if(v.length<4){v[v.length-1].label=p.formatNum(Math.round((v[v.length-1].angle-w.startAngle)/u))}return v};var t=function(u){return u.angle>Math.PI?"rotate(180)translate(-16)":null};var s=h.filter(this.chroms_layout,function(u){return u.endAngle-u.startAngle>p.min_arc_len});this.drawTicks(this.parent_elt,s,r,t)}});h.extend(b.prototype,i);var g=l.extend({initialize:function(o){l.prototype.initialize.call(this,o);var p=this.track.get("config");p.get("min_value").on("change:value",this._update_min_max,this);p.get("max_value").on("change:value",this._update_min_max,this);p.get("color").on("change:value",this._transition_chrom_data,this)},_update_min_max:function(){var p=this.track.get("config"),o=[p.get_value("min_value"),p.get_value("max_value")];this._update_data_bounds(o);this.parent_elt.selectAll(".min_max").text(function(r,q){return o[q]})},_quantile:function(p,o){p.sort(m.ascending);return m.quantile(p,o)},_render_chrom_data:function(o,r,p){var s=this._get_path_function(r,p);if(!s){return null}var q=o.datum(p.data),t=q.append("path").attr("class","chrom-data").attr("chrom",r.data.chrom).attr("d",s);return t},_get_path_function:function(r,q){if(typeof q==="string"||!q.data||q.data.length===0){return null}var o=m.scale.linear().domain(this.data_bounds).range(this.radius_bounds).clamp(true);var s=m.scale.linear().domain([0,q.data.length]).range([r.startAngle,r.endAngle]);var p=m.svg.line.radial().interpolate("linear").radius(function(t){return o(t[1])}).angle(function(u,t){return s(t)});return m.svg.area.radial().interpolate(p.interpolate()).innerRadius(o(0)).outerRadius(p.radius()).angle(p.angle())},render_labels:function(){var o=this,q=function(){return"rotate(90)"};var p=this.drawTicks(this.parent_elt,[this.chroms_layout[0]],this._data_bounds_ticks_fn(),q,true).classed("min_max",true);h.each(p,function(r){$(r).click(function(){var s=new c.ConfigSettingCollectionView({collection:o.track.get("config")});s.render_in_modal("Configure Track")})})},_transition_labels:function(){if(this.data_bounds.length===0){return}var p=this,r=h.filter(this.chroms_layout,function(s){return s.endAngle-s.startAngle>0.08}),q=h.filter(r,function(t,s){return s%3===0}),o=h.flatten(h.map(q,function(s){return p._data_bounds_ticks_fn()(s)}));this.parent_elt.selectAll("g.tick").data(o).transition().attr("transform",function(s){return"rotate("+(s.angle*180/Math.PI-90)+")translate("+s.radius+",0)"})},_data_bounds_ticks_fn:function(){var o=this;visibleChroms=0;return function(p){return[{radius:o.radius_bounds[0],angle:p.startAngle,label:o.formatNum(o.data_bounds[0])},{radius:o.radius_bounds[1],angle:p.startAngle,label:o.formatNum(o.data_bounds[1])}]}},get_data_bounds:function(o){}});h.extend(g.prototype,i);var e=g.extend({get_data_bounds:function(p){var o=h.flatten(h.map(p,function(q){if(q){return h.map(q.data,function(r){return parseInt(r[1],10)||0})}else{return 0}}));return[h.min(o),this._quantile(o,0.98)||h.max(o)]}});var k=l.extend({render:function(){var o=this;$.when(o.track.get("data_manager").data_is_ready()).then(function(){$.when(o.track.get("data_manager").get_genome_wide_data(o.genome)).then(function(r){var q=[],p=o.genome.get_chroms_info();h.each(r,function(v,u){var s=p[u].chrom;var t=h.map(v.data,function(x){var w=o._get_region_angle(s,x[1]),y=o._get_region_angle(x[3],x[4]);return{source:{startAngle:w,endAngle:w+0.01},target:{startAngle:y,endAngle:y+0.01}}});q=q.concat(t)});o.parent_elt.append("g").attr("class","chord").selectAll("path").data(q).enter().append("path").style("fill",o.get_fill_color()).attr("d",m.svg.chord().radius(o.radius_bounds[0])).style("opacity",1)})})},update_radius_bounds:function(o){this.radius_bounds=o;this.parent_elt.selectAll("path").transition().attr("d",m.svg.chord().radius(this.radius_bounds[0]))},_get_region_angle:function(q,o){var p=h.find(this.chroms_layout,function(r){return r.data.chrom===q});return p.endAngle-((p.endAngle-p.startAngle)*(p.data.len-o)/p.data.len)}});var f=Backbone.View.extend({initialize:function(){var o=new j.Genome(galaxy_config.app.genome),p=new j.GenomeVisualization(galaxy_config.app.viz_config);p.get("config").add([{key:"arc_dataset_height",label:"Arc Dataset Height",type:"int",value:25,view:"circster"},{key:"track_gap",label:"Gap Between Tracks",type:"int",value:5,view:"circster"},{key:"total_gap",label:"Gap [0-1]",type:"float",value:0.4,view:"circster",hidden:true}]);var r=new a({el:$("#center .unified-panel-body"),genome:o,model:p});r.render();$("#center .unified-panel-header-inner").append(galaxy_config.app.viz_config.title+" "+galaxy_config.app.viz_config.dbkey);var q=mod_icon_btn.create_icon_buttons_menu([{icon_class:"plus-button",title:"Add tracks",on_click:function(){j.select_datasets(galaxy_config.root+"visualization/list_current_history_datasets",galaxy_config.root+"api/datasets",p.get("dbkey"),function(s){p.add_tracks(s)})}},{icon_class:"gear",title:"Settings",on_click:function(){var s=new c.ConfigSettingCollectionView({collection:p.get("config")});s.render_in_modal("Configure Visualization")}},{icon_class:"disk--arrow",title:"Save",on_click:function(){Galaxy.modal.show({title:"Saving...",body:"progress"});$.ajax({url:galaxy_config.root+"visualization/save",type:"POST",dataType:"json",data:{id:p.get("vis_id"),title:p.get("title"),dbkey:p.get("dbkey"),type:"trackster",vis_json:JSON.stringify(p)}}).success(function(s){Galaxy.modal.hide();p.set("vis_id",s.vis_id)}).error(function(){Galaxy.modal.show({title:"Could Not Save",body:"Could not save visualization. Please try again later.",buttons:{Cancel:function(){Galaxy.modal.hide()}}})})}},{icon_class:"cross-circle",title:"Close",on_click:function(){window.location=galaxy_config.root+"visualization/list"}}],{tooltip_config:{placement:"bottom"}});q.$el.attr("style","float: right");$("#center .unified-panel-header-inner").append(q.$el);$(".menu-button").tooltip({placement:"bottom"})}});return{GalaxyApp:f}});