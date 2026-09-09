/* Accessible offline map and hypothetical walkthrough; all labels use textContent. */
(function (root) {
  'use strict';
  const clone = value => JSON.parse(JSON.stringify(value));
  const fresh = () => ({answers:{}, blockAnswers:{}, embedded:{}, choices:{}, completed:[]});
  const owns = (object, key) => Object.prototype.hasOwnProperty.call(object, key);

  function createController(document, payload, engine) {
    const $ = id => document.getElementById('flow-' + id);
    const all = selector => [...document.querySelectorAll(selector)];
    const surveys = payload.surveys || [];
    let currentSurvey = null, started = false, scenario = fresh(), history = [], result = null, readInputs = [];
    const node = (tag, className, text) => {
      const element = document.createElement(tag);
      if (className) element.className = className;
      if (text !== undefined) element.textContent = text;
      return element;
    };
    const addOption = (select, value, label) => {
      const option = node('option', '', label); option.value = String(value); select.append(option);
    };
    function selectControl(id, label, options, value = '') {
      const wrap = node('div', 'flow-input'), select = node('select'); select.id = id;
      const caption = node('label', '', label); caption.setAttribute('for', id);
      options.forEach(option => addOption(select, option.value, option.label)); select.value = value;
      wrap.append(caption, select); $('current').append(wrap); return select;
    }
    const findNode = (rootNode, id) => {
      if (rootNode.node_id === id) return rootNode;
      for (const child of rootNode.children || []) { const found = findNode(child, id); if (found) return found; }
      return null;
    };
    const titleFor = item => item ? currentSurvey.definition.blocks?.[item.config?.ID]?.name
      || item.config?.Description || ({Root:'Survey start', Block:'Question block', Standard:'Question block', Branch:'Branch', Group:'Group', Randomizer:'Randomizer', BlockRandomizer:'Randomizer', EndSurvey:'Survey ending', EmbeddedData:'Embedded data', WebService:'Web service', Authenticator:'Authenticator', Quota:'Quota', ReferenceSurvey:'Referenced survey'}[item.type]) || item.type : 'Survey flow';
    function reset() {
      started = false; scenario = fresh(); history = []; result = null; render();
    }
    function openAncestors(target, focus = false) {
      for (let ancestor = target; ancestor; ancestor = ancestor.parentElement) {
        if (ancestor.tagName === 'DETAILS') ancestor.open = true;
      }
      if (focus) { target.setAttribute('tabindex', '-1'); target.focus(); target.scrollIntoView({block:'nearest', behavior:'smooth'}); }
    }
    function markMap() {
      for (const survey of surveys) {
        for (const [id, anchor] of Object.entries(survey.nodes)) {
          const element = document.getElementById(anchor); if (!element) continue;
          const step = started && survey === currentSurvey ? result?.steps.find(item => item.node_id === id) : null;
          const pending = step?.status === 'pending' && result?.pending?.node_id === id;
          const state = !step ? 'configured' : pending ? 'pending' : step.status === 'pending' ? 'unreached' : step.status;
          const labels = {configured:'Configured', reached:'Reached', skipped:'Skipped', pending:'Pending', unreached:'Not reached'};
          element.dataset.flowStatus = state;
          const badge = element.querySelector('.flow-state'); if (badge) { badge.textContent = labels[state] || state; badge.title = step?.reason || ''; }
          if (pending) openAncestors(element);
        }
      }
    }
    function renderAnswer(input, index) {
      const occurrence = result.pending.node_id;
      const targetValues = draft => input.source === 'embedded' ? draft.embedded : (draft.blockAnswers[occurrence] ||= {});
      const values = input.source === 'embedded' ? scenario.embedded : (scenario.blockAnswers[occurrence] || {});
      const supplied = owns(values, input.key), value = values[input.key];
      const id = 'flow-answer-' + index, choices = input.choices || [];
      if (input.kind === 'choice') {
        const options = [{value:'unknown',label:'Not supplied (unknown)'}, {value:'blank',label:'No option selected (explicit answer)'},
          ...choices.map((choice, i) => ({value:String(i),label:choice.label}))];
        const selected = supplied ? (value === '' ? 'blank' : String(choices.findIndex(choice => choice.value === value))) : 'unknown';
        const control = selectControl(id, input.label, options, selected);
        readInputs.push(draft => {
          const target = targetValues(draft);
          if (control.value === 'unknown') delete target[input.key];
          else target[input.key] = control.value === 'blank' ? '' : choices[Number(control.value)]?.value;
        });
      } else if (input.kind === 'multiple') {
        const fieldset = node('fieldset', 'flow-input'); fieldset.append(node('legend', '', input.label));
        const selected = Array.isArray(value) ? value : [];
        const boxes = choices.map((choice, i) => {
          const label = node('label', 'flow-check'), box = node('input'); box.type = 'checkbox';box.id = id + '-' + i;
          box.checked = selected.includes(choice.value);label.append(box, node('span','',choice.label));fieldset.append(label);
          return {box, value:choice.value};
        });
        const empty = node('input');empty.type = 'checkbox';empty.checked = supplied && selected.length === 0;
        const blank = node('label','flow-check');blank.append(empty,node('span','','Explicitly no choices selected'));fieldset.append(blank);
        boxes.forEach(({box}) => box.addEventListener('change', () => { if (box.checked) empty.checked = false; }));
        empty.addEventListener('change', () => { if (empty.checked) boxes.forEach(({box}) => { box.checked = false; }); });
        $('current').append(fieldset);
        readInputs.push(draft => {
          const chosen = boxes.filter(({box}) => box.checked).map(item => item.value);
          const target = targetValues(draft);
          if (chosen.length || empty.checked) target[input.key] = chosen; else delete target[input.key];
        });
      } else {
        const wrap = node('div','flow-input'), caption = node('label','',input.label), control = node('input');
        caption.setAttribute('for',id);control.id=id;control.type=input.kind === 'number' ? 'number' : 'text';
        control.value=supplied ? String(value) : '';control.placeholder='Not supplied (unknown)';
        const explicit=node('input');explicit.type='checkbox';explicit.checked=supplied;
        const checkbox=node('label','flow-check');checkbox.append(explicit,node('span','','Use this value, including an empty value'));
        control.addEventListener('input',()=>{explicit.checked=true;});wrap.append(caption,control,checkbox);$('current').append(wrap);
        readInputs.push(draft=>{
          const target=targetValues(draft);
          if(explicit.checked) target[input.key]=control.value; else delete target[input.key];
        });
      }
    }
    function render() {
      readInputs=[]; $('current').replaceChildren(); $('error').hidden=true;
      $('continue').disabled=!currentSurvey; $('back').disabled=history.length === 0; $('reset').disabled=!started;
      $('continue').textContent=started ? 'Continue' : 'Start walkthrough';
      if (!currentSurvey) {
        $('walkthrough-status').textContent='Select a survey with an available flow definition to begin.';
        $('assumptions').hidden=true; markMap(); return;
      }
      if (!started) {
        $('walkthrough-status').textContent='Ready to explore ' + currentSurvey.label + '.';
        $('current').append(node('p','flow-note','Expand any map card to inspect its settings and questions. Start when you are ready to choose hypothetical answers.'));
        $('assumptions').hidden=true; markMap(); return;
      }
      result=engine.walkFlow(currentSurvey.definition,scenario);
      // Keep only reached occurrence answers and the current draft shown by Back.
      // A later appearance of the same question must have an independent answer.
      const pendingDraft=result.pending?.kind === 'block' ? scenario.blockAnswers[result.pending.node_id] : null;
      scenario.blockAnswers=clone(result.blockAnswers || {});
      if(pendingDraft) scenario.blockAnswers[result.pending.node_id]=pendingDraft;
      scenario.completed=[...(result.completed || [])];
      scenario.answers=clone(result.answers || {});
      const assumptions=[...(result.assumptions || [])];
      // Keep randomizer order visible even if the engine only records rule assumptions.
      for(const [id, order] of Object.entries(scenario.choices)) {
        if(Array.isArray(order) && result.steps.some(step=>step.node_id===id && step.status==='reached')) {
          assumptions.push('Randomizer ' + id + ': scenario order ' + order.map(child=>titleFor(findNode(currentSurvey.definition.root,child))).join(' → '));
        }
      }
      $('assumptions').hidden=assumptions.length === 0;
      $('assumption-list').replaceChildren(...assumptions.map(text=>node('li','',text)));
      markMap();
      const pending=result.pending;
      if(!pending) {
        $('continue').disabled=true;
        $('walkthrough-status').textContent=result.ended ? 'Scenario reached a survey ending.' : 'Scenario complete: no further configured steps.';
        $('current').append(node('p','flow-complete','Use Back to change earlier answers, or Reset to try another scenario.'));
        return;
      }
      const item=findNode(currentSurvey.definition.root,pending.node_id);
      const heading=node('h4','flow-current-title',titleFor(item));heading.setAttribute('tabindex','-1');
      const link=node('a','flow-current-link','Show this step in the map');link.href='#'+currentSurvey.nodes[pending.node_id];
      link.addEventListener('click',event=>{event.preventDefault();reveal(currentSurvey.nodes[pending.node_id]);});
      $('current').append(heading,link,node('p','flow-pending-reason',pending.reason));
      const completedCount=(result.completed || scenario.completed).length;
      $('walkthrough-status').textContent=`${completedCount} ${completedCount === 1 ? 'block' : 'blocks'} continued · ${pending.kind === 'block' ? 'Hypothetical answers' : 'Scenario choice required'}`;
      if(pending.canContinue === false) {
        $('continue').disabled=true;
        $('walkthrough-status').textContent='The scenario cannot continue with this definition.';
        $('current').append(node('p','flow-note','This step cannot continue. Inspect its definition, use Back to revise earlier choices, or Reset the scenario.'));
        return;
      }
      if(pending.kind === 'block') {
        (pending.inputs || []).forEach(renderAnswer);
        if(!pending.inputs?.length) $('current').append(node('p','flow-note','There are no supported answer inputs for this step. Continue to follow the configured route.'));
      } else if(pending.kind === 'condition') {
        const embeddedInputs=(pending.inputs || []).filter(input=>input.source === 'embedded');
        if(embeddedInputs.length) {
          $('current').append(node('p','flow-note','Supply hypothetical embedded values and recheck, or make an explicit condition assumption.'));
          embeddedInputs.forEach(renderAnswer);
          const recheck=node('button','','Recheck with these values');recheck.type='button';
          recheck.addEventListener('click',()=>{
            const draft=clone(scenario);readInputs.slice(0,embeddedInputs.length).forEach(read=>read(draft));
            history.push(clone(scenario));scenario=draft;render();
          });$('current').append(recheck);
        }
        $('current').append(node('p','flow-note','Unreached question answers cannot decide this condition. To explore further, label an assumption below.'));
        const select=selectControl('flow-condition-choice','Assume this condition',[
          {value:'',label:'Choose an explicit assumption'}, {value:'true',label:'Assume true — enter this branch'}, {value:'false',label:'Assume false — skip this branch'},
        ], typeof scenario.choices[pending.node_id] === 'boolean' ? String(scenario.choices[pending.node_id]) : '');
        readInputs.push(draft=>{
          if(select.value !== 'true' && select.value !== 'false') throw Error('Choose true or false explicitly before continuing.');
          draft.choices[pending.node_id]=select.value === 'true';
        });
      } else if(pending.kind === 'randomizer') {
        $('current').append(node('p','flow-note',`Choose ${pending.count} eligible ${pending.count === 1 ? 'step' : 'steps'} in the order this scenario should follow. This does not reproduce real allocation history.`));
        const controls=Array.from({length:Math.max(0,Math.min(500,pending.count || 0))},(_,index)=>selectControl('flow-draw-'+index,`Draw ${index+1}`,
          [{value:'',label:'Choose a step'},...(pending.options || [])],scenario.choices[pending.node_id]?.[index] || ''));
        readInputs.push(draft=>{
          const order=controls.map(control=>control.value);
          if(order.length !== pending.count || order.some(value=>!value) || new Set(order).size !== order.length) throw Error('Choose each required step once, in the order to follow.');
          draft.choices[pending.node_id]=order;
        });
      } else {
        const label=node('label','flow-check flow-assumption-choice'),check=node('input');check.type='checkbox';
        label.append(check,node('span','','For this scenario, assume this unsupported step allows continuation.'));
        $('current').append(node('p','flow-note','An explicit assumption is required. You can stop here and inspect the map without assuming a result.'),label);
        readInputs.push(draft=>{if(!check.checked) throw Error('Confirm the continuation assumption before proceeding.');draft.choices[pending.node_id]=true;});
      }
    }
    function proceed() {
      if(!currentSurvey) return;
      if(!started) { started=true;render();return; }
      if(!result?.pending || result.pending.canContinue === false) return;
      const draft=clone(scenario);
      try { readInputs.forEach(read=>read(draft)); }
      catch(error) { $('error').textContent=error.message;$('error').hidden=false;return; }
      const pending=result.pending;
      // Snapshot includes edits at this pending step, before advancing. Back
      // restores this exact prefix; later block answers and choices disappear.
      history.push(clone(pending.kind === 'block' ? draft : scenario));
      if(pending.kind === 'block') draft.completed=[...(result.completed || scenario.completed),pending.node_id];
      scenario=draft;render();
    }
    function update(selectedSurveyIds) {
      const selected=new Set(selectedSurveyIds), available=surveys.filter(survey=>selected.has(survey.id));
      all('.flow-survey').forEach(map=>{map.hidden=!selected.has(map.dataset.survey);});
      $('scope-empty').hidden=selected.size>0;
      const previous=currentSurvey?.id;
      $('survey-select').replaceChildren();available.forEach(survey=>addOption($('survey-select'),survey.id,survey.label));
      currentSurvey=available.find(survey=>survey.id===previous) || available[0] || null;
      $('survey-select').disabled=available.length<2; $('survey-select').value=currentSurvey?.id || '';
      if(currentSurvey?.id !== previous) reset();
    }
    function reveal(targetId) {
      const target=document.getElementById(String(targetId).replace(/^#/,''));
      if(!target || !all('.flow-node').includes(target)) return false;
      openAncestors(target,true);return true;
    }
    function records() {
      const rows=[];
      for(const survey of surveys) {
        function visit(item) {
          const target=document.getElementById(survey.nodes[item.node_id]);
          if(target) {
            const block=survey.definition.blocks?.[item.config?.ID];
            const questionText=(block?.elements || []).map(element=>survey.definition.questions?.[element.question_external_id]?.text || element.question_external_id || '').join(' ');
            const condition=item.config?.BranchLogic ? engine.describeCondition(item.config.BranchLogic,survey.definition) : '';
            const settings=(item.config?.EmbeddedData || []).map(entry=>[entry.Field,entry.Value,entry.Description].filter(value=>value !== undefined).join(' ')).join(' · ');
            rows.push({scope:'Flow',node:target,title:block?.name || item.config?.Description || item.type,
              content:[item.type,item.external_id,item.config?.ID,condition,questionText,settings].filter(Boolean).join(' · '),context:survey.label});
          }
          (item.children || []).forEach(visit);
        }
        visit(survey.definition.root);
      }
      return rows;
    }
    $('interactive').hidden=false;all('.flow-map-controls').forEach(control=>{control.hidden=false;});
    $('continue').addEventListener('click',proceed);
    $('back').addEventListener('click',()=>{if(history.length) {scenario=history.pop();render();}});
    $('reset').addEventListener('click',reset);
    $('survey-select').addEventListener('change',()=>{currentSurvey=surveys.find(survey=>survey.id===$('survey-select').value) || null;reset();});
    $('expand').addEventListener('click',()=>all('.flow-survey').filter(map=>!map.hidden).forEach(map=>map.querySelectorAll('details').forEach(detail=>{detail.open=true;})));
    $('collapse').addEventListener('click',()=>all('.flow-survey').filter(map=>!map.hidden).forEach(map=>map.querySelectorAll('.flow-node').forEach(detail=>{detail.open=false;})));
    render();
    return {update,reveal,records};
  }
  let controller;
  const api={createController,
    init() {
      if(controller) return controller;
      const element=root.document?.getElementById('flow-data');
      if(element && root.QualtricsFlowEngine) {
        try { controller=createController(root.document,JSON.parse(element.textContent),root.QualtricsFlowEngine); }
        catch(error) { const status=root.document.getElementById('flow-walkthrough-status');if(status) status.textContent='The walkthrough could not be initialized. The configured map remains available.'; }
      }
      return controller;
    },
    update(ids) { api.init()?.update(ids); },reveal(id) { return api.init()?.reveal(id) || false; },records() { return api.init()?.records() || []; },
  };
  if(typeof module === 'object' && module.exports) module.exports=api;
  else { root.ReportFlow=api;api.init(); }
})(typeof window !== 'undefined' ? window : globalThis);
