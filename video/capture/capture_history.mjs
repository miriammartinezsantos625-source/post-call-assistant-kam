// Marks the duplicated commitment as done (the app's own reversible action) and re-captures the history screen.
import { createRequire } from "node:module";
import path from "node:path";
const [, , pptrDir, chromePath, out] = process.argv;
const require = createRequire(path.join(pptrDir, "package.json"));
const puppeteer = require(pptrDir);
const browser = await puppeteer.launch({ executablePath: chromePath, headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900, deviceScaleFactor: 2 });
const idle = async () => { await new Promise(r => setTimeout(r, 700)); await page.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), { timeout: 60000 }); await new Promise(r => setTimeout(r, 900)); };
await page.goto("http://localhost:8502/page_history", { waitUntil: "networkidle2" });
await page.waitForFunction(() => document.body.innerText.includes("Historial y"), { timeout: 30000 });
await idle();
await page.click('input[aria-label="Cuenta"]'); await page.keyboard.type("4 ·"); await page.keyboard.press("Enter"); await idle();
const count = await page.evaluate(() => document.body.innerText.split("Hablar de circuitos de derivación con").length - 1);
console.log("occurrences before:", count);
if (count > 2) {   // brief + expander list each show it; >2 means duplicated
  const exp = await page.waitForSelector("summary::-p-text(Gestionar compromisos pendientes)");
  await exp.click(); await idle();
  const clicked = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('[data-testid="stHorizontalBlock"]')].filter(r => r.innerText.includes("Hablar de circuitos"));
    const btn = rows.length ? [...rows[0].querySelectorAll("button")].find(b => b.innerText.includes("Hecho")) : null;
    if (btn) { btn.click(); return true; } return false;
  });
  console.log("marked one as done:", clicked); await idle();
}
await page.evaluate(() => window.scrollTo(0, 0));
await page.screenshot({ path: out });
console.log("saved", out);
await browser.close();
