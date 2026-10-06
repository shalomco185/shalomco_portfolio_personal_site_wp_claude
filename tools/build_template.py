#!/usr/bin/env python3
"""Builds the Elementor one-page template (InBio light style) for Shalom Cohen.

    python3 tools/build_template.py          -> elementor/shalom-cohen-portfolio-inbio.json      (Elementor Free)
    python3 tools/build_template.py --pro    -> elementor/shalom-cohen-portfolio-inbio-pro.json  (Elementor Pro)

Import in WordPress: Templates > Saved Templates > Import Templates.

Only classic (non-atomic) widgets in Section/Column layout are used.
Free build: heading, text-editor, button, image, icon-box, icon-list, social-icons,
counter, progress, accordion, html, shortcode, spacer.
Pro build adds: nav-menu (+ sticky header), progress-tracker, animated-headline,
blockquote, flip-box, call-to-action, form, share-buttons, motion effects and
element Custom CSS.
All fonts: "Assistant", all font sizes in px.
"""
import json
import os
import random
import sys
from urllib.parse import quote

PRO = "--pro" in sys.argv

random.seed(185)

# ---------------------------------------------------------------- design tokens
FONT = "Assistant"
BG = "#ECF0F3"
PRIMARY = "#FF014F"
HEADING = "#3C3E41"
BODY = "#474B50"
MUTED = "#878E99"
LINE = "#DCE1E4"
CARD_A = "#E2E8EC"
CARD_B = "#FFFFFF"

PHONE = "054-4755-025"
PHONE_INTL = "972544755025"
EMAIL = "shalomco185@gmail.com"
SITE_AUDIT = "https://docs.google.com/presentation/d/1JgnzTpKl0bJt7pKhb_tBH9UylWct5m8dB9t8lZ7PT8A/edit?usp=sharing"
PLACEHOLDER = "/wp-content/plugins/elementor/assets/images/placeholder.png"

_used = set()


def uid():
    while True:
        v = "%07x" % random.randrange(16 ** 7)
        if v not in _used:
            _used.add(v)
            return v


# ---------------------------------------------------------------- helpers
def px(size):
    return {"unit": "px", "size": size, "sizes": []}


def box(t, r=None, b=None, l=None, unit="px"):
    r = t if r is None else r
    b = t if b is None else b
    l = r if l is None else l
    return {"unit": unit, "top": str(t), "right": str(r), "bottom": str(b), "left": str(l),
            "isLinked": len({t, r, b, l}) == 1}


def typo(prefix, size, weight="400", lh=None, mobile=None, tablet=None, ls=None, transform=None):
    d = {
        f"{prefix}_typography": "custom",
        f"{prefix}_font_family": FONT,
        f"{prefix}_font_size": px(size),
        f"{prefix}_font_weight": str(weight),
    }
    if lh:
        d[f"{prefix}_line_height"] = px(lh)
    if tablet:
        d[f"{prefix}_font_size_tablet"] = px(tablet)
    if mobile:
        d[f"{prefix}_font_size_mobile"] = px(mobile)
        if lh:
            d[f"{prefix}_line_height_mobile"] = px(round(lh * mobile / size))
    if ls is not None:
        d[f"{prefix}_letter_spacing"] = px(ls)
    if transform:
        d[f"{prefix}_text_transform"] = transform
    return d


def link(url, external=False, nofollow=False):
    return {"url": url, "is_external": "on" if external else "", "nofollow": "on" if nofollow else "",
            "custom_attributes": ""}


def icon(value):
    lib = "fa-brands" if value.startswith("fab ") else ("fa-regular" if value.startswith("far ") else "fa-solid")
    return {"value": value, "library": lib}


def widget(wtype, settings):
    return {"id": uid(), "elType": "widget", "isInner": False, "settings": settings,
            "elements": [], "widgetType": wtype}


def column(elements, size=100, inner=False, **settings):
    std = min((100, 66, 50, 33, 25), key=lambda v: abs(v - size))
    s = {"_column_size": std, "_inline_size": None if size == 100 else (33.333 if size == 33 else size)}
    s.update(settings)
    return {"id": uid(), "elType": "column", "isInner": inner, "settings": s, "elements": elements}


def section(columns, inner=False, **settings):
    s = {"gap": "extended"}
    if not inner:
        s.update({
            "layout": "boxed",
            "content_width": px(1230),
            "background_background": "classic",
            "background_color": BG,
            "padding": box(100, 0, 100, 0),
            "padding_tablet": box(80, 15, 80, 15),
            "padding_mobile": box(60, 10, 60, 10),
            "border_border": "solid",
            "border_width": box(0, 0, 1, 0),
            "border_color": LINE,
        })
    s.update(settings)
    return {"id": uid(), "elType": "section", "isInner": inner, "settings": s, "elements": columns}


def card_settings(pad=(40, 35), radius=10, cls="inb-card", hover=True):
    return {
        "background_background": "gradient",
        "background_color": CARD_A,
        "background_color_b": CARD_B,
        "background_gradient_type": "linear",
        "background_gradient_angle": {"unit": "deg", "size": 145, "sizes": []},
        "border_radius": box(radius),
        "padding": box(pad[0], pad[1], pad[0], pad[1]),
        "padding_mobile": box(30, 22, 30, 22),
        "margin": box(0, 0, 30, 0),
        "css_classes": cls + (" inb-hover" if hover else ""),
    }


def card(elements, size=33, **extra):
    s = card_settings(**{k: v for k, v in extra.items() if k in ("pad", "radius", "cls", "hover")})
    s.update({k: v for k, v in extra.items() if k not in ("pad", "radius", "cls", "hover")})
    return column(elements, size, inner=True, **s)


def heading(text, tag="h2", size=40, weight="700", color=HEADING, align="right", lh=None, mobile=None,
            url=None, **extra):
    s = {"title": text, "header_size": tag, "align": align, "title_color": color}
    s.update(typo("typography", size, weight, lh or round(size * 1.3), mobile))
    if url:
        s["link"] = link(url, external=url.startswith("http"))
    s.update(extra)
    return widget("heading", s)


def text(html, size=18, color=BODY, align="right", lh=30, mobile=None, **extra):
    s = {"editor": html, "align": align, "text_color": color}
    s.update(typo("typography", size, "400", lh, mobile or (16 if size > 16 else None)))
    s.update(extra)
    return widget("text-editor", s)


def button(label, url, ico=None, primary=False, align="right", size=16, **extra):
    s = {
        "text": label,
        "link": link(url, external=url.startswith("http")),
        "align": align,
        "align_mobile": "justify" if align != "center" else "center",
        "button_text_color": "#FFFFFF" if primary else PRIMARY,
        "background_color": PRIMARY if primary else BG,
        "hover_color": "#FFFFFF",
        "button_background_hover_color": PRIMARY if not primary else "#E0003F",
        "border_radius": box(6),
        "text_padding": box(18, 36, 18, 36),
        "_css_classes": "inb-btn",
    }
    s.update(typo("typography", size, "600", 22, ls=0.5))
    if ico:
        s["selected_icon"] = icon(ico)
        s["icon_align"] = "right"
        s["icon_indent"] = px(10)
    s.update(extra)
    return widget("button", s)


def image(url, alt_link=None, radius=10, **extra):
    s = {"image": {"url": url, "id": "", "alt": "", "source": "url"}, "image_size": "full", "align": "center",
         "image_border_radius": box(radius), "width": {"unit": "%", "size": 100, "sizes": []}}
    if alt_link:
        s["link_to"] = "custom"
        s["link"] = link(alt_link, external=True)
    s.update(extra)
    return widget("image", s)


def icon_box(ico, title, desc, align="right", **extra):
    s = {
        "selected_icon": icon(ico),
        "title_text": title,
        "description_text": desc,
        "position": "top",
        "text_align": align,
        "title_size": "h3",
        "primary_color": PRIMARY,
        "icon_size": px(44),
        "icon_space": px(22),
        "title_bottom_space": px(14),
        "title_color": HEADING,
        "description_color": BODY,
    }
    s.update(typo("title_typography", 22, "600", 30, 20))
    s.update(typo("description_typography", 17, "400", 28, 16))
    s.update(extra)
    return widget("icon-box", s)


def icon_list(items, view="traditional", ico_color=PRIMARY, color=BODY, size=17, align="right", **extra):
    lst = []
    for it in items:
        if isinstance(it, str):
            it = {"text": it}
        row = {"_id": uid(), "text": it["text"], "selected_icon": icon(it.get("icon", "fas fa-check"))}
        if it.get("url"):
            row["link"] = link(it["url"], external=it["url"].startswith("http"))
        lst.append(row)
    s = {"view": view, "icon_list": lst, "icon_color": ico_color, "text_color": color,
         "text_color_hover": PRIMARY, "icon_size": px(14), "text_indent": px(10), "icon_align": align,
         "space_between": px(10)}
    s.update(typo("icon_typography", size, "500", round(size * 1.6), 16 if size > 16 else None))
    s.update(extra)
    return widget("icon-list", s)


