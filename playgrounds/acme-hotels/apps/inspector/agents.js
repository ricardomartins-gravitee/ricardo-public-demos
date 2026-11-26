/* Icons for the three agents, drawn on a flow row and on the cards in its agent column. */
(function () {
  window.decorateFlowAgent = function (wrapper, agent) {
    if (!wrapper || !agent) return;
    wrapper.querySelectorAll(".msg-agent").forEach(function (card) {
      if (card.querySelector(".flow-agent-mark")) return;
      var mark = document.createElement("div");
      mark.className = "flow-agent-mark";
      mark.style.color = agent.color;
      mark.innerHTML = '<i class="ph ' + agent.icon + '"></i> ' + agent.name;
      card.prepend(mark);
    });
  };
})();
