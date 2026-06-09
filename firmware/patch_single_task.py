import io, sys

p = "/home/tom/LilyGo-EPD47/src/epd_driver.c"
s = io.open(p, encoding="utf-8").read()


def replace_once(s, old, new, label):
    if old not in s:
        print("ERROR not found:", label)
        sys.exit(1)
    if s.count(old) != 1:
        print("ERROR ambiguous (%d):" % s.count(old), label)
        sys.exit(1)
    return s.replace(old, new)


# 1) Add forward declaration after feed_display's forward decl.
fwd_old = "static void IRAM_ATTR feed_display(OutputParams *params);\n"
fwd_new = (
    "static void IRAM_ATTR feed_display(OutputParams *params);\n"
    "static void IRAM_ATTR draw_frame_inline(Rect_t area, uint8_t *data, uint8_t frame, DrawMode_t mode);\n"
)
s = replace_once(s, fwd_old, fwd_new, "forward decl")

# 2) Replace epd_draw_image body (single-task, no per-frame task churn).
body_old = """    uint8_t frame_count = 15;

    SemaphoreHandle_t fetch_sem = xSemaphoreCreateBinary();
    SemaphoreHandle_t feed_sem = xSemaphoreCreateBinary();
    vTaskDelay(10);
    for (uint8_t k = 0; k < frame_count; k++)
    {
        OutputParams p1 = {
            .area = area,
            .data_ptr = data,
            .frame = k,
            .mode = mode,
            .done_smphr = fetch_sem,
        };
        OutputParams p2 = {
            .area = area,
            .data_ptr = data,
            .frame = k,
            .mode = mode,
            .done_smphr = feed_sem,
        };

        TaskHandle_t t1, t2;
        xTaskCreatePinnedToCore((void (*)(void *))provide_out, "privide_out", 16384,
                                &p1, 10, &t1, 0);
        xTaskCreatePinnedToCore((void (*)(void *))feed_display, "render", 16384, &p2,
                                10, &t2, 1);

        xSemaphoreTake(fetch_sem, portMAX_DELAY);
        xSemaphoreTake(feed_sem, portMAX_DELAY);

        vTaskDelete(t1);
        vTaskDelete(t2);
        vTaskDelay(5);
    }
    vSemaphoreDelete(fetch_sem);
    vSemaphoreDelete(feed_sem);
}"""

body_new = """    // Single-task pipeline: build + feed each row inline on the calling task.
    // The original two-task-per-frame design (provide_out/feed_display +
    // output_queue + per-frame xTaskCreate/vTaskDelete) crashes under IDF5
    // FreeRTOS at end-of-draw; this inline path matches the stable low-level
    // output flow (same as epd_clear / epd_test_fill_raw).
    uint8_t frame_count = 15;
    for (uint8_t k = 0; k < frame_count; k++)
    {
        draw_frame_inline(area, data, k, mode);
    }
}"""
s = replace_once(s, body_old, body_new, "epd_draw_image body")

# 3) Insert draw_frame_inline definition before epd_test_fill_raw.
anchor = "void IRAM_ATTR epd_test_fill_raw(uint8_t pattern, int32_t cycles, int32_t time)"
definition = """static void IRAM_ATTR draw_frame_inline(Rect_t area, uint8_t *data, uint8_t frame,
                                       DrawMode_t mode)
{
    uint8_t line[EPD_WIDTH / 2];
    memset(line, 255, EPD_WIDTH / 2);
    uint8_t *ptr = data;

    const int32_t *contrast_lut = contrast_cycles_4;
    switch (mode)
    {
    case WHITE_ON_WHITE:
    case BLACK_ON_WHITE:
        contrast_lut = contrast_cycles_4;
        break;
    case WHITE_ON_BLACK:
        contrast_lut = contrast_cycles_4_white;
        break;
    }

    if (frame == 0)
    {
        reset_lut(conversion_lut, mode);
    }
    update_LUT(conversion_lut, frame, mode);

    if (area.x < 0)
    {
        ptr += -area.x / 2;
    }
    if (area.y < 0)
    {
        ptr += (area.width / 2 + area.width % 2) * -area.y;
    }

    epd_start_frame();
    for (int32_t i = 0; i < EPD_HEIGHT; i++)
    {
        if (i < area.y || i >= area.y + area.height)
        {
            skip_row(contrast_lut[frame]);
            continue;
        }

        uint32_t *lp;
        bool shifted = false;
        if (area.width == EPD_WIDTH && area.x == 0)
        {
            lp = (uint32_t *)ptr;
            ptr += EPD_WIDTH / 2;
        }
        else
        {
            uint8_t *buf_start = (uint8_t *)line;
            uint32_t line_bytes = area.width / 2 + area.width % 2;
            if (area.x >= 0)
            {
                buf_start += area.x / 2;
            }
            else
            {
                line_bytes += area.x / 2;
            }
            line_bytes =
                min(line_bytes, EPD_WIDTH / 2 - (uint32_t)(buf_start - line));
            memcpy(buf_start, ptr, line_bytes);
            ptr += area.width / 2 + area.width % 2;

            if (area.width % 2 == 1 && area.x / 2 + area.width / 2 + 1 < EPD_WIDTH)
            {
                *(buf_start + line_bytes - 1) |= 0xF0;
            }
            if (area.x % 2 == 1 && area.x < EPD_WIDTH)
            {
                shifted = true;
                nibble_shift_buffer_right(
                    buf_start, min(line_bytes + 1, (uint32_t)line + EPD_WIDTH / 2 -
                                                       (uint32_t)buf_start));
            }
            lp = (uint32_t *)line;
        }

        calc_epd_input_4bpp(lp, epd_get_current_buffer(), frame, conversion_lut);
        write_row(contrast_lut[frame]);
        if (shifted)
        {
            memset(line, 255, EPD_WIDTH / 2);
        }
    }
    if (!skipping)
    {
        write_row(contrast_lut[frame]);
    }
    epd_end_frame();
}


"""
s = replace_once(s, anchor, definition + anchor, "insert draw_frame_inline")

io.open(p, "w", encoding="utf-8").write(s)
print("epd_draw_image converted to single-task inline pipeline")
