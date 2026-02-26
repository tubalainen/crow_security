# Crow Shepherd — Session Progress

## Current State (as of 2026-02-26)

**Integration version:** `0.2.7`
**Repo:** https://github.com/tubalainen/crow_security
**Library:** https://github.com/tubalainen/crow_security_ng (read-only, at `Q:/Claude/crow_security_ng/`)
**Integration path:** `Q:/Claude/crow_security/custom_components/crow_shepherd/`
**main branch is clean and up to date.**

---

## What Was Done This Session

### PR #14 — v0.2.7 — Real camera capture (MERGED)
**Problem:** `fetch_camera_snapshot` action only retrieved cached/stored pictures from the API.
**Fix:** Rewrote `async_fetch_snapshot` in `image.py`:
- `silent=True` (startup): GET latest stored picture only, silent if none
- `silent=False` (user action): POST `panel.capture_picture(zone_id)` → poll every 3s up to 30s for new picture ID → download & update entity

### Commit — docs: disclaimer (direct to main)
Added disclaimer to `README.md` that this is not an official Crow Group product.
> Source: https://www.thecrowgroup.com/

### PR #16 — assets: crow icon (MERGED)
Added HACS/HA integration icons:
- `custom_components/crow_shepherd/icon.png` (256×256)
- `custom_components/crow_shepherd/icon@2x.png` (512×512)
- White crow silhouette on dark navy gradient circle, transparent outside
- Source: Openclipart #254449 by Waldryano, CC0 Public Domain

Social preview banner (1280×640) was generated and saved locally at:
`C:\Users\tuben\AppData\Local\Temp\crow_social_preview.png`
**→ User still needs to upload this manually via GitHub Settings → Social preview → Edit**

---

## Open Issues / Planned Work

### Issue #15 — Panel connectivity attributes
**Status:** Plan written, not yet implemented.
**Plan file:** `C:\Users\tuben\.claude\plans\linked-sparking-comet.md`

**Summary of plan:**
Add WiFi/Ethernet/GSM connectivity info to `alarm_control_panel.*` entity attributes.
The Crow Cloud API returns connectivity fields in the panel response, but the library only parses a subset — the rest lands in `panel.raw_data`. Plan is to surface all non-sensitive `raw_data` fields as extra state attributes.

**Key constraint:** `session.get_panel()` is cached — re-fetching requires bypassing `session._panels` cache.

**Files to change (next session):**
| File | Change |
|------|--------|
| `hub.py` | Add `async_refresh_panel()` — clears cache, re-fetches, preserves user_code |
| `coordinator.py` | Add `panel_info: Panel \| None` to `CrowData`; call `async_refresh_panel()` non-fatally each update |
| `alarm_control_panel.py` | Extend `extra_state_attributes` with `firmware_version` + all non-sensitive `raw_data` fields |
| `manifest.json` | Bump to `0.2.8` |
| `README.md` | Document new attributes |

**Sensitive fields to exclude from raw_data:** `remote_access_password`, `user_code`, `id`, `mac`, `name`, `state`, `state_full`, `version`, `latitude`, `longitude`

**Branch name to use:** `feature/v0.2.8-panel-attributes`
**Base:** current tip of `origin/main`

---

## Key File Locations

| File | Purpose |
|------|---------|
| `custom_components/crow_shepherd/__init__.py` | Entry point, WS loop, coordinator setup |
| `custom_components/crow_shepherd/coordinator.py` | `CrowData` dataclass + `_async_update_data` |
| `custom_components/crow_shepherd/hub.py` | `CrowHub` — wraps Session + Panel, `async_connect()` |
| `custom_components/crow_shepherd/alarm_control_panel.py` | Alarm entity, `extra_state_attributes` |
| `custom_components/crow_shepherd/image.py` | PIR camera image entity, `async_fetch_snapshot` |
| `custom_components/crow_shepherd/config_flow.py` | Setup wizard + options flow (camera zone selector) |
| `custom_components/crow_shepherd/const.py` | Constants incl. `CONF_CAMERA_ZONE_IDS` |
| `custom_components/crow_shepherd/strings.json` | Service definitions incl. `fetch_camera_snapshot` target |
| `custom_components/crow_shepherd/translations/en.json` | English translations |
| `README.md` | `Q:/Claude/crow_security/README.md` |

---

## Library API Reference (crow_security_ng)

```python
# Panel object (hub.panel)
panel.id                            # int — used in all sub-resource API URLs
panel.mac                           # str — 12-char hex
panel.name                          # str
panel.firmware_version              # str | None
panel.state                         # str | None — e.g. "disarmed"
panel.raw_data                      # dict[str, Any] — full API response

# REST methods on panel
await panel.get_areas()             # → list[Area]
await panel.get_zones()             # → list[Zone]
await panel.get_outputs()           # → list[Output]
await panel.get_measurements()      # → list[Measurement] (optional, may fail)
await panel.set_area_state(area_id, AreaCommand)
await panel.get_zone_pictures(zone_id, page_size=1)  # GET cached pictures
await panel.capture_picture(zone_id)                 # POST triggers new capture

# Session
hub.session.get_panel(mac)          # CACHED — returns same Panel object
hub.session._panels                 # dict — session-level panel cache (private)

# Picture model
pic.id        # unique ID
pic.url       # pre-signed URL
pic.created   # datetime | None
pic.panel_time # datetime | None
pic.picture_type  # 0=manual, 1=alarm

await hub.session.get_picture_bytes(pic)  # → bytes (JPEG)
```

---

## Version History

| Version | PR | Description |
|---------|----|-------------|
| 0.2.7 | #14 | Real camera capture on `fetch_camera_snapshot` action |
| 0.2.6 | #13 | Added `target` to service so entity picker works |
| 0.2.5 | #12 | Fixed `access_tokens` crash (explicit dual `__init__`) |
| 0.2.4 | #11 | Restored camera zone selector; fixed OptionsFlow + WS refresh |
| 0.2.3 | #10 | (Reverted approach — image entities for all zones caused issues) |
| 0.2.2 | #9  | Camera zone config in options flow |
| 0.2.1 | —  | Initial release |

---

## Git Workflow Reminder

1. Branch from `origin/main`: `git checkout -b feature/vX.X.X-description`
2. Commit changes
3. `git push -u origin <branch>`
4. `gh pr create --title "..." --body "..."`
5. `git checkout main`

**Never commit directly to main** (except explicit user override for docs/assets).
**Always update README.md** in the same PR as a feature change.