def social(items, align="right", **extra):
    s = {
        "social_icon_list": [{"_id": uid(), "social_icon": icon(i), "link": link(u, external=u.startswith("http"))}
                             for i, u in items],
        "shape": "rounded",
        "align": align,
        "icon_color": "custom",
        "icon_primary_color": BG,
        "icon_secondary_color": HEADING,
        "icon_size": px(20),
        "icon_padding": {"unit": "px", "size": 20, "sizes": []},
        "icon_spacing": px(18),
        "border_radius": box(6),
        "hover_primary_color": BG,
        "hover_secondary_color": PRIMARY,
        "_css_classes": "inb-social",
    }
    s.update(extra)
    return widget("social-icons", s)


def counter(number, title, suffix="+"):
    s = {"starting_number": 0, "ending_number": number, "suffix": suffix, "thousand_separator": "",
         "title": title, "number_color": PRIMARY, "title_color": HEADING, "duration": 2000}
    s.update(typo("typography_number", 54, "700", 60, 44))
    s.update(typo("typography_title", 18, "500", 26, 16))
    return widget("counter", s)


def progress(title, pct):
    s = {"title": title, "percent": {"unit": "%", "size": pct, "sizes": []}, "display_percentage": "show",
         "inner_text": "", "bar_color": PRIMARY, "bar_bg_color": LINE, "title_color": HEADING,
         "bar_inline_color": "#FFFFFF", "bar_height": px(10), "bar_border_radius": box(10),
         "_margin": box(0, 0, 14, 0)}
    s.update(typo("typography", 16, "600", 24))
    s.update(typo("bar_inner_typography", 12, "600", 10))
    return widget("progress", s)


def spacer(h):
    return widget("spacer", {"space": px(h)})


def section_title(sub, title, desc=None):
    w = [heading(sub, "p", 15, "600", PRIMARY, "center", 22,
                 typography_letter_spacing=px(2), typography_text_transform="uppercase"),
         heading(title, "h2", 52, "700", HEADING, "center", 64, 34)]
    if desc:
        w.append(text(f"<p>{desc}</p>", 18, BODY, "center", 30, _padding=box(0, 120, 0, 120),
                      _padding_mobile=box(0)))
    return section([column(w, 100)], inner=True, margin=box(0, 0, 40, 0))


def mshot(url):
    return "https://s.wordpress.com/mshots/v1/" + quote(url, safe="") + "?w=800&h=600"


# ---------------------------------------------------------------- Elementor Pro widgets
MENU_SLUG = "one-page-menu"


def nav_menu():
    s = {
        "menu": MENU_SLUG,
        "layout": "horizontal",
        "align_items": "center",
        "pointer": "underline",
        "animation_line": "fade",
        "submenu_icon": icon("fas fa-caret-down"),
        "dropdown": "tablet",
        "toggle": "burger",
        "toggle_align": "left",
        "full_width": "stretch",
        "text_align": "aside",
        "color_menu_item": HEADING,
        "color_menu_item_hover": PRIMARY,
        "pointer_color_menu_item_hover": PRIMARY,
        "color_menu_item_active": PRIMARY,
        "pointer_color_menu_item_active": PRIMARY,
        "padding_horizontal_menu_item": px(14),
        "pointer_width": px(2),
        "color_dropdown_item": HEADING,
        "background_color_dropdown_item": BG,
        "color_dropdown_item_hover": "#FFFFFF",
        "background_color_dropdown_item_hover": PRIMARY,
        "toggle_color": PRIMARY,
        "toggle_background_color": BG,
        "toggle_size": px(24),
        "toggle_border_radius": px(6),
        "_css_classes": "inb-menu",
    }
    s.update(typo("menu_typography", 16, "600", 24))
    s.update(typo("dropdown_typography", 17, "600", 26))
    return widget("nav-menu", s)


def progress_tracker():
    s = {"type": "horizontal", "relative_to": "entire_page", "direction": "rtl", "percentage": "",
         "horizontal_progress_color": PRIMARY, "progress_color": PRIMARY, "tracker_background_color": LINE,
         "horizontal_height": px(3), "height": px(3), "border_radius": box(0)}
    return widget("progress-tracker", s)


def animated_headline(before, words, tag="h2", size=30, mobile=22):
    s = {"headline_style": "rotate", "animation_type": "typing", "before_text": before,
         "rotating_text": "\n".join(words), "after_text": "", "loop": "yes",
         "rotate_iteration_delay": 2500, "tag": tag, "alignment": "right",
         "title_color": HEADING, "words_color": PRIMARY}
    s.update(typo("title_typography", size, "600", round(size * 1.35), mobile))
    s.update(typo("words_typography", size, "700", round(size * 1.35), mobile))
    return widget("animated-headline", s)


def blockquote(quote_text, author):
    s = {"blockquote_skin": "border", "blockquote_content": quote_text, "author_name": author,
         "tweet_button": "", "alignment": "right", "content_text_color": HEADING, "author_text_color": PRIMARY,
         "border_color": PRIMARY, "border_width": px(4), "border_gap": px(24), "_margin": box(10, 0, 0, 0)}
    s.update(typo("content_typography", 21, "600", 34, 18))
    s.update(typo("author_typography", 16, "700", 24))
    return widget("blockquote", s)


def flip_box(ico, title, front, back, cta="לפרטים ולהצעת מחיר", url="#contact"):
    s = {
        "graphic_element": "icon",
        "selected_icon": icon(ico),
        "icon_view": "default",
        "icon_primary_color": PRIMARY,
        "icon_size": px(44),
        "icon_spacing": px(20),
        "title_text_a": title,
        "description_text_a": front,
        "title_text_b": title,
        "description_text_b": back,
        "button_text": cta,
        "link": link(url),
        "link_click": "button",
        "height": px(330),
        "height_mobile": px(320),
        "border_radius": box(10),
        "flip_effect": "flip",
        "flip_direction": "up",
        "flip_3d": "yes",
        "background_a_background": "gradient",
        "background_a_color": CARD_A,
        "background_a_color_b": CARD_B,
        "background_a_gradient_angle": {"unit": "deg", "size": 145, "sizes": []},
        "background_b_background": "gradient",
        "background_b_color": PRIMARY,
        "background_b_color_b": "#C4003C",
        "background_b_gradient_angle": {"unit": "deg", "size": 145, "sizes": []},
        "alignment_a": "right",
        "alignment_b": "right",
        "vertical_position_a": "middle",
        "vertical_position_b": "middle",
        "padding_a": box(40, 35, 40, 35),
        "padding_b": box(40, 35, 40, 35),
        "title_color_a": HEADING,
        "description_color_a": BODY,
        "title_color_b": "#FFFFFF",
        "description_color_b": "#FFFFFF",
        "title_spacing_a": px(12),
        "title_spacing_b": px(12),
        "description_spacing_b": px(22),
        "button_size": "sm",
        "button_text_color": PRIMARY,
        "button_background_color": "#FFFFFF",
        "button_hover_text_color": "#FFFFFF",
        "button_hover_background_color": HEADING,
        "button_border_radius": px(6),
        "_css_classes": "inb-flip",
    }
    s.update(typo("title_typography_a", 22, "700", 30, 20))
    s.update(typo("description_typography_a", 17, "400", 28, 16))
    s.update(typo("title_typography_b", 22, "700", 30, 20))
    s.update(typo("description_typography_b", 16, "400", 27))
    s.update(typo("button_typography", 15, "700", 20))
    return widget("flip-box", s)


def cta_card(cat, title, url, desc, img):
    s = {
        "skin": "classic",
        "layout": "above",
        "bg_image": {"url": img, "id": "", "alt": title, "source": "url"},
        "bg_image_size": "full",
        "image_min_height": px(230),
        "image_min_height_mobile": px(200),
        "graphic_element": "none",
        "title": title,
        "title_tag": "h3",
        "description": desc,
        "button": "לצפייה באתר ↗",
        "link": link(url, external=True),
        "link_click": "button",
        "ribbon_title": cat,
        "ribbon_horizontal_position": "right",
        "ribbon_bg_color": PRIMARY,
        "ribbon_text_color": "#FFFFFF",
        "alignment": "right",
        "vertical_position": "top",
        "padding": box(28, 26, 30, 26),
        "content_bg_color": "rgba(0,0,0,0)",
        "title_color": HEADING,
        "description_color": BODY,
        "title_spacing": px(10),
        "description_spacing": px(18),
        "button_size": "sm",
        "button_text_color": PRIMARY,
        "button_background_color": BG,
        "button_hover_text_color": "#FFFFFF",
        "button_hover_background_color": PRIMARY,
        "button_border_radius": px(6),
        "transformation": "zoom-in",
        "bg_image_transformation": "zoom-in",
        "transformation_duration": px(800),
        "box_border_radius": px(10),
        "_css_classes": "inb-cta",
    }
    s.update(typo("title_typography", 22, "700", 30, 20))
    s.update(typo("description_typography", 16, "400", 26))
    s.update(typo("button_typography", 15, "700", 20))
    s.update(typo("ribbon_typography", 13, "700", 18))
    return widget("call-to-action", s)


