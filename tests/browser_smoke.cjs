/* Optional real-browser verification. Not required for running Staydesk. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");
const { spawn } = require("node:child_process");
const root = path.resolve(__dirname, "..");
const data = fs.mkdtempSync(path.join(os.tmpdir(), "staydesk-browser-"));
const python =
  process.env.BROWSER_TEST_PYTHON ||
  path.join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function poll(check) {
  for (let i = 0; i < 100; i++) {
    if (await check()) return;
    await pause(100);
  }
  throw new Error("Condition timeout: " + check.toString());
}
let server;
let logs = "";
async function freePort() {
  const socket = net.createServer();
  await new Promise((resolve) => socket.listen(0, "127.0.0.1", resolve));
  const port = socket.address().port;
  await new Promise((resolve) => socket.close(resolve));
  return port;
}
async function start(port) {
  logs = "";
  server = spawn(python, ["run.py"], {
    cwd: root,
    env: {
      ...process.env,
      HOTEL_PORT: String(port),
      HOTEL_DATA_DIR: data,
      HOTEL_NO_BROWSER: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  server.stdout.on("data", (chunk) => {
    logs += chunk;
  });
  server.stderr.on("data", (chunk) => {
    logs += chunk;
  });
  for (let i = 0; i < 100; i++) {
    if (server.exitCode !== null)
      throw new Error("Server startup failed: " + logs);
    try {
      if ((await fetch(`http://127.0.0.1:${port}/api/health`)).ok) return;
    } catch {}
    await pause(100);
  }
  throw new Error("Server timeout: " + logs);
}
async function stop() {
  if (!server || server.exitCode !== null) return;
  const exited = new Promise((resolve) => server.once("exit", resolve));
  server.kill("SIGTERM");
  await exited;
}
async function run() {
  const port = await freePort();
  const url = `http://127.0.0.1:${port}`;
  let browser;
  try {
    await start(port);
    browser = await chromium.launch({
      headless: true,
      ...(process.env.CHROMIUM_EXECUTABLE
        ? { executablePath: process.env.CHROMIUM_EXECUTABLE }
        : {}),
    });
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1100 },
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(url);
    await poll(async () => (await page.locator("#stay option").count()) === 3);
    await poll(async () =>
      (await page.locator("#updated").textContent()).startsWith("Stand:"),
    );
    fs.mkdirSync(path.join(root, "test-results"), { recursive: true });
    await page.screenshot({
      path: path.join(root, "test-results/desktop.png"),
      fullPage: true,
    });
    async function count(n) {
      await poll(
        async () =>
          (await page.locator("#stat-total").textContent()) === String(n),
      );
    }
    async function wish(text) {
      await page.locator("#wish").fill(text);
      await page.locator("#interpret").click();
      await page.locator("#preview").waitFor({ state: "visible" });
    }
    async function mode(service, mode) {
      await page.locator(`#mode-${service}`).selectOption(mode);
      await poll(
        async () => !(await page.locator(`#mode-${service}`).isDisabled()),
      );
    }
    await wish("Ich hätte gerne zwei Handtücher und eine Pizza.");
    assert.equal(await page.locator(".preview-item").count(), 2);
    await page.locator("#confirm").click();
    await count(2);
    await page.locator("#replay").click();
    await poll(async () =>
      (await page.locator("#feedback").textContent()).startsWith(
        "Wiederholung erkannt",
      ),
    );
    await count(2);
    assert.equal(await page.locator("#stat-received").textContent(), "2");
    await wish("2 Handtücher");
    assert.equal(await page.locator("#confirm").isDisabled(), true);
    await page.locator("#additional").check();
    await page.locator("#confirm").click();
    await count(3);
    await page.locator("#stay").selectOption("stay-204");
    await mode("housekeeping", "lose_response_once");
    await wish("2 Handtücher");
    await page.locator("#confirm").click();
    await count(4);
    const uncertain = page
      .locator("article.order")
      .filter({ has: page.locator(".status.uncertain") });
    assert.equal(await uncertain.count(), 1);
    await uncertain
      .getByRole("button", { name: "Abgleichen / erneut übermitteln" })
      .click();
    await poll(
      async () => (await page.locator(".status.uncertain").count()) === 0,
    );
    assert.equal(await page.locator("#stat-received").textContent(), "4");
    await mode("kitchen", "offline");
    await page.locator("#stay").selectOption("stay-305");
    await wish("2 Handtücher und 1 Pizza");
    await page.locator("#confirm").click();
    await count(6);
    assert.equal(await page.locator(".status.saved").count(), 1);
    assert.equal(await page.locator("#stat-received").textContent(), "5");
    await mode("kitchen", "normal");
    await page
      .locator("article.order")
      .filter({ has: page.locator(".status.saved") })
      .getByRole("button", { name: "Abgleichen / erneut übermitteln" })
      .click();
    await poll(
      async () => (await page.locator("#stat-received").textContent()) === "6",
    );
    // Lose the browser response AFTER the backend has committed the request.
    await page.locator("#stay").selectOption("stay-204");
    await wish("1 Pizza");
    let lose = true;
    await page.route("**/api/requests", async (route) => {
      if (lose) {
        lose = false;
        await route.fetch();
        await route.abort();
      } else await route.continue();
    });
    await page.locator("#confirm").click();
    await poll(
      async () =>
        (await page.locator("#pending-banner").isVisible()) &&
        !(await page.locator("#retry-pending").isDisabled()),
    );
    await page.reload();
    await page.locator("#pending-banner").waitFor({ state: "visible" });
    await page.locator("#retry-pending").click();
    await page.locator("#pending-banner").waitFor({ state: "hidden" });
    await count(7);
    assert.equal(await page.locator("#stat-received").textContent(), "7");
    await page.unroute("**/api/requests");
    const firstOrder = page.locator("article.order").first();
    const firstId = await firstOrder.getAttribute("data-id");
    await firstOrder
      .getByRole("button", { name: "Simulator: Bearbeitung starten" })
      .click();
    const progressing = page.locator(`article[data-id="${firstId}"]`);
    await progressing
      .getByRole("button", { name: "Simulator: Erledigen" })
      .waitFor();
    await progressing
      .getByRole("button", { name: "Simulator: Erledigen" })
      .click();
    await poll(
      async () =>
        (await progressing.locator(".status.completed").count()) === 1,
    );
    await page.locator("#wish").fill("2 Handtücher und 1 Wein");
    await page.locator("#interpret").click();
    await page.locator("#questions").waitFor({ state: "visible" });
    assert.equal(await page.locator("#preview").isVisible(), false);
    await page.screenshot({
      path: path.join(root, "test-results/orders.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: path.join(root, "test-results/mobile.png"),
      fullPage: true,
    });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
    );
    await stop();
    await start(port);
    await page.reload();
    await count(7);
    assert.equal(await page.locator("#stat-received").textContent(), "7");
    assert.deepEqual(errors, []);
    console.log(
      "PASS: confirmation, replay, semantic duplicate/additional, response loss, offline/partial success, browser response loss + reload, progress/completion, clarification, mobile overflow, real process restart; no JS errors.",
    );
  } finally {
    if (browser) await browser.close();
    await stop();
    fs.rmSync(data, { recursive: true, force: true });
  }
}
run().catch((error) => {
  console.error(error);
  console.error(logs);
  process.exitCode = 1;
});
