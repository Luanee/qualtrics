const test = require('node:test');
const assert = require('node:assert/strict');
const engine = require('../../src/qualtrics/reporting/static/flow-engine.js');
const {createController} = require('../../src/qualtrics/reporting/static/flow.js');

// Native DOM operations only are represented here; the real controller and
// production engine run together, including their registered button handlers.
function element(tag = 'div') {
  return {tagName:tag.toUpperCase(), children:[], dataset:{}, attributes:{}, handlers:{}, hidden:false, value:'', checked:false, disabled:false,
    append(...items) { for (const item of items) { item.parentElement = this; this.children.push(item); } },
    replaceChildren(...items) { this.children=[]; this.ownText=''; this.append(...items); },
    set textContent(value) { this.ownText=String(value); this.children=[]; },
    get textContent() { return (this.ownText || '') + this.children.map(child=>child.textContent).join(''); },
    setAttribute(name,value) { this.attributes[name]=String(value); },
    addEventListener(event,callback) { this.handlers[event]=callback; },
    querySelectorAll(selector) {
      const matches = item => selector.startsWith('.') ? (item.className || '').split(' ').includes(selector.slice(1))
        : selector === '[data-survey]' ? item.dataset.survey !== undefined : item.tagName.toLowerCase() === selector;
      return this.children.flatMap(child=>[...(matches(child)?[child]:[]), ...child.querySelectorAll(selector)]);
    },
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; },
    closest(selector) { for(let item=this;item;item=item.parentElement) if(selector === '[data-survey]' && item.dataset.survey !== undefined) return item; return null; },
    focus() { this.focused=true; }, scrollIntoView() { this.scrolled=true; },
  };
}
const n=(node_id,type,config={},children=[])=>({node_id,type,config,children});
const block=id=>n(id,'Block',{ID:id});
const selected=id=>({LogicType:'Question',QuestionID:id,ChoiceLocator:`q://${id}/SelectableChoice/1`,Operator:'Selected'});
const choice={type:'MC',selector:'SAVR',text:'Department',choices:{1:'Sales',2:'Engineering'},choice_order:['1','2']};
function definition(children=[block('a'),n('b-branch','Branch',{BranchLogic:selected('Q1')},[block('b')]),n('c-branch','Branch',{BranchLogic:selected('Q2')},[block('c')])]) {
  return {schema_version:1,root:n('0','Root',{},children),questions:{Q1:choice,Q2:{...choice,text:'Continue to details?'}},blocks:{
    a:{name:'Introduction',elements:[{type:'question',question_external_id:'Q1'}],options:{}},
    b:{name:'Sales detail',elements:[{type:'question',question_external_id:'Q2'}],options:{}},
    c:{name:'Finish',elements:[],options:{}},
  }};
}
function fixture(def=definition()) {
  const document=element(), ids={}; document.createElement=element;
  const add=(id,tag='div')=>{const item=element(tag);item.id=id;ids[id]=item;document.append(item);return item;};
  ['interactive','current','walkthrough-status','error','assumptions','assumption-list','scope-empty'].forEach(id=>add('flow-'+id));
  ['continue','back','reset','expand','collapse'].forEach(id=>add('flow-'+id,'button'));
  add('flow-survey-select','select');
  const controls=add('controls');controls.className='flow-map-controls';
  const surveys=['s','other'].map(id=>{
    const map=add('map-'+id,'section');map.className='flow-survey';map.dataset.survey=id;
    const nodes={};
    function card(node,parent) {
      const item=element('details');item.id=id+'-'+node.node_id;nodes[node.node_id]=item.id;ids[item.id]=item;
      item.className='flow-node';item.dataset.flowNode=node.node_id;item.open=false;parent.append(item);
      for(const [className,text] of [['flow-node-title',node.config.ID || node.type],['flow-state','Configured'],['flow-setting','Own step description']]) {
        const child=element('span');child.className=className;child.textContent=text;item.append(child);
      }
      node.children.forEach(child=>card(child,item));
    }
    card(def.root,map);
    return {id,label:id==='s'?'Team survey':'Other survey',definition:def,nodes,targets:{}};
  });
  document.getElementById=id=>ids[id] || null;
  const controller=createController(document,{surveys},engine);
  controller.update(['s']);
  const click=id=>ids['flow-'+id].handlers.click({preventDefault(){}});
  const inputs=()=>ids['flow-current'].querySelectorAll('select');
  return {document,ids,controller,click,inputs};
}

