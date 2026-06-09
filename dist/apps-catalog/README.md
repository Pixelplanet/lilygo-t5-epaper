# LilyGo T5 community app catalog

A simple, shareable catalog of installable apps for the LilyGo T5 4.7" starter.
Apps from here can be browsed and added in the **web builder**
(`tools/ui-builder.html`) or installed **on-device over Wi-Fi**.

## Layout

```
apps-catalog/
├─ index.json          ← the catalog (list of apps + metadata)
└─ apps/
   └─ clock_app.py     ← app source files referenced by the manifest
```

## Catalog format (`index.json`)

```jsonc
{
  "version": 1,
  "name": "LilyGo T5 community app catalog",
  "apps": [
    {
      "id": "clock",                       // unique app id
      "name": "Big Clock",                 // tile label
      "icon": "gear",                      // wifi|calendar|bolt|star|gear|help|app
      "author": "you",
      "description": "Short summary.",
      "entry": "clock_app:open_clock",      // module:callable returning a Screen
      "files": ["apps/clock_app.py"]        // files to copy to the device
    }
  ]
}
```

## Writing an app

An installable app is normally **one file** in `apps/` that exposes an
`open_<name>(app)` function returning a `Screen` (see
[`apps/clock_app.py`](apps/clock_app.py)). It can use anything in `lib/`
(widgets, theme, the title bar + `add_back_button()`, `board.rtc`, etc.).

The manifest's `files` paths are **device-relative** (they map straight onto the
flash root). Keep app files under `apps/` and any shared modules under `lib/`.

## Installing

- **Web builder:** open `tools/ui-builder.html`, click **Catalog**, pick an app,
  **Add to device**. It adds the launcher tile and bundles the app's files into
  the exported `ui.json` download set.
- **On device (Wi-Fi):** open the **Apps** installer on the device, which pulls
  this catalog and downloads the selected app's files over HTTPS.

> Set the catalog URL in the builder / installer to wherever this folder is
> hosted (e.g. a raw GitHub URL). For local testing the builder can also load a
> catalog file directly.
