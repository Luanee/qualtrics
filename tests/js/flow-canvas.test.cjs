const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path='../../src/qualtrics/reporting/static/flow-canvas.js';
const canvas=fs.existsSync(require('node:path').resolve(__dirname,path)) ? require(path) : {};
const graph={width:1000,height:1800,nodes:[{id:'first',occurrenceId:'first',x:100,y:100,width:260,height:126},{id:'last',occurrenceId:'last',x:100,y:1400,width:260,height:126}]};
test('fit contains the whole graph and resize recenters the selected occurrence at readable zoom',()=>{
  assert.equal(typeof canvas.createViewport,'function');
  const view=canvas.createViewport();view.setGraph(graph);view.resize(600,500);view.fit();
  let s=view.snapshot();assert.ok(s.x>=0 && s.y>=0);assert.ok(s.x+graph.width*s.scale<=600);assert.ok(s.y+graph.height*s.scale<=500);
  view.select('last');s=view.snapshot();assert.ok(s.scale>=.75);assert.equal(s.selected,'last');
  assert.ok(Math.abs(s.y+(1400+63)*s.scale-250)<.001);
  view.resize(320,440);s=view.snapshot();assert.ok(Math.abs(s.x+230*s.scale-160)<.001);
});
test('zoom preserves its focal point, clamps scale, and pan changes translation only',()=>{
  const view=canvas.createViewport();view.setGraph(graph);view.resize(600,500);view.select('first');
  let s=view.snapshot(), gx=(120-s.x)/s.scale,gy=(90-s.y)/s.scale;
  view.zoom(1.2,120,90);s=view.snapshot();assert.ok(Math.abs((120-s.x)/s.scale-gx)<.001);assert.ok(Math.abs((90-s.y)/s.scale-gy)<.001);
  view.pan(30,-20);assert.equal(view.snapshot().x,s.x+30);assert.equal(view.snapshot().y,s.y-20);
  view.zoom(1000);assert.equal(view.snapshot().scale,1.6);view.zoom(.00001);assert.equal(view.snapshot().scale,.05);
});
test('invalid selections cannot change current selection; changing graph clears it',()=>{
  const view=canvas.createViewport();view.setGraph(graph);view.resize(600,500);view.select('first');
  assert.equal(view.select('missing'),false);assert.equal(view.snapshot().selected,'first');
  view.setGraph({width:100,height:100,nodes:[]});assert.equal(view.snapshot().selected,null);
});

test('resize preserves fitted and panned framing; real size changes preserve the graph point at viewport center',()=>{
  const view=canvas.createViewport();view.setGraph(graph);view.resize(600,500);view.select('first');view.fit();
  const fitted=view.snapshot();view.resize(600,500);assert.deepEqual(view.snapshot(),fitted);
  view.pan(70,-120);const panned=view.snapshot();view.resize(600,500);assert.deepEqual(view.snapshot(),panned);
  const centerX=(panned.width/2-panned.x)/panned.scale,centerY=(panned.height/2-panned.y)/panned.scale;
  view.resize(320,400);const resized=view.snapshot();
  assert.equal((resized.width/2-resized.x)/resized.scale,centerX);
  assert.equal((resized.height/2-resized.y)/resized.scale,centerY);
});
