.PHONY: docs docs-serve

docs:
	.venv/bin/pdoc getmotion -o docs/

docs-serve:
	.venv/bin/pdoc getmotion