def contact_form_pro():
    def field(cid, ftype, label, ph, width="100", required=True, **extra):
        f = {"_id": uid(), "custom_id": cid, "field_type": ftype, "field_label": label, "placeholder": ph,
             "required": "true" if required else "", "width": width, "width_mobile": "100"}
        f.update(extra)
        return f

    s = {
        "form_name": "צור קשר – אתר אישי",
        "form_fields": [
            field("name", "text", "שם מלא", "השם שלכם", "50"),
            field("phone", "tel", "טלפון", "05X-XXXXXXX", "50"),
            field("email", "email", "אימייל", "name@example.com", "100"),
            field("service", "select", "במה אפשר לעזור?", "", "100",
                  field_options="בניית אתר WordPress\nחנות WooCommerce\nפיתוח PHP / מערכת\n"
                                "קידום אורגני SEO / GEO\nקמפיינים ממומנים PPC\nהנגשת אתר\n"
                                "תחזוקה ושיפור מהירות\nאחר"),
            field("message", "textarea", "ספרו לי על הפרויקט", "סוג האתר, מטרות, לוחות זמנים…", "100",
                  required=False, rows=5),
            field("privacy", "acceptance", "אישור", "", "100",
                  acceptance_text="אני מאשר/ת ששלום כהן יחזור אליי בנוגע לפנייה זו"),
        ],
        "input_size": "md",
        "show_labels": "yes",
        "mark_required": "yes",
        "button_text": "שליחת הודעה",
        "button_size": "md",
        "button_width": "100",
        "button_align": "stretch",
        "selected_button_icon": icon("fas fa-paper-plane"),
        "button_icon_align": "right",
        "button_icon_indent": px(10),
        "submit_actions": ["email"],
        "email_to": EMAIL,
        "email_subject": "פנייה חדשה מהאתר – [field id=\"service\"]",
        "email_content": "[all-fields]",
        "email_from_name": "האתר של שלום כהן",
        "email_reply_to": "[field id=\"email\"]",
        "email_content_type": "html",
        "success_message": "תודה! ההודעה נשלחה ואחזור אליכם בהקדם.",
        "error_message": "אירעה שגיאה בשליחה. אפשר לפנות ישירות בוואטסאפ " + PHONE,
        "required_field_message": "שדה חובה",
        "invalid_message": "הערך שהוזן אינו תקין",
        "column_gap": px(20),
        "row_gap": px(20),
        "label_spacing": px(8),
        "label_color": HEADING,
        "mark_required_color": PRIMARY,
        "field_text_color": HEADING,
        "field_background_color": BG,
        "field_border_color": BG,
        "field_border_width": box(2),
        "field_border_radius": box(6),
        "button_background_color": PRIMARY,
        "button_text_color": "#FFFFFF",
        "button_background_hover_color": HEADING,
        "button_hover_color": "#FFFFFF",
        "button_border_radius": box(6),
        "button_text_padding": box(18, 30, 18, 30),
        "success_message_color": "#1E9E5A",
        "error_message_color": PRIMARY,
        "_css_classes": "inb-form",
    }
    s.update(typo("label_typography", 15, "600", 22))
    s.update(typo("field_typography", 16, "400", 24))
    s.update(typo("button_typography", 17, "700", 24))
    s.update(typo("message_typography", 15, "600", 22))
    return widget("form", s)


def share_buttons():
    s = {"share_buttons": [{"_id": uid(), "button": b} for b in ("whatsapp", "facebook", "linkedin", "email")],
         "view": "icon", "skin": "minimal", "shape": "rounded", "columns": "0", "alignment": "center",
         "share_url_type": "current_page", "color_source": "custom", "primary_color": BG,
         "secondary_color": HEADING, "icon_size": {"unit": "em", "size": 1.1, "sizes": []},
         "button_height": {"unit": "em", "size": 3.2, "sizes": []}, "_css_classes": "inb-share"}
    return widget("share-buttons", s)


def motion_mouse(extra=None):
    """Pro Motion Effects: mouse track + vertical scroll for the hero image."""
    d = {"motion_fx_motion_fx_scrolling": "yes", "motion_fx_translateY_effect": "yes",
         "motion_fx_translateY_direction": "negative", "motion_fx_translateY_speed": {"unit": "px", "size": 2, "sizes": []},
         "motion_fx_motion_fx_mouse": "yes", "motion_fx_mouseTrack_effect": "yes",
         "motion_fx_mouseTrack_direction": "negative", "motion_fx_mouseTrack_speed": {"unit": "px", "size": 0.6, "sizes": []}}
    d.update(extra or {})
    return d


# ---------------------------------------------------------------- global CSS (neumorphic shadows)
GLOBAL_CSS = """<style>
html{scroll-behavior:smooth}
body{background:%(bg)s;font-family:'%(font)s',sans-serif}
.inb-card,.inb-btn .elementor-button,.inb-social .elementor-social-icon,.inb-shadow img,.inb-pill{
  box-shadow:5px 5px 15px #D1D9E6,-5px -5px 15px #FFFFFF !important;transition:all .4s ease}
.inb-hover:hover{transform:translateY(-6px)}
.inb-hover:hover .elementor-icon-box-title,.inb-hover:hover .elementor-heading-title a{color:%(primary)s !important}
.inb-btn .elementor-button:hover,.inb-social .elementor-social-icon:hover{transform:translateY(-3px)}
.inb-card img{transition:transform .5s ease}
.inb-card:hover img{transform:scale(1.04)}
.inb-card .elementor-widget-image{overflow:hidden;border-radius:10px}
.inb-hero-img img{border-radius:10px;box-shadow:5px 5px 15px #D1D9E6,-5px -5px 15px #FFFFFF}
.inb-faq .elementor-accordion-item{background:linear-gradient(145deg,%(a)s,%(b)s);border-radius:10px !important;
  margin-bottom:20px;box-shadow:5px 5px 15px #D1D9E6,-5px -5px 15px #FFFFFF;border:0 !important;overflow:hidden}
.inb-faq .elementor-tab-content{border-top:1px solid %(line)s !important}
.inb-header{position:sticky;top:0;z-index:999;backdrop-filter:blur(6px)}
.inb-nav .elementor-icon-list-item a:hover .elementor-icon-list-text{color:%(primary)s}
.inb-timeline{border-right:5px solid %(line)s;padding-right:30px !important;position:relative}
.inb-dot{position:relative}
.inb-dot:before{content:"";position:absolute;right:-50px;top:56px;width:15px;height:15px;border-radius:50%%;
  background:%(bg)s;border:5px solid %(line)s;z-index:2}
.inb-dot:hover:before{border-color:%(primary)s}
@media(max-width:767px){.inb-timeline{padding-right:18px !important}.inb-dot:before{right:-38px}}
</style>""" % {"bg": BG, "font": FONT, "primary": PRIMARY, "a": CARD_A, "b": CARD_B, "line": LINE}

PRO_CSS = """
.inb-flip .elementor-flip-box,.inb-cta .elementor-cta,.inb-share .elementor-share-btn{
  box-shadow:5px 5px 15px #D1D9E6,-5px -5px 15px #FFFFFF;border-radius:10px}
.inb-cta .elementor-cta{background:linear-gradient(145deg,%(a)s,%(b)s);transition:transform .4s ease}
.inb-cta:hover .elementor-cta{transform:translateY(-6px)}
.inb-cta .elementor-cta__bg-wrapper{margin:22px 22px 0;border-radius:10px;overflow:hidden}
.inb-cta .elementor-cta__button,.inb-flip .elementor-flip-box__button{box-shadow:5px 5px 15px #D1D9E6,-5px -5px 15px #FFFFFF}
.inb-form .elementor-field-textual,.inb-form select{box-shadow:inset 3px 3px 8px #D1D9E6,inset -3px -3px 8px #FFFFFF}
.inb-form .elementor-field-textual:focus{border-color:%(primary)s !important}
.inb-menu .elementor-nav-menu--dropdown{box-shadow:0 20px 40px rgba(60,62,65,.12)}
.elementor-sticky--effects.inb-header{box-shadow:0 8px 30px rgba(60,62,65,.08)}
""" % {"a": CARD_A, "b": CARD_B, "primary": PRIMARY}
CUSTOM_CSS = GLOBAL_CSS.replace("<style>", "").replace("</style>", "").replace(
    ".inb-header{position:sticky;top:0;z-index:999;backdrop-filter:blur(6px)}",
    ".inb-header{backdrop-filter:blur(6px)}") + PRO_CSS

