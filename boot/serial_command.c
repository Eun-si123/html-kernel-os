#include "serial_command.h"
#include "romfs.h"

void htmlk_console_line_clear(struct htmlk_console_line *line) {
    if (line == 0) return;
    line->length = 0;
    line->invalid = false;
    line->bytes[0] = 0;
}

enum htmlk_console_line_event htmlk_console_line_feed(struct htmlk_console_line *line,
                                                      uint8_t input) {
    if (line == 0) return HTMLK_CONSOLE_INVALID;
    if (input == '\r' || input == '\n') {
        if (line->invalid) return HTMLK_CONSOLE_INVALID;
        if (line->length == 0) return HTMLK_CONSOLE_WAIT;
        line->bytes[line->length] = 0;
        return HTMLK_CONSOLE_READY;
    }
    if (input == 8 || input == 127) {
        if (line->length != 0 && !line->invalid) --line->length;
        return HTMLK_CONSOLE_WAIT;
    }
    if (input < 32 || input > 126 || line->length >= HTMLK_CONSOLE_LINE_CAP - 1) {
        line->invalid = true;
        return HTMLK_CONSOLE_WAIT;
    }
    if (!line->invalid) line->bytes[line->length++] = (char)input;
    return HTMLK_CONSOLE_WAIT;
}

static bool equal(const char *a, const char *b) {
    if (a == 0 || b == 0) return false;
    for (size_t i = 0; i < HTMLK_CONSOLE_LINE_CAP; ++i) {
        if (a[i] != b[i]) return false;
        if (a[i] == 0) return true;
    }
    return false;
}

struct htmlk_console_command htmlk_console_parse(const char *line) {
    if (equal(line, "help")) return (struct htmlk_console_command){HTMLK_CONSOLE_HELP, 0};
    if (equal(line, "ls")) return (struct htmlk_console_command){HTMLK_CONSOLE_LS, 0};
    if (equal(line, "exit")) return (struct htmlk_console_command){HTMLK_CONSOLE_EXIT, 0};
    if (line != 0 && line[0] == 'c' && line[1] == 'a' &&
        line[2] == 't' && line[3] == ' ') {
        const char *path = &line[4];
        if (!htmlk_romfs_path_valid(path))
            return (struct htmlk_console_command){HTMLK_CONSOLE_BAD_PATH, 0};
        return (struct htmlk_console_command){HTMLK_CONSOLE_CAT, path};
    }
#ifdef HTMLK_M5_D_SHELL
    if (line != 0 && line[0] == 'r' && line[1] == 'u' &&
        line[2] == 'n' && line[3] == ' ') {
        const char *path = &line[4];
        if (!htmlk_romfs_path_valid(path))
            return (struct htmlk_console_command){HTMLK_CONSOLE_BAD_PATH, 0};
        return (struct htmlk_console_command){HTMLK_CONSOLE_RUN, path};
    }
#endif
    return (struct htmlk_console_command){HTMLK_CONSOLE_UNKNOWN, 0};
}