test('walkthrough answers, Back edits and branch replay never reuse a skipped question answer',()=>{
  const f=fixture();f.click('continue');
  assert.match(f.ids['flow-current'].textContent,/Department/);
  f.inputs()[0].value='0';f.click('continue');
  assert.match(f.ids['flow-current'].textContent,/Continue to details/);
  f.inputs()[0].value='0';f.click('continue');
  assert.match(f.ids['flow-current'].textContent,/Finish/);
  f.click('back');f.click('back');
  f.inputs()[0].value='1';f.click('continue');
  assert.equal(f.ids['s-b'].dataset.flowStatus,'skipped');
  assert.match(f.ids['flow-current'].textContent,/Assume/);
  assert.doesNotMatch(f.ids['flow-current'].textContent,/Finish/);
});

test('unknown condition and unsupported step require an explicit assumption before proceeding',()=>{
  const f=fixture(definition([n('branch','Branch',{BranchLogic:selected('Q1')}),n('u','WebService'),block('c')]));
  f.click('continue');f.click('continue');
  assert.equal(f.ids['flow-error'].hidden,false);
  f.inputs()[0].value='false';f.click('continue');
  assert.match(f.ids['flow-current'].textContent,/explicit assumption/i);
  f.click('continue');assert.equal(f.ids['flow-error'].hidden,false);
  const checkbox=f.ids['flow-current'].querySelector('input');checkbox.checked=true;f.click('continue');
  assert.match(f.ids['flow-current'].textContent,/Finish/);
  assert.match(f.ids['flow-assumption-list'].textContent,/assumed/);
});

test('randomizer controls preserve the requested order and reject duplicate draws',()=>{
  const f=fixture(definition([n('r','Randomizer',{SubSet:2},[block('a'),block('c')])]));
  f.click('continue');
  assert.equal(f.inputs().length,2);
  f.inputs()[0].value='a';f.inputs()[1].value='a';f.click('continue');
  assert.equal(f.ids['flow-error'].hidden,false);
  f.inputs()[0].value='c';f.inputs()[1].value='a';f.click('continue');
  assert.match(f.ids['flow-current'].textContent,/Finish/);
  f.click('continue');assert.match(f.ids['flow-current'].textContent,/Department/);
});

test('reset and selected-survey changes clear the current walkthrough and filter the map',()=>{
  const f=fixture();f.click('continue');f.inputs()[0].value='0';f.click('continue');
  f.click('reset');assert.equal(f.ids['flow-continue'].textContent,'Start walkthrough');
  assert.equal(f.ids['s-b'].dataset.flowStatus,'configured');
  f.click('continue');f.controller.update(['other']);
  assert.equal(f.ids['map-s'].hidden,true);assert.equal(f.ids['map-other'].hidden,false);
  assert.equal(f.ids['flow-continue'].textContent,'Start walkthrough');
  assert.equal(f.ids['flow-survey-select'].value,'other');
  f.controller.update([]);assert.equal(f.ids['flow-continue'].disabled,true);
  assert.equal(f.ids['flow-scope-empty'].hidden,false);
});

test('exact search reveal opens ancestors and records link each occurrence separately',()=>{
  const f=fixture();const records=f.controller.records();
  assert.equal(records.length,12);
  assert.ok(records.some(record=>record.node.id==='s-b'));
  assert.equal(f.controller.reveal('s-b'),true);
  assert.equal(f.ids['s-b'].open,true);assert.equal(f.ids['s-b-branch'].open,true);assert.equal(f.ids['s-0'].open,true);
  assert.equal(f.ids['s-b'].focused,true);
  assert.equal(f.controller.reveal('unrelated'),false);
});

