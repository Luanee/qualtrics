/* Offline canvas interaction and rendering; all definition labels use textContent. */
(function (root, factory) {
  const api=factory();
  if(typeof module==='object' && module.exports) module.exports=api;
  else root.QualtricsFlowCanvas=api;
})(typeof window!=='undefined'?window:globalThis,function () {
  'use strict';
  const clamp=value=>Math.max(.05,Math.min(1.6,value));
  function createViewport() {
    let graph={width:1,height:1,nodes:[]}, width=600,height=500,scale=1,x=0,y=0,selected=null;
    function center() { const n=graph.nodes.find(n=>n.id===selected);if(n) {x=width/2-(n.x+n.width/2)*scale;y=height/2-(n.y+n.height/2)*scale;} }
    return {
      setGraph(value) {graph=value;selected=null;},
      resize(w,h) {if(w>0 && h>0) {x+=(w-width)/2;y+=(h-height)/2;width=w;height=h;}},
      fit() {scale=Math.min(1,Math.max(.001,Math.min((width-32)/graph.width,(height-32)/graph.height)));x=(width-graph.width*scale)/2;y=(height-graph.height*scale)/2;},
      select(id) {if(!graph.nodes.some(n=>n.id===id && n.occurrenceId)) return false;selected=id;scale=Math.max(.75,scale);center();return true;},
      zoom(factor,cx=width/2,cy=height/2) {const next=clamp(scale*factor);x=cx-(cx-x)*next/scale;y=cy-(cy-y)*next/scale;scale=next;},
      pan(dx,dy) {x+=dx;y+=dy;},
      snapshot() {return {x,y,scale,selected,width,height};},
    };
  }
  function create(document, graphBuilder, onSelect, engine) {
    const $=id=>document.getElementById('flow-'+id), viewport=$('canvas');
    if(!viewport) return null;
    const view=createViewport(), layer=$('canvas-layer'), cards=new Map();
    let survey=null,graph=null,pointer=null, suppressClick=false, initial=false, touchMove=false;
    const make=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
    const svg=tag=>document.createElementNS('http://www.w3.org/2000/svg',tag);
    function paint() {const s=view.snapshot();layer.style.transform=`translate(${s.x}px, ${s.y}px) scale(${s.scale})`;$('zoom-value').textContent=Math.round(s.scale*100)+'%';}
    function resize() {view.resize(viewport.clientWidth,viewport.clientHeight);if(initial && graph && viewport.clientWidth>0 && viewport.clientHeight>0) {const s=view.snapshot(),first=graph.nodes[0];view.pan(0,32-(first.y*s.scale+s.y));initial=false;}paint();}
    function details(id) {
      const original=document.getElementById(survey.nodes[id]), target=$('selection');
      const item=graph.nodes.find(n=>n.id===id);
      if(!item || !target) return;
      target.replaceChildren(make('p','flow-detail-eyebrow',item.typeLabel),make('h4','',item.title));
      // Clone only this card's server-escaped settings/questions, never its children.
      const body=original?.querySelector('.flow-node-body');
      if(body) for(const child of body.children) if(!child.classList.contains('flow-children')) {
        const copy=child.cloneNode(true);copy.removeAttribute('id');
        copy.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));
        if(copy.tagName==='DETAILS') copy.open=true;
        target.append(copy);
      }

    }
    function select(id,{focus=false,notify=true}={}) {
      if(!survey || !view.select(id)) return false;
      initial=false;
      for(const [key,card] of cards) {card.setAttribute('aria-pressed',String(key===id));card.classList.toggle('is-selected',key===id);}
      details(id);paint();if(focus)cards.get(id)?.focus({preventScroll:true});if(notify)onSelect?.(id);return true;
    }
    function setSurvey(value) {
      if(survey && survey.id===value?.id) return;
      survey=value;cards.clear();layer.replaceChildren();$('selection').hidden=true;
      $('canvas-title').textContent=survey?survey.label:'No flow selected';
      viewport.hidden=!survey;$('canvas-empty').hidden=!!survey;
      ['zoom-in','zoom-out','fit','center'].forEach(id=>{$(id).disabled=!survey;});
      if(!survey) return;
      graph=graphBuilder.build(survey.definition,logic=>engine?.describeCondition(logic,survey.definition));view.setGraph(graph);
      layer.style.width=graph.width+'px';layer.style.height=graph.height+'px';
      const connections=svg('svg');connections.setAttribute('class','flow-edges');connections.setAttribute('width',graph.width);connections.setAttribute('height',graph.height);connections.setAttribute('aria-hidden','true');
      const defs=svg('defs'), marker=svg('marker'), arrow=svg('path');
      marker.setAttribute('id','flow-arrow');marker.setAttribute('viewBox','0 0 10 10');marker.setAttribute('refX','9');marker.setAttribute('refY','5');marker.setAttribute('markerWidth','6');marker.setAttribute('markerHeight','6');marker.setAttribute('orient','auto');arrow.setAttribute('d','M 0 0 L 10 5 L 0 10 z');marker.append(arrow);defs.append(marker);connections.append(defs);
      const nodes=new Map(graph.nodes.map(n=>[n.id,n]));
      graph.edges.forEach(edge=>{
        const a=nodes.get(edge.source), b=nodes.get(edge.target), ax=a.x+a.width/2,ay=a.y+a.height,bx=b.x+b.width/2,by=b.y;
        const path=svg('path');path.setAttribute('class','flow-edge flow-edge-'+edge.kind);
        let d,tx,ty;
        if(edge.kind==='unmet') {
          const lane=Math.min(a.x,b.x)-48;d=`M ${ax} ${ay} V ${ay+24} H ${lane} V ${by-24} H ${bx} V ${by}`;tx=lane;ty=(ay+by)/2;
        } else {const middle=(ay+by)/2;d=`M ${ax} ${ay} V ${middle} H ${bx} V ${by}`;tx=(ax+bx)/2;ty=middle-9;}
        path.setAttribute('d',d);path.setAttribute('marker-end','url(#flow-arrow)');connections.append(path);
        if(edge.label) {const label=svg('text');label.setAttribute('x',tx);label.setAttribute('y',ty);label.setAttribute('text-anchor','middle');label.setAttribute('class','flow-edge-label');label.textContent=edge.label;connections.append(label);}
      });
      layer.append(connections);
      for(const item of graph.nodes) {
        const card=make(item.occurrenceId?'button':'div','flow-card'+(item.kind==='join'?' flow-join':''));
        card.style.left=item.x+'px';card.style.top=item.y+'px';card.style.width=item.width+'px';card.style.height=item.height+'px';
        card.dataset.kind=item.kind;card.dataset.flowUnreachable=String(item.unreachable);
        if(item.occurrenceId) {
          card.type='button';card.dataset.occurrence=item.id;card.setAttribute('aria-pressed','false');
          card.append(make('span','flow-card-type',item.typeLabel),make('strong','flow-card-title',item.title),make('span','flow-card-description',item.description),make('span','flow-card-state','Configured'));
          card.setAttribute('aria-label',item.typeLabel+': '+item.title+'. '+item.description);
          card.addEventListener('click',()=>{if(!suppressClick)select(item.id);});
          card.addEventListener('focus',()=>{if(view.snapshot().selected!==item.id)select(item.id);});
          cards.set(item.id,card);
        } else card.append(make('strong','flow-card-title',item.title),make('span','flow-card-description',item.description));
        layer.append(card);
      }
      resize();select(survey.definition.root.node_id,{notify:false});initial=true;resize();
    }
    function mark(result) {
      const steps=new Map((result?.steps || []).map(step=>[step.node_id,step]));
      const labels={configured:'Configured',reached:'Reached',skipped:'Skipped',pending:'Pending',unreached:'Not reached',unreachable:'No route from start'};
      for(const [id,card] of cards) {const step=steps.get(id),status=!step?(card.dataset.flowUnreachable==='true'?'unreachable':'configured'):step.status==='pending' && result.pending?.node_id!==id?'unreached':step.status;
        card.dataset.flowStatus=status;card.querySelector('.flow-card-state').textContent=labels[status] || status;
        card.title=step?.reason || '';
      }
    }
    viewport.addEventListener('pointerdown',event=>{
      suppressClick=false;
      if(event.button!==0 || (event.pointerType==='touch' && !touchMove)) return;
      pointer={id:event.pointerId,x:event.clientX,y:event.clientY,moved:false};suppressClick=false;
      if(!event.target.closest('button')) viewport.focus({preventScroll:true});
    });
    viewport.addEventListener('pointermove',event=>{
      if(!pointer || event.pointerId!==pointer.id) return;
      const dx=event.clientX-pointer.x,dy=event.clientY-pointer.y;
      if(!pointer.moved && Math.abs(dx)+Math.abs(dy)<5) return;
      pointer.moved=true;suppressClick=true;viewport.setPointerCapture(event.pointerId);view.pan(dx,dy);pointer.x=event.clientX;pointer.y=event.clientY;paint();
    });
    const release=()=>{pointer=null;};viewport.addEventListener('pointerup',release);viewport.addEventListener('pointercancel',release);
    viewport.addEventListener('wheel',event=>{event.preventDefault();if(event.ctrlKey || event.metaKey) {const rect=viewport.getBoundingClientRect();view.zoom(Math.exp(-event.deltaY*.008),event.clientX-rect.left,event.clientY-rect.top);}else view.pan(-event.deltaX,-event.deltaY);paint();},{passive:false});
    viewport.addEventListener('keydown',event=>{
      if(event.target!==viewport) return;
      const movement={ArrowLeft:[48,0],ArrowRight:[-48,0],ArrowUp:[0,48],ArrowDown:[0,-48]};
      if(movement[event.key])view.pan(...movement[event.key]);
      else if(event.key==='+' || event.key==='=')view.zoom(1.2);
      else if(event.key==='-')view.zoom(1/1.2);
      else if(event.key==='Home')view.fit();else return;
      event.preventDefault();paint();
    });
    $('move-toggle').addEventListener('click',()=>{
      touchMove=!touchMove;pointer=null;
      viewport.classList.toggle('is-touch-moving',touchMove);
      $('move-toggle').setAttribute('aria-pressed',String(touchMove));
      $('move-toggle').textContent=touchMove?'Done moving':'Move map';
    });
    $('zoom-in').addEventListener('click',()=>{view.zoom(1.2);paint();});
    $('zoom-out').addEventListener('click',()=>{view.zoom(1/1.2);paint();});
    $('fit').addEventListener('click',()=>{resize();view.fit();paint();});
    $('center').addEventListener('click',()=>{if(view.snapshot().selected)select(view.snapshot().selected,{focus:true});});
    $('canvas-shell').hidden=false;
    if(document.defaultView?.ResizeObserver) new document.defaultView.ResizeObserver(resize).observe(viewport);
    return {setSurvey,select,mark,resize,snapshot:()=>view.snapshot()};
  }
  return {createViewport,create};
});
