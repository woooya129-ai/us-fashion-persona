# SPDX-License-Identifier: AGPL-3.0-only
"""Static CSS retained for compatibility with the K twin layout split."""

from __future__ import annotations

APPLE_UI_CSS = """
<style>
:root {
  --kfps-primary: #0066cc;
  --kfps-primary-focus: #0071e3;
  --kfps-primary-on-dark: #2997ff;
  --kfps-ink: #1d1d1f;
  --kfps-muted: #7a7a7a;
  --kfps-muted-dark: #cccccc;
  --kfps-hairline: #e0e0e0;
  --kfps-canvas: #ffffff;
  --kfps-parchment: #f5f5f7;
  --kfps-pearl: #fafafc;
  --kfps-dark: #272729;
  --kfps-black: #000000;
}

.stApp {
  background: var(--kfps-canvas);
  color: var(--kfps-ink);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}

[data-testid="stAppViewContainer"] {
  background: var(--kfps-canvas);
}

[data-testid="stHeader"] {
  background: rgba(245, 245, 247, 0.82);
  backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.block-container {
  max-width: 1180px;
  padding-top: 0;
  padding-bottom: 64px;
}

.kfps-global-nav {
  width: 100vw;
  height: 44px;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  background: var(--kfps-black);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  font-size: 12px;
  line-height: 1;
  letter-spacing: -0.12px;
}

.kfps-global-nav span:first-child {
  font-weight: 600;
}

.kfps-subnav {
  width: 100vw;
  min-height: 52px;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  background: rgba(245, 245, 247, 0.88);
  color: var(--kfps-ink);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: saturate(180%) blur(20px);
  font-size: 14px;
  letter-spacing: -0.224px;
}

.kfps-subnav strong {
  font-size: 21px;
  line-height: 1.19;
  letter-spacing: 0.231px;
}

.kfps-subnav .kfps-buy-chip {
  background: var(--kfps-primary);
  color: #ffffff;
  border-radius: 9999px;
  padding: 7px 15px;
}

.kfps-hero {
  width: 100vw;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  padding: 80px 24px 72px;
  background: var(--kfps-parchment);
  color: var(--kfps-ink);
  text-align: center;
}

.kfps-hero h1 {
  margin: 0;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: clamp(34px, 5vw, 56px);
  font-weight: 600;
  line-height: 1.07;
  letter-spacing: -0.28px;
}

.kfps-hero p {
  max-width: 760px;
  margin: 17px auto 0;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: clamp(21px, 2.6vw, 28px);
  font-weight: 400;
  line-height: 1.2;
  letter-spacing: 0.196px;
}

.kfps-hero .kfps-hero-pills {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 24px;
}

.kfps-hero .kfps-pill {
  border: 1px solid var(--kfps-primary);
  border-radius: 9999px;
  color: var(--kfps-primary);
  background: #ffffff;
  padding: 10px 18px;
  font-size: 14px;
  line-height: 1.29;
  letter-spacing: -0.224px;
}

.kfps-hero .kfps-pill-primary {
  background: var(--kfps-primary);
  color: #ffffff;
}

.kfps-section-band {
  width: 100vw;
  margin: 56px calc(50% - 50vw) 24px;
  padding: 48px 24px;
  text-align: center;
  background: var(--kfps-dark);
  color: #ffffff;
}

.kfps-section-band.light {
  background: var(--kfps-parchment);
  color: var(--kfps-ink);
}

.kfps-section-band h2 {
  margin: 0;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: clamp(28px, 3.4vw, 40px);
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: 0;
}

.kfps-section-band p {
  margin: 12px auto 0;
  max-width: 720px;
  color: var(--kfps-muted-dark);
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
}

.kfps-section-band.light p {
  color: var(--kfps-muted);
}

h1, h2, h3, [data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  color: var(--kfps-ink);
  font-weight: 600;
  letter-spacing: -0.28px;
}

p, label, [data-testid="stMarkdownContainer"] p, .stMarkdown {
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
}

[data-testid="stSidebar"] {
  background: rgba(245, 245, 247, 0.94);
  border-right: 1px solid rgba(0, 0, 0, 0.08);
}

[data-testid="stSidebar"] h3 {
  font-size: 21px;
  line-height: 1.19;
  letter-spacing: 0.231px;
}

[data-testid="stMetric"] {
  background: var(--kfps-canvas);
  border: 1px solid var(--kfps-hairline);
  border-radius: 18px;
  padding: 24px;
  box-shadow: none;
}

[data-testid="stMetric"] label,
[data-testid="stMetricLabel"] {
  color: var(--kfps-muted);
  font-size: 14px;
  line-height: 1.29;
  letter-spacing: -0.224px;
}

[data-testid="stMetricValue"] {
  color: var(--kfps-ink);
  font-size: 34px;
  line-height: 1.18;
  letter-spacing: -0.374px;
}

.stButton > button,
.stDownloadButton > button {
  min-height: 44px;
  border-radius: 9999px;
  border: 1px solid var(--kfps-primary);
  background: var(--kfps-primary);
  color: #ffffff;
  padding: 11px 22px;
  box-shadow: none;
  font-size: 17px;
  font-weight: 400;
  letter-spacing: -0.374px;
  transition: transform 120ms ease, background-color 120ms ease;
}

.stButton > button:active,
.stDownloadButton > button:active {
  transform: scale(0.95);
}

.stButton > button:focus,
.stDownloadButton > button:focus {
  outline: 2px solid var(--kfps-primary-focus);
  outline-offset: 2px;
}

.stButton > button:disabled,
.stDownloadButton > button:disabled {
  background: var(--kfps-pearl);
  color: var(--kfps-muted);
  border-color: var(--kfps-hairline);
}

[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-baseweb="textarea"] textarea {
  border-radius: 18px;
  border-color: rgba(0, 0, 0, 0.08);
  background: var(--kfps-canvas);
  box-shadow: none;
}

[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
}

[data-testid="stExpander"] {
  border: 1px solid var(--kfps-hairline);
  border-radius: 18px;
  box-shadow: none;
}

[data-testid="stAlert"] {
  border-radius: 18px;
  border: 1px solid var(--kfps-hairline);
  box-shadow: none;
}

[data-testid="stProgress"] > div > div {
  background-color: var(--kfps-primary);
}

hr {
  border-color: var(--kfps-hairline);
}

@media (max-width: 640px) {
  .block-container {
    padding-left: 16px;
    padding-right: 16px;
  }
  .kfps-global-nav {
    gap: 14px;
    overflow: hidden;
  }
  .kfps-subnav {
    justify-content: space-between;
    padding: 0 16px;
    gap: 12px;
  }
  .kfps-subnav span:not(:first-child):not(.kfps-buy-chip) {
    display: none;
  }
  .kfps-hero {
    padding: 56px 20px 48px;
  }
  .kfps-section-band {
    padding: 40px 20px;
  }
}
</style>
"""
