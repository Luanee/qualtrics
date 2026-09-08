# Survey terms in plain language

| Term | Meaning here |
| --- | --- |
| API | A way for software to ask Qualtrics to list surveys, download responses, or make changes. Local CSV parsing does not need it. |
| API token | A credential for your Qualtrics account's API access. Keep it private. |
| Block / section | A group of questions within a survey. The output table calls it a section. |
| Catalog | A set of question or field meanings that you can compare across surveys. |
| CLI / command line | The commands you type or paste into a terminal. |
| CSV | A text file that stores rows and columns. A Qualtrics export also includes header rows that describe the fields. |
| Definition / QSF | A file describing survey questions, choices, blocks, and settings. QSF means Qualtrics Survey Format. |
| Entity | One of the toolkit's nine organized tables, such as responses or questions. |
| Export | A copy of survey responses downloaded from Qualtrics. |
| Field | One concrete question column in the export. A question may have several fields. |
| ID | A value used to identify and connect records. IDs ending in `_external_id` retain the original Qualtrics identity. |
| ImportId | Qualtrics metadata that helps identify the question and field behind an exported column. It can include a matrix row, choice, loop, or text suffix. |
| Label / code | The displayed wording of a choice, such as Satisfied, or its exported value, such as 1. |
| Parse | Read an export and turn it into the toolkit's tables. |
| Parquet | A file format for analytical tables that keeps column types. It is useful in data platforms and Power BI workflows. |
| Response | One survey submission, including its dates and other metadata. |
| Answer / answer row | A non-empty value for one exported question field in a response. |
| Semantic model | Five related tables prepared for analysis: two fact tables with responses and answers, and three dimension tables that describe them. |
| Terminal | The application in which you run commands. Use Terminal on macOS/Linux or PowerShell on Windows. |
| ZIP | A compressed archive. The toolkit accepts a response-export ZIP that contains one CSV. |

Continue with [your first report](../getting-started/first-report.md) or [an explanation of the output tables](your-data.md).
