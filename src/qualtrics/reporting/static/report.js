const cards=[...document.querySelectorAll('.respondent')],search=document.querySelector('#search'),
        count=document.querySelector('#count'),empty=document.querySelector('#empty'),
        choices=[...document.querySelectorAll('.question-choice')],
        toggle=document.querySelector('#question-toggle'),menu=document.querySelector('#question-menu'),
        selectedCount=document.querySelector('#selected-count'),
        surveyChoices=[...document.querySelectorAll('.survey-choice')],
        surveyToggle=document.querySelector('#survey-toggle'),surveyMenu=document.querySelector('#survey-menu'),
        surveySelectedCount=document.querySelector('#survey-selected-count');
        function selectedSurveys(){return new Set(surveyChoices.filter(choice=>choice.checked).map(choice=>choice.value));}
        function aggregateMetrics(surveys){const names=['responses','finished','questions','answers','unanswered','unusedFields'];
        return surveyChoices.filter(choice=>surveys.has(choice.value)).reduce((totals,choice)=>{
        names.forEach(name=>totals[name]+=Number(choice.dataset[name]||0));return totals;},
        Object.fromEntries(names.map(name=>[name,0])));}
        function updateCatalogGroups(surveys){let visibleCoverageGroups=0,visibleAnalyticsGroups=0;
        document.querySelectorAll('.catalog-group').forEach(group=>{const rows=[...group.querySelectorAll('.survey-occurrence')];
        rows.forEach(row=>row.hidden=!surveys.has(row.dataset.survey));
        const visibleRows=rows.filter(row=>surveys.has(row.dataset.survey)),
        occurrenceCount=new Set(visibleRows.map(row=>row.dataset.survey)).size;
        group.hidden=visibleRows.length===0;
        const label=occurrenceCount===1?'survey occurrence':'survey occurrences';
        group.querySelector('.occurrence-count').textContent=occurrenceCount+' '+label;
        if(!group.hidden&&group.closest('#question-coverage'))visibleCoverageGroups+=1;
        if(!group.hidden&&group.closest('#question-analytics'))visibleAnalyticsGroups+=1;});
        document.querySelector('#coverage-count').textContent=visibleCoverageGroups+' canonical '+
        (visibleCoverageGroups===1?'question':'questions');
        document.querySelector('#analytics-count').textContent=visibleAnalyticsGroups+' canonical '+
        (visibleAnalyticsGroups===1?'question':'questions');}
        function filter(){const term=search.value.trim().toLowerCase(),surveys=selectedSurveys(),
        activeChoices=choices.filter(c=>surveys.has(c.closest('label').dataset.survey)),selected=new Set(
        activeChoices.filter(c=>c.checked).map(c=>c.value));let visible=0;
        choices.forEach(c=>c.closest('label').hidden=!surveys.has(c.closest('label').dataset.survey));
        document.querySelectorAll('.quality').forEach(item=>item.hidden=!surveys.has(item.dataset.survey));
        updateCatalogGroups(surveys);
        cards.forEach(card=>{const answerRows=[...card.querySelectorAll('.answer')];let shownAnswers=0;
        answerRows.forEach(row=>{const show=selected.has(row.dataset.question);
        row.hidden=!show;if(show)shownAnswers+=1;});
        card.querySelector('.no-selected').hidden=shownAnswers>0;
        card.querySelector('.badge').textContent=shownAnswers+' '+(shownAnswers===1?'answer':'answers');
        const show=surveys.has(card.dataset.survey)&&(!term||card.dataset.search.includes(term));
        card.hidden=!show;if(show)visible+=1;});
        const eligibleCards=cards.filter(card=>surveys.has(card.dataset.survey)),metrics=aggregateMetrics(surveys),
        responses=metrics.responses,finished=metrics.finished;
        count.textContent=visible+' of '+eligibleCards.length;empty.classList.toggle('hidden',visible>0);
        selectedCount.textContent=selected.size===activeChoices.length?'All':selected.size+' selected';
        surveySelectedCount.textContent=surveys.size===surveyChoices.length?'All':
        surveys.size===0?'None':surveys.size+' selected';
        document.querySelector('#stat-responses').textContent=responses.toLocaleString();
        document.querySelector('#stat-questions').textContent=metrics.questions.toLocaleString();
        document.querySelector('#stat-answers').textContent=metrics.answers.toLocaleString();
        document.querySelector('#overview-finished').textContent=finished.toLocaleString();
        document.querySelector('#overview-completion').textContent=(responses?Math.round(finished/responses*100):0)+'%';
        document.querySelector('#overview-unanswered').textContent=metrics.unanswered.toLocaleString();
        document.querySelector('#overview-unused-fields').textContent=metrics.unusedFields.toLocaleString();}
        search.addEventListener('input',filter);
        surveyChoices.forEach(choice=>choice.addEventListener('change',filter));
        choices.forEach(choice=>choice.addEventListener('change',filter));
        toggle.onclick=event=>{event.stopPropagation();const opening=menu.hidden;
        menu.hidden=!opening;surveyMenu.hidden=true;toggle.setAttribute('aria-expanded',String(opening));
        surveyToggle.setAttribute('aria-expanded','false');};
        surveyToggle.onclick=event=>{event.stopPropagation();const opening=surveyMenu.hidden;
        surveyMenu.hidden=!opening;menu.hidden=true;surveyToggle.setAttribute('aria-expanded',String(opening));
        toggle.setAttribute('aria-expanded','false');};
        menu.onclick=event=>event.stopPropagation();surveyMenu.onclick=event=>event.stopPropagation();
        document.addEventListener('click',()=>{menu.hidden=true;surveyMenu.hidden=true;
        toggle.setAttribute('aria-expanded','false');surveyToggle.setAttribute('aria-expanded','false');});
        function visibleChoices(){const surveys=selectedSurveys();return choices.filter(c=>
        surveys.has(c.closest('label').dataset.survey));}
        document.querySelector('#survey-select-all').onclick=()=>{
        surveyChoices.forEach(choice=>choice.checked=true);filter();};
        document.querySelector('#survey-clear').onclick=()=>{
        surveyChoices.forEach(choice=>choice.checked=false);filter();};
        document.querySelector('#select-all').onclick=()=>{visibleChoices().forEach(c=>c.checked=true);filter();};
        document.querySelector('#clear-all').onclick=()=>{visibleChoices().forEach(c=>c.checked=false);filter();};
        document.querySelector('#expand').onclick=()=>cards.filter(c=>!c.classList.contains('hidden'))
        .forEach(c=>c.open=true);
        document.querySelector('#collapse').onclick=()=>cards.forEach(c=>c.open=false);
        filter();
