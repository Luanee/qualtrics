/* Pure control-flow graph. Occurrence IDs identify cards; external IDs never do. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.QualtricsFlowGraph = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const types = {Root:'Survey start',Block:'Question block',Standard:'Question block',Branch:'Condition',Group:'Group',Randomizer:'Randomizer',BlockRandomizer:'Randomizer',EndSurvey:'Survey ending',EmbeddedData:'Embedded data'};
  function build(definition, describeCondition) {
    const nodes=[], edges=[], used=new Set();
    function reserve(item) { used.add(item.node_id);(item.children || []).forEach(reserve); }
    reserve(definition.root);
    function add(data) { const item={width:260,height:120,...data};nodes.push(item);return item.id; }
    function link(source,target,label='',kind='sequence') { edges.push({id:'edge-'+edges.length,source,target,label,kind}); }
    function join(item,random,conditional=false) {
      let id='@join:'+item.node_id;while(used.has(id)) id+=':';used.add(id);
      return add({id,kind:'join',title:random?'After selected draws':'Routes rejoin',description:random?(conditional?'Continuation depends on selected steps, conditions and assumptions.':'Continue once all chosen steps finish.'):'Continue along the shared route.',height:74});
    }
    // This is possible configured continuation, not evaluation of a live condition.
    // A Branch chosen by a randomizer has already met its eligibility condition.
    function continuation(item, selected=false) {
      const children=item.children || [], config=item.config || {};
      if(item.type==='EndSurvey') return 'never';
      if(['Randomizer','BlockRandomizer'].includes(item.type)) {
        const count=Number(config.SubSet);
        if(config.SubSet==null || config.SubSet==='' || !Number.isInteger(count) || count<0 || count>children.length) return 'never';
        if(count===0) return 'always';
        const alternatives=children.map(child=>continuation(child,true));
        if(alternatives.filter(result=>result!=='never').length<count) return 'never';
        return alternatives.every(result=>result==='always') && children.every(child=>child.type!=='Branch') ? 'always':'maybe';
      }
      const results=children.map(child=>continuation(child));
      const result=results.includes('never')?'never':results.includes('maybe')?'maybe':'always';
      if(item.type==='Branch' && !selected) return result==='always'?'always':'maybe';
      return !types[item.type] && result!=='never' ? 'maybe':result;
    }
    function sequence(items, incoming, label='',kind='sequence') {
      let exits=incoming;
      for(const item of items) { const part=visit(item);exits.forEach(id=>link(id,part.entry,label,kind));exits=exits.length ? part.exits : [];label='';kind='sequence'; }
      return exits;
    }
    function visit(item,selected=false) {
      const config=item.config || {}, children=item.children || [], block=definition.blocks?.[config.ID];
      const random=['Randomizer','BlockRandomizer'].includes(item.type);
      let description='Follow the configured sequence.';
      if(item.type==='Block' || item.type==='Standard') { const count=(block?.elements || []).filter(e=>e.type==='question').length;description=count+' '+(count===1?'question':'questions')+' · Select to inspect'; }
      if(item.type==='Branch') description=describeCondition?.(config.BranchLogic) || 'Enter when the condition is met; otherwise bypass.';
      if(random) description=continuation(item)==='never'?'This draw configuration cannot continue beyond the randomizer.':'Choose '+(config.SubSet ?? 'configured')+' eligible steps; order is set in the scenario.';
      if(item.type==='EndSurvey') description='Ends the whole survey route. No continuation.';
      if(item.type==='EmbeddedData') description=(config.EmbeddedData || []).map(e=>e.Field || e.Description).filter(Boolean).join(', ') || 'Set or read embedded fields.';
      if(!types[item.type]) description='Requires an explicit continuation assumption.';
      const id=add({id:item.node_id,occurrenceId:item.node_id,kind:item.type,typeLabel:types[item.type] || item.type,title:String(block?.name || config.Description || types[item.type] || item.type),description});
      if(item.type==='EndSurvey') { sequence(children,[]);return {entry:id,exits:[]}; }
      if(item.type==='Branch' || random) {
        const outcome=random?continuation(item):selected?continuation(item,true):'always';
        const end=outcome==='never'?null:join(item,random,outcome==='maybe');
        if(random) {
          for(const child of children) {
            const part=visit(child,true);link(id,part.entry,'Eligible choice','choice');
            if(end && continuation(child,true)!=='never') part.exits.forEach(exit=>link(exit,end,outcome==='maybe'?'If chosen steps finish':'After final draw','choice'));
          }
          if(end && Number(config.SubSet)===0) link(id,end,'No draws','choice');
        } else {
          const exits=sequence(children,[id],'Condition met','met');
          exits.forEach(exit=>link(exit,end,children.length?'':'Condition met','met'));
          if(!selected) link(id,end,'Condition not met','unmet');
        }
        return {entry:id,exits:end?[end]:[]};
      }
      return {entry:id,exits:sequence(children,[id])};
    }
    visit(definition.root);
    // Stable topological layers keep all edges downward and cards nonoverlapping.
    const indegree=new Map(nodes.map(n=>[n.id,0])), outgoing=new Map(nodes.map(n=>[n.id,[]])), ranks=new Map(nodes.map(n=>[n.id,0]));
    edges.forEach(e=>{indegree.set(e.target,indegree.get(e.target)+1);outgoing.get(e.source).push(e.target);});
    const queue=nodes.filter(n=>indegree.get(n.id)===0).map(n=>n.id);
    for(let i=0;i<queue.length;i++) for(const target of outgoing.get(queue[i])) {
      ranks.set(target,Math.max(ranks.get(target),ranks.get(queue[i])+1));indegree.set(target,indegree.get(target)-1);
      if(!indegree.get(target)) queue.push(target);
    }
    const reachable=new Set(), pending=[definition.root.node_id];
    for(let i=0;i<pending.length;i++) if(!reachable.has(pending[i])) {reachable.add(pending[i]);pending.push(...outgoing.get(pending[i]));}
    nodes.forEach(n=>{n.unreachable=!reachable.has(n.id);});
    const layers=[];nodes.forEach(n=>(layers[ranks.get(n.id)] ||= []).push(n));
    const width=Math.max(1,...layers.map(row=>row.length))*330+120;
    layers.forEach((row,rank)=>row.forEach((n,index)=>{n.x=(width-row.length*330)/2+index*330+35;n.y=40+rank*196;}));
    return {nodes,edges,width,height:Math.max(...nodes.map(n=>n.y+n.height))+40};
  }
  return {build};
});
