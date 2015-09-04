

# This script launches the less CSS pre-processor in order to generate the CSS files.

# Pre-requisites:
# - node.js
# - less (nodejs package)
# - Grunt + other Bootstrap dependencies
#
# Linux install (example):
# - Install packages
#   sudo apt-get update
#   sudo apt-get install nodejs npm
#   sudo ln -s /usr/bin/nodejs /usr/bin/node
# - Upgrade nodejs
#   sudo npm cache clean -f
#   sudo npm install -g n
#   sudo n stable
# - Install nodejs packages
#   sudo npm install -g less
#   sudo npm install -g grunt-cli
# - Install Bootstrap dependencies
#   cd templates/dwr_default/data/bootstrap
#   npm install


MAKEFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST))/..)
TEMPLATES_PATH := $(MAKEFILE_PATH)/templates


default_target:
	@echo ''
	@echo 'Use the following targets:'
	@echo '    make css: builds the DynamicWeb report CSS files'
	@echo '    make bootstrap: builds Bootstrap'
	@echo '    make all: builds everything'
	@echo '    make clean_dist: Removes useles files (generated during the build process).'
	@echo ''

.PHONY: all clean_dist css bootstrap clean_css clean_bootstrap force

all: bootstrap css

clean_dist: clean_css clean_bootstrap

bootstrap:
	@for template in $(wildcard $(TEMPLATES_PATH)/*); do \
		cd $$template/data/bootstrap; npm install; \
		rm -rf cd $$template/data/bootstrap/dist; \
		cd $$template/data/bootstrap; grunt dist; \
	done

clean_bootstrap:
	@for template in $(wildcard $(TEMPLATES_PATH)/*); do \
		rm -rf \
		$$template/data/bootstrap/dist/css/*.map \
		$$template/data/bootstrap/dist/css/bootstrap.css \
		$$template/data/bootstrap/dist/css/bootstrap-theme.css \
		$$template/data/bootstrap/dist/js/bootstrap.js \
		$$template/data/bootstrap/dist/js/npm.js \
		$$template/data/bootstrap/node_modules \
	; done

css: $(patsubst %.less,%.css,$(wildcard $(TEMPLATES_PATH)/*/data/*.less))

clean_css:
	@#Nothing to do
	@#rm -f $(patsubst %.less,%.css,$(wildcard $(TEMPLATES_PATH)/*/data/*.less))

%.css: %.less force
	lessc $< $@

force:
