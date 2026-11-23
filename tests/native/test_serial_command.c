#include "serial_command.h"
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void enter(struct htmlk_console_line *line, const char *text) {
    htmlk_console_line_clear(line);
    for (; *text; ++text)
        assert(htmlk_console_line_feed(line, (uint8_t)*text) == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(line, '\r') == HTMLK_CONSOLE_READY);
}

int main(void) {
    struct htmlk_console_line line;
    htmlk_console_line_clear(&line);
    assert(line.length == 0 && line.bytes[0] == 0 && !line.invalid);
    assert(htmlk_console_line_feed(&line, '\r') == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(0, 'a') == HTMLK_CONSOLE_INVALID);
    htmlk_console_line_clear(0);
    enter(&line, "help");
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_HELP);
    enter(&line, "ls");
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_LS);
    enter(&line, "exit");
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_EXIT);
    enter(&line, "cat /config/build.txt");
    struct htmlk_console_command cmd = htmlk_console_parse(line.bytes);
    assert(cmd.kind == HTMLK_CONSOLE_CAT && strcmp(cmd.path,"/config/build.txt") == 0);
    enter(&line, "cat /missing.txt");
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_CAT);
    enter(&line, "cat /../welcome.txt");
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_BAD_PATH);
    enter(&line, "cat /");
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_BAD_PATH);
    enter(&line, "CAT /welcome.txt");
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_UNKNOWN);
    enter(&line, "cat");
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_UNKNOWN);
    enter(&line, "hepl");
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_UNKNOWN);
    assert(htmlk_console_parse(0).kind == HTMLK_CONSOLE_UNKNOWN);

    htmlk_console_line_clear(&line);
    for (const char *text = "helxp"; *text; ++text)
        assert(htmlk_console_line_feed(&line, (uint8_t)*text) == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line, 8) == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line, 8) == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line, 'p') == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line, '\n') == HTMLK_CONSOLE_READY);
    assert(strcmp(line.bytes,"help") == 0);
    assert(htmlk_console_parse(line.bytes).kind == HTMLK_CONSOLE_HELP);

    htmlk_console_line_clear(&line);
    for (size_t i=0;i<HTMLK_CONSOLE_LINE_CAP-1;++i)
        assert(htmlk_console_line_feed(&line,'a') == HTMLK_CONSOLE_WAIT);
    assert(!line.invalid && line.length == HTMLK_CONSOLE_LINE_CAP-1);
    assert(htmlk_console_line_feed(&line,'b') == HTMLK_CONSOLE_WAIT);
    assert(line.invalid && line.length == HTMLK_CONSOLE_LINE_CAP-1);
    assert(htmlk_console_line_feed(&line,8) == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line,'c') == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line,'\r') == HTMLK_CONSOLE_INVALID);
    htmlk_console_line_clear(&line);
    assert(line.length == 0 && !line.invalid);
    assert(htmlk_console_line_feed(&line,'h') == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line,0) == HTMLK_CONSOLE_WAIT);
    assert(line.invalid && htmlk_console_line_feed(&line,'\r') == HTMLK_CONSOLE_INVALID);
    htmlk_console_line_clear(&line);
    assert(htmlk_console_line_feed(&line,255) == HTMLK_CONSOLE_WAIT);
    assert(line.invalid);
    htmlk_console_line_clear(&line);
    assert(htmlk_console_line_feed(&line,127) == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line,'x') == HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line,'\r') == HTMLK_CONSOLE_READY);
    assert(strcmp(line.bytes,"x") == 0);
    puts("M5 SERIAL PARSER HOST BOUNDS/RECOVERY PASS");
    return 0;
}
