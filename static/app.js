document.addEventListener("DOMContentLoaded", () => {
  const copyButtons = document.querySelectorAll("[data-copy-text]");
  copyButtons.forEach((button) => {
    const originalLabel = button.textContent;
    button.addEventListener("click", async () => {
      const text = button.getAttribute("data-copy-text");
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied";
        button.classList.add("btn-primary");
        setTimeout(() => {
          button.textContent = originalLabel;
          button.classList.remove("btn-primary");
        }, 1200);
      } catch (err) {
        button.textContent = "Copy failed";
        setTimeout(() => (button.textContent = originalLabel), 1200);
      }
    });
  });

  const lockButtons = document.querySelectorAll("[data-require-text]");
  lockButtons.forEach((button) => {
    const fieldId = button.getAttribute("data-require-text");
    const requiredValue = button.getAttribute("data-required-value") || "RESET";
    const field = document.getElementById(fieldId);
    if (!field) return;
    const toggle = () => {
      button.disabled = field.value.trim() !== requiredValue;
    };
    toggle();
    field.addEventListener("input", toggle);
  });

  const printTriggers = document.querySelectorAll("[data-print]");
  printTriggers.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      window.print();
    });
  });
});
