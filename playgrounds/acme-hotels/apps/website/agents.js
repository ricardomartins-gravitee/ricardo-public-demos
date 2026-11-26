/* The chat shows who answered. The concierge prefixes a reply; this removes the prefix and sets the icon. */
(function () {
  var AGENTS = {
    concierge: { name: "Concierge", icon: "ph-user-circle", color: "#1d4ed8" },
    booking: { name: "Booking desk", icon: "ph-bed", color: "#0f766e" },
    loyalty: { name: "Loyalty desk", icon: "ph-gift", color: "#b45309" }
  };
  var MARK = /^\[\[acme-agent:(concierge|booking|loyalty)\]\](?:<br>)?/;

  function paint(message, id) {
    var agent = AGENTS[id] || AGENTS.concierge;
    var avatar = message.querySelector(".message-avatar");
    if (!avatar) return;
    message.classList.add("acme-spoke");
    avatar.innerHTML =
      '<span class="acme-agent-badge" style="background:' + agent.color + '">' +
      '<i class="ph ' + agent.icon + '"></i></span>' +
      '<span class="acme-agent-name">' + agent.name + "</span>";
  }

  function read(message) {
    var paragraph = message.querySelector(".message-content p");
    if (!paragraph) return;
    var found = paragraph.innerHTML.match(MARK);
    if (!found) {
      if (!message.classList.contains("acme-spoke")) paint(message, "concierge");
      return;
    }
    paragraph.innerHTML = paragraph.innerHTML.replace(MARK, "");
    paint(message, found[1]);
  }

  function watch() {
    var box = document.getElementById("chatMessages");
    if (!box) return;
    box.querySelectorAll(".agent-message").forEach(read);
    new MutationObserver(function (records) {
      records.forEach(function (record) {
        record.addedNodes.forEach(function (node) {
          if (node.nodeType === 1 && node.classList.contains("agent-message")) read(node);
        });
      });
    }).observe(box, { childList: true });
  }

  function header() {
    var icon = document.querySelector(".chat-bot-icon i");
    var title = document.querySelector(".chat-header h3");
    if (icon) icon.className = "ph " + AGENTS.concierge.icon;
    if (title) title.textContent = AGENTS.concierge.name;
  }

  header();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch);
  else watch();
})();
