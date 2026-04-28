// SkyEngPro per-tenant brand loader.
//
// Reads frappe.boot.brand (set server-side by skyengpro_brand.theme.boot_session)
// and applies it to the desk:
//   - injects CSS variables on :root so skyengpro.css picks up the tenant palette
//   - swaps the navbar logo
//   - swaps the favicon
//
// Designed to be safe: any failure logs and falls through. Never blocks the desk.

(function () {
    "use strict";

    function applyBrand() {
        if (!window.frappe || !frappe.boot || !frappe.boot.brand) {
            console.debug("[skyengpro_brand] applyBrand skipped: frappe.boot.brand is",
                          window.frappe && frappe.boot ? frappe.boot.brand : "(no frappe)");
            return;
        }
        var b = frappe.boot.brand;
        console.info("[skyengpro_brand] applying tenant '" + b.slug + "' logo=" + b.logo_navbar);

        // 1) CSS variables on :root — skyengpro.css consumes these.
        injectStyle("skyengpro-tenant-vars",
            ":root{" +
                "--skyengpro-primary:" + b.primary + ";" +
                "--skyengpro-primary-hover:" + b.primary_hover + ";" +
                "--skyengpro-primary-light:" + b.primary_light + ";" +
                "--skyengpro-navbar-bg:" + b.navbar_bg + ";" +
                "--skyengpro-navbar-fg:" + b.navbar_fg + ";" +
            "}"
        );

        // 2) Navbar logo. Pick the variant that contrasts with the navbar bg.
        //    On a dark navbar, the white logo reads better; on a light bg
        //    (login card), the color logo is correct. The earlier "always
        //    color" approach hid the adorsys logo against the navy navbar.
        //    We detect the actual rendered navbar background — falls back to
        //    the navbar_bg from boot if not yet rendered.
        var actualBg = getNavbarBg() || b.navbar_bg;
        var preferWhite = isDark(actualBg);
        var logoUrl = (preferWhite && b.logo_navbar_white)
            ? b.logo_navbar_white
            : b.logo_navbar;
        swapLogo(logoUrl);

        // 3) Favicon
        if (b.favicon) swapFavicon(b.favicon);
    }

    function injectStyle(id, css) {
        var el = document.getElementById(id);
        if (!el) {
            el = document.createElement("style");
            el.id = id;
            document.head.appendChild(el);
        }
        el.textContent = css;
    }

    function swapLogo(url) {
        if (!url) return;
        // Cover all known logo render points across Frappe v15:
        //   - /app (Vue SPA): .navbar .navbar-brand img, .app-logo
        //   - /desk and /desk/desktop (legacy Jinja): #brand-logo
        //   - login + portal templates: .app-logo
        var selectors = [
            "#brand-logo",                               // legacy /desk template
            ".navbar-home img",                          // legacy /desk navbar wrapper
            ".navbar .navbar-brand img",                 // /app SPA
            "header.navbar .navbar-brand img",           // /app SPA (header tag)
            ".navbar .app-logo",                         // misc components
            ".app-logo",                                 // login + portal
        ];
        var imgs = document.querySelectorAll(selectors.join(","));
        console.debug("[skyengpro_brand] swapLogo found", imgs.length, "img element(s) for url", url);
        imgs.forEach(function (img) {
            if (img.src !== url) img.src = url;
            // Strip any inline maxHeight from older versions of this script.
            img.style.maxHeight = "";
        });
    }

    function swapFavicon(url) {
        var existing = document.querySelectorAll("link[rel~='icon']");
        existing.forEach(function (l) { l.parentNode.removeChild(l); });
        var link = document.createElement("link");
        link.rel = "icon";
        link.href = url;
        document.head.appendChild(link);
    }

    function isDark(color) {
        if (!color) return true;  // assume dark navbar if unknown
        var rgb;
        if (color.charAt(0) === "#") {
            var h = color.length === 4
                ? color.replace(/^#(.)(.)(.)$/, "#$1$1$2$2$3$3")
                : color;
            rgb = [
                parseInt(h.substr(1, 2), 16),
                parseInt(h.substr(3, 2), 16),
                parseInt(h.substr(5, 2), 16),
            ];
        } else {
            // rgb(...)/rgba(...) form — strip and split
            var m = color.match(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
            if (!m) return true;
            rgb = [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)];
        }
        var luma = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]);
        return luma < 128;
    }

    function getNavbarBg() {
        // Read the actually-rendered background of the navbar — picks up our
        // CSS-var override if applied, or the original Frappe value otherwise.
        var nav = document.querySelector("header.navbar, .navbar");
        if (!nav) return null;
        var bg = window.getComputedStyle(nav).backgroundColor;
        return (bg && bg !== "rgba(0, 0, 0, 0)") ? bg : null;
    }

    // Run after Frappe finishes booting (when frappe.boot exists), and again
    // on app_ready as a safety net for SPA route changes that re-render header.
    if (window.frappe && frappe.boot && frappe.boot.brand) {
        applyBrand();
    }
    document.addEventListener("DOMContentLoaded", applyBrand);
    if (window.$) {
        $(document).on("app_ready startup_ready", applyBrand);
    }

    // The legacy /desk page mounts the navbar (and its #brand-logo img) AFTER
    // DOMContentLoaded and AFTER app_ready, via desk.js initialisation. So a
    // one-shot apply runs before the img exists and fails silently.
    //
    // Watch the body for any added/changed nodes and re-apply when we see a
    // logo element whose src isn't ours yet. The check is cheap (only when
    // mutations happen) and self-terminates: once the src matches, the
    // condition `img.src !== url` short-circuits the swap.
    function observeNavbar() {
        if (!window.MutationObserver) return;
        var pending = false;
        var obs = new MutationObserver(function () {
            if (pending) return;
            pending = true;
            // Coalesce bursts of mutations into one apply per animation frame.
            requestAnimationFrame(function () {
                pending = false;
                applyBrand();
            });
        });
        obs.observe(document.body || document.documentElement, {
            childList: true,
            subtree: true,
            attributeFilter: ["src"],
        });
    }
    if (document.body) {
        observeNavbar();
    } else {
        document.addEventListener("DOMContentLoaded", observeNavbar);
    }
})();
