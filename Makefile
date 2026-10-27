.PHONY: check verify scripts draft game committed notices gozen-check voice-size run web web-size desktop voices voices-en banner clean help

# gozen comes from go.mod (the tool directive), so the CLI and the player runtimes are one version.
GOZEN = go tool gozen
# The voices of both languages, a part of the site below.
VOICE_LIMIT = 800000000
# The whole browser version (dist/web after make web): GitHub Pages takes a site of 1 GB at most.
SITE_LIMIT = 950000000
DESKTOP_TARGETS = linux-amd64 linux-arm64 windows-amd64 windows-arm64 darwin-amd64 darwin-arm64

# The steps run one after another, in this order, even under make -j: each one reads what
# the one before it wrote.
check: ## Check the scripts, write game/ and check it with gozen
	$(MAKE) scripts
	$(MAKE) game
	$(MAKE) notices
	$(MAKE) gozen-check
	$(MAKE) voice-size

# What CI runs before Pages and a release publish anything (.github/workflows/verify.yml):
# check, and game/ must be the one committed.
verify: ## check, and fail when game/ differs from the commit
	$(MAKE) scripts
	$(MAKE) game
	$(MAKE) committed
	$(MAKE) notices
	$(MAKE) gozen-check
	$(MAKE) voice-size

scripts: ## Check the scripts in src/ and the reactions against the expected comments (needs Node.js); writes nothing
	python3 tools/build.py --check
	python3 tools/kwtest.py

game: ## Write game/ from src/ and assets/
	python3 tools/import_stream.py

committed: ## Fail when game/ is not the one committed (after make game)
	@git status --porcelain -- game
	@test -z "$$(git status --porcelain -- game)" || { echo "game/ differs from the commit: commit what make game wrote" >&2; exit 1; }

notices: ## Fail when game/LICENSE or game/NOTICE.txt (in every export) differ from LICENSE and NOTICE.md
	cmp LICENSE game/LICENSE
	cmp NOTICE.md game/NOTICE.txt

gozen-check: ## Run gozen check on game/
	$(GOZEN) check game

voice-size: ## Fail when the voices grow past VOICE_LIMIT bytes
	python3 tools/size.py game/assets/voice $(VOICE_LIMIT)

run: ## Play game/ in a window
	$(GOZEN) run game

web: ## Export the browser version into dist/web, failing past SITE_LIMIT bytes
	$(MAKE) notices
	rm -rf dist/web
	rt=$$(tools/runtime.sh web) || exit 1; \
	$(GOZEN) export game --runtime "$$rt" --target web --out dist/web
	cp LICENSE dist/web/LICENSE
	cp NOTICE.md dist/web/NOTICE.txt
	cp game/assets/fonts/LICENSE.txt dist/web/LICENSE-mplus.txt
	$(MAKE) web-size

web-size: ## Fail when dist/web is past SITE_LIMIT bytes
	python3 tools/size.py dist/web $(SITE_LIMIT)

desktop: ## Export a zip of the game for each desktop OS into dist/
	$(MAKE) notices
	mkdir -p dist
	for t in $(DESKTOP_TARGETS); do \
		rm -rf dist/succubus-live_$$t dist/succubus-live_$$t.zip; \
		rt=$$(tools/runtime.sh $$t) || exit 1; \
		$(GOZEN) export game --runtime "$$rt" --target $$t --out dist/succubus-live_$$t || exit 1; \
		(cd dist && zip -qr succubus-live_$$t.zip succubus-live_$$t) || exit 1; \
		rm -rf dist/succubus-live_$$t; \
	done

voices: ## Render the Japanese voices of new or changed lines (needs uv, git and ffmpeg; takes hours on a CPU)
	python3 tools/voices.py

voices-en: ## Render the English voices of new or changed lines and reactions (needs uv, git, ffmpeg and espeak-ng)
	python3 tools/voices.py --lang en

draft: ## Write data/ for the browser draft of src/ (index.html, reader.html; serve it with python3 tools/serve.py)
	python3 tools/build.py

banner: ## Draw doc/img/banner.png (needs Pillow)
	python3 tools/make_banner.py

clean: ## Remove the exports and the downloaded runtimes
	rm -rf dist .cache data

.DEFAULT_GOAL := help
help:
	@grep -E '^[0-9a-zA-Z_-]+[[:blank:]]*:.*?## .*$$' $(MAKEFILE_LIST) | sort \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[1;32m%-12s\033[0m %s\n", $$1, $$2}'
