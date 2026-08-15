(function () {
  const list = document.querySelector("[data-message-list]");
  const form = document.querySelector("[data-composer]");

  if (!list) {
    return;
  }

  const groupId = list.dataset.groupId;
  const currentUserId = Number(list.dataset.currentUserId);
  const seenIds = new Set();
  let lastMessageId = 0;
  let isPolling = false;

  function updateSeenMessages() {
    list.querySelectorAll("[data-message-id]").forEach((item) => {
      const id = Number(item.dataset.messageId);
      if (id > lastMessageId) {
        lastMessageId = id;
      }
      seenIds.add(id);
    });
  }

  function scrollIfNearBottom() {
    const distance = list.scrollHeight - list.scrollTop - list.clientHeight;
    return distance < 120;
  }

  function removeEmptyState() {
    const empty = list.querySelector("[data-empty-state]");
    if (empty) {
      empty.remove();
    }
  }

  function messageNode(message) {
    const article = document.createElement("article");
    article.className = "message";
    article.dataset.messageId = message.id;

    if (Number(message.user_id) === currentUserId) {
      article.classList.add("mine");
    }

    const meta = document.createElement("div");
    meta.className = "message-meta";

    const name = document.createElement("strong");
    name.textContent = message.display_name;

    const username = document.createElement("span");
    username.textContent = message.username;

    meta.append(name, username);
    article.append(meta);

    if (message.body) {
      const body = document.createElement("p");
      body.textContent = message.body;
      article.append(body);
    }

    if (message.attachment_url && message.original_filename) {
      const attachment = document.createElement("a");
      attachment.className = "attachment";
      attachment.href = message.attachment_url;
      attachment.textContent = message.original_filename;
      article.append(attachment);
    }

    return article;
  }

  function appendMessages(messages) {
    if (!messages.length) {
      return;
    }

    const shouldScroll = scrollIfNearBottom();
    removeEmptyState();

    messages.forEach((message) => {
      if (seenIds.has(message.id)) {
        return;
      }
      seenIds.add(message.id);
      lastMessageId = Math.max(lastMessageId, message.id);
      list.append(messageNode(message));
    });

    if (shouldScroll) {
      list.scrollTop = list.scrollHeight;
    }
  }

  async function pollMessages() {
    if (isPolling || document.hidden) {
      return;
    }

    isPolling = true;
    try {
      const response = await fetch(`/groups/${groupId}/messages?after_id=${lastMessageId}`, {
        headers: { Accept: "application/json" },
      });
      if (response.ok) {
        const data = await response.json();
        appendMessages(data.messages || []);
      }
    } finally {
      isPolling = false;
    }
  }

  async function sendMessage(event) {
    event.preventDefault();

    const submit = form.querySelector("button[type='submit']");
    const formData = new FormData(form);
    submit.disabled = true;

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: formData,
        headers: {
          Accept: "application/json",
          "X-Requested-With": "fetch",
        },
      });

      const data = await response.json();
      if (!response.ok) {
        alert(data.error || "Could not send message.");
        return;
      }

      appendMessages([data.message]);
      form.reset();
      list.scrollTop = list.scrollHeight;
    } finally {
      submit.disabled = false;
    }
  }

  updateSeenMessages();
  list.scrollTop = list.scrollHeight;
  setInterval(pollMessages, 400);

  if (form) {
    form.addEventListener("submit", sendMessage);
  }
})();