# ---------------------------------------------------------------- JSON-LD (GEO / AEO entity data)
JSON_LD = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Person",
            "@id": "#shalom-cohen",
            "name": "שלום כהן",
            "alternateName": "Shalom Cohen",
            "jobTitle": "מפתח WordPress ו-PHP פרילנסר, מומחה SEO/GEO וקמפיינים ממומנים PPC",
            "email": "mailto:" + EMAIL,
            "telephone": "+" + PHONE_INTL,
            "address": {"@type": "PostalAddress", "addressLocality": "אשדוד", "addressCountry": "IL"},
            "alumniOf": [
                {"@type": "CollegeOrUniversity", "name": "הטכניון – מכון טכנולוגי לישראל"},
                {"@type": "CollegeOrUniversity", "name": "אוניברסיטת בן-גוריון בנגב"},
                {"@type": "CollegeOrUniversity", "name": "האוניברסיטה הפתוחה"},
            ],
            "knowsLanguage": ["he", "en"],
            "knowsAbout": ["WordPress", "WooCommerce", "Elementor", "JetEngine / Crocoblock", "PHP", "Laravel",
                           "CodeIgniter", "ACF", "Bootstrap 5", "REST API", "Zapier", "Make", "SEO",
                           "Technical SEO", "GEO - Generative Engine Optimization",
                           "AEO - Answer Engine Optimization", "Google Ads", "Meta Ads", "Google Tag Manager",
                           "GA4", "Core Web Vitals", "Schema Markup", "WCAG 2.1", "תקן ישראלי 5568"],
        },
        {
            "@type": "ProfessionalService",
            "name": "שלום כהן – פיתוח WordPress, SEO/GEO ו-PPC",
            "founder": {"@id": "#shalom-cohen"},
            "email": EMAIL,
            "telephone": "+" + PHONE_INTL,
            "areaServed": {"@type": "Country", "name": "ישראל"},
            "address": {"@type": "PostalAddress", "addressLocality": "אשדוד", "addressCountry": "IL"},
            "serviceType": ["בניית אתרי וורדפרס", "פיתוח PHP", "חנויות WooCommerce", "קידום אתרים SEO",
                            "קידום ב-AI (GEO/AEO)", "ניהול קמפיינים ממומנים PPC", "הנגשת אתרים",
                            "תחזוקת אתרים", "אינטגרציות API"],
        },
    ],
}

# ================================================================= SECTIONS
content = []

# ---------------------------------------------------------------- 0. header
nav_items = [("בית", "#home"), ("שירותים", "#services"), ("SEO & PPC", "#marketing"),
             ("תיק עבודות", "#portfolio"), ("קורות חיים", "#resume"), ("שאלות נפוצות", "#faq"),
             ("צור קשר", "#contact")]
header = section([
    column([
        widget("html", {"html": GLOBAL_CSS + '\n<script type="application/ld+json">'
                        + json.dumps(JSON_LD, ensure_ascii=False) + "</script>"}),
        heading('שלום<span style="color:%s">.</span>כהן' % PRIMARY, "p", 30, "800", HEADING, "right", 36, 26,
                url="#home"),
    ], 25, content_position="center", _inline_size_mobile=50),
    column([
        icon_list([{"text": t, "url": u, "icon": "fas fa-circle"} for t, u in nav_items], view="inline",
                  ico_color=BG, color=HEADING, size=16, align="center", icon_size=px(0), text_indent=px(0),
                  space_between=px(28), hide_mobile="hidden-mobile", hide_tablet="hidden-tablet",
                  _css_classes="inb-nav"),
    ], 50, content_position="center"),
    column([
        button("בואו נדבר", "#contact", "fas fa-paper-plane", primary=False, align="left", size=15,
               text_padding=box(14, 26, 14, 26), align_mobile="left"),
    ], 25, content_position="center", _inline_size_mobile=50),
], css_classes="inb-header", padding=box(18, 0, 18, 0), padding_tablet=box(14, 15, 14, 15),
    padding_mobile=box(12, 5, 12, 5), background_color="#ECF0F3F2", _element_id="top")
if PRO:
    header = section([column([
        widget("html", {"html": '<script type="application/ld+json">'
                        + json.dumps(JSON_LD, ensure_ascii=False) + "</script>"}),
        section([
            column([
                heading('שלום<span style="color:%s">.</span>כהן' % PRIMARY, "p", 30, "800", HEADING, "right", 36, 26,
                        url="#home"),
            ], 25, inner=True, content_position="center", _inline_size_mobile=60, _inline_size_tablet=30),
            column([nav_menu()], 55, inner=True, content_position="center", _inline_size_mobile=40,
                   _inline_size_tablet=40),
            column([
                button("בואו נדבר", "#contact", "fas fa-paper-plane", primary=False, align="left", size=15,
                       text_padding=box(14, 26, 14, 26), hide_mobile="hidden-mobile"),
            ], 20, inner=True, content_position="center", _inline_size_tablet=30),
        ], inner=True),
        progress_tracker(),
    ], 100)], css_classes="inb-header", padding=box(14, 0, 0, 0), padding_tablet=box(12, 15, 0, 15),
        padding_mobile=box(10, 5, 0, 5), background_color="#ECF0F3F2", _element_id="top",
        sticky="top", sticky_on=["desktop", "tablet", "mobile"], sticky_offset=0, sticky_effects_offset=60,
        z_index=999, custom_css=CUSTOM_CSS)
content.append(header)

# ---------------------------------------------------------------- 1. hero
hero = section([
    column([
        heading("ברוכים הבאים לעולם שלי", "p", 15, "600", HEADING, typography_letter_spacing=px(2)),
        heading('היי, אני <span style="color:%s">שלום כהן</span>' % PRIMARY, "h1", 60, "700", HEADING, lh=74,
                mobile=38),
        animated_headline("אני ", ["מפתח WordPress פרילנסר", "מפתח PHP & Laravel", "מומחה SEO ו-GEO",
                                    "מנהל קמפיינים PPC", "מנגיש אתרים לפי התקן"])
        if PRO else
        heading("מפתח WordPress & PHP פרילנסר | SEO, GEO וקמפיינים PPC", "h2", 30, "600", HEADING, lh=40,
                mobile=22),
        text("<p>14 שנות ניסיון בפיתוח, בנייה ותחזוקה של מאות אתרים – מתבניות מותאמות אישית ועד חנויות "
             "WooCommerce, מערכות PHP ואינטגרציות API. אני בונה נכסים דיגיטליים שלא רק נראים מצוין, "
             "אלא גם מביאים תוצאות: אתרים מהירים, נגישים, מוכנים לקידום בגוגל ובמנועי ה-AI, "
             "ומחוברים למדידה ולקמפיינים ממומנים.</p>", 19, BODY, lh=32, _margin=box(10, 0, 30, 0)),
        section([
            column([
                heading("מצאו אותי ב-", "p", 14, "600", HEADING, typography_letter_spacing=px(2)),
                social([("fab fa-whatsapp", f"https://wa.me/{PHONE_INTL}"), ("fas fa-envelope", f"mailto:{EMAIL}"),
                        ("fas fa-phone-alt", f"tel:+{PHONE_INTL}"), ("fab fa-linkedin-in", "#")]),
            ], 50, inner=True),
            column([
                heading("המומחיות שלי", "p", 14, "600", HEADING, typography_letter_spacing=px(2)),
                social([("fab fa-wordpress", "#services"), ("fab fa-php", "#services"),
                        ("fab fa-elementor", "#services"), ("fab fa-google", "#marketing")]),
            ], 50, inner=True),
        ], inner=True),
    ], 58, content_position="center"),
    column([
        image(PLACEHOLDER, _css_classes="inb-hero-img", **(motion_mouse() if PRO else {})),
    ], 42, content_position="center", padding=box(0, 0, 0, 30), padding_mobile=box(30, 0, 0, 0)),
], _element_id="home", padding=box(90, 0, 110, 0), content_position="middle")
content.append(hero)

# ---------------------------------------------------------------- 2. about + counters
about = section([
    column([
        section_title("נעים להכיר", "קצת עליי"),
        section([
            column([
                text("<p><strong>שלום כהן הוא מפתח WordPress ו-PHP פרילנסר מאשדוד</strong>, עם 14 שנות ניסיון "
                     "בפיתוח WEB בחברות דיגיטל מובילות כמו Vibit, A-2-Z, SOGO, MCPUBLISH ו-ECPM. "
                     "לאורך השנים פיתחתי ותחזקתי מאות אתרים – אתרי תדמית, חנויות WooCommerce, אתרים דו-לשוניים, "
                     "מערכות PHP MVC ואתרי השוואה המבוססים על מאגרי מידע ממשלתיים.</p>"
                     "<p>הייחוד שלי הוא גישה הוליסטית: רקע טכנולוגי עמוק (MSc בהנדסה מהטכניון) יחד עם תפיסה "
                     "שיווקית שמבינה איך כל פיצ'ר טכני משפיע על השיווק והמכירות. לאחרונה השלמתי הכשרה בשיווק "
                     "דיגיטלי, ניהול קמפיינים וקידום אורגני באוניברסיטה הפתוחה – כך שאתם מקבלים מפתח שחושב "
                     "כמו איש שיווק.</p>", 18, lh=32),
                *([blockquote("אני בונה נכסים דיגיטליים שלא רק נראים מצוין – אלא גם מביאים תוצאות.",
                              "שלום כהן")] if PRO else []),
            ], 58, inner=True),
            card([
                icon_list([
                    "14 שנות ניסיון בפיתוח WordPress ו-PHP",
                    "מאות אתרים שפותחו ותוחזקו",
                    "43+ פרויקטי הנגשה לפי ת\"י 5568 ו-WCAG 2.1",
                    "SEO טכני, GEO/AEO וקידום ב-AI",
                    "קמפיינים ממומנים ב-Google Ads ו-Meta",
                    "MSc טכניון, BSc בן-גוריון",
                    "עברית – שפת אם, אנגלית – רמה גבוהה",
                ], size=17),
            ], 42, pad=(35, 30), hover=False),
        ], inner=True),
    ], 100),
], _element_id="about")
content.append(about)

