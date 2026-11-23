#include "serial_command.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static enum htmlk_console_command_kind command(const char *text,
                                                const char **path) {
    struct htmlk_console_line line;
    htmlk_console_line_clear(&line);
    for (; *text; ++text)
        assert(htmlk_console_line_feed(&line, (unsigned char)*text) ==
               HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line, '\r') == HTMLK_CONSOLE_READY);
    const struct htmlk_console_command parsed=htmlk_console_parse(line.bytes);
    if (path) *path=0; /* Do not return pointer into the dead local array. */
    return parsed.kind;
}

int main(void) {
    assert(command("help",0) == HTMLK_CONSOLE_HELP);
    assert(command("ls",0) == HTMLK_CONSOLE_LS);
    assert(command("exit",0) == HTMLK_CONSOLE_EXIT);
    assert(command("cat /welcome.txt",0) == HTMLK_CONSOLE_CAT);
    assert(command("run /apps/hello.hke",0) == HTMLK_CONSOLE_RUN);
    assert(command("run /apps/other.hke",0) == HTMLK_CONSOLE_RUN);
    assert(command("run /../bad",0) == HTMLK_CONSOLE_BAD_PATH);
    assert(command("run /",0) == HTMLK_CONSOLE_BAD_PATH);
    assert(command("run /apps//hello.hke",0) == HTMLK_CONSOLE_BAD_PATH);
    assert(command("run",0) == HTMLK_CONSOLE_UNKNOWN);
    assert(command("RUN /apps/hello.hke",0) == HTMLK_CONSOLE_UNKNOWN);
    assert(command("run apps/hello.hke",0) == HTMLK_CONSOLE_BAD_PATH);
    assert(command("run /apps/hello.hke extra",0) == HTMLK_CONSOLE_BAD_PATH);
    struct htmlk_console_line line;
    htmlk_console_line_clear(&line);
    for (size_t i=0;i<HTMLK_CONSOLE_LINE_CAP-1;++i)
        assert(htmlk_console_line_feed(&line, 'a')==HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line, 'x')==HTMLK_CONSOLE_WAIT);
    assert(line.invalid);
    assert(htmlk_console_line_feed(&line,'\r')==HTMLK_CONSOLE_INVALID);
    htmlk_console_line_clear(&line);
    for (const char *s="run /apps/hello.hke";*s;++s)
        assert(htmlk_console_line_feed(&line,(unsigned char)*s)==HTMLK_CONSOLE_WAIT);
    assert(htmlk_console_line_feed(&line,'\n')==HTMLK_CONSOLE_READY);
    struct htmlk_console_command parsed=htmlk_console_parse(line.bytes);
    assert(parsed.kind==HTMLK_CONSOLE_RUN);
    assert(strcmp(parsed.path,"/apps/hello.hke")==0);
    puts("M5-D SHELL PARSER / PATH / LONG LINE PASS");
}
