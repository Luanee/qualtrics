/* Pure, offline scenario evaluator. Unknown definitions never imply false. */
(function (root, factory) {
    var api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.QualtricsFlowEngine = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';
    var own = function (o, k) { return o != null && Object.prototype.hasOwnProperty.call(o, k); };
    function parts(logic) {
        if (!logic || typeof logic !== 'object' || Array.isArray(logic)) return [];
        return Object.keys(logic).filter(function (k) { return /^\d+$/.test(k); })
            .sort(function (a, b) { return Number(a) - Number(b); }).map(function (k) { return logic[k]; });
    }
    function choiceQuestion(q) { return q && q.type === 'MC' && ['SAVR','SAHR','SACOL','MAVR','MAHR','MACOL','DL'].includes(q.selector); }
    function disabledOption(value) { return value == null || value === false || value === 0 || value === '' || value === 'false' || value === 'False' || value === 'None' || value === 'none' || value === '0'; }
    function answerQuestion(q) { return choiceQuestion(q) || q && q.type === 'TE' && ['SL','ML'].includes(q.selector); }
    function questionInput(id, definition) {
        var q = (definition && definition.questions || {})[id];
        if (!q) return {key:id, source:'question', label:id, kind:'text'};
        var result = {key:id, source:'question', label:q.text || id, kind:'text'};
        if (choiceQuestion(q)) {
            result.kind = /^MA/.test(q.selector) ? 'multiple' : 'choice';
            result.choices = (q.choice_order || Object.keys(q.choices || {})).map(function (key) {
                return {value:String(key), label:String(q.choices[key] || key)};
            });
        }
        return result;
    }
    function embeddedKey(logic) {
        var key = logic.Field || logic.LeftOperand;
        if (typeof key !== 'string') return null;
        if (key.indexOf('ed://') === 0) return key.slice(5);
        return key.indexOf('://') < 0 ? key : null;
    }
    function conditionInputs(logic, definition) {
        var result = [], seen = Object.create(null);
        function visit(l, depth) {
            if (!l || typeof l !== 'object' || depth > 100) return;
            var input;
            if (l.LogicType === 'Question' && l.QuestionID) input = questionInput(l.QuestionID, definition);
            if (l.LogicType === 'EmbeddedField' && embeddedKey(l) !== null) input = {key:embeddedKey(l), source:'embedded', label:embeddedKey(l), kind:/Greater|Less/.test(l.Operator || '') ? 'number' : 'text'};
            if (input && !seen[input.source + ':' + input.key]) { result.push(input); seen[input.source + ':' + input.key] = true; }
            parts(l).forEach(function (child) { visit(child, depth + 1); });
        }
        visit(logic, 0); return result;
    }
    function evaluateCondition(logic, context, definition) {
        context = context || {};
        function evaluate(l, depth) {
            if (!l || typeof l !== 'object' || depth > 100) return null;
            if (l.Type === 'BooleanExpression' || l.Type === 'If') {
                var children = parts(l);
                if (!children.length) return null;
                var result = evaluate(children[0], depth + 1);
                for (var i = 1; i < children.length; i++) {
                    var op = children[i].Conjuction || children[i].Conjunction || l.Conjuction || l.Conjunction;
                    var next = evaluate(children[i], depth + 1);
                    if (typeof op !== 'string') return null;
                    if (op.toLowerCase() === 'and') result = result === false || next === false ? false : result === null || next === null ? null : true;
                    else if (op.toLowerCase() === 'or') result = result === true || next === true ? true : result === null || next === null ? null : false;
                    else return null;
                }
                return result;
            }
            if (l.LogicType === 'Question') {
                var match = /^q:\/\/([^/]+)\/SelectableChoice\/([^/]+)$/.exec(l.ChoiceLocator || '');
                if (!match || match[1] !== l.QuestionID || !['Selected','NotSelected'].includes(l.Operator)) return null;
                var q = definition && (definition.questions || {})[l.QuestionID];
                if (definition && (!q || !choiceQuestion(q) || !own(q.choices,match[2]))) return null;
                if (!own(context.answers, l.QuestionID)) return null;
                var answer = context.answers[l.QuestionID];
                if (!(typeof answer === 'string' || Array.isArray(answer) && answer.every(function (v) { return typeof v === 'string'; }))) return null;
                var yes = (Array.isArray(answer) ? answer : [answer]).includes(match[2]);
                return l.Operator === 'Selected' ? yes : !yes;
            }
            if (l.LogicType === 'EmbeddedField') {
                var key = embeddedKey(l);
                if (key === null || !own(context.embedded,key) || !own(l,'RightOperand')) return null;
                var actual = context.embedded[key], expected = l.RightOperand;
                if (!['string','number','boolean'].includes(typeof actual) || !['string','number','boolean'].includes(typeof expected)) return null;
                if (l.Operator === 'EqualTo') return String(actual) === String(expected);
                if (l.Operator === 'NotEqualTo') return String(actual) !== String(expected);
                if (String(actual).trim() === '' || String(expected).trim() === '') return null;
                var a = Number(actual), b = Number(expected);
                if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
                switch (l.Operator) {
                    case 'GreaterThan': return a > b;
                    case 'GreaterThanOrEqual': case 'GreaterThanOrEqualTo': return a >= b;
                    case 'LessThan': return a < b;
                    case 'LessThanOrEqual': case 'LessThanOrEqualTo': return a <= b;
                    default: return null;
                }
            }
            return null;
        }
        return evaluate(logic, 0);
    }
    function describeCondition(logic, definition, depth) {
        depth = depth || 0;
        if (depth > 100) return 'Unknown condition (nesting limit)';
        if (!logic || typeof logic !== 'object') return 'Unknown condition';
        var children = parts(logic);
        if (children.length) return children.map(function (l, i) {
            var text = describeCondition(l, definition, depth + 1);
            if (parts(l).length > 1) text = '(' + text + ')';
            var conjunction = l.Conjuction || l.Conjunction || logic.Conjuction || logic.Conjunction || '[unknown operator]';
            return (i ? ' ' + String(conjunction).toUpperCase() + ' ' : '') + text;
        }).join('');
        var operators = {Selected:'is selected',NotSelected:'is not selected',EqualTo:'equals',NotEqualTo:'does not equal',GreaterThan:'is greater than',GreaterThanOrEqual:'is greater than or equal to',GreaterThanOrEqualTo:'is greater than or equal to',LessThan:'is less than',LessThanOrEqual:'is less than or equal to',LessThanOrEqualTo:'is less than or equal to'};
        var operator = operators[logic.Operator] || logic.Operator || 'unknown operator';
        var inputs = conditionInputs(logic, definition), label = inputs.length ? inputs[0].label : 'Unknown input';
        if (logic.LogicType === 'Question') {
            var match = /\/SelectableChoice\/([^/]+)$/.exec(logic.ChoiceLocator || '');
            var q = definition && (definition.questions || {})[logic.QuestionID];
            return label + ': ' + (match && q && q.choices && q.choices[match[1]] || match && match[1] || 'unsupported choice') + ' ' + operator;
        }
        return label + ' ' + operator + ' ' + (own(logic,'RightOperand') ? String(logic.RightOperand) : 'unknown value');
    }
    function walkFlow(definition, scenario) {
        scenario = scenario || {};
        var result = {steps:[], pending:null, ended:false, embedded:Object.assign(Object.create(null),scenario.embedded || {}), assumptions:[], completed:[], answers:Object.create(null), blockAnswers:Object.create(null)};
        var records = Object.create(null), questionOccurrences = Object.create(null), completed = Array.isArray(scenario.completed) ? scenario.completed : [], cursor = 0, replayValid = true, budget = 10000;
        function collect(n, depth) {
            if (!n || typeof n !== 'object' || typeof n.node_id !== 'string' || !Array.isArray(n.children) || depth > 100 || --budget < 0 || own(records,n.node_id)) return false;
            records[n.node_id] = {node_id:n.node_id,status:'pending',reason:'Not reached yet'};
            result.steps.push(records[n.node_id]);
            if (n.type === 'Block' || n.type === 'Standard') {
                var sourceBlock = (definition.blocks || {})[(n.config || {}).ID];
                var seenQuestions = Object.create(null);
                (sourceBlock && sourceBlock.elements || []).forEach(function (element) {
                    var id = element.question_external_id;
                    if (element.type === 'question' && !seenQuestions[id]) {
                        questionOccurrences[id] = (questionOccurrences[id] || 0) + 1;
                        seenQuestions[id] = true;
                    }
                });
            }
            return (n.children || []).every(function (c) { return collect(c,depth + 1); });
        }
        if (!definition || !definition.root || !collect(definition.root,0)) {
            result.pending = {node_id:definition && definition.root && definition.root.node_id || '0',kind:'unsupported',canContinue:false,reason:'Missing, invalid, or oversized flow definition'}; return result;
        }
        function mark(n, status, reason) { Object.assign(records[n.node_id], {status:status,reason:reason}); }
        function skip(n, reason) {
            mark(n,'skipped',reason);
            if (completed[cursor] === n.node_id) replayValid = false;
            (n.children || []).forEach(function (c) { skip(c,reason); });
        }
        function pause(n, kind, reason, extra) { mark(n,'pending',reason); result.pending = Object.assign({node_id:n.node_id,kind:kind,reason:reason},extra || {}); return false; }
        function choice(n) { return replayValid && own(scenario.choices,n.node_id) ? scenario.choices[n.node_id] : undefined; }
        function assume(n, reason) {
            if (choice(n) !== true) return pause(n,'unsupported',reason);
            result.assumptions.push(n.node_id + ': assumed continuation — ' + reason); return true;
        }
        function branch(n) {
            var value = evaluateCondition((n.config || {}).BranchLogic,{answers:result.answers,embedded:result.embedded},definition);
            if (value === null) {
                if (typeof choice(n) === 'boolean') { value = choice(n); result.assumptions.push(n.node_id + ': assumed condition ' + value); }
                else { pause(n,'condition','Condition is unknown: ' + describeCondition((n.config || {}).BranchLogic,definition),{inputs:conditionInputs((n.config || {}).BranchLogic,definition)}); }
            }
            return value;
        }
        function sequence(children) {
            for (var i=0;i<children.length;i++) {
                if (result.ended) { skip(children[i],'After EndSurvey'); continue; }
                if (!visit(children[i])) return false;
            }
            return true;
        }
        function visit(n, knownBranch) {
            var config = n.config || {}, children = n.children || [];
            mark(n,'reached','Reached in this scenario');
            if (n.type === 'Root' || n.type === 'Group') return sequence(children);
            if (n.type === 'Branch') {
                var value = knownBranch === undefined ? branch(n) : knownBranch;
                if (value === null) return false;
                if (!value) { children.forEach(function (c) { skip(c,'Branch condition is false'); }); mark(n,'skipped','Branch condition is false'); return true; }
                return sequence(children);
            }
            if (n.type === 'EndSurvey') { result.ended = true; children.forEach(function (c) { skip(c,'After EndSurvey'); }); return true; }
            if (n.type === 'EmbeddedData') {
                var entries = config.EmbeddedData;
                if (!Array.isArray(entries)) return assume(n,'Unsupported embedded-data assignment');
                for (var e of entries) {
                    if (!e || typeof e.Field !== 'string') { if (!assume(n,'Unsupported embedded-data field')) return false; continue; }
                    if (!own(e,'Value') || e.Type === 'Recipient') continue;
                    if (!['string','number','boolean'].includes(typeof e.Value) || /\$\{/.test(String(e.Value)) || e.Type && !['Custom','Value'].includes(e.Type)) {
                        delete result.embedded[e.Field];
                        if (!assume(n,'Unsupported dynamic embedded-data assignment: ' + e.Field)) return false;
                    } else result.embedded[e.Field] = String(e.Value);
                }
                return sequence(children);
            }
            if (n.type === 'Block' || n.type === 'Standard') {
                var b = (definition.blocks || {})[config.ID];
                if (!b) return assume(n,'Block definition is missing');
                var ids = (b.elements || []).filter(function (e) { return e.type === 'question'; }).map(function (e) { return e.question_external_id; });
                var options = b.options || {};
                var unsafe = !disabledOption(options.Looping) || !disabledOption(options.RandomizeQuestions) || !disabledOption(options.skip_logic) || ids.some(function (id) {
                    var q = (definition.questions || {})[id];
                    return !q || q.display_logic || q.skip_logic || !(answerQuestion(q) || q.type === 'DB');
                });
                if (unsafe && !assume(n,'Question display/skip logic, ordering, looping, or question type is unsupported')) return false;
                if (!replayValid || completed[cursor] !== n.node_id) { replayValid = false; return pause(n,'block','Enter hypothetical answers, then continue',{inputs:ids.filter(function (id) { var q = (definition.questions || {})[id]; return answerQuestion(q); }).map(function (id) { return questionInput(id,definition); })}); }
                cursor++; result.completed.push(n.node_id);
                var scoped = own(scenario.blockAnswers,n.node_id) ? scenario.blockAnswers[n.node_id] : null;
                var accepted = Object.create(null);
                ids.forEach(function (id) {
                    // Each occurrence replaces the previous answer, even when left unknown.
                    delete result.answers[id];
                    var source = scoped !== null ? scoped : questionOccurrences[id] === 1 ? scenario.answers : null;
                    if (own(source,id)) {
                        var value = Array.isArray(source[id]) ? source[id].slice() : source[id];
                        accepted[id] = value;
                        result.answers[id] = value;
                    }
                });
                result.blockAnswers[n.node_id] = accepted;
                return sequence(children);
            }
            if (n.type === 'Randomizer' || n.type === 'BlockRandomizer') {
                var eligible = [];
                for (var child of children) {
                    var ok = child.type === 'Branch' ? branch(child) : true;
                    if (ok === null) return false;
                    if (ok) eligible.push(child); else skip(child,'Randomizer branch is ineligible');
                }
                var count = Number(config.SubSet);
                if (!Number.isInteger(count) || count < 0 || config.SubSet === '' || config.SubSet == null || count > eligible.length) return pause(n,'unsupported','Randomizer count is invalid or exceeds eligible children',{canContinue:false});
                var selected = choice(n), allowed = eligible.map(function (c) { return c.node_id; });
                if (!Array.isArray(selected) || selected.length !== count || new Set(selected).size !== count || !selected.every(function (id) { return allowed.includes(id); })) return pause(n,'randomizer','Choose exactly ' + count + ' eligible ' + (count === 1 ? 'element' : 'elements') + ' in scenario order',{count:count, options:eligible.map(function (c) { return {value:c.node_id,label:(c.config || {}).Description || ((definition.blocks || {})[(c.config || {}).ID] || {}).name || c.type + ' ' + c.node_id}; })});
                eligible.filter(function (c) { return !selected.includes(c.node_id); }).forEach(function (c) { skip(c,'Not selected by the scenario randomizer'); });
                for (var id of selected) {
                    var selectedNode = eligible.find(function (c) { return c.node_id === id; });
                    if (result.ended) skip(selectedNode,'After EndSurvey');
                    else if (!visit(selectedNode,selectedNode.type === 'Branch' ? true : undefined)) return false;
                }
                return true;
            }
            if (!assume(n,'Unsupported flow element: ' + n.type)) return false;
            return sequence(children);
        }
        visit(definition.root); return result;
    }
    return {describeCondition:describeCondition,conditionInputs:conditionInputs,evaluateCondition:evaluateCondition,walkFlow:walkFlow};
}));