stats = section([
    column([card([counter(14, "שנות ניסיון")], 100, pad=(35, 20))], 25),
    column([card([counter(100, "אתרים שפותחו ותוחזקו")], 100, pad=(35, 20))], 25),
    column([card([counter(43, "פרויקטי הנגשת אתרים")], 100, pad=(35, 20))], 25),
    column([card([counter(6, "חברות דיגיטל מובילות", suffix="")], 100, pad=(35, 20))], 25),
], padding=box(0, 0, 70, 0), padding_mobile=box(0, 10, 40, 10))
# counters: wrap each card in its own inner section (column > inner section > card column)
for col in stats["elements"]:
    c = col["elements"][0]
    col["elements"] = [section([c], inner=True)]
    c["settings"]["_column_size"] = 100
    c["settings"]["_inline_size"] = None
    col["settings"]["_inline_size_mobile"] = 50
content.append(stats)

# ---------------------------------------------------------------- 3. services
services = [
    ("fab fa-wordpress", "פיתוח אתרי WordPress",
     "אתרי תדמית, תוכן ובלוגים בהתאמה אישית – באלמנטור או בקוד נקי (ACF + Bootstrap 5), מ-PSD, Illustrator או Canva."),
    ("fas fa-shopping-cart", "חנויות WooCommerce",
     "הקמת חנויות וקטלוגים, סליקה (Cardcom ועוד), משלוחים, מוצרים משתנים ואופטימיזציה להמרות."),
    ("fab fa-php", "פיתוח PHP ו-MVC",
     "פיתוח ותחזוקה של מערכות ואפליקציות WEB ב-Laravel ו-CodeIgniter, תוספים ופיצ'רים מותאמים לוורדפרס."),
    ("fab fa-elementor", "אלמנטור ו-JetPlugins",
     "בניית אתרים מתקדמים באלמנטור ו-Crocoblock: CPT, שדות דינמיים, פילטרים, טפסים ותבניות."),
    ("fas fa-plug", "אינטגרציות API ואוטומציות",
     "חיבור CRM, סליקה, חברות ביטוח, מאגרי מידע ממשלתיים, גוגל עסקים, רשתות חברתיות ו-Zapier / Make."),
    ("fas fa-universal-access", "הנגשת אתרים",
     "הנגשה לפי תקן ישראלי 5568 ו-WCAG 2.1 AA/AAA – ניסיון ב-43+ פרויקטים לחברות מובילות במשק."),
    ("fas fa-search", "SEO טכני ו-GEO/AEO",
     "Schema Markup, מבנה כותרות, Sitemap, robots.txt, הפניות 301 ותוכן שמנועי AI יודעים לצטט."),
    ("fas fa-bullhorn", "קמפיינים ממומנים PPC",
     "הקמה, ניהול ואופטימיזציה של קמפיינים ב-Google Ads ו-Meta, מבוססי דאטה ומדידת המרות."),
    ("fas fa-tachometer-alt", "מהירות, תחזוקה ואחסון",
     "שיפור Core Web Vitals, עדכונים, גיבויים ואבטחה, ניהול שרתים ב-cPanel/WHM, Plesk, DirectAdmin ו-UPRESS."),
]
front_lines = ["אתרים מהירים ומותאמים אישית", "חנויות שמוכרות", "מערכות WEB בקוד נקי", "אתרים דינמיים ומתקדמים",
               "המערכות שלכם מדברות זו עם זו", "נגישות לפי החוק", "להופיע בגוגל ובתשובות ה-AI",
               "Google Ads ו-Meta", "אתר מהיר, מאובטח ומעודכן"]
rows = []
for i in range(0, len(services), 3):
    if PRO:
        rows.append(section([column([flip_box(ico, t, front_lines[i + k], d)], 33, inner=True,
                                    _animation="fadeInUp", margin=box(0, 0, 30, 0))
                             for k, (ico, t, d) in enumerate(services[i:i + 3])], inner=True))
    else:
        rows.append(section([card([icon_box(*s)], 33, _animation="fadeInUp") for s in services[i:i + 3]],
                            inner=True))
content.append(section([column([
    section_title("מה אני עושה", "השירותים שלי",
                  "פתרון אחד מקצה לקצה: פיתוח, ביצועים, נגישות, קידום אורגני וקמפיינים – תחת קורת גג אחת."),
    *rows,
], 100)], _element_id="services"))

# ---------------------------------------------------------------- 4. SEO / GEO / PPC
seo_card = card([
    icon_box("fas fa-chart-line", "SEO ו-GEO: להופיע בגוגל ובתשובות ה-AI",
             "קידום אורגני שמתחיל כבר בשלב הפיתוח – תשתית טכנית נקייה, תוכן מובנה וסכמות שמאפשרות "
             "לגוגל, ל-ChatGPT, ל-Gemini ול-Perplexity להבין ולצטט את העסק שלכם."),
    icon_list([
        "מבדקי אתר מקיפים (Site Audit) ומחקר מילות מפתח",
        "SEO טכני: היררכיית H1–H6, Sitemap.xml, robots.txt, הפניות 301 ועמודי 404",
        "Schema Markup: FAQ, Person, Organization, LocalBusiness, Product",
        "GEO/AEO: תוכן בפורמט שאלה-תשובה, ישויות (Entities) ותשובות ממוקדות",
        "חיבור Google Search Console ו-GA4, מבנה קישורים פנימיים",
        "עבודה עם SEMrush ו-Screaming Frog",
    ], size=16),
    spacer(10),
    button("צפו במבדק אתר לדוגמה", SITE_AUDIT, "fas fa-external-link-alt", primary=True),
], 50, pad=(45, 40), hover=False)
ppc_card = card([
    icon_box("fas fa-bullseye", "PPC: קמפיינים ממומנים שמביאים המרות",
             "ניהול קמפיינים ב-Google Ads וב-Meta (פייסבוק ואינסטגרם) עם הבנה מדויקת של קהלי יעד, "
             "מדידה מלאה ומקסום התקציב לטובת לידים ומכירות."),
    icon_list([
        "אסטרטגיה, מחקר קהלים ובניית מבנה קמפיינים",
        "קמפייני חיפוש, רשת המדיה, שופינג וקמפיינים חברתיים",
        "Google Tag Manager: Tags, Triggers, Variables ובדיקות Preview/Debug",
        "הטמעת Meta Pixel, Google Tag ומעקב המרות ב-GA4",
        "דפי נחיתה מהירים וממוקדי המרה (CRO)",
        "קריאטיב וכתיבה שיווקית, דוחות וניתוח נתונים",
    ], size=16),
    spacer(10),
    button("בואו נבנה קמפיין", "#contact", "fas fa-arrow-left"),
], 50, pad=(45, 40), hover=False)
content.append(section([column([
    section_title("שיווק דיגיטלי", "SEO, GEO וקידום ממומן PPC",
                  "אתר מעולה צריך גם תנועה. אני משלב את הידע הטכני בפיתוח עם קידום אורגני, אופטימיזציה "
                  "למנועי AI וניהול קמפיינים מבוססי דאטה."),
    section([seo_card, ppc_card], inner=True),
], 100)], _element_id="marketing"))

# ---------------------------------------------------------------- 5. work process
steps = [
    ("fas fa-clipboard-list", "01. אפיון ומחקר", "הבנת העסק, קהל היעד, מחקר מילות מפתח ומתחרים ובניית מפת אתר."),
    ("fas fa-code", "02. עיצוב ופיתוח", "פיתוח WordPress / PHP מותאם, רספונסיבי ו-Mobile First, עם קוד נקי ומהיר."),
    ("fas fa-shield-alt", "03. SEO, נגישות ומהירות", "Schema, תגיות Meta, הנגשה לפי 5568 ואופטימיזציית Core Web Vitals."),
    ("fas fa-rocket", "04. השקה ומדידה", "חיבור GA4, GTM ו-Search Console, קמפיינים ממומנים, תחזוקה ושיפור מתמיד."),
]
content.append(section([column([
    section_title("תהליך עבודה", "איך אני עובד"),
    section([card([icon_box(*s, icon_size=px(36))], 25, pad=(35, 25), _animation="fadeInUp",
                  _inline_size_tablet=50) for s in steps], inner=True),
], 100)], _element_id="process"))

