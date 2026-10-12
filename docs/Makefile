# Build the documentation. Needs `pip install -r requirements.txt` and the cefweaver wheel installed
# (autodoc imports the package): outside the source tree, or with `python -P`.
SPHINXBUILD ?= sphinx-build
BUILD       ?= _build
LANGUAGES   ?= ko

.PHONY: html html-all gettext update-po clean

html:
	$(SPHINXBUILD) -b html -W --keep-going . $(BUILD)/html/en

# one site per language: _build/html/en, _build/html/ko
html-all: html
	for lang in $(LANGUAGES); do $(SPHINXBUILD) -b html -D language=$$lang . $(BUILD)/html/$$lang; done

# message templates (.pot), then the catalogs of every language (.po)
gettext:
	$(SPHINXBUILD) -b gettext . $(BUILD)/gettext

update-po: gettext
	sphinx-intl update -p $(BUILD)/gettext $(addprefix -l ,$(LANGUAGES))

clean:
	rm -rf $(BUILD)
