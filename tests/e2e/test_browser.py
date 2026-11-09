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
    page.select_option("#category", "Theft")
    page.fill("#location", "Station Road")
    page.fill("#description", "Taken from the rack outside the library.")
    page.fill("#incident_date", "2026-11-01")
    page.click(".map--pick", position={"x": 200, "y": 120})  # drop a pin
    page.click("button[type=submit]")
    expect(page.locator("h1")).to_have_text("Bicycle stolen")
    expect(page.locator("main")).to_contain_text("FIR/")
    expect(page.locator(".map--small")).to_be_visible()
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

    # chain of custody
    page.click("text=Log movement or attach a file")
    page.fill("#where-1", "Evidence room, shelf 3")
    page.click("button:has-text('Log')")
    expect(page.locator(".custody")).to_contain_text("stored, Evidence room, shelf 3")

    # a chargesheet needs someone to charge; the page says so, then accepts it once a suspect is linked
    page.click("text=File the chargesheet")
    page.fill("#cs-sections", "BNS 303")
    page.fill("#cs-summary", "Bicycle taken from the rack.")
    page.click("button:has-text('File chargesheet')")
    expect(page.locator(".flash--error")).to_contain_text("suspect or accused")
    headers = {"X-Requested-With": "crms"}
    person = page.request.post(page.base + "/api/criminals", headers=headers, data={"name": "Ravi Menon"}).json()
    page.request.post(page.base + "/api/cases/1/criminals", headers=headers, data={"criminal_id": person["criminal_id"], "role": "accused"})
    page.reload()
    page.click("text=File the chargesheet")
    page.fill("#cs-sections", "BNS 303")
    page.fill("#cs-summary", "Bicycle taken from the rack.")
    page.click("button:has-text('File chargesheet')")
    expect(page.locator(".facts").filter(has_text="BNS 303")).to_be_visible()
    expect(page.locator(".timeline")).to_contain_text("Chargesheet filed under BNS 303")

    # the map and the station pages
    page.goto(page.base + "/map")
    expect(page.locator(".map--big")).to_be_visible()
    expect(page.locator("main")).to_contain_text("Busiest areas")
    page.goto(page.base + "/stations")
    page.click("text=Central")
    expect(page.locator("h1")).to_have_text("Central")

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



def test_speaking_a_complaint_fills_the_form(page):
    from datetime import date, timedelta

    # headless Chromium cannot hear anything, so a stand-in speech engine "hears" one sentence
    page.add_init_script("""
      window.SpeechRecognition = window.webkitSpeechRecognition = class {
        start() {
          setTimeout(() => {
            const heard = Object.assign([{ transcript: 'someone stole my bike near the bus stand yesterday evening' }], { isFinal: true });
            this.onresult({ resultIndex: 0, results: [heard] });
          }, 50);
        }
        stop() { setTimeout(() => this.onend(), 0); }
        abort() {}
      };
    """)
    sign_in(page, "asha@e2e.test")
    page.goto(page.base + "/complaints/new")
    page.fill("#location", "")
    page.click("text=Speak your complaint")
    expect(page.locator(".voice-heard")).to_contain_text("stole my bike")
    page.click("text=Stop and fill the form")

    expect(page.locator(".voice-result")).to_contain_text("Check every field")
    expect(page.locator("#title")).to_have_value("Theft at the bus stand")
    expect(page.locator("#category")).to_have_value("Theft")
    expect(page.locator("#location")).to_have_value("the bus stand")
    expect(page.locator("#incident_date")).to_have_value((date.today() - timedelta(days=1)).isoformat())
    expect(page.locator("#description")).to_have_value("Someone stole my bike near the bus stand yesterday evening.")