# ---------------------------------------------------------------- 6. portfolio
projects = [
    ("WooCommerce", "Opera – בגדי נשים אונליין", "https://operaltd.co.il/", "חנות אופנה מקוונת ב-WooCommerce."),
    ("Elementor + API", "Igemel – השוואת נכסים פיננסיים", "https://igemel.co.il",
     "אתר השוואה המבוסס על אינטגרציית API למאגרים ממשלתיים."),
    ("PHP · CodeIgniter", "MYB – כרטיסי ביקור דיגיטליים", "https://myb.bio", "מערכת SaaS בפריימוורק CodeIgniter."),
    ("PHP · CodeIgniter", "BAMA – מערכת B2B", "https://bama.bio/b2b", "פיתוח מערכת B2B ב-PHP MVC."),
    ("WordPress · דו-לשוני", "סטודיו הנקין-שביט", "https://henkinshavit.com",
     "תבנית ועיצוב בהתאמה אישית, עברית ואנגלית."),
    ("WooCommerce", "Krav Maga Global", "http://www.krav-maga.com/", "חנות מקוונת בינלאומית לארגון קרב מגע."),
    ("Elementor", "קבוצת יצחקי – נכסים מניבים", "https://itzhaki-info.co.il/", "אלמנטור בעיצוב בהתאמה אישית."),
    ("Elementor", "DEN – השוואת מחירי רפואת שיניים", "https://den.co.il", "אתר השוואת מחירים מבוסס אלמנטור."),
    ("Bootstrap 5 + ACF", "bclass", "http://www.bclass.co.il", "תבנית וורדפרס בקוד נקי, Bootstrap 5 ו-ACF."),
    ("WooCommerce", "Inspire – הבית של הספורטאים", "https://inspire-int.co.il/", "חנות WooCommerce לציוד ספורט."),
    ("Elementor · דו-לשוני", "האיגוד הישראלי למערכות מידע ברפואה", "https://ilami.org",
     "אתר ארגוני בעברית ובאנגלית."),
    ("WordPress", "KIA רחובות", "https://kia-rehovot.co.il/", "אתר תדמית ולידים לסוכנות רכב."),
]
prow = []
for i in range(0, len(projects), 3):
    cards = []
    for cat, title, url, desc in projects[i:i + 3]:
        if PRO:
            cards.append(column([cta_card(cat, title, url, desc, mshot(url))], 33, inner=True,
                                _animation="fadeInUp", margin=box(0, 0, 30, 0)))
            continue
        cards.append(card([
            image(mshot(url), alt_link=url, radius=10, image_border_radius=box(10)),
            heading(cat, "p", 14, "600", PRIMARY, _margin=box(20, 0, 0, 0),
                    typography_letter_spacing=px(1)),
            heading(title + " ↗", "h3", 22, "700", HEADING, lh=30, mobile=20, url=url),
            text(f"<p>{desc}</p>", 16, BODY, lh=26),
        ], 33, pad=(25, 25), _animation="fadeInUp"))
    prow.append(section(cards, inner=True))

more_projects = [
    ("Mid Diamonds", "https://www.middiamonds.com/"), ("סמארטפליי – משטחי בטיחות", "https://www.smartplay.co.il"),
    ("קבוצת מחול נעה דר", "https://noadar.com/"), ("מגן פרזול", "https://magenetzbaot.co.il"),
    ("ShortDial", "https://shortdial.cl"), ("ניצן סוכנות לביטוח", "https://avisaporta.co.il"),
    ("שורשים ייעוץ ופיתוח ארגוני", "https://ssg.co.il"), ("אסקדיניה עובדים זרים", "https://askedinia.co.il/"),
    ("Ulpan in Israel", "https://www.homeulpan.com"), ("מורפיקס סקול – בלוג", "https://blog.morfix.co.il"),
    ("טיפולי שיניים באלבניה", "https://healingtravel.co.il"), ("RDC Rehovot Dental", "https://rdc-dental.co.il/"),
    ("Moya CBD", "https://www.moya-cbd.com"), ("עו\"ד אלון שליכטר", "https://a-law.co.il/"),
    ("עו\"ד עדי קפלן", "https://klaw.co.il"), ("דוד איזן מכונות", "https://deisen.co.il"),
    ("בית אקשטיין", "https://b-e.org.il"), ("Black&White", "http://www.blackandwhite.org.il"),
    ("קחטן עבודות מתכת", "https://kahtan.biz/"), ("DNR", "https://dnr.org.il"),
    ("דור סנטר", "https://dcenter.co.il/"), ("מקרו סטורס", "https://www.macro-stores.co.il/"),
    ("Ozasakim", "https://www.ozasakim.com/"), ("Ptravels", "http://www.ptravels.co.il"),
    ("דשא עוז", "https://desheoz.co.il/"), ("WebPerformance", "https://s2uthemes.com/"),
]
third = (len(more_projects) + 2) // 3
more_cols = [column([icon_list([{"text": t, "url": u, "icon": "fas fa-external-link-alt"}
                                for t, u in more_projects[k * third:(k + 1) * third]], size=16)], 33, inner=True)
             for k in range(3)]

content.append(section([column([
    section_title("תיק עבודות", "פרויקטים נבחרים",
                  "מבחר פרויקטים מייצגים בפיתוח WordPress, WooCommerce, PHP ואינטגרציות API – "
                  "אתרים שבניתי, תחזקתי וניהלתי."),
    *prow,
    spacer(20),
    heading("פרויקטים נוספים", "h3", 28, "700", HEADING, "center", 36, 24),
    spacer(10),
    section(more_cols, inner=True),
    text("<p>ועוד רבים וטובים שעברו לעולם שכולו 404… אבל עדיין מופיעים בגוגל 😉</p>", 16, MUTED, "center"),
], 100)], _element_id="portfolio"))

# ---------------------------------------------------------------- 7. accessibility portfolio
a11y = ["https://www.sugat.com", "https://www.salt.co.il", "https://psagot.org", "https://www.burlingtonenglish.co.il",
        "https://www.shaanan.ac.il", "https://magalcom.com", "https://palsar7-67.co.il", "https://www.hemdat.ac.il",
        "https://www.matav.org.il", "https://deisen.co.il", "https://w3.braude.ac.il", "https://www.golanwines.co.il",
        "https://www.iconfitness.co.il", "https://memoriesofethiopia.com", "https://stagkal.co.il",
        "http://www.goldfarb.com", "https://www.eintal-hadassah.com", "https://www.rivka.org.il",
        "https://www.herzog.ac.il", "https://www.moreinvest.co.il"]


def short(u):
    return u.split("//")[1].replace("www.", "").rstrip("/")


a11y_cols = [card([icon_list([{"text": short(u), "url": u, "icon": "fas fa-universal-access"}
                              for u in a11y[k * 5:(k + 1) * 5]], size=16)], 25, pad=(30, 25),
                  _inline_size_tablet=50)
             for k in range(4)]
content.append(section([column([
    section_title("נגישות ותקינה", "43+ פרויקטי הנגשת אתרים",
                  "ייעוץ וביצוע הנגשה לפי תקן ישראלי 5568 ו-WCAG 2.1 לחברות, מוסדות אקדמיים וארגונים מובילים במשק."),
    section(a11y_cols, inner=True),
    text("<p>+ 23 פרויקטים נוספים</p>", 18, PRIMARY, "center", typography_font_weight="700"),
], 100)], _element_id="accessibility"))

