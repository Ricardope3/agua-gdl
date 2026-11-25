#!/bin/sh
# shoot.sh <film.html> <outdir> <frame>: one PNG per frame, each Chrome with its own profile dir so runs don't collide
f=$(printf "%06d" $3); p=$(mktemp -d)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --user-data-dir=$p --window-size=1080,1920 --screenshot=$2/$f.png "file://$1?f=$3" >/dev/null 2>&1 </dev/null
rm -rf $p
