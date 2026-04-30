const copyButton = document.querySelector("[data-copy-command]");

if (copyButton) {
  copyButton.addEventListener("click", async () => {
    const command = copyButton.getAttribute("data-copy-command");
    const original = copyButton.textContent;

    try {
      await navigator.clipboard.writeText(command);
      copyButton.textContent = "Copied";
      window.setTimeout(() => {
        copyButton.textContent = original;
      }, 1600);
    } catch {
      copyButton.textContent = command;
      copyButton.setAttribute("aria-label", "Command text shown");
    }
  });
}
