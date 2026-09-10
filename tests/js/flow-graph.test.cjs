const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = '../../src/qualtrics/reporting/static/flow-graph.js';
const graph = fs.existsSync(require('node:path').resolve(__dirname,path)) ? require(path) : {};
const n=(node_id,type='Block',children=[],config={})=>({node_id,type,children,config,external_id:'duplicated'});
const build=children=>graph.build({root:n('root','Root',children),blocks:{},questions:{}});
const edge=(g,from,to,label)=>g.edges.some(e=>e.source===from && e.target===to && (!label || e.label===label));

test('sequence uses occurrence IDs even when external block IDs repeat',()=>{
  assert.equal(typeof graph.build,'function');
  const g=build([n('first'),n('second')]);
  assert.equal(g.nodes.filter(n=>n.occurrenceId).length,3);
  assert.ok(edge(g,'root','first'));assert.ok(edge(g,'first','second'));
});
test('branch has explicit met/unmet routes that rejoin before the next step',()=>{
  const g=build([n('branch','Branch',[n('yes')]),n('after')]);
  const join=g.nodes.find(n=>n.kind==='join');
  assert.ok(edge(g,'branch','yes','Condition met'));
  assert.ok(edge(g,'branch',join.id,'Condition not met'));
  assert.ok(edge(g,'yes',join.id));assert.ok(edge(g,join.id,'after'));
});
test('ending terminates its route while a skipped ending branch can continue',()=>{
  const g=build([n('branch','Branch',[n('end','EndSurvey'),n('unreachable')]),n('after')]);
  assert.equal(g.edges.some(e=>e.source==='end'),false);
  assert.equal(g.edges.some(e=>e.target==='unreachable'),false);
  assert.ok(g.nodes.some(n=>n.id==='unreachable'));
  assert.ok(g.edges.some(e=>e.target==='after'));
});
test('randomizer options fan out and rejoin only after the final chosen draw',()=>{
  const g=build([n('random','Randomizer',[n('a'),n('b')],{SubSet:2}),n('after')]);
  assert.ok(edge(g,'random','a'));assert.ok(edge(g,'random','b'));
  assert.equal(edge(g,'a','b') || edge(g,'b','a'),false);
  assert.match(g.nodes.find(n=>n.id==='random').description,/2/);
  assert.ok(g.edges.filter(e=>e.source==='a' || e.source==='b').every(e=>e.label==='After final draw'));
});
test('unknown nodes are labelled as assumptions and empty roots remain inspectable',()=>{
  const g=build([n('unknown','FutureStep')]);
  assert.match(g.nodes.find(n=>n.id==='unknown').description,/assumption/i);
  assert.equal(build([]).nodes.length,1);assert.equal(build([]).edges.length,0);
});
test('nested layout is deterministic, bounded by graph dimensions and never overlaps cards',()=>{
  const source=[n('branch','Branch',[n('random','Randomizer',[n('a'),n('b'),n('c')],{SubSet:1})]),n('after')];
  const g=build(source);assert.deepEqual(build(source),g);
  for(const a of g.nodes) {
    assert.ok(a.x>=0 && a.y>=0 && a.x+a.width<=g.width && a.y+a.height<=g.height);
    for(const b of g.nodes) if(a!==b) assert.ok(a.x+a.width<=b.x || b.x+b.width<=a.x || a.y+a.height<=b.y || b.y+b.height<=a.y);
  }
});
test('synthetic join IDs cannot collide with stored occurrence IDs',()=>{
  const g=build([n('x','Branch',[n('@join:x')]),n('after')]);
  assert.equal(new Set(g.nodes.map(n=>n.id)).size,g.nodes.length);
});

test('nodes after an unconditional ending are explicitly identified as unreachable',()=>{
  const g=build([n('end','EndSurvey'),n('later')]);
  assert.equal(g.nodes.find(n=>n.id==='later').unreachable,true);
  assert.equal(g.nodes.find(n=>n.id==='end').unreachable,false);
});

test('mandatory terminal randomizer choices never produce an ordinary continuation',()=>{
  for(const terminal of [n('end','EndSurvey'),n('nested','Group',[n('end','EndSurvey')])]) {
    const g=build([n('r','Randomizer',[terminal,n('work','Group')],{SubSet:2}),n('after')]);
    assert.equal(g.nodes.find(n=>n.id==='after').unreachable,true);
    assert.equal(g.edges.some(e=>e.source==='work' && e.label==='After final draw'),false);
    assert.match(g.nodes.find(n=>n.id==='r').description,/cannot continue/i);
  }
});
test('eligible branches that end are terminal when chosen by a randomizer',()=>{
  const g=build([n('r','Randomizer',[n('branch','Branch',[n('end','EndSurvey')]),n('work','Group')],{SubSet:2}),n('after')]);
  assert.equal(g.nodes.find(n=>n.id==='after').unreachable,true);
});
test('conditional termination preserves only an explicitly conditional possible continuation',()=>{
  const g=build([n('r','Randomizer',[n('maybe','Group',[n('branch','Branch',[n('end','EndSurvey')])]),n('work','Group')],{SubSet:2}),n('after')]);
  assert.equal(g.nodes.find(n=>n.id==='after').unreachable,false);
  assert.ok(g.edges.some(e=>e.label==='If chosen steps finish'));
  assert.match(g.nodes.find(n=>n.kind==='join' && n.title==='After selected draws').description,/depend/i);
});
test('optional terminal draws can continue only by selecting nonterminating alternatives',()=>{
  const g=build([n('r','Randomizer',[n('end','EndSurvey'),n('work','Group')],{SubSet:1}),n('after')]);
  assert.equal(g.nodes.find(n=>n.id==='after').unreachable,false);
  assert.equal(g.edges.some(e=>e.source==='end'),false);
  assert.ok(g.edges.some(e=>e.source==='work' && e.label==='If chosen steps finish'));
});

test('a directly selected randomizer branch has no ineligible bypass route',()=>{
  const g=build([n('r','Randomizer',[n('branch','Branch',[n('end','EndSurvey')]),n('work','Group')],{SubSet:1})]);
  assert.equal(g.edges.some(e=>e.source==='branch' && e.kind==='unmet'),false);
});
