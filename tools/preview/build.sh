#!/bin/sh
# Turns the mod's generated scenes.ts into plain JS for the preview page.
MOD="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$(dirname "$0")"
sed -e '/^import type/d' -e '/^export type/d' \
    -e 's/^export const \([A-Z_]*\): [^=]*=/export const \1 =/' \
    "$MOD/hooks/scenes.ts" > scenes.js
