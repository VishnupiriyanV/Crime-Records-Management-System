"""One walk through the app as a citizen and then as an admin."""
import re

from playwright.sync_api import expect


def sign_in(page, email):
    page.goto(page.base + "/login")
    page.fill("#email", email)
    page.fill("#password", "password123")
    page.click("button[type=submit]")
    expect(page.locator(".who")).to_be_visible()


def test_complaint_to_case(page):
    sign_in(page, "asha@e2e.test")
    page.click("text=File a complaint")
    page.fill("#title", "Bicycle stolen")
    page.fill("#location", "Station Road")
    page.fill("#description", "Taken from the rack outside the library.")
    page.fill("#incident_date", "2026-11-01")
    page.click("button[type=submit]")
    expect(page.locator("h1")).to_have_text("Bicycle stolen")
    expect(page.locator(".progress li.now")).to_have_text("Filed")

    # a note and a file from the citizen
    page.fill("#body", "It was a red bicycle.")
    page.click("text=Add >> nth=-1")
    page.set_input_files("#file", {"name": "photo.txt", "mimeType": "text/plain", "buffer": b"serial 12345"})
    page.click("text=Upload")
    page.click("button:has-text('photo.txt')")
    expect(page.locator("dialog[open] .preview-text")).to_have_text("serial 12345")
    page.keyboard.press("Escape")
    page.click("text=Sign out")

    sign_in(page, "admin@e2e.test")
    page.goto(page.base + "/complaints")
    page.click("text=Bicycle stolen")
    page.click("text=Verify complaint")
    page.select_option("#station_id", label="Central")
    page.click("text=Register case")
    expect(page.locator("h1")).to_have_text("Bicycle stolen")
    expect(page.locator(".timeline")).to_contain_text("Case opened")

    page.click("text=Record evidence")
    page.fill("#ev-desc", "CCTV still of the rack")
    page.fill("#type", "CCTV")
    page.click("text=Save evidence")
    expect(page.locator(".timeline")).to_contain_text("Evidence 1 recorded")

    # search, shortcuts and exports
    page.fill(".search input", "bicycle")
    page.keyboard.press("Enter")
    expect(page.locator("h1")).to_have_text("Search")
    expect(page.locator("main")).to_contain_text("Case 1: Bicycle stolen")
    page.goto(page.base + "/cases")
    expect(page.locator(".who")).to_be_visible()  # the shortcuts start once the session has loaded
    page.keyboard.press("g")
    page.keyboard.press("p")
    expect(page).to_have_url(re.compile("/reports$"))
    expect(page.locator("svg.chart").first).to_be_visible()
    with page.expect_download() as download:
        page.goto(page.base + "/cases")
        page.click("text=Export CSV")
    assert download.value.suggested_filename == "cases.csv"
    page.goto(page.base + "/audit")
    expect(page.locator("table.data")).to_contain_text("Under Investigation")


def test_dark_mode_and_phone_layout(page):
    sign_in(page, "admin@e2e.test")
    page.click(".theme-btn")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")  # remembered

    page.set_viewport_size({"width": 390, "height": 800})
    for path in ("/dashboard", "/cases", "/reports", "/users", "/audit"):
        page.goto(page.base + path)
        page.wait_for_selector("h1")
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 0, f"{path} scrolls sideways by {overflow}px"