# ---------------------------------------------------------------- 8. resume
experience = [
    ("2025 – היום", "פרילנסר עצמאי", "פיתוח WordPress & PHP, SEO/GEO ו-PPC",
     "פיתוח אתרים ומערכות ללקוחות פרטיים ועסקיים, קידום אורגני, אופטימיזציה למנועי AI וניהול קמפיינים ממומנים."),
    ("2021 – 2025", "Vibit", "מפתח / בונה אתרים ומנהל אתרי לקוחות",
     "פיתוח אתרי WordPress באלמנטור ובקוד נקי, פיתוח ב-PHP MVC (CodeIgniter, Laravel), אינטגרציות API "
     "(Cardcom, CRM, חברות ביטוח, מאגרים ממשלתיים, גוגל עסקים), SEO טכני, שיפור מהירות וניהול שרתים."),
    ("2019 – 2021", "A-2-Z", "מפתח / בונה אתרים ומנהל אתרי לקוחות",
     "פיתוח אתרים מ-PSD לוורדפרס, הנגשת 43 אתרים לפי ת\"י 5568 ו-WCAG 2.1, הכנת אתרים למחלקות SEO ופרסום: "
     "Schema, הפניות 301, Sitemap, היררכיית כותרות והטמעת פיקסלים."),
    ("2018 – 2019", "EOI", "מפתח / בונה אתרים ומנהל אתרי לקוחות",
     "הקמת אתרי וורדפרס מתבניות Themeforest ומעיצובים בהתאמה אישית, ניהול אתרים, שרתים (cPanel/WHM, Plesk, "
     "DirectAdmin) ומשימות SEO."),
    ("2017 – 2018", "SOGO", "מפתח / בונה אתרים ומנהל אתרי לקוחות",
     "פיתוח אתרים ומערכות WEB אינטראקטיביות בוורדפרס, תבניות Bootstrap 5 + ACF, התאמת אתרים לצרכים שיווקיים."),
    ("2016 – 2017", "MCPUBLISH", "מפתח / בונה אתרים ומנהל אתרי לקוחות",
     "פיתוח צד לקוח ושרת, הסבת עיצובי PSD/Illustrator לתבניות וורדפרס, תחזוקה ושיפור מהירות."),
    ("2014 – 2016", "ECPM", "מפתח / בונה אתרים ומנהל אתרי לקוחות",
     "הקמת אתרי וורדפרס, ניהול אתרי לקוחות ושרתים וביצוע משימות SEO לפי מחלקת הקידום."),
    ("2010 – 2013", "Site2U – עסק עצמאי", "פיתוח וקידום אתרי אינטרנט",
     "הקמת עסק לבנייה וקידום אתרים. עבודה עם מערכות CMS ולאחר מכן התמחות בוורדפרס – עשרות אתרים מכל הסוגים. "
     "ב-2013 גם קבלן משנה לאל על בפרויקט מערכות מידע."),
]
education = [
    ("2025 – 2026", "האוניברסיטה הפתוחה", "קורס שיווק דיגיטלי, ניהול קמפיינים וקידום אורגני",
     "אסטרטגיה דיגיטלית, קריאטיב וכתיבה שיווקית, Google Ads ו-Meta, SEO, אופטימיזציית המרות, אנליטיקה ושיווק תוכן."),
    ("2001 – 2004", "הטכניון, חיפה", "MSc בהנדסת חומרים",
     "תואר שני בהנדסה – חשיבה אנליטית, מחקר ועבודה מבוססת נתונים."),
    ("1993 – 1997", "אוניברסיטת בן-גוריון", "BSc בהנדסת חומרים", "תואר ראשון בהנדסה."),
    ("2001 – 2009", "קורסים והסמכות", "מסחר אלקטרוני, סחר בינלאומי, הקמה וניהול עסק",
     "סיוון מחשבים (מסחר אלקטרוני), מ.ט.י אשדוד (סחר בינלאומי; הקמה וניהול עסק)."),
    ("1997 – 2009", "לפני הדיגיטל", "הנדסה, מחקר ושיווק טכני",
     "ישקר, אוניברסיטת תל אביב (עוזר מחקר), סקופ סחר מתכות ו-Adionim – רקע הנדסי ועסקי שמשפיע על הדרך שבה אני "
     "בונה פתרונות."),
]


def tl_card(period, org, role, desc):
    return section([card([
        heading(org, "h3", 22, "700", HEADING, lh=30, mobile=20),
        heading(role, "p", 16, "500", BODY, lh=24),
        heading(period, "p", 14, "700", PRIMARY, lh=20, _padding=box(6, 14, 6, 14),
                _background_background="classic", _background_color=BG, _border_radius=box(6),
                _css_classes="inb-pill", _element_width="auto", _margin=box(4, 0, 12, 0)),
        text(f"<p>{desc}</p>", 16, BODY, lh=27),
    ], 100, pad=(35, 35), cls="inb-card inb-dot")], inner=True)


def tl_column(title, ico, items):
    return column([
        heading(f'<i class="{ico}" style="color:{PRIMARY}"></i>&nbsp; {title}', "h3", 30, "700", HEADING,
                lh=40, mobile=24, _margin=box(0, 0, 30, 0)),
        *[tl_card(*it) for it in items],
    ], 50, css_classes="inb-timeline")


content.append(section([column([section_title("8 תפקידים · 14 שנות ניסיון", "קורות חיים")], 100)],
                       _element_id="resume", padding=box(100, 0, 0, 0), padding_tablet=box(80, 15, 0, 15),
                       padding_mobile=box(60, 10, 0, 10), border_border="none"))
content.append(section([tl_column("ניסיון תעסוקתי", "fas fa-briefcase", experience),
                        tl_column("השכלה והסמכות", "fas fa-graduation-cap", education)],
                       padding=box(0, 0, 100, 0), padding_tablet=box(0, 15, 80, 15), padding_mobile=box(0, 10, 60, 10)))

# skills
dev = [("WordPress & WooCommerce", 95), ("Elementor & Crocoblock JetPlugins", 95), ("PHP · Laravel · CodeIgniter", 85),
       ("HTML5 · CSS3 · LESS · Bootstrap 5", 92), ("JavaScript · jQuery · AJAX", 82), ("MySQL · GIT", 80),
       ("API · Zapier · Make", 88), ("נגישות ת\"י 5568 · WCAG 2.1", 92)]
mkt = [("SEO טכני ו-On-Page", 90), ("GEO / AEO – קידום במנועי AI", 82), ("Google Ads", 78), ("Meta Ads", 76),
       ("Google Tag Manager · GA4", 85), ("Core Web Vitals ומהירות", 88), ("Schema Markup", 90),
       ("AI Tools: ChatGPT · Claude · Gemini · Perplexity", 90)]
content.append(section([column([
    section_title("כישורים מקצועיים", "המיומנויות שלי"),
    section([
        card([heading("פיתוח", "h3", 26, "700", HEADING, lh=34, _margin=box(0, 0, 20, 0)),
              *[progress(t, p) for t, p in dev]], 50, pad=(40, 35), hover=False),
        card([heading("שיווק דיגיטלי", "h3", 26, "700", HEADING, lh=34, _margin=box(0, 0, 20, 0)),
              *[progress(t, p) for t, p in mkt]], 50, pad=(40, 35), hover=False),
    ], inner=True),
], 100)], _element_id="skills"))

# ---------------------------------------------------------------- 9. companies
companies = [("Vibit", "https://www.vibit.co.il/"), ("A-2-Z", "https://a-2-z.co.il/"), ("SOGO", "https://sogo.co.il/"),
             ("MCPUBLISH", "https://www.mcpublish.co.il/"), ("ECPM", "https://ecpm.co.il"), ("EOI", "https://eoi.co.il/"),
             ("אל על", None), ("Site2U", None)]
crow = []
for i in range(0, 8, 4):
    crow.append(section([card([heading(n, "p", 26, "800", HEADING, "center", 34, 22, url=u)], 25, pad=(35, 15),
                              _inline_size_mobile=50)
                         for n, u in companies[i:i + 4]], inner=True))
content.append(section([column([section_title("ניסיון מוכח", "חברות שעבדתי איתן"), *crow], 100)],
                       _element_id="clients"))

