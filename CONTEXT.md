# Qualtrics survey data

The toolkit keeps survey definitions, respondent facts, and optional prepared translations distinct so analyses can change their display language without changing their facts.

## Language

**Survey language**:
The language of a survey's base definition labels, declared as `SurveyLanguage` in its QSF.
_Avoid_: Respondent language, report language

**Respondent language**:
The language Qualtrics records for one response as `UserLanguage`; it may be absent or differ from the survey language.
_Avoid_: Survey language

**Target language**:
The language requested for prepared labels and written-answer text. Without an override, each survey uses its survey language.
_Avoid_: Source language

**Definition label**:
Text attached to a question, field, or answer option. A QSF can supply a localized label; a user-supplied translator can prepare a missing one.
_Avoid_: Answer

**Written answer**:
Respondent-authored free text that remains an answer fact in its original form. A prepared translation is another display form of that same answer.
_Avoid_: Translated answer fact
