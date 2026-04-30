const copyButton = document.querySelector("[data-copy-command]");
const videoPosters = document.querySelectorAll("[data-video-src]");
const mediaModal = document.querySelector(".media-modal");
const mediaModalBody = document.querySelector(".media-modal-body");
const mediaModalClose = document.querySelector(".media-modal-close");
const mediaModalOpen = document.querySelector(".media-modal-open");
const mediaModalLinks = document.querySelectorAll("[data-modal]");

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

const clearModal = () => {
  if (mediaModalBody) {
    mediaModalBody.replaceChildren();
  }
};

const closeModal = () => {
  if (!mediaModal) return;
  clearModal();
  mediaModal.close();
};

mediaModalLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    if (!mediaModal || !mediaModalBody || !mediaModalOpen || typeof mediaModal.showModal !== "function") {
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener");
      return;
    }

    event.preventDefault();
    clearModal();

    const type = link.getAttribute("data-modal");
    const source = link.getAttribute("href");
    mediaModalOpen.setAttribute("href", source);

    if (type === "video") {
      const video = document.createElement("video");
      const videoSource = document.createElement("source");

      video.controls = true;
      video.playsInline = true;
      video.autoplay = true;
      video.preload = "metadata";
      videoSource.src = source;
      videoSource.type = "video/mp4";
      video.append(videoSource, "Your browser does not support embedded MP4 video.");
      mediaModalBody.append(video);
    } else if (type === "pdf") {
      const frame = document.createElement("iframe");

      frame.src = `${source}#view=FitH`;
      frame.title = "PDF preview";
      mediaModalBody.append(frame);
    } else {
      const image = document.createElement("img");
      const inlineImage = link.querySelector("img");

      image.src = source;
      image.alt = inlineImage?.alt || "Media preview";
      mediaModalBody.append(image);
    }

    mediaModal.showModal();
    mediaModalBody.focus();
  });
});

mediaModalClose?.addEventListener("click", closeModal);

mediaModal?.addEventListener("click", (event) => {
  if (event.target === mediaModal) {
    closeModal();
  }
});

mediaModal?.addEventListener("close", clearModal);
