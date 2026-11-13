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
        page.wait_for_selector("h1, .empty")
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


def test_admin_makes_a_token_and_a_webhook(page):
    sign_in(page, "admin@e2e.test")
    page.goto(page.base + "/integrations")
    page.fill("#tk-name", "Court feed")
    page.click("text=Create token")
    expect(page.locator(".voice-panel code")).to_contain_text("crms_")
    page.click("text=I have saved it")
    expect(page.locator("table.data").first).to_contain_text("Court feed")

    page.fill("#wh-url", "https://example.test/hook")
    page.check("input[value='case.opened']")
    page.click("text=Add webhook")
    expect(page.locator(".voice-panel code")).to_be_visible()  # the signing secret, shown once
    page.click("text=I have saved it")
    expect(page.locator("table.data").nth(1)).to_contain_text("case.opened")
    # remove it again, or every later test that opens a case would try to deliver to this address
    for hook in page.request.get(page.base + "/api/webhooks").json()["items"]:
        page.request.delete(page.base + f"/api/webhooks/{hook['webhook_id']}", headers={"X-Requested-With": "crms"})


def test_similar_complaint_is_flagged_before_filing(page):
    sign_in(page, "asha@e2e.test")

    def fill(title, text):
        page.goto(page.base + "/complaints/new")
        page.fill("#title", title)
        page.fill("#description", text)
        page.fill("#location", "Harbour road jetty")
        page.fill("#incident_date", "2026-09-14")
        page.select_option("#category", "Theft")

    fill("Boat engine stolen", "The outboard engine of my boat was stolen from the jetty on Harbour road")
    page.click("text=Submit complaint")
    expect(page).to_have_url(re.compile(r"/complaints/\d+$"))

    fill("Boat engine theft", "Someone stole the outboard engine from my boat at the Harbour road jetty")
    page.click("text=Submit complaint")
    expect(page.locator(".voice-panel[role=alert]")).to_contain_text("You may have filed this already")
    page.click("text=This is a different incident")
    expect(page).to_have_url(re.compile(r"/complaints/\d+$"))


def test_forms_in_hindi_and_tamil(page):
    page.goto(page.base + "/login")
    page.select_option(".lang-pick", "ta")
    expect(page.locator("h1")).to_have_text("உள்நுழை")
    expect(page.locator("html")).to_have_attribute("lang", "ta")
    page.select_option(".lang-pick", "hi")
    expect(page.locator("h1")).to_have_text("साइन इन करें")
    page.fill("#email", "asha@e2e.test")
    page.fill("#password", "password123")
    page.click("button[type=submit]")
    expect(page.locator(".who")).to_be_visible()

    page.goto(page.base + "/complaints/new")  # a full reload keeps the chosen language
    expect(page.locator("h1")).to_have_text("शिकायत दर्ज करें")
    expect(page.locator("label[for=category]")).to_have_text("श्रेणी")
    expect(page.locator("#category option[value=Theft]")).to_have_text("चोरी")

    # the form still sends the English values the server expects
    page.fill("#title", "दुकान का ताला टूटा")
    page.fill("#description", "रात में दुकान का ताला तोड़कर सामान ले गए")
    page.fill("#location", "मुख्य बाज़ार")
    page.fill("#incident_date", "2026-08-02")
    page.select_option("#category", "Burglary")
    page.click("text=शिकायत जमा करें")
    expect(page).to_have_url(re.compile(r"/complaints/\d+$"))
    expect(page.locator(".page-head .badge").last).to_have_text("दर्ज")
    expect(page.locator("h2").first).to_have_text("शिकायत")


def test_tamil_and_hindi_fit_on_a_phone(page):
    page.set_viewport_size({"width": 390, "height": 800})
    page.goto(page.base + "/login")
    for code in ("ta", "hi"):
        page.select_option(".lang-pick", code)
        sign_in_needed = page.locator("#email").count()
        if sign_in_needed:
            page.fill("#email", "asha@e2e.test")
            page.fill("#password", "password123")
            page.click("button[type=submit]")
            expect(page.locator(".who")).to_be_visible()
        for path in ("/complaints", "/complaints/new", "/notifications", "/records", "/profile"):
            page.goto(page.base + path)
            page.wait_for_selector("h1, .empty")
            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            assert overflow <= 0, f"{path} in {code} scrolls sideways by {overflow}px"