test('Back reopens an assumption or randomizer choice so it can be changed',()=>{
  const f=fixture(definition([n('r','Randomizer',{SubSet:1},[block('a'),block('c')])]));
  f.click('continue');f.inputs()[0].value='c';f.click('continue');
  f.click('back');assert.match(f.ids['flow-current'].textContent,/Draw 1/);
  f.inputs()[0].value='a';f.click('continue');assert.match(f.ids['flow-current'].textContent,/Department/);
  const unknown=fixture(definition([n('branch','Branch',{BranchLogic:selected('Q1')},[block('a')]),block('c')]));
  unknown.click('continue');unknown.inputs()[0].value='false';unknown.click('continue');
  unknown.click('back');assert.match(unknown.ids['flow-current'].textContent,/Assume this condition/);
  unknown.inputs()[0].value='true';unknown.click('continue');assert.match(unknown.ids['flow-current'].textContent,/Department/);
});

test('embedded values can resolve an unknown condition without recording an assumed result',()=>{
  const f=fixture(definition([n('branch','Branch',{BranchLogic:{LogicType:'EmbeddedField',LeftOperand:'score',Operator:'GreaterThanOrEqual',RightOperand:'0'}},[block('c')])]));
  f.click('continue');
  const inputs=f.ids['flow-current'].querySelectorAll('input');
  inputs[0].value='0';inputs[0].handlers.input();
  f.ids['flow-current'].querySelector('button').handlers.click();
  assert.match(f.ids['flow-current'].textContent,/Finish/);
  assert.equal(f.ids['flow-assumptions'].hidden,true);
  f.click('back');assert.match(f.ids['flow-current'].textContent,/Assume this condition/);
});

test('multiple selections and an explicitly empty text answer reach the next block',()=>{
  const def=definition([block('a'),block('b'),block('c')]);
  def.questions.Q1={...choice,selector:'MAVR'};
  def.questions.Q2={text:'A written note',type:'TE',selector:'SL'};
  const f=fixture(def);f.click('continue');
  f.ids['flow-current'].querySelectorAll('input')[1].checked=true;f.click('continue');
  const inputs=f.ids['flow-current'].querySelectorAll('input');inputs[1].checked=true;
  f.click('continue');assert.match(f.ids['flow-current'].textContent,/Finish/);
  f.click('back');assert.equal(f.ids['flow-current'].querySelectorAll('input')[1].checked,true);
  f.click('back');assert.equal(f.ids['flow-current'].querySelectorAll('input')[1].checked,true);
});

test('repeated blocks keep separate hypothetical answers and cannot rewrite an earlier branch',()=>{
  const f=fixture(definition([block('a'),n('branch','Branch',{BranchLogic:selected('Q1')},[block('b')]),n('a-again','Block',{ID:'a'})]));
  f.click('continue');f.inputs()[0].value='0';f.click('continue');
  f.inputs()[0].value='0';f.click('continue');
  assert.equal(f.inputs()[0].value,'unknown');
  f.inputs()[0].value='1';f.click('continue');
  assert.equal(f.ids['s-b'].dataset.flowStatus,'reached');
  assert.match(f.ids['flow-walkthrough-status'].textContent,/Scenario complete/);
  f.click('back');assert.equal(f.inputs()[0].value,'1');
  f.click('back');f.click('back');assert.equal(f.inputs()[0].value,'0');
  f.inputs()[0].value='1';f.click('continue');
  assert.equal(f.ids['s-b'].dataset.flowStatus,'skipped');
  assert.equal(f.inputs()[0].value,'unknown');
});

test('search records include embedded field settings without borrowing child card content',()=>{
  const f=fixture(definition([n('e','EmbeddedData',{EmbeddedData:[{Field:'cohort',Value:'Pilot'}]},[block('a')])]));
  const record=f.controller.records().find(item=>item.node.id==='s-e');
  assert.match(record.content,/cohort/);assert.match(record.content,/Pilot/);
  assert.doesNotMatch(record.content,/Department/);
});

test('an impossible randomizer draw stops with its reason and does not create phantom history',()=>{
  const f=fixture(definition([n('r','Randomizer',{SubSet:2},[block('a')])]));
  f.click('continue');
  assert.equal(f.ids['flow-continue'].disabled,true);
  assert.match(f.ids['flow-current'].textContent,/cannot continue/i);
  assert.equal(f.ids['flow-current'].querySelector('input'),null);
  assert.equal(f.ids['flow-back'].disabled,true);
  f.click('continue');assert.equal(f.ids['flow-back'].disabled,true);
  assert.equal(f.ids['flow-reset'].disabled,false);
});
