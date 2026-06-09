# micropython.cmake - USER_C_MODULES entry for the EPD47 e-paper driver.
#
# Compiles the LilyGo-EPD47 ESP-IDF driver sources together with the
# MicroPython binding (modepd.c) into a single usermod.
#
# The driver needs the `esp_lcd` IDF component (for esp_lcd_panel_io.h used by
# the I2S parallel bus). esp_lcd is added to the port's IDF_COMPONENTS list by a
# patch applied in build_epd_firmware.sh (it cannot be added from here because
# this file is not include()d during IDF's early-expansion pass, which is when
# the component dependency graph is built). All other components the driver uses
# (driver, esp_hw_support, esp_timer, hal, soc, esp_rom) are already required.
#
# NOTE: We must NOT target_link_libraries against idf:: targets here -- doing so
# re-evaluates those components' interface include dirs out of context and fails
# (e.g. esp_hw_support's config-conditional mspi_timing_tuning include dir).
#
# The driver sources are staged into ./epd47/ by build_epd_firmware.sh.

add_library(usermod_epd INTERFACE)

target_sources(usermod_epd INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/modepd.c
    ${CMAKE_CURRENT_LIST_DIR}/epd47/epd_driver.c
    ${CMAKE_CURRENT_LIST_DIR}/epd47/ed047tc1.c
    ${CMAKE_CURRENT_LIST_DIR}/epd47/i2s_data_bus.c
    ${CMAKE_CURRENT_LIST_DIR}/epd47/rmt_pulse.c
)

target_include_directories(usermod_epd INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
    ${CMAKE_CURRENT_LIST_DIR}/epd47
)

target_link_libraries(usermod INTERFACE usermod_epd)
