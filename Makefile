##@ SharingHub utilities

COMPOSE:=docker compose -f deploy/compose/docker-compose.yml
COMPOSE_CMDS:=up build down stop start restart pause unpause config
COMPOSE_ARGS:=

SERVICES:=

.PHONY: default run rund logs $(COMPOSE_CMDS)

# ======================================================= #

default: build run

run: ## Equivalent to docker compose up
	$(COMPOSE) up $(COMPOSE_ARGS) $(SERVICES)

rund: ## Equivalent to docker compose up -d
	$(COMPOSE) up -d $(COMPOSE_ARGS) $(SERVICES)

logs: ## Equivalent to docker compose logs -f
	$(COMPOSE) $@ -f $(COMPOSE_ARGS) $(SERVICES)

$(COMPOSE_CMDS): ## Docker compose commands
	$(COMPOSE) $@ $(COMPOSE_ARGS) $(SERVICES)

# ======================================================= #

HELP_COLUMN=5
help: ## Show this help.
	@printf "\033[1m################\n#     Help     #\n################\033[0m\n"
	@if [ -n "$(MAKEFILE_HELP)" ]; then echo "\n$(MAKEFILE_HELP)"; fi;
	@if [ -f Makefile.help ]; then echo && cat Makefile.help && echo; fi;
	@awk 'BEGIN {FS = ":.*##@"; printf "\n"} /^##@/ { printf "%s\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n\n  make \033[36m<target>\033[0m\n\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-$(HELP_COLUMN)s\033[0m %s\n", $$1, $$2 } ' $(MAKEFILE_LIST)
	@printf "\n"
