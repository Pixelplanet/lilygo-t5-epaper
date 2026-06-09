#!/usr/bin/env bash
# build_epd_firmware.sh - Build custom MicroPython firmware for the LilyGo
# T5 4.7" Plus (ESP32-S3) with the native EPD47 `epd` C module.
#
# Run inside WSL:  bash build_epd_firmware.sh [deps|stage|build|all]
#
#   deps   - clone MicroPython v1.28.0 (+submodules) and build mpy-cross (slow, run once)
#   stage  - copy the usermod + LilyGo driver sources into the space-free build tree
#   build  - run the esp32 firmware build
#   all    - stage + build   (default)
#
# The Windows workspace path has a space in it which breaks cmake/make, so the
# whole build happens under ~/mpbuild (WSL-native, no spaces).
set -euo pipefail

MPVER="v1.28.0"
BOARD="ESP32_GENERIC_S3"
VARIANT="SPIRAM_OCT"

BUILD="$HOME/mpbuild"
MP="$BUILD/micropython"
WS="/mnt/c/Projects/Lillygo Micropython"
USERCMOD_SRC="$WS/firmware/usercmod/epd"
USERCMOD_DST="$BUILD/usercmod/epd"
DRIVER_SRC="$HOME/LilyGo-EPD47/src"
IDF_EXPORT="$HOME/esp/esp-idf/export.sh"

OUT_BIN="$MP/ports/esp32/build-${BOARD}-${VARIANT}/firmware.bin"
WS_OUT="$WS/firmware/firmware-epd.bin"

log() { echo -e "\n=== $* ==="; }

do_deps() {
    log "Sourcing ESP-IDF"
    # shellcheck disable=SC1090
    source "$IDF_EXPORT"

    mkdir -p "$BUILD"
    if [ ! -d "$MP/.git" ]; then
        log "Cloning MicroPython $MPVER"
        git clone --depth 1 --branch "$MPVER" https://github.com/micropython/micropython.git "$MP"
    fi

    log "Building mpy-cross"
    make -C "$MP/mpy-cross" -j"$(nproc)"

    log "Fetching esp32 port submodules"
    make -C "$MP/ports/esp32" BOARD="$BOARD" BOARD_VARIANT="$VARIANT" submodules
}

do_stage() {
    log "Staging usermod + driver sources into $USERCMOD_DST"
    rm -rf "$USERCMOD_DST"
    mkdir -p "$USERCMOD_DST/epd47"

    # Authored binding + cmake from the Windows workspace.
    cp "$USERCMOD_SRC/modepd.c"        "$USERCMOD_DST/modepd.c"
    cp "$USERCMOD_SRC/micropython.cmake" "$USERCMOD_DST/micropython.cmake"

    # LilyGo driver core sources only (exclude touch.cpp / fonts / jpeg / zlib).
    for f in epd_driver.c epd_driver.h ed047tc1.c ed047tc1.h \
             i2s_data_bus.c i2s_data_bus.h rmt_pulse.c rmt_pulse.h \
             utilities.h; do
        cp "$DRIVER_SRC/$f" "$USERCMOD_DST/epd47/$f"
    done

    # --- IDF v5.x compatibility patches for the (older) driver sources ---
    # periph_ctrl.h moved from public driver/ to esp_private/ in IDF 5.x.
    sed -i 's#<driver/periph_ctrl.h>#"esp_private/periph_ctrl.h"#' \
        "$USERCMOD_DST/epd47/i2s_data_bus.c" || true

    # rmt_pulse.c gates the RMT new/legacy driver on ESP_IDF_VERSION_MAJOR but
    # never includes esp_idf_version.h, so the FIRST #if (which selects the
    # headers) sees the macro undefined (-> legacy headers) while LATER #ifs see
    # it defined transitively (-> new-driver code). Force the macro defined up
    # front so all #ifs agree and the new RMT TX headers get included.
    if ! grep -q 'esp_idf_version.h' "$USERCMOD_DST/epd47/rmt_pulse.c"; then
        sed -i '1i #include <esp_idf_version.h>' "$USERCMOD_DST/epd47/rmt_pulse.c"
    fi

    # xTaskCreatePinnedToCore moved to freertos/idf_additions.h in IDF 5.x and is
    # no longer pulled in transitively by freertos/task.h.
    if ! grep -q 'idf_additions.h' "$USERCMOD_DST/epd47/epd_driver.c"; then
        sed -i '1i #include <freertos/idf_additions.h>' "$USERCMOD_DST/epd47/epd_driver.c"
    fi

    # The usermod's esp_lcd dependency cannot be added from micropython.cmake
    # because py/usermod.cmake is only included outside IDF's early-expansion
    # pass (where the component dependency graph is built). Patch the port's
    # IDF_COMPONENTS list (which runs in both passes) to add esp_lcd.
    COMMON="$MP/ports/esp32/esp32_common.cmake"
    if ! grep -qE '^\s*esp_lcd\b' "$COMMON"; then
        sed -i '/^list(APPEND IDF_COMPONENTS$/a\    esp_lcd' "$COMMON"
        echo "Patched esp32_common.cmake: added esp_lcd to IDF_COMPONENTS"
    fi

    log "Staged files:"
    ls -R "$USERCMOD_DST"
}

do_build() {
    log "Sourcing ESP-IDF"
    # shellcheck disable=SC1090
    source "$IDF_EXPORT"

    log "Building firmware ($BOARD / $VARIANT)"
    make -C "$MP/ports/esp32" \
        BOARD="$BOARD" BOARD_VARIANT="$VARIANT" \
        USER_C_MODULES="$USERCMOD_DST/micropython.cmake" \
        -j"$(nproc)"

    if [ -f "$OUT_BIN" ]; then
        cp "$OUT_BIN" "$WS_OUT"
        log "Firmware copied to: $WS_OUT"
        ls -l "$WS_OUT"
    else
        echo "!! firmware.bin not found at $OUT_BIN" >&2
        exit 1
    fi
}

case "${1:-all}" in
    deps)  do_deps ;;
    stage) do_stage ;;
    build) do_build ;;
    all)   do_stage; do_build ;;
    *) echo "usage: $0 [deps|stage|build|all]"; exit 2 ;;
esac

log "DONE"
