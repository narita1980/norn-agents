(() => {
    const messagesEl = document.getElementById("messages");
    const form = document.getElementById("composer");
    const input = document.getElementById("input");
    const threadIdEl = document.getElementById("thread-id");
    let threadId = null;

    function appendMessage(role, content) {
        const li = document.createElement("li");
        li.className = `message message--${role}`;
        const label = document.createElement("span");
        label.className = "message__role";
        label.textContent = role === "user" ? "あなた" : "Norn";
        const body = document.createElement("div");
        body.className = "message__body";
        body.textContent = content;
        li.appendChild(label);
        li.appendChild(body);
        messagesEl.appendChild(li);
        li.scrollIntoView({ behavior: "smooth", block: "end" });
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const content = input.value.trim();
        if (!content) return;

        appendMessage("user", content);
        input.value = "";
        input.disabled = true;

        try {
            const response = await fetch("/chat/messages", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ thread_id: threadId, content }),
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            if (!threadId) {
                threadId = data.thread_id;
                threadIdEl.textContent = threadId;
            }
            appendMessage("assistant", data.reply);
        } catch (err) {
            appendMessage("assistant", `エラーが発生しました: ${err.message}`);
        } finally {
            input.disabled = false;
            input.focus();
        }
    });
})();
