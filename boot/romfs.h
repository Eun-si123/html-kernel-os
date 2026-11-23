#ifndef HTMLK_ROMFS_H
#define HTMLK_ROMFS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { HTMLK_ROMFS_MAX_FILES = 16, HTMLK_ROMFS_MAX_PATH = 63,
       HTMLK_ROMFS_MAX_FILE_BYTES = 4096, HTMLK_ROMFS_MAX_BYTES = 32768 };
struct htmlk_romfs_file {
    const char *path; /* absolute canonical ASCII path, sorted strictly */
    const uint8_t *data; /* zero-length files may use NULL */
    size_t length;
};
struct htmlk_romfs_volume {
    const struct htmlk_romfs_file *files;
    size_t count;
};
/* All pointers refer to trusted kernel-owned immutable data, not user memory. */
bool htmlk_romfs_path_valid(const char *path);
bool htmlk_romfs_validate(const struct htmlk_romfs_volume *volume);
bool htmlk_romfs_read(const struct htmlk_romfs_volume *volume,
                      const char *path, size_t offset,
                      uint8_t *destination, size_t capacity, size_t *read_bytes);
extern const struct htmlk_romfs_volume htmlk_romfs_image;
#endif
