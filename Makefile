.PHONY: fetch build standalone serve clean

fetch:
	python3 fetch_worldmonitor.py --public-only

build: fetch
	python3 make_map.py
	python3 build.py

standalone: build
	python3 make_standalone.py

serve:
	python3 -m http.server 8080

clean:
	rm -f data.js standalone.html
