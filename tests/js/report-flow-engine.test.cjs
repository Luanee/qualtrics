const test = require('node:test');
const assert = require('node:assert/strict');
const engine = require('../../src/qualtrics/ui/static/flow-engine.js');
const {evaluateCondition: evaluate, walkFlow: walk} = engine;
const q = {text:'Department', type:'MC',selector:'SAVR',choices:{1:'Sales',2:'Engineering'},choice_order:['1','2']};
const selected = (id='Q1', choice='1') => ({LogicType:'Question',QuestionID:id,ChoiceLocator:`q://${id}/SelectableChoice/${choice}`,Operator:'Selected'});
const embedded = (value, operator='EqualTo') => ({LogicType:'EmbeddedField',LeftOperand:'score',Operator:operator,RightOperand:value});
const node = (id,type,config={},children=[]) => ({node_id:id,type,config,children});
const block = id => node(id,'Block',{ID:id});
function def(children) { return {schema_version:1,root:node('0','Root',{},children),questions:{Q1:{...q},Q2:{...q}},blocks:{a:{elements:[{type:'question',question_external_id:'Q1'}],options:{}},b:{elements:[{type:'question',question_external_id:'Q2'}],options:{}},c:{elements:[],options:{}}}}; }
const status = (result,id) => result.steps.find(s=>s.node_id===id)?.status;
test('condition evaluator recognizes choices, missing and unsupported locators',()=>{
 assert.equal(evaluate(selected(),{answers:{Q1:'1'}}),true);
 assert.equal(evaluate(selected(),{answers:{Q1:[]}}),false);
 assert.equal(evaluate(selected(),{answers:{}}),null);
 assert.equal(evaluate({...selected(),ChoiceLocator:'q://Q1/SelectableAnswer/1'},{answers:{Q1:'1'}}),null);
 assert.equal(evaluate({...selected(),Operator:'Custom'},{answers:{Q1:'1'}}),null);
});
test('nested If and BooleanExpression obey explicit AND/OR tri-state logic',()=>{
 const tree={Type:'BooleanExpression',0:{Type:'If',0:selected(),1:{...selected('Q2'),Conjuction:'Or'}}};
 assert.equal(evaluate(tree,{answers:{Q1:'2',Q2:'1'}}),true);
 assert.equal(evaluate(tree,{answers:{Q1:'2'}}),null);
 assert.equal(evaluate({...tree,0:{Type:'If',0:selected(),1:{...selected('Q2'),Conjuction:'And'}}},{answers:{Q1:'2'}}),false);
 assert.equal(evaluate({Type:'If',0:selected(),1:selected('Q2')},{answers:{Q1:'1',Q2:'1'}}),null);
});
test('embedded comparisons distinguish missing, empty and zero',()=>{
 assert.equal(evaluate(embedded(''),{embedded:{score:''}}),true);
 assert.equal(evaluate(embedded(''),{embedded:{}}),null);
 assert.equal(evaluate(embedded('0','GreaterThanOrEqual'),{embedded:{score:0}}),true);
 assert.equal(evaluate(embedded('0','GreaterThanOrEqual'),{embedded:{score:''}}),null);
 assert.equal(evaluate(embedded('0','GreaterThanOrEqual'),{embedded:{score:'bad'}}),null);
});
test('input descriptions expose source labels and choices',()=>{
 const inputs=engine.conditionInputs(selected(),{questions:{Q1:q}});
 assert.equal(inputs[0].key,'Q1'); assert.equal(inputs[0].label,'Department');
 assert.equal(inputs[0].choices[0].label,'Sales');
 assert.match(engine.describeCondition(selected(),{questions:{Q1:q}}),/Sales/);
});
test('branches rejoin their following sibling and nested EndSurvey terminates route',()=>{
 const d=def([block('a'),node('branch','Branch',{BranchLogic:selected()},[block('b')]),block('c')]);
 let r=walk(d,{answers:{Q1:'1'},completed:['a','b']}); assert.equal(r.pending.node_id,'c');
 r=walk(d,{answers:{Q1:'2'},completed:['a']}); assert.equal(status(r,'b'),'skipped'); assert.equal(r.pending.node_id,'c');
 d.root.children[1].children.push(node('end','EndSurvey'));
 r=walk(d,{answers:{Q1:'1'},completed:['a','b']}); assert.equal(r.ended,true); assert.equal(status(r,'c'),'skipped');
});
test('only completed reached blocks expose answers and replay rejects stale completion suffix',()=>{
 const d=def([block('a'),node('branch','Branch',{BranchLogic:selected()},[block('b')]),node('later','Branch',{BranchLogic:selected('Q2')},[block('c')])]);
 let r=walk(d,{answers:{Q1:'1',Q2:'1'},completed:[]}); assert.equal(r.pending.node_id,'a');
 r=walk(d,{answers:{Q1:'2',Q2:'1'},completed:['a','b'],choices:{later:true}});
 assert.equal(r.pending.node_id,'later'); assert.equal(r.pending.kind,'condition');
});
test('randomizers require exact ordered unique eligible choices and unknown eligibility pauses',()=>{
 const d=def([node('r','Randomizer',{SubSet:1},[block('a'),node('no','Branch',{BranchLogic:embedded('yes')},[block('b')]),block('c')])]);
 let r=walk(d,{}); assert.equal(r.pending.node_id,'no');
 r=walk(d,{embedded:{score:'no'}}); assert.equal(r.pending.kind,'randomizer'); assert.deepEqual(r.pending.options.map(o=>o.value),['a','c']);
 for(const choice of [['a','a'],['no'],[]]) assert.equal(walk(d,{embedded:{score:'no'},choices:{r:choice}}).pending.kind,'randomizer');
 r=walk(d,{embedded:{score:'no'},choices:{r:['c']}}); assert.equal(r.pending.node_id,'c'); assert.equal(status(r,'a'),'skipped');
});
test('embedded assignments and unsupported nodes require explicit assumptions',()=>{
 const d=def([node('e','EmbeddedData',{EmbeddedData:[{Field:'score',Value:'0',Type:'Custom'}]}),node('u','WebService'),block('c')]);
 let r=walk(d,{}); assert.equal(r.embedded.score,'0'); assert.equal(r.pending.kind,'unsupported');
 r=walk(d,{choices:{u:true}}); assert.equal(r.pending.node_id,'c'); assert.equal(r.assumptions.length,1);
});
test('question display/skip and block loops stop before offering ordinary block answers',()=>{
 const d=def([block('a')]); d.questions.Q1.skip_logic=true;
 assert.equal(walk(d,{}).pending.kind,'unsupported');
 assert.equal(walk(d,{choices:{a:true}}).pending.kind,'block');
});
test('malformed children pause safely, and unknown question types do not get fake answer controls',()=>{
 const malformed=def([]); malformed.root.children={bad:true};
 assert.equal(walk(malformed,{}).pending.kind,'unsupported');
 const d=def([block('a')]); d.questions.Q1.type='Matrix';
 assert.deepEqual(walk(d,{choices:{a:true}}).pending.inputs,[]);
});
test('randomizer selection order is respected and dynamic assignments remain unknown',()=>{
 const d=def([node('r','Randomizer',{SubSet:2},[block('a'),block('c')])]);
 const r=walk(d,{choices:{r:['c','a']},completed:['c']}); assert.equal(r.pending.node_id,'a');
 const dynamic=def([node('e','EmbeddedData',{EmbeddedData:[{Field:'score',Value:'${q://Q1/ChoiceTextEntryValue}',Type:'Custom'}]}),node('b','Branch',{BranchLogic:embedded('yes')})]);
 assert.equal(walk(dynamic,{embedded:{score:'yes'},choices:{e:true}}).pending.kind,'condition');
});
test('unsupported selectors and missing choices are unknown, explicit blank is a supplied answer',()=>{
 assert.equal(evaluate(selected(),{answers:{Q1:'1'}},{questions:{Q1:{...q,selector:'Unknown'}}}),null);
 assert.equal(evaluate(selected('Q1','9'),{answers:{Q1:'9'}},{questions:{Q1:q}}),null);
 assert.equal(evaluate({...selected(),Operator:'NotSelected'},{answers:{Q1:''}},{questions:{Q1:q}}),true);
});
test('selector prefixes alone do not establish supported semantics',()=>{
 assert.equal(evaluate(selected(),{answers:{Q1:'1'}},{questions:{Q1:{...q,selector:'SACustom'}}}),null);
 const d=def([block('a')]); d.questions.Q1={text:'Form',type:'TE',selector:'FORM'};
 assert.equal(walk(d,{}).pending.kind,'unsupported');
 assert.deepEqual(walk(d,{choices:{a:true}}).pending.inputs,[]);
});
test('condition descriptions bound excessive nesting',()=>{
 let logic=selected(); for(let i=0;i<1000;i++) logic={Type:'If',0:logic};
 assert.match(engine.describeCondition(logic,{questions:{Q1:q}}),/Unknown condition/);
});
test('QSF BlockRandomizer uses explicit scenario selection',()=>{
 const d=def([node('r','BlockRandomizer',{SubSet:1},[block('a'),block('c')])]);
 assert.equal(walk(d,{}).pending.kind,'randomizer');
 assert.equal(walk(d,{choices:{r:['c']}}).pending.node_id,'c');
});
test('descriptive text and known disabled block defaults are ordinary block content',()=>{
 const d=def([block('a')]); d.questions.INTRO={text:'Welcome',type:'DB',selector:'TB'};
 d.blocks.a.elements.unshift({type:'question',question_external_id:'INTRO'});
 d.blocks.a.options={Looping:'None',RandomizeQuestions:'false'};
 let r=walk(d,{}); assert.equal(r.pending.kind,'block'); assert.deepEqual(r.pending.inputs.map(i=>i.key),['Q1']);
 d.blocks.a.options.RandomizeQuestions='None'; assert.equal(walk(d,{}).pending.kind,'block');
 d.blocks.a.options.Looping='Unexpected'; assert.equal(walk(d,{}).pending.kind,'unsupported');
});
test('human descriptions preserve expression grouping and use readable operators',()=>{
 const logic={Type:'BooleanExpression',0:{Type:'If',0:selected(),1:{...selected('Q2'),Operator:'NotSelected',Conjuction:'Or'}},1:{...embedded('yes'),Conjuction:'And'}};
 assert.equal(engine.describeCondition(logic,{questions:{Q1:q,Q2:q}}),'(Department: Sales is selected OR Department: Sales is not selected) AND score equals yes');
});
test('repeated block answers preserve earlier branch routing and later occurrence overrides',()=>{
 const d=def([block('a'),node('branch','Branch',{BranchLogic:selected()},[block('b')]),node('again','Block',{ID:'a'}),node('later','Branch',{BranchLogic:selected()},[block('c')])]);
 const scenario={completed:['a','b','again'],blockAnswers:{a:{Q1:'1'},b:{Q2:'1'},again:{Q1:'2'}}};
 let r=walk(d,scenario);
 assert.equal(status(r,'b'),'reached'); assert.equal(status(r,'c'),'skipped');
 assert.equal(r.answers.Q1,'2'); assert.deepEqual(r.completed,['a','b','again']);
 assert.equal(r.blockAnswers.a.Q1,'1'); assert.equal(r.blockAnswers.again.Q1,'2');
 r=walk(d,{...scenario,blockAnswers:{...scenario.blockAnswers,a:{Q1:'2'}}});
 assert.equal(status(r,'b'),'skipped'); assert.equal(r.pending.node_id,'again');
 assert.deepEqual(r.completed,['a']); assert.equal(r.blockAnswers.again,undefined);
});
test('ambiguous legacy question answers cannot silently route repeated blocks',()=>{
 const d=def([block('a'),node('branch','Branch',{BranchLogic:selected()},[block('b')]),node('again','Block',{ID:'a'})]);
 const r=walk(d,{answers:{Q1:'1'},completed:['a']});
 assert.equal(r.pending.kind,'condition'); assert.equal(r.pending.node_id,'branch');
 assert.equal(r.answers.Q1,undefined);
});
test('immutable definition errors explicitly disallow continuation assumptions',()=>{
 assert.equal(walk(null,{}).pending.canContinue,false);
 const malformed=def([]); malformed.root.children='bad';
 assert.equal(walk(malformed,{}).pending.canContinue,false);
 for(const count of [2,-1,1.5,'bad']) {
  const d=def([node('r','BlockRandomizer',{SubSet:count},[block('a')])]);
  const r=walk(d,{choices:{r:true}});
  assert.equal(r.pending.kind,'unsupported'); assert.equal(r.pending.canContinue,false);
 }
 const ordinary=walk(def([node('u','WebService')]),{});
 assert.notEqual(ordinary.pending.canContinue,false);
});
