#!/bin/sh
# runtime.sh TARGET: download the gozen player runtime for TARGET (web, or linux/windows/darwin
# with amd64/arm64, as gozen export takes it) of the gozen version in go.mod (read from the file,
# so Go is not needed), check it against
# the release's checksums.txt, unpack it into .cache/runtime/VERSION/TARGET and print that directory.
# GOZEN_VERSION overrides go.mod (CI passes the version setup-gozen installed).
#
# What this proves: the archive is the one the gozen release lists in its checksums.txt, both
# fetched over HTTPS from GitHub. It is not a signature check. A directory is moved into
# .cache/runtime/ only after its archive passed, and a later run trusts it as it is; remove
# .cache/ (make clean) to fetch and check it again. gozen export then checks the player against
# the hash in the runtime's runtime.json.
set -eu
target=$1
if [ -z "${GOZEN_VERSION:-}" ]; then
	# require github.com/nao1215/gozen vX.Y.Z, on its own line or in a require ( ) block
	GOZEN_VERSION=$(awk '$1 == "require" && $2 == "github.com/nao1215/gozen" { print $3; n++ }
		$1 == "github.com/nao1215/gozen" && NF >= 2 { print $2; n++ }
		END { if (n != 1) exit 1 }' go.mod) || {
		echo "runtime.sh: go.mod has no single require of github.com/nao1215/gozen" >&2
		exit 1
	}
fi
version=$GOZEN_VERSION
dir=.cache/runtime/$version/$target
if [ -f "$dir/runtime.json" ]; then
	echo "$dir"
	exit 0
fi
case $target in
web) archive=gozen-runtime_${version#v}_js_wasm.tar.gz ;;
windows-*) archive=gozen-runtime_${version#v}_$(echo "$target" | tr - _).zip ;;
*) archive=gozen-runtime_${version#v}_$(echo "$target" | tr - _).tar.gz ;;
esac
url=https://github.com/nao1215/gozen/releases/download/$version
tmp=.cache/download
sums=$tmp/checksums-$version.txt
mkdir -p "$tmp"
curl -sSfL -o "$tmp/$archive" "$url/$archive"
curl -sSfL -o "$sums" "$url/checksums.txt"

# The line of the archive: its name compared as a string (not a pattern), on exactly one line
# of two fields (the hash and the name).
want=$(awk -v f="$archive" '$2 == f || $2 == "*" f { n++; h = $1; if (NF != 2) bad = 1 } END { if (n != 1 || bad) exit 1; print h }' "$sums") || {
	echo "runtime.sh: checksums.txt of $version has no single line for $archive" >&2
	exit 1
}
want=$(printf '%s' "$want" | tr 'A-F' 'a-f')
case $want in
*[!0-9a-f]* | '')
	echo "runtime.sh: the checksum of $archive is not a SHA-256: $want" >&2
	exit 1
	;;
esac
if [ ${#want} -ne 64 ]; then
	echo "runtime.sh: the checksum of $archive is not a SHA-256: $want" >&2
	exit 1
fi
if command -v sha256sum >/dev/null; then
	got=$(sha256sum "$tmp/$archive" | cut -d ' ' -f 1)
else
	got=$(shasum -a 256 "$tmp/$archive" | cut -d ' ' -f 1)
fi
if [ "$got" != "$want" ]; then
	echo "runtime.sh: $archive is $got, checksums.txt says $want" >&2
	exit 1
fi

rm -rf "$dir.tmp"
mkdir -p "$dir.tmp"
case $archive in
*.zip) unzip -q "$tmp/$archive" -d "$dir.tmp" ;;
*) tar xzf "$tmp/$archive" -C "$dir.tmp" ;;
esac
mv "$dir.tmp" "$dir"
echo "$dir"
