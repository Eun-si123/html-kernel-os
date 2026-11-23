#include "romfs.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static const uint8_t alpha[] = {'A','B','C','D'};
static const uint8_t beta[] = {0,255,12};

int main(void) {
    const struct htmlk_romfs_file files[] = {
        {"/a", alpha, sizeof(alpha)},
        {"/config/build.txt", beta, sizeof(beta)},
        {"/zero", 0, 0},
    };
    const struct htmlk_romfs_volume volume = {files, 3};
    assert(htmlk_romfs_validate(&volume));
    assert(htmlk_romfs_path_valid("/valid/child-2.txt"));
    const char *invalid[] = {"", "a", "/", "//a", "/a/", "/a//b",
                             "/.", "/..", "/a/../b", "/a/./b",
                             "/a?b", "/a\\b", "/a\xc3\xa9"};
    for (size_t i = 0; i < sizeof(invalid)/sizeof(invalid[0]); ++i)
        assert(!htmlk_romfs_path_valid(invalid[i]));
    char too_long[HTMLK_ROMFS_MAX_PATH + 3] = {'/'};
    for (size_t i = 1; i < sizeof(too_long)-1; ++i) too_long[i] = 'a';
    assert(!htmlk_romfs_path_valid(too_long));

    uint8_t dst[7] = {0x55,0x55,0x55,0x55,0x55,0x55,0x55};
    size_t got = 99;
    assert(htmlk_romfs_read(&volume, "/a", 1, dst, 2, &got));
    assert(got == 2 && dst[0] == 'B' && dst[1] == 'C' && dst[2] == 0x55);
    assert(htmlk_romfs_read(&volume, "/config/build.txt", 0, dst, 3, &got));
    assert(got == 3 && dst[0] == 0 && dst[1] == 255 && dst[2] == 12);
    assert(htmlk_romfs_read(&volume, "/a", SIZE_MAX, dst, sizeof(dst), &got) && got == 0);
    assert(htmlk_romfs_read(&volume, "/zero", 0, dst, sizeof(dst), &got) && got == 0);
    assert(htmlk_romfs_read(&volume, "/a", 0, 0, 0, &got) && got == 0);
    assert(!htmlk_romfs_read(&volume, "/a", 0, 0, 1, &got) && got == 0);
    assert(!htmlk_romfs_read(&volume, "/missing", 0, dst, 3, &got) && got == 0);
    assert(!htmlk_romfs_read(&volume, "/../a", 0, dst, 3, &got) && got == 0);
    assert(!htmlk_romfs_read(&volume, "/a", 0, dst, 2, 0));
    assert(dst[3] == 0x55 && dst[4] == 0x55);

    const struct htmlk_romfs_file duplicate[] = {{"/a", alpha, 1}, {"/a", beta, 1}};
    const struct htmlk_romfs_file unsorted[] = {{"/z", alpha, 1}, {"/a", beta, 1}};
    const struct htmlk_romfs_file bad_path[] = {{"/a/../b", alpha, 1}};
    const struct htmlk_romfs_file bad_pointer[] = {{"/a", 0, 1}};
    const struct htmlk_romfs_file bad_length[] = {{"/a", alpha, HTMLK_ROMFS_MAX_FILE_BYTES + 1}};
    assert(!htmlk_romfs_validate(&(struct htmlk_romfs_volume){duplicate, 2}));
    assert(!htmlk_romfs_validate(&(struct htmlk_romfs_volume){unsorted, 2}));
    assert(!htmlk_romfs_validate(&(struct htmlk_romfs_volume){bad_path, 1}));
    assert(!htmlk_romfs_validate(&(struct htmlk_romfs_volume){bad_pointer, 1}));
    assert(!htmlk_romfs_validate(&(struct htmlk_romfs_volume){bad_length, 1}));
    assert(!htmlk_romfs_validate(&(struct htmlk_romfs_volume){files, 17}));
    assert(!htmlk_romfs_validate(&(struct htmlk_romfs_volume){files, 0}));
    assert(!htmlk_romfs_validate(0));
    struct htmlk_romfs_file aggregate[9];
    char names[9][4];
    for (size_t i = 0; i < 9; ++i) {
        names[i][0] = '/'; names[i][1] = 'a';
        names[i][2] = (char)('0' + i); names[i][3] = 0;
        aggregate[i] = (struct htmlk_romfs_file){names[i], alpha, 4096};
    }
    assert(htmlk_romfs_validate(&(struct htmlk_romfs_volume){aggregate, 8}));
    assert(!htmlk_romfs_validate(&(struct htmlk_romfs_volume){aggregate, 9}));
    assert(!htmlk_romfs_read(&(struct htmlk_romfs_volume){duplicate,2}, "/a",0,dst,3,&got));
    puts("M5 ROMFS HOST BOUNDS/NEGATIVES PASS");
    return 0;
}
