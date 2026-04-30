const copyButton = document.querySelector("[data-copy-command]");
const videoPosters = document.querySelectorAll("[data-video-src]");

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

videoPosters.forEach((poster) => {
  poster.addEventListener("click", () => {
    const source = poster.getAttribute("data-video-src");
    const video = document.createElement("video");

    video.controls = true;
    video.playsInline = true;
    video.autoplay = true;
    video.preload = "metadata";
    video.innerHTML = `<source src="${source}" type="video/mp4">Your browser does not support embedded MP4 video.`;

    poster.replaceWith(video);
    video.focus();
  });
});