# ---------------------------------------------------------------- 10. FAQ (GEO / AEO)
faq = [
    ("מי זה שלום כהן?",
     "שלום כהן הוא מפתח WordPress ו-PHP פרילנסר מאשדוד עם 14 שנות ניסיון בפיתוח WEB. הוא עבד בחברות דיגיטל "
     "מובילות כמו Vibit, A-2-Z ו-SOGO, פיתח ותחזק מאות אתרים, ומשלב פיתוח עם SEO, GEO וניהול קמפיינים ממומנים "
     "(PPC). בעל תואר MSc בהנדסה מהטכניון ובוגר קורס שיווק דיגיטלי של האוניברסיטה הפתוחה."),
    ("אילו שירותים מציע מפתח וורדפרס פרילנסר?",
     "השירותים כוללים: בניית אתרי WordPress ואלמנטור, חנויות WooCommerce, פיתוח PHP (Laravel, CodeIgniter), "
     "אינטגרציות API ואוטומציות (Zapier / Make), הנגשת אתרים לפי ת\"י 5568, שיפור מהירות (Core Web Vitals), "
     "תחזוקה וניהול שרתים, קידום אורגני SEO, קידום במנועי AI (GEO/AEO) וניהול קמפיינים ב-Google Ads וב-Meta."),
    ("מה ההבדל בין SEO, GEO ו-AEO?",
     "SEO (Search Engine Optimization) הוא קידום אתר בתוצאות החיפוש הרגילות של גוגל. "
     "GEO (Generative Engine Optimization) הוא אופטימיזציה כדי שמנועי AI גנרטיביים כמו ChatGPT, Gemini, "
     "Perplexity ו-Google AI Overviews יזכירו ויצטטו את האתר שלכם. "
     "AEO (Answer Engine Optimization) מתמקד בכתיבת תשובות קצרות, ברורות ומובנות לשאלות של גולשים, "
     "כך שמנועי חיפוש ועוזרים קוליים יציגו אותן כתשובה ישירה."),
    ("איך גורמים לאתר להופיע בתשובות של ChatGPT ו-Gemini?",
     "בונים את האתר כך שמנועי AI יבינו מי אתם ומה אתם מציעים: נתוני Schema מובנים (Person, Organization, FAQ), "
     "תוכן בפורמט שאלה-תשובה שעונה ישירות על השאלה כבר במשפט הראשון, ציון ברור של שמות, מקומות, שירותים ונתונים, "
     "אתר מהיר ונגיש שקל לסרוק, ואזכורים עקביים של העסק במקורות אמינים ברשת."),
    ("כמה זמן לוקח לבנות אתר וורדפרס?",
     "זה תלוי בהיקף הפרויקט. אתר תדמית בסיסי נבנה בדרך כלל בתוך כמה שבועות, בעוד שחנות WooCommerce, "
     "אתר דו-לשוני או מערכת עם אינטגרציות API דורשים זמן ארוך יותר. לוח הזמנים המדויק נקבע אחרי שלב האפיון."),
    ("האם אתה בונה אתרים רק באלמנטור?",
     "לא. אני בונה אתרים באלמנטור וב-Crocoblock JetPlugins, וגם בקוד נקי – תבניות וורדפרס מותאמות אישית "
     "עם ACF ו-Bootstrap 5, הסבה מעיצובי PSD, Illustrator ו-Canva, ופיתוח מערכות PHP ב-Laravel וב-CodeIgniter."),
    ("האם האתר שלי יהיה נגיש לפי החוק בישראל?",
     "כן. אני מנגיש אתרים לפי תקן ישראלי 5568 והנחיות WCAG 2.1 ברמת AA (וגם AAA לפי הצורך), עם ניסיון "
     "ב-43+ פרויקטי הנגשה לחברות ולמוסדות אקדמיים מובילים כמו מכללת בראודה, יקבי רמת הגולן ומכללת הרצוג."),
    ("האם אתה מנהל גם קמפיינים ממומנים בגוגל ובפייסבוק?",
     "כן. אני מקים ומנהל קמפיינים ב-Google Ads וב-Meta (פייסבוק ואינסטגרם), כולל מחקר קהלים, "
     "הטמעת Google Tag Manager, GA4 ו-Meta Pixel ומדידת המרות מדויקת – כך שכל שקל בתקציב נמדד."),
    ("אפשר לשפר את המהירות של אתר וורדפרס קיים?",
     "בהחלט. שיפור מהירות כולל אופטימיזציית תמונות, Caching, צמצום תוספים וקוד, שיפור ציוני Core Web Vitals "
     "(LCP, INP, CLS) ובדיקת האחסון והשרת. אתר מהיר משפר גם את חוויית המשתמש, גם את ה-SEO וגם את יחס ההמרה."),
    ("האם אתה מבצע אינטגרציות API ואוטומציות?",
     "כן. ביצעתי אינטגרציות לחברות סליקה כמו Cardcom, מערכות CRM, חברות ביטוח, מאגרי מידע ממשלתיים, "
     "גוגל עסקים וגוגל מפות, יוטיוב, פייסבוק, אינסטגרם, טיקטוק ו-ActiveTrail – ידנית או באמצעות Zapier ו-Make."),
    ("האם אתה מציע תחזוקה שוטפת לאתרים?",
     "כן. התחזוקה כוללת עדכוני וורדפרס ותוספים, גיבויים, אבטחה, טיפול בתקלות, הזנת תכנים ומוצרים וניהול "
     "חשבונות אחסון ב-cPanel/WHM, Plesk, DirectAdmin ו-UPRESS."),
    ("איפה אתה נמצא ועם אילו לקוחות אתה עובד?",
     "אני נמצא באשדוד ועובד עם עסקים, חברות, ארגונים וסוכנויות דיגיטל בכל הארץ – גם מרחוק. "
     "אני עובד בעברית ובאנגלית ובונה גם אתרים דו-לשוניים."),
    ("איך מתחילים לעבוד איתך?",
     f"פשוט פונים אליי בטלפון או בוואטסאפ {PHONE} או במייל {EMAIL}. נקבע שיחת היכרות קצרה, נבין את הצרכים "
     "והיעדים שלכם, ואחריה תקבלו הצעה מסודרת עם תכולת עבודה ולוחות זמנים."),
]
acc = {
    "tabs": [{"_id": uid(), "tab_title": q, "tab_content": f"<p>{a}</p>"} for q, a in faq],
    "selected_icon": icon("fas fa-plus"),
    "selected_active_icon": icon("fas fa-minus"),
    "title_html_tag": "h3",
    "faq_schema": "yes",
    "icon_align": "left",
    "border_width": px(0),
    "title_background": "rgba(0,0,0,0)",
    "title_color": HEADING,
    "tab_active_color": PRIMARY,
    "icon_color": PRIMARY,
    "icon_active_color": PRIMARY,
    "title_padding": box(26, 30, 26, 30),
    "content_background_color": "rgba(0,0,0,0)",
    "content_color": BODY,
    "content_padding": box(24, 30, 28, 30),
    "_css_classes": "inb-faq",
}
acc.update(typo("title_typography", 20, "700", 30, 18))
acc.update(typo("content_typography", 17, "400", 30, 16))
content.append(section([column([
    section_title("שאלות ותשובות", "שאלות נפוצות",
                  "תשובות קצרות וברורות לשאלות שלקוחות שואלים הכי הרבה – על פיתוח וורדפרס, SEO, GEO, AEO וקמפיינים."),
    section([column([widget("accordion", acc)], 100, inner=True, padding=box(0, 100, 0, 100),
                    padding_mobile=box(0))], inner=True),
], 100)], _element_id="faq"))

# ---------------------------------------------------------------- 11. contact
contact_info = card([
    image(PLACEHOLDER, radius=10, _css_classes="inb-shadow"),
    heading("שלום כהן", "h3", 30, "700", HEADING, lh=40, _margin=box(25, 0, 0, 0)),
    heading("מפתח WordPress & PHP · SEO/GEO · PPC", "p", 17, "500", BODY, lh=26),
    text("<p>זמין לפרויקטים חדשים: בניית אתרים, תחזוקה, קידום אורגני וקמפיינים. "
         "דברו איתי בטלפון, בוואטסאפ או במייל – אחזור אליכם בהקדם.</p>", 17, BODY, lh=28),
    icon_list([
        {"text": f"טלפון: {PHONE}", "url": f"tel:+{PHONE_INTL}", "icon": "fas fa-phone-alt"},
        {"text": f"מייל: {EMAIL}", "url": f"mailto:{EMAIL}", "icon": "fas fa-envelope"},
        {"text": "אשדוד, ישראל – עבודה עם לקוחות בכל הארץ", "icon": "fas fa-map-marker-alt"},
    ], size=17, color=HEADING),
    heading("מצאו אותי ב-", "p", 14, "600", HEADING, typography_letter_spacing=px(2), _margin=box(20, 0, 10, 0)),
    social([("fab fa-whatsapp", f"https://wa.me/{PHONE_INTL}"), ("fas fa-envelope", f"mailto:{EMAIL}"),
            ("fas fa-phone-alt", f"tel:+{PHONE_INTL}"), ("fab fa-linkedin-in", "#")]),
], 42, pad=(30, 30), hover=False)

contact_form = card([
    heading("שלחו לי הודעה", "h3", 28, "700", HEADING, lh=36),
    text("<p>ספרו לי בקצרה על הפרויקט – סוג האתר, מטרות ולוחות זמנים.</p>", 17, BODY, lh=28),
    *([contact_form_pro()] if PRO else [
        widget("shortcode", {"shortcode": '[contact-form-7 id="REPLACE_ME" title="צור קשר"]'}),
        spacer(10),
        button("וואטסאפ – תגובה מהירה", f"https://wa.me/{PHONE_INTL}", "fab fa-whatsapp", primary=True,
               align="justify"),
        spacer(6),
        button("שלחו מייל", f"mailto:{EMAIL}", "fas fa-envelope", align="justify"),
    ]),
], 58, pad=(40, 35), hover=False)

content.append(section([column([
    section_title("צור קשר", "בואו נעבוד ביחד",
                  "יש לכם רעיון לאתר, צריכים שדרוג, קידום או קמפיין? אשמח לשמוע."),
    section([contact_info, contact_form], inner=True),
], 100)], _element_id="contact"))

# ---------------------------------------------------------------- 12. footer
content.append(section([
    column([
        heading('שלום<span style="color:%s">.</span>כהן' % PRIMARY, "p", 28, "800", HEADING, "center", 34, url="#home"),
        text("<p>© 2026 שלום כהן · פיתוח WordPress & PHP · SEO / GEO · PPC · כל הזכויות שמורות</p>",
             15, MUTED, "center", 24),
        *([heading("שתפו את האתר", "p", 14, "600", HEADING, "center", 22, typography_letter_spacing=px(2)),
           share_buttons(), spacer(10)] if PRO else []),
        button("חזרה למעלה", "#top", "fas fa-arrow-up", align="center", size=14, text_padding=box(12, 24, 12, 24)),
    ], 100),
], padding=box(50, 0, 50, 0), border_border="none"))

# ================================================================= write
def normalize(sec):
    """A column's isInner flag must match its parent section."""
    for col in sec["elements"]:
        col["isInner"] = sec["isInner"]
        for el in col["elements"]:
            if el["elType"] == "section":
                normalize(el)


for sec in content:
    normalize(sec)

template = {
    "version": "0.4",
    "title": "Shalom Cohen – Personal Portfolio Resume (InBio Light)" + (" – Elementor Pro" if PRO else ""),
    "type": "page",
    "page_settings": {
        "template": "elementor_canvas",
        "hide_title": "yes",
        "background_background": "classic",
        "background_color": BG,
    },
    "content": content,
}

out = os.path.join(os.path.dirname(__file__), "..", "elementor", "shalom-cohen-portfolio-inbio" + ("-pro" if PRO else "") + ".json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(template, f, ensure_ascii=False, indent=1)
print("written", os.path.normpath(out), "elements:", len(_used))
