"""
src/tools/browser.py
Playwright Stealth Browser Automation Tool.
Manages persistent browser profiles, anti-bot evasion, job card scraping,
and automated Easy Apply form completion.
"""

import time
import random
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Page, BrowserContext
from playwright_stealth.stealth import Stealth

import sys
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from src.config import get_config

class StealthBrowser:
    def __init__(self, headless: bool = False):
        self.config = get_config()
        self.headless = headless
        self.profile_dir = self.config.browser_profile_dir
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def __enter__(self):
        self.playwright = sync_playwright().start()
        launch_kwargs = {
            "user_data_dir": str(self.profile_dir),
            "headless": self.headless,
            "viewport": {"width": 1280, "height": 850},
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        }
        try:
            # Launch real Google Chrome for Google OAuth & anti-detection
            self.context = self.playwright.chromium.launch_persistent_context(
                channel="chrome",
                **launch_kwargs
            )
        except Exception:
            self.context = self.playwright.chromium.launch_persistent_context(
                **launch_kwargs
            )

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        Stealth().apply_stealth_sync(self.page)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass

    def check_health(self) -> bool:
        """Verifies Chromium and stealth hooks launch properly."""
        try:
            with sync_playwright() as p:
                b = p.chromium.launch(headless=True)
                pg = b.new_page()
                Stealth().apply_stealth_sync(pg)
                b.close()
            return True
        except Exception:
            return False

    def launch_login_session(self):
        """Interactive session for one-time manual login to LinkedIn and Indeed."""
        print("\n" + "=" * 65)
        print(" 🌐 LAUNCHING STEALTH BROWSER FOR ONE-TIME LOGIN")
        print("=" * 65)
        print(" 1. The browser window will open.")
        print(" 2. Log into LinkedIn and/or Indeed.")
        print(f" 3. Session cookies will be saved in: {self.profile_dir}")
        print("=" * 65 + "\n")

        # If browser context is already active via context manager:
        if self.page:
            try:
                self.page.goto("https://www.linkedin.com/login", wait_until="commit", timeout=45000)
            except Exception as e:
                print(f"Notice during navigation: {e}")

            print("👉 Browser is open at LinkedIn login. Please log in with your credentials.")
            input("✅ Press ENTER here once you have finished logging in: ")
            print("💾 Saving session cookies...")
            print("🎉 Login profile saved!\n")
            return

    def scrape_linkedin_jobs(
        self,
        role: str,
        location: str,
        limit: int = 10,
        work_types: list = None,
        include_external: bool = True,
        cities: list = None,
        date_posted: str = None
    ) -> List[Dict[str, Any]]:
        """Search and extract job cards with JD snippets, apply type detection, and profile URLs."""
        import re as _re

        if not self.page:
            return []

        query = urllib.parse.quote(role)

        # Smart Location Resolution:
        # If user wants Hybrid or On-site, geographic location cannot be literally "Remote".
        # We anchor geographic search to target cities (e.g. "India", "Hyderabad", "Bangalore").
        search_loc = location.strip()
        has_onsite_or_hybrid = any(
            wt.lower().strip() in ("hybrid", "on-site", "onsite") 
            for wt in (work_types or [])
        )
        if search_loc.lower() == "remote" and has_onsite_or_hybrid:
            if cities and len(cities) > 0:
                search_loc = "India" if any(c.lower() == "india" for c in cities) else cities[0]
            else:
                search_loc = "India"

        loc = urllib.parse.quote(search_loc)

        # Build work-type filter (f_WT): 1=On-site, 2=Remote, 3=Hybrid
        wt_map = {"on-site": "1", "onsite": "1", "remote": "2", "hybrid": "3"}
        f_wt_parts = []
        if work_types:
            for wt in work_types:
                mapped = wt_map.get(wt.lower().strip())
                if mapped and mapped not in f_wt_parts:
                    f_wt_parts.append(mapped)

        # Build date-posted filter (f_TPR): r86400=Past 24h, r604800=Past week, r2592000=Past month
        tpr_map = {
            "24h": "r86400", "24hr": "r86400", "24hrs": "r86400", "25h": "r86400", "25hr": "r86400", "25hrs": "r86400",
            "past_24h": "r86400", "past_25h": "r86400", "day": "r86400", "past_day": "r86400",
            "1_week": "r604800", "week": "r604800", "past_week": "r604800", "1w": "r604800",
            "month": "r2592000", "past_month": "r2592000"
        }
        f_tpr = None
        if date_posted:
            f_tpr = tpr_map.get(date_posted.lower().strip())

        url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={loc}"
        # If user selected all 3 workplace types, omit f_WT to maximize search recall across all listings
        if f_wt_parts and len(f_wt_parts) < 3:
            url += f"&f_WT={'%2C'.join(f_wt_parts)}"
        if f_tpr:
            url += f"&f_TPR={f_tpr}"
        if not include_external:
            url += "&f_AL=true"

        print(f"   🔎 Navigating to LinkedIn Jobs: {role} in {search_loc} (types: {work_types}, posted: {date_posted or 'default'})...")
        print(f"   📡 URL: {url}")
        try:
            self.page.goto(url, wait_until="commit", timeout=45000)
            self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass

        time.sleep(random.uniform(3, 5))

        # Check authentication state
        if "login" in self.page.url or self.page.locator("a[href*='login']").count() > 2:
            print("   ⚠️ Not logged in to LinkedIn! Run one-time login setup first.")
            return []

        def deduplicate_text(s: str) -> str:
            if not s:
                return s
            s = s.strip()
            # If split by newline, take first line
            lines = [l.strip() for l in s.split('\n') if l.strip()]
            if lines:
                s = lines[0]
            # Character-level half repetition: "Foo Foo" -> "Foo"
            half = len(s) // 2
            if half > 3 and s[:half].strip() == s[half:].strip():
                return s[:half].strip()
            # Word-level repetition: "Software Engineer Software Engineer" -> "Software Engineer"
            words = s.split()
            if len(words) >= 4 and len(words) % 2 == 0:
                mid = len(words) // 2
                if words[:mid] == words[mid:]:
                    return " ".join(words[:mid])
            return s

        # Scroll search results list to trigger lazy loading of additional listings
        try:
            scroll_containers = [".jobs-search-results-list", ".scaffold-layout__list-detail-inner", "div.jobs-search-results"]
            for s_sel in scroll_containers:
                s_el = self.page.locator(s_sel).first
                if s_el.count() > 0:
                    for _ in range(4):
                        s_el.evaluate("el => el.scrollTop += 600")
                        time.sleep(0.4)
                    break
        except Exception:
            pass

        cards = self.page.locator(".job-card-container, .jobs-search-results__list-item").all()
        print(f"   📋 Found {len(cards)} listings on page.")

        results = []
        for i, card in enumerate(cards[:limit]):
            try:
                card.scroll_into_view_if_needed()
                time.sleep(0.4)

                # ── 1. Extract Title from Card ──────────────────────────────
                title = ""
                card_title_selectors = [
                    ".job-card-list__title span[aria-hidden='true']",
                    "a.job-card-container__link span[aria-hidden='true']",
                    ".artdeco-entity-lockup__title strong",
                    ".job-card-list__title strong",
                    "a.job-card-list__title",
                    "a.job-card-container__link",
                    ".job-card-list__title",
                ]
                for sel in card_title_selectors:
                    try:
                        el = card.locator(sel).first
                        if el.count() > 0:
                            txt = (el.text_content() or el.inner_text() or "").strip()
                            if txt:
                                title = txt
                                break
                    except Exception:
                        pass
                title = deduplicate_text(title) or "Target Position"

                # ── 2. Extract Company from Card ────────────────────────────
                company = ""
                card_company_selectors = [
                    ".artdeco-entity-lockup__subtitle span[aria-hidden='true']",
                    ".job-card-container__primary-description",
                    ".job-card-container__company-name",
                    "span.job-card-container__primary-description",
                    "a.job-card-container__company-name",
                    ".artdeco-entity-lockup__subtitle a",
                    ".artdeco-entity-lockup__subtitle",
                    "a[data-tracking-control-name*='job_card_company']",
                    "[data-anonymize='company-name']",
                ]
                for sel in card_company_selectors:
                    try:
                        el = card.locator(sel).first
                        if el.count() > 0:
                            txt = (el.text_content() or el.inner_text() or "").strip()
                            txt_clean = txt.split('\n')[0].strip()
                            if txt_clean and txt_clean.lower() not in ("company", "about the company", ""):
                                company = txt_clean
                                break
                    except Exception:
                        pass

                # ── 3. Extract Job Profile URL ──────────────────────────────
                job_url = ""
                try:
                    link_elem = card.locator("a[href*='/jobs/view/']").first
                    if link_elem.count() > 0:
                        href = link_elem.get_attribute("href") or ""
                        if href:
                            clean_href = href.split("?")[0]
                            job_url = f"https://www.linkedin.com{clean_href}" if clean_href.startswith("/") else clean_href
                except Exception:
                    pass

                # ── 4. Click to Load Detail Panel ───────────────────────────
                # Click the title link directly for reliable detail panel loading
                try:
                    click_target = card.locator(
                        "a[href*='/jobs/view/'], a.job-card-list__title, a.job-card-container__link, .job-card-list__title"
                    ).first
                    if click_target.count() > 0:
                        click_target.click(timeout=3000)
                    else:
                        card.click(timeout=3000)
                except Exception:
                    try:
                        card.click(timeout=3000)
                    except Exception:
                        pass

                time.sleep(random.uniform(2.0, 3.0))

                # ── 5. Extract Company from Detail Panel if missing ──────────
                if not company or company.lower() == "company":
                    panel_company_selectors = [
                        ".job-details-jobs-unified-top-card__company-name a",
                        ".job-details-jobs-unified-top-card__company-name",
                        ".jobs-unified-top-card__company-name a",
                        ".jobs-unified-top-card__company-name",
                        ".job-details-jobs-unified-top-card__primary-description-container a",
                        ".jobs-unified-top-card__primary-description a",
                        "a.job-details-jobs-unified-top-card__company-name-link",
                        "a[href*='/company/']",
                        "div[class*='company-name']",
                    ]
                    for c_sel in panel_company_selectors:
                        try:
                            c_loc = self.page.locator(c_sel).first
                            if c_loc.count() > 0:
                                c_txt = (c_loc.text_content() or c_loc.inner_text() or "").strip()
                                c_clean = c_txt.split('\n')[0].strip()
                                if c_clean and c_clean.lower() not in ("company", "about the company", ""):
                                    company = c_clean
                                    break
                        except Exception:
                            pass

                company = deduplicate_text(company) or "Company"

                # ── 6. Fallback Title from Detail Panel if generic/duplicated
                if title == "Target Position" or len(title) < 3:
                    panel_title_selectors = [
                        ".job-details-jobs-unified-top-card__job-title",
                        ".jobs-unified-top-card__job-title",
                        "h1.job-details-jobs-unified-top-card__job-title",
                        "h1.t-24",
                        "h2.job-details-jobs-unified-top-card__job-title",
                    ]
                    for t_sel in panel_title_selectors:
                        try:
                            t_loc = self.page.locator(t_sel).first
                            if t_loc.count() > 0:
                                t_txt = (t_loc.text_content() or t_loc.inner_text() or "").strip()
                                if t_txt:
                                    title = deduplicate_text(t_txt)
                                    break
                        except Exception:
                            pass

                # ── 7. Extract JD Snippet from Detail Panel ─────────────────
                # ── 7. Extract JD Snippet from Detail Panel ─────────────────
                # Always attempt to expand the "Show more" button first so full JD is in DOM
                try:
                    show_more_selectors = [
                        "button.jobs-description__footer-button",
                        "button[aria-label*='Show more']",
                        "button[aria-label*='See more']",
                        "button[aria-label*='more']",
                        "button:has-text('Show more')",
                        "button:has-text('See more')",
                        ".artdeco-card__actions button",
                    ]
                    for b_sel in show_more_selectors:
                        b_loc = self.page.locator(b_sel).first
                        if b_loc.count() > 0 and b_loc.is_visible():
                            b_loc.click(timeout=1200)
                            time.sleep(0.3)
                            break
                except Exception:
                    pass

                jd_snippet = ""
                jd_selectors = [
                    "[data-testid='expandable-text-box']",
                    "[id^='JobDetails_AboutTheJob_']",
                    "[componentkey^='JobDetails_AboutTheJob_']",
                    "#job-details",
                    ".jobs-description__content",
                    ".jobs-description-content__text",
                    ".jobs-description",
                    "article.jobs-description__container",
                    ".jobs-box__html-content",
                    ".jobs-search__job-details--container",
                    ".jobs-details__main-content",
                    "[data-sdui-component*='JobDetails']",
                    "[data-sdui-component*='AboutTheJob']",
                    "div[class*='jobs-description']",
                    "div[class*='job-details']",
                ]
                for sel in jd_selectors:
                    try:
                        panel = self.page.locator(sel).first
                        if panel.count() > 0:
                            txt = (panel.text_content() or panel.inner_text() or "").strip()
                            if len(txt) > 40:
                                jd_snippet = txt[:8000].strip()
                                break
                    except Exception:
                        pass

                # ── 7b. Direct URL Fallback: Fetch from job_url if snippet still empty ──
                if len(jd_snippet) < 50 and job_url and self.context:
                    try:
                        detail_pg = self.context.new_page()
                        detail_pg.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                        time.sleep(2)
                        for sel in jd_selectors:
                            try:
                                p_loc = detail_pg.locator(sel).first
                                if p_loc.count() > 0:
                                    t_txt = (p_loc.text_content() or p_loc.inner_text() or "").strip()
                                    if len(t_txt) > 40:
                                        jd_snippet = t_txt[:8000].strip()
                                        break
                            except Exception:
                                pass

                        # Enrich company from direct page if needed
                        if not company or company.lower() == "company":
                            c_loc = detail_pg.locator("a[href*='/company/']").first
                            if c_loc.count() > 0:
                                c_txt = (c_loc.text_content() or "").strip()
                                if c_txt and c_txt.lower() not in ("company", "about the company", ""):
                                    company = deduplicate_text(c_txt)

                        # Enrich title from direct page if generic
                        if title == "Target Position" or len(title) < 3:
                            pg_title = detail_pg.title()
                            if "|" in pg_title:
                                parts = pg_title.split("|")
                                title = deduplicate_text(parts[0])
                                if not company or company.lower() == "company":
                                    company = deduplicate_text(parts[1])

                        detail_pg.close()
                    except Exception:
                        try:
                            detail_pg.close()
                        except Exception:
                            pass

                # ── 8. Detect Apply Type: Easy Apply vs External ────────────
                apply_type = "easy_apply"
                external_url = ""
                try:
                    easy_btn = self.page.locator("button:has-text('Easy Apply')").first
                    if easy_btn.count() > 0 and easy_btn.is_visible():
                        apply_type = "easy_apply"
                    else:
                        apply_btn = self.page.locator("button:has-text('Apply')").first
                        if apply_btn.count() > 0 and apply_btn.is_visible():
                            apply_type = "external"
                            try:
                                ext_link = self.page.locator("a[href*='externalApply'], a.jobs-apply-button--external").first
                                if ext_link.count() > 0:
                                    external_url = ext_link.get_attribute("href") or ""
                            except Exception:
                                pass
                except Exception:
                    pass

                # ── 9. Parse Experience from JD Snippet + Seniority Insight ──
                experience_required = 0
                if jd_snippet:
                    # Look for explicit experience requirement patterns tied to candidate work/experience
                    exp_patterns = [
                        r'(?:minimum|min|at\s+least)\s*(\d+)\s*[-–to]*\s*\d*\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp|relevant\s+experience|work\s+experience|professional\s+experience)',
                        r'(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp|relevant\s+experience|work\s+experience|professional\s+experience)',
                        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp|relevant\s+experience|work\s+experience|professional\s+experience)',
                        r'(?:experience|exp|qualifications?)\s*[:\-]\s*(\d+)\+?\s*(?:years?|yrs?)',
                        r'(?:requires?|requiring)\s*(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)',
                    ]
                    for pattern in exp_patterns:
                        match = _re.search(pattern, jd_snippet, _re.IGNORECASE)
                        if match:
                            experience_required = int(match.group(1))
                            break

                # Also inspect Seniority Level insight if experience is 0
                if experience_required == 0:
                    try:
                        insight_elements = self.page.locator(
                            ".job-details-jobs-unified-top-card__job-insight, .jobs-unified-top-card__job-insight"
                        ).all()
                        for ins in insight_elements:
                            ins_text = (ins.text_content() or "").lower()
                            if "entry level" in ins_text or "internship" in ins_text or "fresher" in ins_text:
                                experience_required = 0
                                break
                            elif "associate" in ins_text:
                                experience_required = 1
                                break
                            elif "mid-senior" in ins_text or "mid senior" in ins_text:
                                experience_required = 3
                                break
                            elif "director" in ins_text or "executive" in ins_text:
                                experience_required = 8
                                break
                    except Exception:
                        pass

                results.append({
                    "index": i + 1,
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": job_url,
                    "job_url": job_url,
                    "has_easy_apply": apply_type == "easy_apply",
                    "apply_type": apply_type,
                    "external_url": external_url,
                    "jd_snippet": jd_snippet,
                    "jd_summary": "",   # Populated by jd_prescreen node
                    "experience_required": experience_required,
                    "applied": False
                })
                print(f"   [{i+1}] {title} @ {company} | {apply_type} | exp: {experience_required}yr | snippet: {len(jd_snippet)} chars")
            except Exception as ex:
                print(f"   ⚠️ Error processing card {i+1}: {ex}")
                continue

        return results

    def apply_to_job(
        self,
        job: Dict[str, Any],
        screening_answer_fn,
        candidate_summary: str,
        resume_upload_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executes the Easy Apply interaction flow on a given job card."""
        if not self.page:
            return {"status": "failed", "error": "Browser page not initialized"}

        try:
            print(f"\n   🎯 Targeting: {job.get('title')} at {job.get('company')}")
            
            # If URL provided, navigate directly; otherwise find on current page
            if job.get("url"):
                self.page.goto(job["url"], wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2, 3.5))

            # Look for Easy Apply button
            apply_btn = self.page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
            if not apply_btn.is_visible():
                return {"status": "skipped", "reason": "No Easy Apply button found (external apply)"}

            apply_btn.click()
            time.sleep(random.uniform(2, 3))

            modal = self.page.locator(".jobs-easy-apply-modal, div[role='dialog']").first
            if not modal.is_visible():
                return {"status": "failed", "error": "Application modal did not open"}

            # Handle multi-step modal (up to 5 steps)
            for step in range(5):
                time.sleep(1.5)

                # Fill empty text inputs / textareas
                inputs = modal.locator("input[type='text'], textarea").all()
                for inp in inputs:
                    val = inp.input_value()
                    if not val:
                        label = inp.get_attribute("aria-label") or inp.get_attribute("id") or "Question"
                        answer = screening_answer_fn(label, candidate_summary)
                        print(f"      📝 Form Q: {label[:35]}... -> A: {answer[:30]}")
                        inp.fill(answer)
                        time.sleep(random.uniform(0.4, 0.9))

                # Handle resume upload if present
                if resume_upload_path and Path(resume_upload_path).exists():
                    file_inputs = modal.locator("input[type='file']").all()
                    for f_inp in file_inputs:
                        try:
                            f_inp.set_input_files(resume_upload_path)
                            print(f"      📎 Attached tailored resume: {Path(resume_upload_path).name}")
                            time.sleep(1.5)
                        except Exception:
                            pass

                # Check for Submit button
                submit_btn = modal.locator("button:has-text('Submit application'), button:has-text('Submit')").first
                if submit_btn.is_visible():
                    print("      🚀 Clicking 'Submit application'...")
                    submit_btn.click()
                    time.sleep(random.uniform(2, 4))
                    return {"status": "submitted", "title": job.get("title"), "company": job.get("company")}

                # Next / Review button
                next_btn = modal.locator("button:has-text('Next'), button:has-text('Review')").first
                if next_btn.is_visible():
                    print("      ➡️ Moving to next step in application modal...")
                    next_btn.click()
                    time.sleep(random.uniform(1.5, 2.5))
                else:
                    break

            return {"status": "submitted", "title": job.get("title"), "company": job.get("company")}

        except Exception as e:
            return {"status": "failed", "error": str(e)}