def test_staff_screens_work_in_tamil_and_hindi(page):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(page, "admin@e2e.test")
    paths = (
        "/dashboard", "/complaints", "/complaints/1", "/cases", "/cases/1", "/criminals", "/criminals/new", "/map",
        "/stations", "/stations/1", "/reports", "/users", "/audit", "/integrations", "/search?q=boat", "/notifications",
    )
    for code in ("ta", "hi"):
        page.select_option(".lang-pick", code)
        for path in paths:
            page.goto(page.base + path)
            page.wait_for_selector("h1, .empty")
            page.wait_for_timeout(150)
        # the menu itself is translated, not just the page body
        assert page.locator(".pivot a").first.inner_text() not in ("Dashboard", "")
    assert errors == []

    # the longer words must not push a phone screen sideways
    page.set_viewport_size({"width": 390, "height": 800})
    for code in ("ta", "hi"):
        page.select_option(".lang-pick", code)
        for path in paths:
            page.goto(page.base + path)
            page.wait_for_selector("h1, .empty")
            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            assert overflow <= 0, f"{path} in {code} scrolls sideways by {overflow}px"


def test_accounts_table_sorts_when_a_heading_is_clicked(page):
    sign_in(page, "admin@e2e.test")
    page.goto(page.base + "/users")
    page.click("th button:has-text('Email')")
    expect(page).to_have_url(re.compile(r"sort=email&dir=asc"))
    emails = page.locator("table.data").first.locator("tbody tr td:nth-child(2)").all_inner_texts()
    assert emails == sorted(emails)
    page.click("th button:has-text('Email')")
    expect(page).to_have_url(re.compile(r"dir=desc"))
    first = page.locator("table.data").first.locator("tbody tr td:nth-child(2)").first
    expect(first).to_have_text(emails[-1])  # the table is reloaded with the last address on top


HEADERS = {"X-Requested-With": "crms"}


def file_via_api(page, title):
    made = page.request.post(page.base + "/api/complaints", headers=HEADERS, data={
        "title": title, "description": "Left at the bus stop.", "location": "Bus stand", "incident_date": "2026-11-02", "category": "Theft",
    })
    return made.json()["complaint_id"]


def sign_out(page):
    page.request.post(page.base + "/api/auth/logout", headers=HEADERS)


def test_citizen_edits_then_withdraws_a_complaint(page):
    sign_in(page, "asha@e2e.test")
    number = file_via_api(page, "Bag lost")
    page.goto(page.base + f"/complaints/{number}")
    page.click("text=Edit complaint")
    expect(page.locator("h1")).to_have_text("Edit your complaint")
    page.fill("#title", "Backpack lost at the bus stand")
    page.click("button:has-text('Save changes')")
    expect(page.locator("h1")).to_have_text("Backpack lost at the bus stand")
    page.click("summary:has-text('Withdraw this complaint')")
    page.click("button:has-text('Yes, withdraw it')")
    expect(page.locator(".badge", has_text="Withdrawn")).to_be_visible()
    expect(page.locator("text=Edit complaint")).to_have_count(0)


def test_officer_takes_an_unassigned_case(page):
    sign_in(page, "asha@e2e.test")
    number = file_via_api(page, "Phone snatched")
    sign_out(page)
    sign_in(page, "officer@e2e.test")
    page.request.post(page.base + f"/api/complaints/{number}/verify", headers=HEADERS)
    case = page.request.post(page.base + f"/api/complaints/{number}/register-case", headers=HEADERS, data={"station_id": 1}).json()["case_id"]
    page.goto(page.base + f"/cases/{case}")
    expect(page.locator("main")).to_contain_text("Only the assigned officer or an admin can change this case.")
    page.click("button:has-text('Take this case')")
    expect(page.locator(".panel--tile")).to_contain_text("Olga")
    expect(page.locator("button:has-text('Take this case')")).to_have_count(0)


def test_a_filter_can_be_saved_and_opened_again(page):
    sign_in(page, "admin@e2e.test")
    page.goto(page.base + "/cases?status=Under+Investigation")
    page.fill("input[name=name]", "Open ones")
    page.click("button:has-text('Save view')")
    link = page.locator(".views-list a", has_text="Open ones")
    expect(link).to_be_visible()
    page.goto(page.base + "/cases")
    page.click(".views-list a:has-text('Open ones')")
    expect(page).to_have_url(re.compile(r"status=Under\+Investigation"))
    page.click("button[aria-label='Delete the view Open ones']")
    expect(page.locator(".views-list")).to_have_count(0)


def test_forgotten_password_page_answers_the_same_for_any_address(page):
    page.goto(page.base + "/login")
    page.click("text=Forgot your password?")
    expect(page.locator("h1")).to_have_text("Reset your password")  # the sign-in form has an #email too
    page.fill("#email", "nobody@e2e.test")
    page.click("button:has-text('Send the link')")
    expect(page.locator("main")).to_contain_text("a link to choose a new password is on its way")
