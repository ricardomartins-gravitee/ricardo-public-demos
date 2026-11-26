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
sed -e 's#<div class="chat-bot-icon"><i class="ph ph-robot"></i></div>#<div class="chat-bot-icon"><i class="ph ph-user-circle"></i></div>#' \
    -e 's#<h3>ACME Bot</h3>#<h3>Concierge</h3>#' \
    /tmp/acme-hotels-plus-index.html > /usr/share/nginx/html/index.html
if ! grep -q 'acme-hotels-plus-agents.js' /usr/share/nginx/html/index.html; then
    awk '
        /<\/body>/ && !done {
            print "<style>"
            print ".message.acme-spoke .message-avatar { width: auto; height: auto; border-radius: 0; overflow: visible; background: transparent; flex-direction: column; gap: .15rem; }"
            print ".acme-agent-badge { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 1.05rem; }"
            print ".acme-agent-name { font-size: .65rem; line-height: 1.1; text-align: center; max-width: 4.6rem; color: var(--dark-navy); }"
            print "</style>"
            print "<script src=\"/acme-hotels-plus-agents.js\"></script>"
            done = 1
        }
        { print }
    ' /usr/share/nginx/html/index.html > /tmp/acme-hotels-plus-index.html
    cat /tmp/acme-hotels-plus-index.html > /usr/share/nginx/html/index.html
fi
exec /docker-entrypoint.sh
