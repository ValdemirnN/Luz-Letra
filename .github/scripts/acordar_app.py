"""Acorda o app no Streamlit Community Cloud e mantém uma sessão aberta por alguns segundos.

- Abre o app; se aparecer a tela de "dormindo", clica em "Yes, get this app back up!".
- Só considera sucesso quando o app realmente carregou (senão sai com erro e o GitHub avisa por e-mail).
- A URL pode ser trocada pela variável APP_URL (Settings → Variables → Actions).
"""
import asyncio
import os
import re
import sys

from playwright.async_api import async_playwright

URL = (os.environ.get("APP_URL") or "https://luzeletra.streamlit.app/").strip()
BOTAO_ACORDAR = re.compile(r"get this app back up", re.I)


async def app_carregou(page):
    """O app pode estar direto na página ou dentro do iframe do Streamlit Cloud."""
    if await page.locator('[data-testid="stApp"]').count():
        return True
    quadro = page.frame_locator('iframe[title="streamlitApp"]')
    return await quadro.locator('[data-testid="stApp"]').count() > 0


async def esperar_app(page, segundos):
    for _ in range(segundos // 3):
        if await app_carregou(page):
            return True
        await page.wait_for_timeout(3000)
    return False


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        for tentativa in range(1, 4):
            print(f"Tentativa {tentativa}: abrindo {URL}")
            try:
                await page.goto(URL, wait_until="domcontentloaded", timeout=90000)
            except Exception as e:
                print("  não abriu:", e)
                continue
            await page.wait_for_timeout(8000)

            botao = page.get_by_role("button", name=BOTAO_ACORDAR)
            if await botao.count():
                print("  App dormindo — clicando para acordar...")
                await botao.first.click()
                await page.wait_for_timeout(5000)

            if await esperar_app(page, 90):
                print("  App está de pé. Mantendo a sessão aberta por 25s...")
                await page.wait_for_timeout(25000)
                await browser.close()
                print("OK")
                return 0
            print("  App ainda não carregou.")
        await browser.close()
        print("FALHA: não consegui confirmar que o app acordou.")
        return 1


sys.exit(asyncio.run(main()))
