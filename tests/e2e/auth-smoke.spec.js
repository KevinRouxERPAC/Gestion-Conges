const { test, expect } = require("@playwright/test");

test("page de connexion accessible", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "ERPAC" })).toBeVisible();
  await expect(page.getByLabel("Identifiant")).toBeVisible();
  await expect(page.getByLabel("Mot de passe")).toBeVisible();
  await expect(page.getByRole("button", { name: "Se connecter" })).toBeVisible();
});
