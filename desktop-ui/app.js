const selectedEl = document.querySelector("#selected");
const copyBtn = document.querySelector("#copyBtn");
const commandButtons = [...document.querySelectorAll("[data-cmd]")];

let current = "";

for (const btn of commandButtons) {
  btn.addEventListener("click", () => {
    current = btn.dataset.cmd || "";
    selectedEl.textContent = current || "No command selected.";
  });
}

copyBtn.addEventListener("click", async () => {
  if (!current) return;
  try {
    await navigator.clipboard.writeText(current);
    copyBtn.textContent = "Copied";
    setTimeout(() => {
      copyBtn.textContent = "Copy command";
    }, 1200);
  } catch {
    copyBtn.textContent = "Copy failed";
    setTimeout(() => {
      copyBtn.textContent = "Copy command";
    }, 1200);
  }
});
