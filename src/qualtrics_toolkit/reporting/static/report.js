const cards=[...document.querySelectorAll('.respondent')],search=document.querySelector('#search'),
        count=document.querySelector('#count'),empty=document.querySelector('#empty'),
        choices=[...document.querySelectorAll('.question-choice')],
        toggle=document.querySelector('#question-toggle'),menu=document.querySelector('#question-menu'),
        selectedCount=document.querySelector('#selected-count'),surveySelect=document.querySelector('#survey-select');
        function filter(){const term=search.value.trim().toLowerCase(),survey=surveySelect.value,
        activeChoices=choices.filter(c=>!survey||c.closest('label').dataset.survey===survey),selected=new Set(
        activeChoices.filter(c=>c.checked).map(c=>c.value));let visible=0;
        choices.forEach(c=>c.closest('label').hidden=!!survey&&c.closest('label').dataset.survey!==survey);
        document.querySelectorAll('.question-analysis,.quality').forEach(item=>
        item.hidden=!!survey&&item.dataset.survey!==survey);
        document.querySelectorAll('#overview tr[data-survey]').forEach(item=>
        item.hidden=!!survey&&item.dataset.survey!==survey);
        cards.forEach(card=>{const answerRows=[...card.querySelectorAll('.answer')];let shownAnswers=0;
        answerRows.forEach(row=>{const show=selected.has(row.dataset.question);
        row.hidden=!show;if(show)shownAnswers+=1;});
        card.querySelector('.no-selected').hidden=shownAnswers>0;
        card.querySelector('.badge').textContent=shownAnswers+' '+(shownAnswers===1?'answer':'answers');
        const show=(!survey||card.dataset.survey===survey)&&(!term||card.dataset.search.includes(term));
        card.hidden=!show;if(show)visible+=1;});
        const eligibleCards=cards.filter(card=>!survey||card.dataset.survey===survey),
        metrics=surveySelect.selectedOptions[0].dataset,responses=Number(metrics.responses||0),
        finished=Number(metrics.finished||0);
        count.textContent=visible+' of '+eligibleCards.length;empty.classList.toggle('hidden',visible>0);
        selectedCount.textContent=selected.size===activeChoices.length?'All':selected.size+' selected';
        document.querySelector('#stat-responses').textContent=responses.toLocaleString();
        document.querySelector('#stat-questions').textContent=Number(metrics.questions||0).toLocaleString();
        document.querySelector('#stat-answers').textContent=Number(metrics.answers||0).toLocaleString();
        document.querySelector('#overview-finished').textContent=finished.toLocaleString();
        document.querySelector('#overview-completion').textContent=(responses?Math.round(finished/responses*100):0)+'%';
        document.querySelector('#overview-unanswered').textContent=Number(metrics.unanswered||0).toLocaleString();
        document.querySelector('#overview-unused-fields').textContent=Number(metrics.unusedFields||0).toLocaleString();}
        search.addEventListener('input',filter);
        surveySelect.addEventListener('change',filter);
        choices.forEach(choice=>choice.addEventListener('change',filter));
        toggle.onclick=event=>{event.stopPropagation();const opening=menu.hidden;
        menu.hidden=!opening;toggle.setAttribute('aria-expanded',String(opening));};
        menu.onclick=event=>event.stopPropagation();
        document.addEventListener('click',()=>{menu.hidden=true;
        toggle.setAttribute('aria-expanded','false');});
        function visibleChoices(){const survey=surveySelect.value;return choices.filter(c=>
        !survey||c.closest('label').dataset.survey===survey);}
        document.querySelector('#select-all').onclick=()=>{visibleChoices().forEach(c=>c.checked=true);filter();};
        document.querySelector('#clear-all').onclick=()=>{visibleChoices().forEach(c=>c.checked=false);filter();};
        document.querySelector('#expand').onclick=()=>cards.filter(c=>!c.classList.contains('hidden'))
        .forEach(c=>c.open=true);
        document.querySelector('#collapse').onclick=()=>cards.forEach(c=>c.open=false);
        filter();
