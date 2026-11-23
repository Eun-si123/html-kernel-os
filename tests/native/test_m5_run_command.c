/* Pure host proof: M5-D run command only exists in explicit combined mode. */
#include "serial_command.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void check(const char *cmd, enum htmlk_console_command_kind expected,
                  const char *path) {
    struct htmlk_console_command got = htmlk_console_parse(cmd);
    assert(got.kind == expected);
    if (path) assert(got.path && strcmp(got.path,path)==0);
    else assert(got.path == 0);
}

int main(void) {
    check("run /apps/hello.hke", HTMLK_CONSOLE_RUN, "/apps/hello.hke");
    check("run /missing.hke", HTMLK_CONSOLE_RUN, "/missing.hke");
    check("run /", HTMLK_CONSOLE_BAD_PATH, 0);
    check("run /../welcome.txt", HTMLK_CONSOLE_BAD_PATH, 0);
    check("run /a//b", HTMLK_CONSOLE_BAD_PATH, 0);
    check("run /a/./b", HTMLK_CONSOLE_BAD_PATH, 0);
    check("run /bad name", HTMLK_CONSOLE_BAD_PATH, 0);
    check("run /good-name_3.hke", HTMLK_CONSOLE_RUN,"/good-name_3.hke");
    check("run", HTMLK_CONSOLE_UNKNOWN, 0);
    check("RUN /apps/hello.hke", HTMLK_CONSOLE_UNKNOWN, 0);
    check("run  /apps/hello.hke", HTMLK_CONSOLE_BAD_PATH, 0);
    check("run /apps/hello.hke ", HTMLK_CONSOLE_BAD_PATH, 0);
    check("cat /welcome.txt", HTMLK_CONSOLE_CAT, "/welcome.txt");
    check("help", HTMLK_CONSOLE_HELP, 0);
    check("ls", HTMLK_CONSOLE_LS, 0);
    check("exit", HTMLK_CONSOLE_EXIT, 0);
    puts("M5-D HOST RUN PARSER CANONICAL/INVALID PASS");
    return 0;
}
