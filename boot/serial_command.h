#ifndef HTMLK_SERIAL_COMMAND_H
#define HTMLK_SERIAL_COMMAND_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { HTMLK_CONSOLE_LINE_CAP = 96 };
enum htmlk_console_line_event { HTMLK_CONSOLE_WAIT, HTMLK_CONSOLE_READY,
                                HTMLK_CONSOLE_INVALID };
enum htmlk_console_command_kind { HTMLK_CONSOLE_HELP, HTMLK_CONSOLE_LS,
                                  HTMLK_CONSOLE_CAT, HTMLK_CONSOLE_EXIT, HTMLK_CONSOLE_RUN,
                                  HTMLK_CONSOLE_UNKNOWN, HTMLK_CONSOLE_BAD_PATH };
struct htmlk_console_line {
    char bytes[HTMLK_CONSOLE_LINE_CAP];
    size_t length;
    bool invalid;
};
struct htmlk_console_command {
    enum htmlk_console_command_kind kind;
    const char *path; /* points into line buffer until next reset */
};
void htmlk_console_line_clear(struct htmlk_console_line *line);
enum htmlk_console_line_event htmlk_console_line_feed(struct htmlk_console_line *line,
                                                      uint8_t input);
struct htmlk_console_command htmlk_console_parse(const char *line);
#endif
