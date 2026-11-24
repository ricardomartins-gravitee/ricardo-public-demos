#!/bin/sh
# The workshop site ships three sample questions. This replaces them with the sentences the guide uses.
if ! grep -q 'id="chatSuggestions"' /usr/share/nginx/html/index.html; then
    echo "The website has no chat suggestions to replace" >&2
    exit 1
fi
awk '
    /id="chatSuggestions"/ {
        while ((getline line < "/acme-hotels-plus-suggestions.html") > 0) print line
        skip = 1
        next
    }
    skip && /<\/div>/ { skip = 0; next }
    !skip { print }
' /usr/share/nginx/html/index.html > /tmp/acme-hotels-plus-index.html
if ! grep -q "Ask the loyalty desk" /tmp/acme-hotels-plus-index.html; then
    echo "The chat suggestions were not replaced" >&2
    exit 1
fi
cat /tmp/acme-hotels-plus-index.html > /usr/share/nginx/html/index.html
exec /docker-entrypoint.sh
