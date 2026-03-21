document.addEventListener("DOMContentLoaded", () => {
  const createToast = (message, tone = "neutral") => {
    const toast = document.createElement("div");
    toast.className = `toast toast-${tone}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("show"));
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 200);
    }, 1800);
  };

  const copyButtons = document.querySelectorAll("[data-copy-text]");
  copyButtons.forEach((button) => {
    const originalLabel = button.innerHTML;
    const isBtnStyled = button.classList.contains("btn");
    button.addEventListener("click", async () => {
      const text = button.getAttribute("data-copy-text");
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        button.innerHTML = "Copied";
        if (isBtnStyled) {
          button.classList.add("btn-primary");
        }
        createToast("Copied to clipboard", "success");
        setTimeout(() => {
          button.innerHTML = originalLabel;
          if (isBtnStyled) {
            button.classList.remove("btn-primary");
          }
        }, 1200);
      } catch (err) {
        button.innerHTML = "Copy failed";
        createToast("Copy failed", "error");
        setTimeout(() => (button.innerHTML = originalLabel), 1200);
      }
    });
  });

  const nav = document.querySelector("[data-nav]");
  const navToggle = document.querySelector("[data-nav-toggle]");
  const actionsToggle = document.querySelector("[data-actions-toggle]");
  const actionsMenu = document.querySelector("[data-actions-menu]");

  const closeActions = () => {
    if (actionsMenu && actionsToggle) {
      actionsMenu.classList.remove("open");
      actionsToggle.setAttribute("aria-expanded", "false");
    }
  };

  if (nav && navToggle) {
    const closeNav = () => {
      nav.classList.remove("open");
      navToggle.setAttribute("aria-expanded", "false");
      closeActions();
    };
    navToggle.addEventListener("click", () => {
      const isOpen = nav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", isOpen.toString());
      if (!isOpen) {
        closeActions();
      }
    });
    nav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeNav);
    });
  }

  if (actionsToggle && actionsMenu) {
    actionsToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const isOpen = actionsMenu.classList.toggle("open");
      actionsToggle.setAttribute("aria-expanded", isOpen.toString());
    });
    document.addEventListener("click", (event) => {
      if (actionsMenu.contains(event.target) || actionsToggle.contains(event.target)) return;
      closeActions();
    });
  }

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

  const demoButtons = document.querySelectorAll("[data-fill-demo]");
  const demoPayloads = {
    "submit-form": {
      citizen_id: "CIT-1001",
      title: "Pothole near community center",
      category: "Road Safety",
      priority: "HIGH",
      description: "Large pothole causing traffic slowdowns near the main junction.",
    },
    "update-form": {
      complaint_id: "CMP-DEMO-0001",
      officer_id: "OFF-210",
      status: "IN_PROGRESS",
      remarks: "Site inspection scheduled with maintenance crew.",
    },
  };

  demoButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-target");
      if (!targetId || !demoPayloads[targetId]) return;
      const form = document.getElementById(targetId);
      if (!form) return;
      const payload = demoPayloads[targetId];
      Object.entries(payload).forEach(([key, value]) => {
        const field = form.querySelector(`[name="${key}"]`);
        if (field && !field.value) {
          field.value = value;
        }
      });
      createToast("Demo values applied", "success");
    });
  });

  const fillSelects = document.querySelectorAll("[data-fill-select]");
  fillSelects.forEach((select) => {
    const targetId = select.getAttribute("data-fill-select");
    const targetField = document.getElementById(targetId);
    if (!targetField) return;
    select.addEventListener("change", () => {
      if (select.value) {
        targetField.value = select.value;
        targetField.focus();
        createToast("Complaint ID selected", "success");
      }
    });
  });
});
