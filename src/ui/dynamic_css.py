# SPDX-License-Identifier: AGPL-3.0-only
"""Dynamic Streamlit CSS for us-fashion-persona."""

from __future__ import annotations

from src.ui.assets import DIRECTION_BG_PATH, FABRIC_PATH, GITHUB_MARK_MASK_URI, _image_data_uri


def build_comfort_ui_css(dark_mode: bool) -> str:
    if dark_mode:
        root = {
            "primary": "#5f8ff7",
            "primary_focus": "#7aa2ff",
            "ink": "#f3f0ea",
            "body": "#e8e4dc",
            "muted": "#c7c0b5",
            "canvas": "#303236",
            "parchment": "#3a3d42",
            "surface": "#42464c",
            "surface_alt": "#383b40",
            "dark": "#34373c",
            "hairline": "#5a5f66",
            "chip": "#4d525a",
            "info": "#dfe8ff",
            "help_dot_ink": "#c7c0b5",
        }
    else:
        root = {
            "primary": "#2f6fdd",
            "primary_focus": "#1f5fc6",
            "ink": "#27282c",
            "body": "#3a3a3d",
            "muted": "#6d7078",
            "canvas": "#f7f6f2",
            "parchment": "#ece9e2",
            "surface": "#fffdfa",
            "surface_alt": "#f1eee7",
            "dark": "#3a3d42",
            "hairline": "#d8d3c9",
            "chip": "#e6e1d7",
            "info": "#22314f",
            "help_dot_ink": "#3a3d42",
        }
    color_scheme = "dark" if dark_mode else "light"
    fabric_uri = _image_data_uri(FABRIC_PATH)
    direction_uri = _image_data_uri(DIRECTION_BG_PATH)
    hero_background = (
        f"background: url('{fabric_uri}') center / cover no-repeat;"
        if fabric_uri
        else "background: linear-gradient(135deg, #9edcff 0%, #5fb3ff 100%);"
    )
    direction_background = (
        f"background: url('{direction_uri}') center / cover no-repeat;"
        if direction_uri
        else "background: var(--kfps-parchment);"
    )
    return f"""
<style>
@import url("https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,600,0,0");
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");

:root {{
  color-scheme: {color_scheme};
  --kfps-primary: {root["primary"]};
  --kfps-primary-focus: {root["primary_focus"]};
  --kfps-primary-on-dark: #9bb9ff;
  --kfps-ink: {root["ink"]};
  --kfps-body: {root["body"]};
  --kfps-muted: {root["muted"]};
  --kfps-muted-dark: {root["muted"]};
  --kfps-hairline: {root["hairline"]};
  --kfps-canvas: {root["canvas"]};
  --kfps-parchment: {root["parchment"]};
  --kfps-pearl: {root["surface"]};
  --kfps-surface: {root["surface"]};
  --kfps-surface-alt: {root["surface_alt"]};
  --kfps-dark: {root["dark"]};
  --kfps-black: {root["dark"]};
  --kfps-chip: {root["chip"]};
  --kfps-info: {root["info"]};
  --kfps-help-dot-ink: {root["help_dot_ink"]};
  --kfps-radius: 16px;
  --kfps-radius-pill: 9999px;
  --kfps-enter-card-height: 272px;
}}

.material-symbols-rounded {{
  font-family: "Material Symbols Rounded";
  font-weight: normal;
  font-style: normal;
  font-size: 24px;
  line-height: 1;
  letter-spacing: 0;
  text-transform: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  direction: ltr;
  font-feature-settings: "liga";
  -webkit-font-feature-settings: "liga";
  -webkit-font-smoothing: antialiased;
}}

html,
body,
.stApp,
[data-testid="stApp"],
[data-testid="stAppViewContainer"] {{
  background: var(--kfps-canvas);
  color: var(--kfps-body);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}}

[data-testid="stHeader"] {{
  background: color-mix(in srgb, var(--kfps-canvas) 88%, transparent);
  border-bottom: 1px solid var(--kfps-hairline);
  z-index: 900 !important;
}}

button[data-testid="stBaseButton-header"][kind="header"],
[data-testid="stMainMenuButton"],
[data-testid="stToolbar"] button[data-testid="stBaseButton-header"],
[data-testid="stToolbar"] [data-testid="stMainMenuButton"] {{
  display: none !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"],
[data-testid="stExpandSidebarButton"],
[data-testid="stHeader"] button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
[data-testid="stSidebar"] button[title*="sidebar" i],
[data-testid="stSidebar"] button[aria-label*="sidebar" i] {{
  position: fixed !important;
  top: 10px !important;
  left: 12px !important;
  z-index: 1000000 !important;
  width: 36px !important;
  height: 36px !important;
  min-width: 36px !important;
  min-height: 36px !important;
  margin: 0 !important;
  padding: 0 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  border: 0 !important;
  border-radius: 9px !important;
  background: transparent !important;
  color: var(--kfps-ink) !important;
  font-size: 0 !important;
  line-height: 0 !important;
  box-shadow: none !important;
  opacity: 1 !important;
  outline: none !important;
  overflow: hidden !important;
}}

[data-testid="stExpandSidebarButton"] svg,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"] svg,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"] span,
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebar"] button[title*="sidebar" i] svg,
[data-testid="stSidebar"] button[aria-label*="sidebar" i] svg {{
  display: none !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"] *,
[data-testid="stExpandSidebarButton"] *,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"] *,
[data-testid="stSidebarCollapseButton"] *,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] *,
[data-testid="stSidebar"] button[title*="sidebar" i] *,
[data-testid="stSidebar"] button[aria-label*="sidebar" i] * {{
  color: transparent !important;
  font-size: 0 !important;
  line-height: 0 !important;
  opacity: 0 !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]::before,
[data-testid="stExpandSidebarButton"]::before,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]::before,
[data-testid="stSidebarCollapseButton"]::before,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]::before,
[data-testid="stSidebar"] button[title*="sidebar" i]::before,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]::before {{
  content: "";
  position: absolute;
  left: 9px;
  top: 10px;
  width: 17px;
  height: 14px;
  border: 1.8px solid currentColor;
  border-radius: 4px;
  background: transparent;
  opacity: 1;
  visibility: visible !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]::after,
[data-testid="stExpandSidebarButton"]::after,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]::after,
[data-testid="stSidebarCollapseButton"]::after,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]::after,
[data-testid="stSidebar"] button[title*="sidebar" i]::after,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]::after {{
  content: "";
  position: absolute;
  left: 15px;
  top: 11px;
  width: 1.8px;
  height: 12px;
  border-radius: 2px;
  background: currentColor;
  opacity: 1;
  visibility: visible !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]:hover,
[data-testid="stExpandSidebarButton"]:hover,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]:hover,
[data-testid="stSidebarCollapseButton"]:hover,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]:hover,
[data-testid="stSidebar"] button[title*="sidebar" i]:hover,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]:hover {{
  background: color-mix(in srgb, var(--kfps-ink) 7%, transparent) !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]:focus,
[data-testid="stExpandSidebarButton"]:focus,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]:focus,
[data-testid="stSidebarCollapseButton"]:focus,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]:focus,
[data-testid="stSidebar"] button[title*="sidebar" i]:focus,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]:focus,
[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]:active,
[data-testid="stExpandSidebarButton"]:active,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]:active,
[data-testid="stSidebarCollapseButton"]:active,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]:active,
[data-testid="stSidebar"] button[title*="sidebar" i]:active,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]:active {{
  background: color-mix(in srgb, var(--kfps-ink) 10%, transparent) !important;
  box-shadow: none !important;
}}

.block-container {{
  max-width: 1120px;
  padding-top: 0;
}}

.st-key-kfps_top_bar {{
  position: sticky;
  top: 0;
  z-index: 999;
  width: 100vw;
  min-height: 52px;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  padding: 7px max(16px, calc((100vw - 1120px) / 2 + 24px)) 7px
    max(56px, calc((100vw - 1120px) / 2 + 24px));
  background: #3a3d42;
  backdrop-filter: saturate(140%) blur(18px);
  border-bottom: 1px solid color-mix(in srgb, #f7f6f2 18%, transparent);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  white-space: nowrap;
}}

.kfps-sidebar-toggle-visual {{
  display: none;
}}

.st-key-kfps_sidebar_toggle_button {{
  position: fixed !important;
  left: 12px !important;
  top: 10px !important;
  z-index: 1000002 !important;
  width: 36px !important;
  height: 36px !important;
}}

.st-key-kfps_sidebar_toggle_button button {{
  position: relative !important;
  width: 36px !important;
  min-width: 36px !important;
  height: 36px !important;
  min-height: 36px !important;
  padding: 0 !important;
  border: 0 !important;
  border-radius: 9px !important;
  background: transparent !important;
  color: var(--kfps-ink) !important;
  box-shadow: none !important;
  font-size: 0 !important;
  line-height: 0 !important;
}}

.st-key-kfps_sidebar_toggle_button button:hover,
.st-key-kfps_sidebar_toggle_button button:focus,
.st-key-kfps_sidebar_toggle_button button:active {{
  background: color-mix(in srgb, var(--kfps-ink) 7%, transparent) !important;
  border: 0 !important;
  box-shadow: none !important;
}}

.st-key-kfps_sidebar_toggle_button button::before {{
  content: "";
  position: absolute;
  left: 9px;
  top: 10px;
  width: 17px;
  height: 14px;
  border: 1.8px solid currentColor;
  border-radius: 4px;
}}

.st-key-kfps_sidebar_toggle_button button::after {{
  content: "";
  position: absolute;
  left: 15px;
  top: 11px;
  width: 1.8px;
  height: 12px;
  border-radius: 2px;
  background: currentColor;
}}

[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"] {{
  display: none !important;
}}

.stApp:has(.kfps-sidebar-hidden) [data-testid="stSidebar"] {{
  display: none !important;
}}

.stApp:has(.kfps-sidebar-hidden) .kfps-hero,
.stApp:has(.kfps-sidebar-hidden) .kfps-section-band,
.stApp:has(.kfps-sidebar-hidden) .kfps-guide {{
  width: 100vw !important;
  margin-left: calc(50% - 50vw) !important;
  margin-right: calc(50% - 50vw) !important;
}}

.st-key-kfps_top_bar::-webkit-scrollbar {{
  display: none;
}}

.st-key-kfps_top_bar [data-testid="stHorizontalBlock"] {{
  display: flex !important;
  flex-direction: row !important;
  align-items: center;
  flex-wrap: nowrap !important;
  width: max(720px, 100%) !important;
}}

.st-key-kfps_top_bar [data-testid="column"] {{
  min-width: 0 !important;
  flex-shrink: 0 !important;
}}

.st-key-kfps_top_controls [data-testid="stHorizontalBlock"] {{
  display: flex !important;
  flex-direction: row !important;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: nowrap !important;
  gap: 0;
  min-width: 300px;
  width: 300px !important;
}}

.kfps-toggle-copy {{
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f7f6f2;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 13px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0.03em;
}}

.kfps-toggle-divider {{
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: color-mix(in srgb, #f7f6f2 66%, transparent);
  font-size: 16px;
  font-weight: 800;
}}

.kfps-sidebar-title {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 4px 0 24px;
  color: var(--kfps-muted);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 13px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.01em;
}}

.kfps-sidebar-gear {{
  width: 18px;
  height: 18px;
  color: var(--kfps-muted);
  font-size: 18px;
  font-variation-settings: "FILL" 0, "wght" 580, "GRAD" 0, "opsz" 20;
}}

.kfps-top-brandbar {{
  display: inline-flex;
  align-items: center;
  min-width: 260px;
  height: 38px;
  color: #f7f6f2;
  overflow: visible;
}}

.kfps-top-brandbar strong {{
  color: #f7f6f2;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 15px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: -0.01em;
  white-space: nowrap;
}}

.st-key-kfps_lang_is_kor,
.st-key-kfps_theme_is_dark {{
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
}}

.st-key-kfps_lang_is_kor label,
.st-key-kfps_theme_is_dark label {{
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  margin: 0 !important;
}}

.st-key-kfps_lang_is_kor [data-testid="stWidgetLabel"],
.st-key-kfps_theme_is_dark [data-testid="stWidgetLabel"],
.st-key-kfps_lang_is_kor [data-testid="stMarkdownContainer"],
.st-key-kfps_theme_is_dark [data-testid="stMarkdownContainer"],
.st-key-kfps_lang_is_kor [data-testid="stMarkdownContainer"] p,
.st-key-kfps_theme_is_dark [data-testid="stMarkdownContainer"] p {{
  display: none !important;
}}

.st-key-kfps_lang_is_kor [role="switch"],
.st-key-kfps_theme_is_dark [role="switch"] {{
  position: relative !important;
  width: 48px !important;
  min-width: 48px !important;
  height: 28px !important;
  border-radius: var(--kfps-radius-pill) !important;
  border: 3px solid #f7f6f2 !important;
  background: color-mix(in srgb, #f7f6f2 92%, transparent) !important;
  box-shadow: none !important;
  overflow: hidden !important;
  transition: background-color 160ms ease, border-color 160ms ease;
}}

.st-key-kfps_lang_is_kor [role="switch"][aria-checked="true"],
.st-key-kfps_theme_is_dark [role="switch"][aria-checked="true"] {{
  border-color: #f8f6ef !important;
  background: #26272a !important;
}}

.st-key-kfps_lang_is_kor [role="switch"] *,
.st-key-kfps_theme_is_dark [role="switch"] * {{
  box-shadow: none !important;
}}

.st-key-kfps_lang_is_kor [role="switch"]::after,
.st-key-kfps_theme_is_dark [role="switch"]::after {{
  content: "";
  position: absolute;
  top: 4px;
  left: 4px;
  width: 14px;
  height: 14px;
  border-radius: 9999px;
  background: #3a3d42;
  transition: transform 160ms ease, background-color 160ms ease;
}}

.st-key-kfps_lang_is_kor [role="switch"][aria-checked="true"]::after,
.st-key-kfps_theme_is_dark [role="switch"][aria-checked="true"]::after {{
  transform: translateX(22px);
  background: #f8f6ef;
}}

.st-key-kfps_top_bar [data-baseweb="button-group"] {{
  display: flex;
  justify-content: flex-end;
  flex-wrap: nowrap;
  width: 100%;
}}

.st-key-kfps_top_bar [data-baseweb="button-group"] button {{
  border-radius: var(--kfps-radius-pill) !important;
  min-height: 36px;
  color: var(--kfps-ink);
  border-color: var(--kfps-hairline);
  background: var(--kfps-surface);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  padding-left: 10px;
  padding-right: 10px;
}}

.st-key-kfps_top_bar [data-baseweb="button-group"] button:hover {{
  border-color: var(--kfps-primary) !important;
  color: var(--kfps-primary) !important;
}}

.st-key-kfps_top_bar [data-baseweb="button-group"] button[aria-pressed="true"],
.st-key-kfps_top_bar [data-baseweb="button-group"] button[aria-selected="true"],
.st-key-kfps_top_bar [data-baseweb="button-group"] button[aria-checked="true"],
.st-key-kfps_top_bar [data-baseweb="button-group"] button[data-selected="true"] {{
  background: var(--kfps-primary) !important;
  border-color: var(--kfps-primary) !important;
  color: #f8f6ef !important;
}}

.kfps-global-nav,
.kfps-subnav {{
  display: none !important;
}}

.kfps-top-brandbar {{
  min-height: 40px;
  display: flex;
  align-items: center;
  overflow: hidden;
  white-space: nowrap;
  color: var(--kfps-body);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}}

.kfps-top-brandbar strong {{
  color: var(--kfps-ink);
  font-size: 18px;
  line-height: 1;
  font-weight: 800;
}}

.kfps-subnav .kfps-buy-chip,
.kfps-hero .kfps-pill-primary {{
  background: var(--kfps-primary);
  color: #f8f6ef;
}}

.kfps-hero {{
  {hero_background}
  position: relative;
  isolation: isolate;
  overflow: hidden;
  color: #ffffff;
  padding: 72px 24px 56px;
  margin-top: 0 !important;
}}

.kfps-hero::before {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background: rgba(0, 0, 0, 0.24);
  backdrop-filter: blur(1.4px);
  -webkit-backdrop-filter: blur(1.4px);
}}

.kfps-hero h1,
.kfps-section-band h2 {{
  color: inherit;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  letter-spacing: -0.02em;
}}

.kfps-hero-eyebrow {{
  display: table;
  margin: 0 auto 14px;
  position: relative;
  z-index: 1;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.95);
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.32);
  padding: 7px 14px;
  border-radius: var(--kfps-radius-pill);
}}

.kfps-hero p,
.kfps-hero-copy {{
  color: #ffffff;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  letter-spacing: -0.01em;
}}

.kfps-hero-copy {{
  display: grid;
  gap: 12px;
  max-width: 880px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
  text-align: center;
  text-shadow: 0 2px 16px rgba(0, 0, 0, 0.34);
}}

.kfps-hero-main {{
  display: block;
  margin: 0;
  padding: 0;
  font-size: clamp(21px, 2.4vw, 27px);
  font-weight: 650;
  line-height: 1.2;
}}

.kfps-hero-subtext {{
  display: block;
  max-width: 760px;
  margin: 0 auto;
  padding: 0;
  color: #ffffff;
  font-size: clamp(13px, 1.35vw, 16px);
  font-weight: 300;
  line-height: 1.6;
}}

.kfps-footer-badges,
.kfps-hero-pills {{
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
}}

.kfps-hero-pills {{
  margin-top: 24px;
  position: relative;
  z-index: 1;
}}

.kfps-footer-badges {{
  margin: 18px 0 12px;
  justify-content: flex-start;
}}

.kfps-footer-badge,
.kfps-hero .kfps-pill {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 34px;
  padding: 8px 13px;
  background: var(--kfps-surface);
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius-pill);
  color: var(--kfps-body);
  font-size: 13px;
  font-weight: 300;
  line-height: 1;
  white-space: nowrap;
}}

.kfps-footer-badges .kfps-footer-badge.kfps-pill-link {{
  text-decoration: none !important;
  font-weight: 450;
}}

.kfps-footer-badges .kfps-footer-badge.kfps-pill-link:hover {{
  border-color: color-mix(in srgb, var(--kfps-primary) 42%, var(--kfps-hairline));
  background: color-mix(in srgb, var(--kfps-primary) 5%, var(--kfps-surface));
}}

.kfps-hero .kfps-pill {{
  background: rgba(18, 25, 35, 0.38);
  border-color: rgba(255, 255, 255, 0.32);
  color: #ffffff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.20), 0 8px 24px rgba(0, 0, 0, 0.12);
  backdrop-filter: blur(16px) saturate(125%);
  -webkit-backdrop-filter: blur(16px) saturate(125%);
  text-shadow: 0 1px 8px rgba(0, 0, 0, 0.30);
}}

.kfps-hero .kfps-pill:hover {{
  background: rgba(18, 25, 35, 0.48);
  border-color: rgba(255, 255, 255, 0.48);
}}

.kfps-pill-link {{
  text-decoration: none !important;
  cursor: pointer;
}}

.kfps-pill-link:focus-visible {{
  outline: 2px solid rgba(255, 255, 255, 0.78);
  outline-offset: 3px;
}}

.kfps-footer-badges .kfps-footer-badge.kfps-pill-link:focus-visible {{
  outline: 2px solid var(--kfps-primary);
  outline-offset: 2px;
}}

.kfps-pill-emoji,
.kfps-footer-emoji {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  font-size: 16px;
  line-height: 1;
}}

.kfps-hero .kfps-pill.kfps-pill-dataset,
.kfps-footer-badges .kfps-footer-badge.kfps-pill-dataset {{
  gap: 7px;
  padding-left: 14px;
  padding-right: 14px;
}}

.kfps-pill-dataset .kfps-pill-emoji {{
  width: 16px;
  height: 16px;
  font-size: 14px;
  flex-shrink: 0;
}}

.kfps-pill-icon {{
  width: 18px;
  height: 18px;
  font-size: 18px;
  color: currentColor;
}}

.kfps-pill-github {{
  display: inline-block;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  background: currentColor;
  -webkit-mask: url("{GITHUB_MARK_MASK_URI}") center / contain no-repeat;
  mask: url("{GITHUB_MARK_MASK_URI}") center / contain no-repeat;
}}

.kfps-symbol {{
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  color: var(--kfps-primary);
  font-size: 0;
  line-height: 1;
}}

.kfps-symbol-screen::before {{
  content: "";
  width: 13px;
  height: 9px;
  border: 1.6px solid currentColor;
  border-radius: 3px;
}}

.kfps-symbol-screen::after {{
  content: "";
  position: absolute;
  left: 5px;
  bottom: 1px;
  width: 6px;
  height: 1.6px;
  background: currentColor;
  box-shadow: 3px 2px 0 currentColor;
}}

.kfps-symbol-lock::before {{
  content: "";
  position: absolute;
  left: 3px;
  bottom: 2px;
  width: 10px;
  height: 8px;
  border: 1.6px solid currentColor;
  border-radius: 3px;
}}

.kfps-symbol-lock::after {{
  content: "";
  position: absolute;
  left: 5px;
  top: 2px;
  width: 6px;
  height: 7px;
  border: 1.6px solid currentColor;
  border-bottom: 0;
  border-radius: 7px 7px 0 0;
}}

.kfps-symbol-export::before {{
  content: "";
  position: absolute;
  left: 3px;
  bottom: 3px;
  width: 9px;
  height: 9px;
  border-left: 1.6px solid currentColor;
  border-bottom: 1.6px solid currentColor;
}}

.kfps-symbol-export::after {{
  content: "";
  position: absolute;
  right: 2px;
  top: 2px;
  width: 9px;
  height: 9px;
  border-top: 1.8px solid currentColor;
  border-right: 1.8px solid currentColor;
  transform: rotate(0deg);
}}

.kfps-footer-note {{
  margin: 0;
}}

.kfps-guide {{
  width: 100vw;
  margin: 0 calc(50% - 50vw);
  padding: 36px 24px 48px;
  background: var(--kfps-canvas);
}}

.kfps-guide-inner {{
  max-width: 1120px;
  margin: 0 auto;
}}

.kfps-eyebrow {{
  color: var(--kfps-primary);
  font-size: 18px;
  font-weight: 850;
  letter-spacing: -0.01em;
}}

.kfps-guide h2 {{
  margin: 6px 0 22px;
  color: var(--kfps-ink);
  font-size: clamp(26px, 3vw, 38px);
  line-height: 1.16;
  letter-spacing: -0.03em;
}}

.kfps-flow {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  align-items: start;
}}

.kfps-flow-card {{
  position: relative;
  min-height: 164px;
  padding: 22px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  color: var(--kfps-body);
  align-self: start;
}}

.kfps-flow-card summary {{
  display: block;
  cursor: pointer;
  list-style: none;
}}

.kfps-flow-card summary:focus,
.kfps-flow-card summary:focus-visible {{
  outline: none !important;
}}

.kfps-flow-card summary::-webkit-details-marker {{
  display: none;
}}

.kfps-flow-card:hover {{
  border-color: color-mix(in srgb, var(--kfps-primary) 46%, var(--kfps-hairline));
  background: color-mix(in srgb, var(--kfps-primary) 4%, var(--kfps-surface));
}}

.kfps-flow-detail {{
  margin-top: 14px;
  padding-top: 13px;
  border-top: 1px solid var(--kfps-hairline);
  color: var(--kfps-muted);
  font-size: 13px;
  line-height: 1.5;
}}

.kfps-flow-card:not(:last-child)::after {{
  content: "";
  position: absolute;
  right: -11px;
  top: 50%;
  width: 18px;
  height: 18px;
  border-top: 2px solid var(--kfps-primary);
  border-right: 2px solid var(--kfps-primary);
  transform: translateY(-50%) rotate(45deg);
  background: transparent;
}}

.kfps-icon {{
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: var(--kfps-radius);
  display: grid;
  place-items: center;
  background: var(--kfps-chip);
  color: var(--kfps-primary);
  margin-bottom: 16px;
}}

.kfps-step-icon {{
  position: relative;
  width: 28px;
  height: 28px;
  color: currentColor;
}}

.kfps-step-icon.material-symbols-rounded {{
  position: static;
  width: auto;
  height: auto;
  font-size: 31px;
  font-variation-settings: "FILL" 1, "wght" 560, "GRAD" 0, "opsz" 32;
}}

.kfps-step-concept::before {{
  content: "";
  position: absolute;
  left: 9px;
  top: 3px;
  width: 6px;
  height: 21px;
  border: 2px solid currentColor;
  border-radius: 4px;
  transform: rotate(-38deg);
}}

.kfps-step-concept::after {{
  content: "";
  position: absolute;
  left: 4px;
  bottom: 2px;
  width: 13px;
  height: 2px;
  background: currentColor;
  border-radius: 2px;
}}

.kfps-step-people i {{
  position: absolute;
  top: 5px;
  width: 7px;
  height: 7px;
  border: 2px solid currentColor;
  border-radius: 9999px;
}}

.kfps-step-people i::after {{
  content: "";
  position: absolute;
  left: -3px;
  top: 10px;
  width: 9px;
  height: 9px;
  border: 2px solid currentColor;
  border-top: 0;
  border-radius: 0 0 9px 9px;
}}

.kfps-step-people i:nth-child(1) {{
  left: 0;
  top: 8px;
}}

.kfps-step-people i:nth-child(2) {{
  left: 10px;
}}

.kfps-step-people i:nth-child(3) {{
  right: 0;
  top: 8px;
}}

.kfps-step-cost::before {{
  content: "$";
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 22px;
  font-weight: 900;
  line-height: 1;
}}

.kfps-step-report::before {{
  content: "";
  position: absolute;
  left: 6px;
  top: 3px;
  width: 16px;
  height: 22px;
  border: 2px solid currentColor;
  border-radius: 4px;
  background:
    linear-gradient(currentColor 0 0) 4px 8px / 8px 2px no-repeat,
    linear-gradient(currentColor 0 0) 4px 13px / 8px 2px no-repeat;
}}

.kfps-step-report::after {{
  content: "";
  position: absolute;
  right: 5px;
  top: 3px;
  width: 7px;
  height: 7px;
  border-left: 2px solid currentColor;
  border-bottom: 2px solid currentColor;
  background: var(--kfps-chip);
}}

.kfps-secret-field-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 14px 0 7px;
}}

.kfps-secret-field-actions {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex: 0 0 auto;
  overflow: visible;
}}

.kfps-key-name {{
  color: var(--kfps-ink);
  font-size: 13px;
  font-weight: 850;
  line-height: 1;
}}

.kfps-key-mark {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 9999px;
  border: 1px solid var(--kfps-hairline);
  font-size: 13px;
  font-weight: 900;
  line-height: 1;
}}

.kfps-key-mark.ok {{
  color: #0f8f5f;
  background: color-mix(in srgb, #18a66f 13%, var(--kfps-surface));
}}

.kfps-key-mark.missing {{
  color: var(--kfps-muted);
  background: var(--kfps-chip);
}}

.kfps-help-dot {{
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border-radius: 9999px;
  border: 1px solid var(--kfps-hairline);
  background: var(--kfps-chip);
  color: var(--kfps-help-dot-ink);
  font-size: 12px;
  font-weight: 900;
  cursor: help;
  overflow: visible;
  outline: none;
}}

.kfps-secret-field-actions .kfps-help-dot {{
  width: 20px;
  height: 20px;
  border: 0;
  background: transparent;
  color: var(--kfps-muted);
  font-size: 18px !important;
  font-variation-settings: "FILL" 0, "wght" 450, "GRAD" 0, "opsz" 20;
  font-weight: normal;
  line-height: 1 !important;
}}

.kfps-secret-field-actions .kfps-help-dot:hover,
.kfps-secret-field-actions .kfps-help-dot:focus-visible {{
  background: color-mix(in srgb, var(--kfps-ink) 8%, transparent);
  color: var(--kfps-ink);
}}

.kfps-help-dot::before,
.kfps-help-dot::after {{
  position: absolute;
  right: 0;
  z-index: 1000006;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity 120ms ease, transform 120ms ease, visibility 120ms ease;
}}

.kfps-help-dot::before {{
  content: "";
  top: calc(100% + 2px);
  width: 10px;
  height: 10px;
  transform: translate(-6px, -2px) rotate(45deg);
  background: var(--kfps-surface);
  border-left: 1px solid var(--kfps-hairline);
  border-top: 1px solid var(--kfps-hairline);
  box-shadow: -2px -2px 6px rgba(39, 40, 44, 0.04);
}}

.kfps-help-dot::after {{
  content: attr(data-tooltip);
  top: calc(100% + 7px);
  min-width: 210px;
  max-width: min(320px, calc(100vw - 32px));
  padding: 9px 11px;
  border: 1px solid var(--kfps-hairline);
  border-radius: 8px;
  background: var(--kfps-surface);
  color: var(--kfps-body);
  box-shadow: 0 14px 36px rgba(39, 40, 44, 0.14);
  font-size: 12px;
  font-weight: 650;
  line-height: 1.45;
  letter-spacing: 0;
  text-align: left;
  white-space: normal;
  word-break: keep-all;
  transform: translateY(-3px);
}}

.kfps-secret-field-actions .kfps-help-dot::after {{
  font-size: 11px;
  line-height: 1.4;
}}

.kfps-help-dot:hover::before,
.kfps-help-dot:hover::after,
.kfps-help-dot:focus-visible::before,
.kfps-help-dot:focus-visible::after {{
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}}

.kfps-help-dot:hover::before,
.kfps-help-dot:focus-visible::before {{
  transform: translate(-6px, 0) rotate(45deg);
}}

.kfps-secret-field-head,
.kfps-secret-status-grid,
.kfps-secret-status-card {{
  overflow: visible;
}}

[role="tooltip"],
[data-baseweb="tooltip"],
[data-testid="stTooltip"] {{
  border: 1px solid var(--kfps-hairline) !important;
  border-radius: 8px !important;
  background: var(--kfps-surface) !important;
  color: var(--kfps-body) !important;
  box-shadow: 0 14px 36px rgba(39, 40, 44, 0.14) !important;
}}

[role="tooltip"] *,
[data-baseweb="tooltip"] *,
[data-testid="stTooltip"] * {{
  background: transparent !important;
  color: var(--kfps-body) !important;
}}

.kfps-secret-status-grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}}

.kfps-secret-status-card {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 10px 12px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
}}

.kfps-secret-provider {{
  color: var(--kfps-ink);
  font-size: 13px;
  font-weight: 850;
  min-width: 0;
}}

.kfps-secret-state {{
  color: var(--kfps-muted);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.04em;
}}

.kfps-secret-state.ok {{
  color: #0f8f5f;
}}

.kfps-secret-state.missing {{
  color: var(--kfps-muted);
}}

.kfps-input-section-title {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin: 22px 0 12px;
  padding: 7px 12px;
  border: 1px solid var(--kfps-hairline);
  border-radius: 9px;
  background: color-mix(in srgb, var(--kfps-primary) 6%, var(--kfps-surface));
  color: var(--kfps-ink);
  font-size: 17px;
  font-weight: 720;
  line-height: 1.08;
  letter-spacing: 0;
}}

.kfps-input-section-title::before {{
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  background: var(--kfps-primary);
}}

@media (max-width: 760px) {{
  .kfps-secret-status-grid {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
}}

.kfps-enter-card {{
  box-sizing: border-box;
  height: var(--kfps-enter-card-height);
  min-height: var(--kfps-enter-card-height);
  margin-top: 27px;
  padding: 92px 28px 30px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  color: var(--kfps-body);
  display: grid;
  align-content: start;
  gap: 0;
  box-shadow: 0 10px 28px rgba(39, 40, 44, 0.04);
  transition: none;
}}

.kfps-enter-card:hover {{
  border-color: color-mix(in srgb, #ef4444 44%, var(--kfps-hairline));
  background: color-mix(in srgb, #ef4444 5%, var(--kfps-surface));
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.22);
}}

.st-key-kfps_enter_overlay {{
  position: relative !important;
}}

.st-key-kfps_enter_overlay [data-testid="stVerticalBlock"] {{
  display: block !important;
  gap: 0 !important;
}}

.st-key-kfps_enter_card_button {{
  box-sizing: border-box !important;
  position: absolute !important;
  top: 27px !important;
  left: 0 !important;
  right: 0 !important;
  width: 100% !important;
  margin: 0 !important;
  z-index: 7 !important;
  min-height: var(--kfps-enter-card-height) !important;
}}

.st-key-kfps_enter_card_button button {{
  box-sizing: border-box !important;
  width: 100% !important;
  min-height: var(--kfps-enter-card-height) !important;
  border: 1px solid transparent !important;
  border-radius: var(--kfps-radius) !important;
  background: transparent !important;
  box-shadow: none !important;
  color: transparent !important;
  cursor: pointer !important;
  transition: none !important;
}}

.st-key-kfps_enter_card_button button p {{
  color: transparent !important;
}}

.st-key-kfps_enter_card_button button:hover,
.st-key-kfps_enter_card_button button:focus-visible {{
  border-color: color-mix(in srgb, #ef4444 44%, var(--kfps-hairline)) !important;
  background: color-mix(in srgb, #ef4444 5%, transparent) !important;
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.22) !important;
}}

.st-key-kfps_enter_card_button button:active {{
  transform: none;
}}

.kfps-enter-top {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
}}

.kfps-enter-title-stack {{
  display: grid;
  gap: 4px;
  min-width: 0;
  text-align: center;
  grid-column: 2;
}}

.kfps-enter-arrow {{
  display: inline-grid;
  place-items: center;
  justify-self: end;
  grid-column: 1;
  width: 30px;
  height: 30px;
  border-radius: 0;
  background: transparent;
  color: var(--kfps-ink);
  font-size: 27px !important;
  font-variation-settings: "FILL" 0, "wght" 680, "GRAD" 0, "opsz" 28;
}}

.kfps-enter-card strong {{
  color: var(--kfps-body);
  font-size: 28px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0;
}}

.kfps-enter-subtitle {{
  color: var(--kfps-muted);
  font-size: 13px;
  font-weight: 650;
  line-height: 1.15;
  letter-spacing: 0;
}}

.kfps-enter-warning {{
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  max-width: 250px;
  margin: 44px auto 0;
  color: var(--kfps-body);
  font-size: 13px;
  line-height: 1.55;
  word-break: keep-all;
}}

.kfps-enter-warning-icon {{
  color: #b45309;
  font-size: 17px !important;
  line-height: 1.25 !important;
  font-variation-settings: "FILL" 1, "wght" 620, "GRAD" 0, "opsz" 20;
}}

.kfps-run-panel {{
  margin: 18px 0 18px;
  padding: 18px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  color: var(--kfps-body);
}}

.kfps-run-panel h3 {{
  margin: 0 0 7px;
  color: var(--kfps-ink);
  font-size: 20px;
  line-height: 1.25;
}}

.kfps-run-panel p {{
  margin: 0;
  color: var(--kfps-muted);
  font-size: 14px;
  line-height: 1.55;
  word-break: keep-all;
}}

.st-key-kfps_cost_confirm {{
  border: 1px solid transparent !important;
  border-radius: var(--kfps-radius) !important;
  padding: 10px 12px !important;
  transition: none !important;
}}

.st-key-kfps_cost_confirm * {{
  transition: none !important;
}}

.st-key-kfps_advanced_expander,
.st-key-kfps_advanced_expander *,
.st-key-kfps_advanced_expander summary,
.st-key-kfps_advanced_expander details {{
  animation: none !important;
  transition: none !important;
}}

.st-key-kfps_advanced_expander summary:hover,
.st-key-kfps_advanced_expander summary:focus,
.st-key-kfps_advanced_expander summary:active {{
  background: transparent !important;
  box-shadow: none !important;
}}

[data-testid="stExpander"] {{
  transition: none !important;
}}

.kfps-result-anchor {{
  display: block;
  height: 1px;
  scroll-margin-top: 86px;
}}

.st-key-kfps_export_md_pending button,
[class*="st-key-kfps_export_md_"] button {{
  pointer-events: auto !important;
  transition: none !important;
}}

.st-key-kfps_export_md_pending button:hover,
.st-key-kfps_export_md_pending button:focus-visible,
[class*="st-key-kfps_export_md_"] button:hover,
[class*="st-key-kfps_export_md_"] button:focus-visible {{
  border-color: color-mix(in srgb, #ef4444 44%, var(--kfps-hairline)) !important;
  background: color-mix(in srgb, #ef4444 5%, var(--kfps-surface)) !important;
  color: #b91c1c !important;
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.22) !important;
}}

.st-key-kfps_export_md_pending button:hover p,
.st-key-kfps_export_md_pending button:focus-visible p,
[class*="st-key-kfps_export_md_"] button:hover p,
[class*="st-key-kfps_export_md_"] button:focus-visible p {{
  color: #b91c1c !important;
}}

.kfps-report-shell {{
  margin: 16px 0 20px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  overflow: hidden;
  user-select: text;
}}

.kfps-report-empty {{
  min-height: 168px;
  display: grid;
  place-items: center;
  padding: 24px;
  color: var(--kfps-muted);
  text-align: center;
}}

.kfps-report-empty strong {{
  display: block;
  margin-bottom: 8px;
  color: color-mix(in srgb, var(--kfps-muted) 82%, var(--kfps-surface));
  font-size: 15px;
  font-weight: 800;
}}

.kfps-report-empty span {{
  display: block;
  color: color-mix(in srgb, var(--kfps-muted) 64%, var(--kfps-surface));
  font-size: 13px;
  line-height: 1.45;
}}

.kfps-report-selectable {{
  min-height: 520px;
  max-height: 520px;
  margin: 0;
  padding: 20px;
  overflow: auto;
  color: var(--kfps-body);
  background: var(--kfps-surface);
  border: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  user-select: text;
  cursor: text;
  font-family: "JetBrains Mono", "Cascadia Mono", "Consolas", monospace;
  font-size: 13px;
  line-height: 1.55;
}}

.kfps-report-selectable::selection,
.kfps-report-shell ::selection {{
  background: color-mix(in srgb, var(--kfps-primary) 24%, transparent);
}}

[class*="st-key-kfps_report_md_source"] textarea {{
  min-height: 520px !important;
  color: var(--kfps-body) !important;
  background: var(--kfps-surface) !important;
  border-color: var(--kfps-hairline) !important;
  font-family: "JetBrains Mono", "Cascadia Mono", "Consolas", monospace !important;
  font-size: 13px !important;
  line-height: 1.55 !important;
}}

.kfps-loading-panel {{
  margin-top: 16px;
  padding: 24px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  display: flex;
  align-items: center;
  gap: 16px;
  color: var(--kfps-body);
}}

.kfps-dot-spinner {{
  width: 36px;
  height: 36px;
  border-radius: 9999px;
  border: 4px dotted color-mix(in srgb, var(--kfps-primary) 42%, transparent);
  border-top-color: var(--kfps-primary);
  animation: kfps-spin 900ms linear infinite;
}}

@keyframes kfps-spin {{
  to {{
    transform: rotate(360deg);
  }}
}}

.kfps-opinion-head {{
  margin-top: 18px;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}}

.kfps-opinion-head h3 {{
  margin: 0 0 5px;
  color: var(--kfps-ink);
  font-size: 24px;
  line-height: 1.2;
}}

.kfps-opinion-head p {{
  margin: 0;
  color: var(--kfps-muted);
  font-size: 14px;
  line-height: 1.5;
}}

.kfps-opinion-grid {{
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}}

.kfps-opinion-card {{
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  color: var(--kfps-body);
}}

.kfps-opinion-meta {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--kfps-muted);
  font-size: 12px;
  font-weight: 750;
}}

.kfps-sentiment {{
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 9px;
  border-radius: 9999px;
  background: var(--kfps-chip);
  color: var(--kfps-ink);
  font-size: 12px;
  font-weight: 850;
}}

.kfps-sentiment.positive {{
  background: color-mix(in srgb, #18a66f 15%, var(--kfps-surface));
  color: #0f7a51;
}}

.kfps-sentiment.neutral {{
  background: color-mix(in srgb, #64748b 13%, var(--kfps-surface));
  color: var(--kfps-body);
}}

.kfps-sentiment.negative {{
  background: color-mix(in srgb, #ef4444 12%, var(--kfps-surface));
  color: #b91c1c;
}}

.kfps-opinion-profile {{
  margin: 0 0 10px;
  color: var(--kfps-ink);
  font-size: 13px;
  line-height: 1.35;
  font-weight: 780;
}}

.kfps-opinion-card h4 {{
  margin: 12px 0 5px;
  color: var(--kfps-muted);
  font-size: 12px;
  line-height: 1.2;
}}

.kfps-opinion-card p {{
  margin: 0;
  color: var(--kfps-body);
  font-size: 13px;
  line-height: 1.45;
  word-break: keep-all;
}}

.kfps-inline-note {{
  margin: 10px 0 12px;
  padding: 13px 14px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: color-mix(in srgb, var(--kfps-primary) 8%, var(--kfps-surface));
  color: var(--kfps-body);
  font-size: 14px;
  line-height: 1.45;
  overflow: hidden;
}}

.kfps-run-mode-note {{
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 44px;
}}

.kfps-model-meta {{
  display: grid;
  gap: 7px;
  margin: 12px 0 12px;
  padding: 12px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  overflow: hidden;
}}

.kfps-model-meta-row {{
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr);
  gap: 9px;
  align-items: baseline;
  min-width: 0;
}}

.kfps-model-meta-label {{
  color: var(--kfps-muted);
  font-size: 12px;
  line-height: 1.25;
  font-weight: 700;
  text-transform: none;
}}

.kfps-model-meta-value {{
  color: var(--kfps-ink);
  font-size: 13px;
  line-height: 1.3;
  font-weight: 700;
  word-break: break-word;
}}

.kfps-flow-card h3 {{
  margin: 0 0 7px;
  color: var(--kfps-ink);
  font-size: 18px;
  line-height: 1.24;
  letter-spacing: -0.02em;
}}

.kfps-flow-card p {{
  margin: 0;
  color: var(--kfps-muted);
  font-size: 15px;
  line-height: 1.45;
  letter-spacing: -0.01em;
}}

.kfps-section-band {{
  background: var(--kfps-dark);
  color: #f4f1ea;
  margin-top: 36px;
  padding: 42px 24px;
}}

.kfps-section-band.light {{
  background: var(--kfps-parchment);
  color: var(--kfps-ink);
}}

.kfps-section-band.direction {{
  {direction_background}
  color: #1d1d1f !important;
}}

.kfps-section-band.direction .kfps-section-band-inner {{
  max-width: 1120px;
  margin: 0 auto;
  text-align: left;
}}

.kfps-section-band.direction p {{
  margin-left: 0;
  margin-right: 0;
  color: #3a3d42 !important;
}}

.kfps-section-band h2 {{
  color: inherit;
}}

.kfps-section-band p,
.kfps-section-band.light p {{
  color: color-mix(in srgb, currentColor 72%, transparent);
}}

h1, h2, h3,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {{
  color: var(--kfps-ink);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  letter-spacing: -0.02em;
}}

p, label, .stMarkdown,
[data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] {{
  color: var(--kfps-body);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  letter-spacing: -0.01em;
}}

[data-testid="stElementContainer"]:has([data-testid="stTextInputRootElement"])
  [data-testid="stWidgetLabel"],
[data-testid="stElementContainer"]:has([data-testid="stNumberInputContainer"])
  [data-testid="stWidgetLabel"],
[data-testid="stElementContainer"]:has([data-testid="stTextAreaRootElement"])
  [data-testid="stWidgetLabel"] {{
  padding-left: 14px !important;
  margin-bottom: 7px !important;
}}

[data-testid="stElementContainer"]:has([data-testid="stTextInputRootElement"])
  [data-testid="stWidgetLabel"] p,
[data-testid="stElementContainer"]:has([data-testid="stNumberInputContainer"])
  [data-testid="stWidgetLabel"] p,
[data-testid="stElementContainer"]:has([data-testid="stTextAreaRootElement"])
  [data-testid="stWidgetLabel"] p {{
  margin: 0 !important;
}}

[data-testid="stSidebar"] {{
  background: var(--kfps-parchment);
  border-right: 1px solid var(--kfps-hairline);
  min-width: 360px !important;
}}

[data-testid="stSidebar"] > div {{
  min-width: 360px !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] {{
  width: 100% !important;
  min-width: 0 !important;
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button {{
  width: 100% !important;
  min-width: 0 !important;
  white-space: nowrap !important;
  color: var(--kfps-ink) !important;
  background: var(--kfps-surface) !important;
  font-size: 0 !important;
  padding: 0 5px !important;
  min-height: 32px !important;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button p {{
  overflow: visible !important;
  text-overflow: clip !important;
  white-space: nowrap !important;
  color: inherit !important;
  font-size: 10px !important;
  font-weight: 720 !important;
  letter-spacing: 0 !important;
  line-height: 1 !important;
}}

[data-testid="stSidebar"] [data-testid="stSegmentedControl"],
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] > div,
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] [data-baseweb="button-group"],
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] [data-baseweb="button-group"] > div {{
  width: 100% !important;
  max-width: none !important;
}}

[data-testid="stSidebar"] [data-testid="stSegmentedControl"] [data-baseweb="button-group"],
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] [data-baseweb="button-group"] > div {{
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}}

[data-testid="stSidebar"] div[role="radiogroup"][aria-label="button group"] {{
  width: 100% !important;
  max-width: none !important;
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}}

[data-testid="stSidebar"] div[role="radiogroup"][aria-label="button group"] > button {{
  width: 100% !important;
  min-width: 0 !important;
  justify-content: center !important;
}}

[data-testid="stSidebar"] .st-key-kfps_run_mode,
[data-testid="stSidebar"] .st-key-kfps_run_mode > div,
[data-testid="stSidebar"] .st-key-kfps_run_mode div[role="radiogroup"],
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(
  div[role="radiogroup"][aria-label="button group"]
) {{
  width: 100% !important;
  max-width: none !important;
}}

[data-testid="stSidebar"] .st-key-kfps_run_mode div[role="radiogroup"] {{
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}}

[data-testid="stSidebar"] .st-key-kfps_run_mode div[role="radiogroup"] > button {{
  width: 100% !important;
  min-width: 0 !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button
  [data-testid="stMarkdownContainer"] {{
  overflow: visible !important;
  min-width: max-content !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-pressed="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-selected="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-checked="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[data-selected="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"]
  button[data-testid="stBaseButton-segmented_controlActive"] {{
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
  border-color: #3b82f6 !important;
  color: #ffffff !important;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.22),
    0 8px 20px rgba(59, 130, 246, 0.18) !important;
}}

[data-testid="stMetric"],
[data-testid="stExpander"],
[data-testid="stAlert"] {{
  background: var(--kfps-surface);
  color: var(--kfps-body);
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  overflow: hidden;
}}

[data-testid="stExpander"] > details,
[data-testid="stExpander"] > details > summary,
[data-testid="stExpander"] [data-testid="stVerticalBlock"],
[data-testid="stAlert"] > div,
[data-testid="stAlert"] [role="alert"] {{
  border-radius: var(--kfps-radius) !important;
  box-shadow: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] {{
  margin-top: 18px;
  background: transparent !important;
  border: 0 !important;
  border-top: 1px solid var(--kfps-hairline) !important;
  border-radius: 0 !important;
  overflow: visible !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] details {{
  border-radius: 0 !important;
  overflow: visible !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
  position: relative !important;
  min-height: 52px !important;
  padding: 15px 42px 15px 0 !important;
  color: var(--kfps-muted) !important;
  border-radius: 0 !important;
  background: transparent !important;
  cursor: pointer !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary p {{
  color: var(--kfps-muted) !important;
  font-size: 14px !important;
  font-weight: 800 !important;
  line-height: 1.25 !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {{
  position: absolute !important;
  right: 8px !important;
  top: 50% !important;
  z-index: 2 !important;
  width: 18px !important;
  height: 18px !important;
  transform: translateY(-50%) !important;
  color: var(--kfps-muted) !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary::after {{
  content: "";
  position: absolute;
  right: 1px;
  top: 50%;
  width: 32px;
  height: 32px;
  border-radius: 9999px;
  background: color-mix(in srgb, var(--kfps-ink) 0%, transparent);
  transform: translateY(-50%);
  opacity: 0;
  transition: background-color 140ms ease, opacity 140ms ease;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover::after {{
  background: color-mix(in srgb, var(--kfps-ink) 9%, transparent);
  opacity: 1;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
  padding-top: 8px !important;
  border-radius: 0 !important;
}}

[data-baseweb="button-group"] {{
  border: 1px solid var(--kfps-hairline) !important;
  border-radius: var(--kfps-radius) !important;
  background: var(--kfps-surface) !important;
  box-shadow: none !important;
  overflow: hidden !important;
}}

[data-baseweb="button-group"] button {{
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
  color: var(--kfps-ink) !important;
}}

[data-baseweb="button-group"] button:not(:last-child) {{
  border-right: 1px solid var(--kfps-hairline) !important;
}}

[data-baseweb="button-group"] button:first-child {{
  border-top-left-radius: var(--kfps-radius) !important;
  border-bottom-left-radius: var(--kfps-radius) !important;
}}

[data-baseweb="button-group"] button:last-child {{
  border-top-right-radius: var(--kfps-radius) !important;
  border-bottom-right-radius: var(--kfps-radius) !important;
}}

[data-baseweb="button-group"] button[aria-pressed="true"],
[data-baseweb="button-group"] button[aria-selected="true"],
[data-baseweb="button-group"] button[aria-checked="true"],
[data-baseweb="button-group"] button[data-selected="true"] {{
  background: color-mix(in srgb, var(--kfps-primary) 14%, var(--kfps-surface)) !important;
  color: var(--kfps-ink) !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button {{
  width: 100% !important;
  min-width: 0 !important;
  white-space: nowrap !important;
  font-size: 0 !important;
  padding: 0 5px !important;
  min-height: 32px !important;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button p {{
  overflow: visible !important;
  text-overflow: clip !important;
  white-space: nowrap !important;
  color: inherit !important;
  font-size: 10px !important;
  font-weight: 720 !important;
  letter-spacing: 0 !important;
  line-height: 1 !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button
  [data-testid="stMarkdownContainer"] {{
  overflow: visible !important;
  min-width: max-content !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-pressed="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-selected="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-checked="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[data-selected="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"]
  button[data-testid="stBaseButton-segmented_controlActive"] {{
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
  border-color: #3b82f6 !important;
  color: #ffffff !important;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.22),
    0 8px 20px rgba(59, 130, 246, 0.18) !important;
}}

[data-testid="stMetricValue"] {{
  color: var(--kfps-ink);
}}

[data-testid="stMetricLabel"],
[data-testid="stCaptionContainer"],
small {{
  color: var(--kfps-muted);
}}

.stButton > button,
.stDownloadButton > button {{
  background: var(--kfps-primary);
  border-color: var(--kfps-primary);
  color: #f8f6ef;
  border-radius: var(--kfps-radius-pill);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}}

.stButton > button:disabled,
.stDownloadButton > button:disabled {{
  background: var(--kfps-chip);
  color: var(--kfps-muted);
  border-color: var(--kfps-hairline);
}}

[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-baseweb="textarea"] textarea,
[data-baseweb="slider"] {{
  background: var(--kfps-surface);
  color: var(--kfps-ink);
  border-color: var(--kfps-hairline);
}}

[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-baseweb="textarea"] > div,
[data-baseweb="textarea"] textarea {{
  border: 1px solid var(--kfps-hairline) !important;
  box-shadow: none !important;
  outline: none !important;
}}

[data-baseweb="input"] > div:hover,
[data-baseweb="select"] > div:hover,
[data-baseweb="textarea"] > div:hover,
[data-baseweb="textarea"] textarea:hover {{
  border-color: var(--kfps-hairline) !important;
}}

[data-baseweb="input"] > div:focus-within,
[data-baseweb="select"] > div:focus-within,
[data-baseweb="textarea"] > div:focus-within,
[data-baseweb="textarea"] textarea:focus {{
  border-color: var(--kfps-primary) !important;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--kfps-primary) 22%, transparent) !important;
}}

[data-testid="stTextInputRootElement"],
[data-testid="stNumberInputContainer"],
[data-testid="stTextAreaRootElement"],
[data-baseweb="input"],
[data-baseweb="input"] [data-baseweb="base-input"],
[data-baseweb="textarea"],
[data-baseweb="textarea"] [data-baseweb="base-input"] {{
  border: 1px solid var(--kfps-hairline) !important;
  border-radius: var(--kfps-radius) !important;
  box-shadow: none !important;
  outline: none !important;
  background: var(--kfps-surface) !important;
  overflow: hidden !important;
  clip-path: inset(0 round var(--kfps-radius));
}}

[data-testid="stTextInputRootElement"] {{
  display: flex !important;
  align-items: stretch !important;
}}

[data-testid="stTextInputRootElement"] [data-baseweb="base-input"] {{
  flex: 1 1 auto !important;
  min-width: 0 !important;
  border: 0 !important;
}}

[data-testid="stTextInputRootElement"],
[data-testid="stNumberInputContainer"],
[data-testid="stTextAreaRootElement"],
[data-baseweb="input"],
[data-baseweb="input"] > div,
[data-baseweb="input"] [data-baseweb="base-input"],
[data-baseweb="select"] > div,
[data-baseweb="textarea"],
[data-baseweb="textarea"] > div,
[data-baseweb="textarea"] [data-baseweb="base-input"],
[data-baseweb="textarea"] textarea,
[data-testid="stMetric"],
[data-testid="stExpander"],
[data-testid="stAlert"],
.kfps-inline-note,
.kfps-secret-status-card,
.kfps-flow-card,
.kfps-icon {{
  border-radius: var(--kfps-radius) !important;
}}

[data-testid="stTextInputRootElement"]::before,
[data-testid="stTextInputRootElement"]::after,
[data-testid="stNumberInputContainer"]::before,
[data-testid="stNumberInputContainer"]::after,
[data-testid="stTextAreaRootElement"]::before,
[data-testid="stTextAreaRootElement"]::after,
[data-baseweb="input"] > div::before,
[data-baseweb="input"] > div::after,
[data-baseweb="textarea"] > div::before,
[data-baseweb="textarea"] > div::after {{
  border: 0 !important;
  box-shadow: none !important;
  outline: none !important;
}}

[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stTextAreaRootElement"]:focus-within,
[data-baseweb="input"]:focus-within,
[data-baseweb="textarea"]:focus-within {{
  border-color: var(--kfps-primary) !important;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--kfps-primary) 22%, transparent) !important;
}}

[data-testid="stTextInputRootElement"] button,
[data-testid="stTextInputRootElement"] button:hover,
[data-testid="stTextInputRootElement"] button:focus,
[data-testid="stTextInputRootElement"] button:active {{
  align-self: stretch !important;
  min-width: 42px !important;
  width: 42px !important;
  height: auto !important;
  margin: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  border-left: 1px solid var(--kfps-hairline) !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  outline: none !important;
  color: var(--kfps-muted) !important;
}}

[data-testid="stTextInputRootElement"] button svg {{
  color: var(--kfps-muted) !important;
  fill: currentColor !important;
  margin-left: auto !important;
  margin-right: 10px !important;
}}

[data-testid="stTextInputRootElement"] button,
[data-testid="stTextInputRootElement"] button:hover,
[data-testid="stTextInputRootElement"] button:focus,
[data-testid="stTextInputRootElement"] button:active {{
  border-left: 0 !important;
  justify-content: flex-end !important;
  width: 48px !important;
  min-width: 48px !important;
}}

[data-testid="stTextInputRootElement"] button::before,
[data-testid="stTextInputRootElement"] button::after {{
  display: none !important;
  border: 0 !important;
  box-shadow: none !important;
}}

[data-testid="stTextInputRootElement"] [data-baseweb="base-input"],
[data-testid="stNumberInputContainer"] [data-baseweb="base-input"],
[data-testid="stTextAreaRootElement"] [data-baseweb="base-input"],
[data-testid="stTextInputRootElement"] [data-baseweb="base-input"] > div,
[data-testid="stNumberInputContainer"] [data-baseweb="base-input"] > div,
[data-testid="stTextAreaRootElement"] [data-baseweb="base-input"] > div,
[data-testid="stNumberInputContainer"] [data-baseweb="input"],
[data-testid="stNumberInputContainer"] input,
[data-testid="stTextAreaRootElement"] textarea {{
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  outline: none !important;
  background: transparent !important;
  clip-path: none !important;
}}

[data-testid="stNumberInputContainer"] button,
[data-testid="stNumberInputContainer"] button:hover,
[data-testid="stNumberInputContainer"] button:focus,
[data-testid="stNumberInputContainer"] button:active {{
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}}

[data-testid="stExpander"] > details,
[data-testid="stExpander"] > details > summary,
[data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
  background: var(--kfps-surface) !important;
}}

[data-testid="stExpander"] > details[open] > summary {{
  border-bottom: 1px solid var(--kfps-hairline) !important;
  border-bottom-left-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
}}

[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea,
[data-baseweb="select"] span {{
  color: var(--kfps-ink);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}}

[data-baseweb="input"] input::placeholder,
[data-baseweb="textarea"] textarea::placeholder,
[data-testid="stTextInputRootElement"] input::placeholder,
[data-testid="stNumberInputContainer"] input::placeholder,
[data-testid="stTextAreaRootElement"] textarea::placeholder {{
  color: color-mix(in srgb, var(--kfps-muted) 72%, var(--kfps-surface)) !important;
  -webkit-text-fill-color:
    color-mix(in srgb, var(--kfps-muted) 72%, var(--kfps-surface)) !important;
  opacity: 1 !important;
}}

.st-key-kfps_concept_description [data-testid="stTextAreaRootElement"],
.st-key-kfps_target_hypothesis [data-testid="stTextAreaRootElement"],
.st-key-kfps_concept_description [data-baseweb="textarea"],
.st-key-kfps_target_hypothesis [data-baseweb="textarea"],
.st-key-kfps_concept_description [data-baseweb="textarea"] > div,
.st-key-kfps_target_hypothesis [data-baseweb="textarea"] > div,
.st-key-kfps_concept_description [data-baseweb="textarea"] [data-baseweb="base-input"],
.st-key-kfps_target_hypothesis [data-baseweb="textarea"] [data-baseweb="base-input"] {{
  box-sizing: border-box !important;
  height: var(--kfps-enter-card-height) !important;
  min-height: var(--kfps-enter-card-height) !important;
  max-height: var(--kfps-enter-card-height) !important;
}}

.st-key-kfps_concept_description textarea,
.st-key-kfps_target_hypothesis textarea {{
  box-sizing: border-box !important;
  height: 100% !important;
  min-height: 100% !important;
  max-height: 100% !important;
  resize: none !important;
}}

div[role="radiogroup"] label,
[data-testid="stCheckbox"] label {{
  background: transparent;
  color: var(--kfps-body);
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"],
.st-key-kfps_injection_confirm [data-baseweb="checkbox"] {{
  position: relative !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 10px !important;
  width: auto !important;
  min-width: 0 !important;
  height: auto !important;
  min-height: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  color: var(--kfps-body) !important;
  accent-color: var(--kfps-primary) !important;
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"] input[type="checkbox"],
.st-key-kfps_injection_confirm [data-baseweb="checkbox"] input[type="checkbox"] {{
  -webkit-appearance: none !important;
  appearance: none !important;
  position: absolute !important;
  inset: 0 auto auto 0 !important;
  z-index: 3 !important;
  width: 22px !important;
  min-width: 22px !important;
  height: 22px !important;
  min-height: 22px !important;
  margin: 0 !important;
  padding: 0 !important;
  opacity: 0 !important;
  cursor: pointer !important;
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"] > div:first-child,
.st-key-kfps_injection_confirm [data-baseweb="checkbox"] > div:first-child {{
  position: relative !important;
  width: 22px !important;
  min-width: 22px !important;
  height: 22px !important;
  min-height: 22px !important;
  border: 1.5px solid var(--kfps-hairline) !important;
  border-radius: 6px !important;
  background: var(--kfps-surface) !important;
  box-shadow: none !important;
  pointer-events: none !important;
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"]:has(input:checked) > div:first-child,
.st-key-kfps_injection_confirm [data-baseweb="checkbox"]:has(input:checked) > div:first-child {{
  border-color: var(--kfps-primary) !important;
  background: var(--kfps-primary) !important;
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"] svg,
.st-key-kfps_injection_confirm [data-baseweb="checkbox"] svg {{
  color: #ffffff !important;
  fill: currentColor !important;
  pointer-events: none !important;
}}

[data-testid="stProgress"] > div > div {{
  background-color: var(--kfps-primary);
}}

hr {{
  border-color: var(--kfps-hairline);
}}

@media (max-width: 900px) {{
  .kfps-flow {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
  .kfps-flow-card::after {{
    display: none;
  }}
}}

/* Final layout overrides: keep the app bar, hero, and guide visually full-width. */
.block-container {{
  padding-top: 42px !important;
}}

.st-key-kfps_top_bar {{
  position: fixed !important;
  inset: 0 0 auto 0 !important;
  z-index: 999999 !important;
  width: 100vw !important;
  height: 60px !important;
  min-height: 60px !important;
  margin: 0 !important;
  padding: 8px 28px 8px 64px !important;
  box-sizing: border-box !important;
  background: var(--kfps-surface-alt) !important;
  border-bottom: 0 !important;
  box-shadow: none !important;
  overflow: hidden !important;
}}

.st-key-kfps_top_bar [data-testid="stHorizontalBlock"] {{
  width: 100% !important;
  min-width: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  flex-wrap: nowrap !important;
}}

.st-key-kfps_top_bar [data-testid="column"] {{
  width: auto !important;
  min-width: 0 !important;
}}

.st-key-kfps_top_bar [data-testid="column"]:first-child {{
  flex: 1 1 auto !important;
}}

.st-key-kfps_top_bar [data-testid="column"]:last-child {{
  flex: 0 0 318px !important;
  max-width: 318px !important;
}}

.st-key-kfps_top_controls [data-testid="stHorizontalBlock"] {{
  width: 100% !important;
  min-width: 0 !important;
  justify-content: flex-end !important;
  gap: 8px !important;
}}

.kfps-top-brandbar {{
  min-width: 0 !important;
  height: 40px !important;
  color: var(--kfps-ink) !important;
  position: fixed !important;
  top: 8px !important;
  left: 360px !important;
  z-index: 1000001 !important;
  width: auto !important;
  max-width: clamp(120px, calc(100vw - 678px), 330px) !important;
  transform: translateY(-1px);
}}

.stApp:has(.kfps-sidebar-hidden) .kfps-top-brandbar {{
  left: 56px !important;
  max-width: clamp(120px, calc(100vw - 374px), 330px) !important;
}}

.kfps-top-brandbar strong {{
  color: var(--kfps-ink) !important;
  font-size: 19px !important;
  font-weight: 900 !important;
  line-height: 1 !important;
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

.kfps-top-toggle-labels {{
  position: fixed !important;
  top: 10px !important;
  right: 24px !important;
  z-index: 1000001 !important;
  display: grid !important;
  grid-template-columns: 32px 48px 32px 10px 42px 48px 34px;
  column-gap: 6px;
  align-items: center;
  height: 34px;
  color: var(--kfps-ink);
  pointer-events: none;
}}

.kfps-top-toggle-labels span,
.kfps-top-toggle-labels b {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--kfps-ink);
  font-size: 11px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0;
}}

.st-key-kfps_lang_is_kor,
.st-key-kfps_theme_is_dark {{
  position: fixed !important;
  top: 14px !important;
  z-index: 1000002 !important;
  width: 48px !important;
  min-width: 48px !important;
  height: 26px !important;
  min-height: 26px !important;
  margin: 0 !important;
}}

.st-key-kfps_lang_is_kor {{
  right: 220px !important;
}}

.st-key-kfps_theme_is_dark {{
  right: 64px !important;
}}

.st-key-kfps_lang_is_kor label,
.st-key-kfps_theme_is_dark label {{
  width: 48px !important;
  min-width: 48px !important;
  height: 26px !important;
  min-height: 26px !important;
}}

.kfps-toggle-copy,
.kfps-toggle-divider {{
  color: var(--kfps-ink) !important;
  font-size: 11px !important;
  font-weight: 900 !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"],
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"] {{
  position: relative !important;
  width: 48px !important;
  min-width: 48px !important;
  height: 26px !important;
  min-height: 26px !important;
  padding: 0 !important;
  border: 2.5px solid var(--kfps-ink) !important;
  border-radius: 9999px !important;
  background: var(--kfps-surface) !important;
  box-shadow: none !important;
  cursor: pointer !important;
  overflow: hidden !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"]:has(input:checked),
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"]:has(input:checked) {{
  background: var(--kfps-ink) !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"] > div,
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"] > div {{
  opacity: 0 !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"] input,
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"] input {{
  position: absolute !important;
  inset: 0 !important;
  z-index: 2 !important;
  width: 100% !important;
  height: 100% !important;
  opacity: 0 !important;
  cursor: pointer !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"]::after,
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"]::after {{
  content: "";
  position: absolute;
  top: 4px;
  left: 4px;
  width: 13px;
  height: 13px;
  border-radius: 9999px;
  background: var(--kfps-ink);
  transition: transform 160ms ease, background-color 160ms ease;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"]:has(input:checked)::after,
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"]:has(input:checked)::after {{
  transform: translateX(23px);
  background: var(--kfps-surface);
}}

.kfps-hero,
.kfps-section-band {{
  width: calc(100vw - 360px) !important;
  margin-left: calc(50% - 50vw + 180px) !important;
  margin-right: 0 !important;
  box-sizing: border-box !important;
}}

.kfps-hero {{
  margin-top: -4px !important;
  padding-top: 44px !important;
  padding-bottom: 58px !important;
}}

div[data-testid="stElementContainer"]:has(.kfps-hero) {{
  margin-top: -4px !important;
}}

.kfps-guide {{
  width: calc(100vw - 360px) !important;
  margin-left: calc(50% - 50vw + 180px) !important;
  margin-right: 0 !important;
  box-sizing: border-box !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"],
[data-testid="stSidebar"] [data-testid="stExpander"] > details,
[data-testid="stSidebar"] [data-testid="stExpander"] details,
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  position: static !important;
  transform: none !important;
  clip-path: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"],
[data-testid="stSidebar"] [data-testid="stExpander"] > details {{
  overflow: hidden !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
  min-height: 44px !important;
  padding: 12px 34px 12px 0 !important;
  margin-bottom: 0 !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  list-style: none !important;
  position: relative !important;
  transition: color 180ms ease, background-color 180ms ease;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary::-webkit-details-marker {{
  display: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary > div:first-child {{
  display: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{
  display: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary::before {{
  content: "";
  position: absolute;
  right: 9px;
  left: auto;
  top: 50%;
  z-index: 2;
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--kfps-muted);
  border-bottom: 2px solid var(--kfps-muted);
  transform: translateY(-68%) rotate(45deg);
  transition: transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1), border-color 180ms ease;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary::before {{
  transform: translateY(-34%) rotate(225deg);
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary::after {{
  right: -4px !important;
  left: auto !important;
  top: 50% !important;
  width: 28px !important;
  height: 28px !important;
  transform: translateY(-50%) !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
  padding-top: 8px !important;
  padding-bottom: 18px !important;
  overflow: hidden !important;
  opacity: 1 !important;
  animation: none !important;
  transition: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] details[open]
  [data-testid="stVerticalBlock"] {{
  display: block !important;
}}

.st-key-kfps_advanced_expander,
.st-key-kfps_advanced_expander *,
.st-key-kfps_advanced_expander summary,
.st-key-kfps_advanced_expander summary::before,
.st-key-kfps_advanced_expander summary::after,
.st-key-kfps_advanced_expander details,
.st-key-kfps_advanced_expander [data-testid="stVerticalBlock"] {{
  animation: none !important;
  transition: none !important;
}}

.st-key-kfps_advanced_expander summary:hover,
.st-key-kfps_advanced_expander summary:focus,
.st-key-kfps_advanced_expander summary:focus-visible,
.st-key-kfps_advanced_expander summary:active {{
  background: transparent !important;
  box-shadow: none !important;
  outline: none !important;
}}

.st-key-kfps_advanced_expander summary:hover::after,
.st-key-kfps_advanced_expander summary:focus::after,
.st-key-kfps_advanced_expander summary:focus-visible::after,
.st-key-kfps_advanced_expander summary:active::after {{
  background: transparent !important;
  opacity: 0 !important;
}}

@media (max-width: 640px) {{
  .st-key-kfps_top_bar {{
    left: 0 !important;
    padding-left: 56px !important;
    padding-right: 14px !important;
  }}
  .st-key-kfps_top_bar [data-testid="column"]:last-child {{
    flex-basis: 310px !important;
    max-width: 310px !important;
  }}
  .kfps-hero,
  .kfps-section-band,
  .kfps-guide {{
    width: 100vw !important;
    margin-left: calc(50% - 50vw) !important;
  }}
  .kfps-flow {{
    grid-template-columns: 1fr;
  }}
  .kfps-opinion-grid {{
    grid-template-columns: 1fr;
  }}
  .st-key-kfps_top_bar {{
    position: sticky;
    padding-left: 56px;
    padding-right: 16px;
  }}
  .kfps-top-brandbar {{
    min-width: 240px;
  }}
  .st-key-kfps_top_bar [data-baseweb="button-group"] {{
    justify-content: flex-start;
  }}
}}

/* 비용 확인 미체크 시 안내: 중앙 모달, 라이트 시트 (toast 대체) */
[data-testid="stDialog"] {{
  background: #ffffff !important;
  color: #111827 !important;
  border: 1px solid rgba(15, 23, 42, 0.12) !important;
  border-radius: var(--kfps-radius) !important;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.22) !important;
}}

[data-testid="stDialog"] h2,
[data-testid="stDialog"] [data-testid="stDialogHeader"] {{
  color: #0f172a !important;
}}

[data-testid="stDialog"] [data-testid="stMarkdownContainer"],
[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p {{
  color: #1f2937 !important;
  font-size: 15px !important;
  line-height: 1.55 !important;
}}

[data-testid="stDialog"] button[aria-label="Close"],
[data-testid="stDialog"] header button {{
  color: #374151 !important;
}}
</style>
"""
