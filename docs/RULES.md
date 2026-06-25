RULES.md

Coding Rules

⸻

Python

Python >=3.12

Use

* pathlib
* dataclass
* typing
* logging

Avoid

* global variables
* print()

except reporter.

⸻

Style

Follow

PEP8

Ruff

Mypy

Every public API

must include

Type Hint

Docstring

⸻

Architecture

Never violate module boundaries.

Fetcher

↓

Indicators

↓

Analyzer

↓

Strategy

↓

Scorer

↓

Reporter

Only.

⸻

Forbidden

Indicators

must NOT

generate suggestions.

Reporter

must NOT

calculate indicators.

Analyzer

must NOT

download data.

Portfolio

must NOT

know technical indicators.

⸻

Data Structure

Never return dict.

Always return dataclass.

⸻

Constants

No magic numbers.

Everything configurable.

⸻

Logging

Every module

logger=logging.getLogger(__name__)

Never print debug information.

⸻

Unit Test

Every indicator

must have unit tests.

Target

Coverage

90%

⸻

Performance

Download data only once.

Reuse DataFrame.

Avoid repeated calculations.

⸻

AI Rules

Every AI-generated suggestion

must contain

Reasons

Confidence

Risk

No black-box output.